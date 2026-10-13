"""The guide's graph against a real Neo4j. Marked `integration`.

Each test uses a corpus name of its own, so nothing here can touch a copy that
`guide refresh` built for the demo on the same database.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from bench.graph.store import driver_from_env, session
from guide.export import read_export
from guide.graph import read
from guide.graph.refresh import RefreshError, delete_generation, refresh
from guide.graph.schema import PLACE_INDEX, ensure_schema

pytestmark = pytest.mark.integration

EXPORT = read_export(Path(__file__).parents[1] / "fixtures" / "hanjeok-export")


@pytest.fixture
def driver():
    d = driver_from_env()
    yield d
    d.close()


@pytest.fixture
def corpus(driver):
    name = f"itest-guide-{uuid4().hex[:8]}"
    yield name
    delete_generation(driver, name, keep="")
    with session(driver) as s:
        s.run("MATCH (c:Corpus {name: $name}) DETACH DELETE c", name=name).consume()


def test_schema_has_the_place_index(driver):
    ensure_schema(driver)
    ensure_schema(driver)  # twice: creating it again must not fail
    with session(driver) as s:
        row = s.run(
            "SHOW INDEXES YIELD name, type, state WHERE name = $n RETURN type, state", n=PLACE_INDEX
        ).single()
    assert row["type"] == "VECTOR"
    assert row["state"] == "ONLINE"


def test_refresh_writes_what_the_export_holds_and_activates_it(driver, corpus, embedder):
    result = refresh(driver, EXPORT, embedder, corpus=corpus)

    current = read.active(driver, corpus)
    assert result.counts == EXPORT.counts
    assert current.generation == result.generation
    assert current.export_sha256 == EXPORT.sha256
    assert current.exported_at == "2026-10-13T02:00:00Z"
    assert current.counts == EXPORT.counts


def test_no_copy_means_none_rather_than_an_empty_one(driver):
    assert read.active(driver, "itest-guide-never-loaded") is None


def test_a_refresh_that_fails_before_activation_leaves_the_previous_copy_serving(
    driver, corpus, embedder
):
    first = refresh(driver, EXPORT, embedder, corpus=corpus)

    def fail(generation):
        raise RuntimeError("stopped just before the pointer moved")

    with pytest.raises(RefreshError) as caught:
        refresh(driver, EXPORT, embedder, corpus=corpus, before_activate=fail)

    assert caught.value.cause == "refresh_failed"
    assert read.active(driver, corpus).generation == first.generation
    assert read.detail(driver, first.generation, 101).name == "가람궁"
    with session(driver) as s:
        generations = s.run(
            "MATCH (p:Place {corpus: $c}) RETURN collect(DISTINCT p.generation) AS g", c=corpus
        ).single()["g"]
    assert generations == [first.generation], "the failed generation was removed"


def test_a_first_refresh_that_fails_leaves_no_copy_at_all(driver, corpus, embedder):
    class Broken:
        def embed(self, texts):
            raise RuntimeError("model unavailable")

    with pytest.raises(RefreshError):
        refresh(driver, EXPORT, Broken(), corpus=corpus)

    assert read.active(driver, corpus) is None


def test_a_second_refresh_replaces_the_first_and_removes_it(driver, corpus, embedder):
    first = refresh(driver, EXPORT, embedder, corpus=corpus)
    second = refresh(driver, EXPORT, embedder, corpus=corpus)

    assert read.active(driver, corpus).generation == second.generation
    assert read.detail(driver, first.generation, 101) is None
    assert read.detail(driver, second.generation, 101).name == "가람궁"


def test_embeddings_are_reused_when_the_text_has_not_changed(driver, corpus, embedder, tmp_path):
    cache = tmp_path / "cache.sqlite"
    first = refresh(driver, EXPORT, embedder, corpus=corpus, model_id="fake-a", cache_path=cache)
    second = refresh(driver, EXPORT, embedder, corpus=corpus, model_id="fake-a", cache_path=cache)
    other_model = refresh(
        driver, EXPORT, embedder, corpus=corpus, model_id="fake-b", cache_path=cache
    )

    assert (first.embedded, first.reused) == (40, 0)
    assert (second.embedded, second.reused) == (0, 40)
    assert (other_model.embedded, other_model.reused) == (40, 0), "a different model shares nothing"


def test_related_places_come_back_in_hanjeoks_order(driver, corpus, embedder):
    generation = refresh(driver, EXPORT, embedder, corpus=corpus).generation

    rows = read.related(driver, generation, 101)

    assert [(r.rank, r.place.name) for r in rows] == [
        (1, "솔내 한옥마을"),
        (2, "물빛 서원"),
        (3, "달맞이 숲길"),
        (4, "옛 성곽길"),
        (5, "가람 시립미술관"),
    ]
    assert [r.place.name for r in read.related(driver, generation, 101, limit=2)] == [
        "솔내 한옥마을",
        "물빛 서원",
    ]


def test_an_unranked_link_is_returned_and_sorts_last(driver, corpus, embedder):
    generation = refresh(driver, EXPORT, embedder, corpus=corpus).generation
    with session(driver) as s:
        # Give 192 a ranked link as well, with a lower score than its unranked one.
        s.run(
            "MATCH (a:Place {generation: $g, id: 192}), (b:Place {generation: $g, id: 173}) "
            "CREATE (a)-[:RELATED_TO {generation: $g, rank: 1, score: 0.1}]->(b)",
            g=generation,
        ).consume()

    rows = read.related(driver, generation, 192)

    assert [(r.rank, r.place.id) for r in rows] == [(1, 173), (None, 178)]


def test_a_name_is_matched_with_spaces_ignored_exact_then_prefix_then_contained(
    driver, corpus, embedder
):
    generation = refresh(driver, EXPORT, embedder, corpus=corpus).generation

    assert [p.id for p in read.match_name(driver, generation, "솔내한옥마을")] == [118]
    # Two places really are called this; both come back, the covered one first.
    assert [p.id for p in read.match_name(driver, generation, "은행나무길")] == [140, 141]
    by_prefix = [p.name for p in read.match_name(driver, generation, "가람")]
    assert by_prefix[0] == "가람궁", "the shortest name that starts with it"
    assert "가람 중앙시장" in by_prefix
    # "서원" starts no name but is inside one.
    assert [p.name for p in read.match_name(driver, generation, "서원")] == ["물빛 서원"]
    assert len(read.match_name(driver, generation, "솔내")) <= read.MAX_NAME_MATCHES
    assert read.match_name(driver, generation, "없는곳") == []
    assert read.match_name(driver, generation, "   ") == []


def test_search_finds_a_place_by_its_words_and_respects_the_region(driver, corpus, embedder):
    generation = refresh(driver, EXPORT, embedder, corpus=corpus).generation
    garam = next(p for p in EXPORT.places if p.id == 101)

    hits = read.search(driver, generation, embedder.embed_query(f"{garam.name} 옛 궁궐"), limit=5)
    in_solnae = read.search(
        driver, generation, embedder.embed_query("숲길"), limit=5, region_code="11140"
    )

    assert hits[0][0].id == 101
    assert len(hits) <= 5
    assert in_solnae and all(place.region_code == "11140" for place, _ in in_solnae)


def test_search_reads_one_generation_while_two_are_in_the_index(driver, corpus, embedder):
    first = refresh(driver, EXPORT, embedder, corpus=corpus).generation
    seen: dict[str, list[int]] = {}

    def look(new_generation):
        vector = embedder.embed_query("가람궁 옛 궁궐")
        seen["old"] = [p.id for p, _ in read.search(driver, first, vector, limit=40)]
        seen["new"] = [p.id for p, _ in read.search(driver, new_generation, vector, limit=40)]

    refresh(driver, EXPORT, embedder, corpus=corpus, before_activate=look)

    # Every place exists twice in the index at that moment. Each generation
    # still returns each of its places once.
    assert len(seen["old"]) == len(set(seen["old"])) == 40
    assert sorted(seen["new"]) == sorted(seen["old"])


def test_detail_carries_coverage_and_no_congestion_value(driver, corpus, embedder):
    generation = refresh(driver, EXPORT, embedder, corpus=corpus).generation

    lighthouse = read.detail(driver, generation, 150)

    assert lighthouse.has_congestion_data is False
    assert not {"grade", "congestion", "concentration"} & set(type(lighthouse).__dataclass_fields__)
    assert read.detail(driver, generation, 99999) is None


def test_events_are_those_tied_to_a_place_or_held_beside_it(driver, corpus, embedder):
    generation = refresh(driver, EXPORT, embedder, corpus=corpus).generation

    palace = read.events(driver, generation, 101)
    museum = read.events(driver, generation, 161)
    forest = read.events(driver, generation, 131)

    assert [e.id for e in palace] == ["festival:garam-night"]
    # The exhibition is tied to the museum. The palace is 500 m away and does
    # not inherit it: an event with a place belongs to that place.
    assert "exhibition:old-maps" in [e.id for e in museum]
    assert forest == []


def test_events_can_be_asked_for_one_day(driver, corpus, embedder):
    generation = refresh(driver, EXPORT, embedder, corpus=corpus).generation

    assert [e.id for e in read.events(driver, generation, 101, on="2026-10-17")] == [
        "festival:garam-night"
    ]
    assert read.events(driver, generation, 101, on="2026-10-26") == []
    assert read.events(driver, generation, 101, on="2026-10-15") == []
