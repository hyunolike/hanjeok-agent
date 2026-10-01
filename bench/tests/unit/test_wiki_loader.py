from pathlib import Path

import pytest

from bench.corpus.wiki import WikiLoader


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def wiki(tmp_path: Path) -> Path:
    write(
        tmp_path / "concepts/alternative-scoring.md",
        """\
---
title: Alternative Scoring
updated: 2026-08-19
type: concept
tags:
  - recommendation-policy
  - congestion
sources:
  - raw/service-snapshots/design-v3.md
  - raw/service-snapshots/gone.md
confidence: high
contested: false
contradictions:
  - "design-v3 places each attraction in the slot where congestion is lowest.
     v4 removed the slot axis."
---

# Alternative Scoring

Ranks related attractions. See [[congestion-diagnosis]] and [[not-a-page]].
""",
    )
    write(
        tmp_path / "concepts/congestion-diagnosis.md",
        """\
---
title: Congestion Diagnosis
updated: 2026-08-19
type: concept
tags: [congestion]
sources: []
contradictions: []
---

# Congestion Diagnosis

Back to [[alternative-scoring]].
""",
    )
    write(tmp_path / "raw/service-snapshots/design-v3.md", "snapshot")
    # No frontmatter: not a canonical page whatever directory it sits in.
    write(tmp_path / "concepts/README.md", "# Just a readme\n")
    return tmp_path


def test_loads_canonical_pages_only(wiki: Path):
    result = WikiLoader(wiki).load()

    paths = {d.path for d in result.docs}
    assert paths == {
        "concepts/alternative-scoring.md",
        "concepts/congestion-diagnosis.md",
    }


def test_unresolved_link_is_reported_and_dropped_but_the_load_succeeds(wiki: Path):
    # The spec's edge case. A curated corpus accumulates dangling references
    # honestly; failing the load would mean never running against a real one.
    result = WikiLoader(wiki).load()

    doc = next(d for d in result.docs if d.path.endswith("alternative-scoring.md"))
    assert doc.links == ("concepts/congestion-diagnosis.md",)

    dangling = [d for d in result.dropped if d.kind == "link"]
    assert [d.target for d in dangling] == ["not-a-page"]


def test_missing_source_is_reported_and_dropped(wiki: Path):
    result = WikiLoader(wiki).load()

    doc = next(d for d in result.docs if d.path.endswith("alternative-scoring.md"))
    assert doc.sources == ("raw/service-snapshots/design-v3.md",)

    missing = [d for d in result.dropped if d.kind == "source"]
    assert [d.target for d in missing] == ["raw/service-snapshots/gone.md"]


def test_conflicts_arrive_as_verbatim_prose(wiki: Path):
    # Carried, never parsed. The sentence names files inside prose, so turning
    # it into edges breaks the day someone rewords it (data-model.md).
    result = WikiLoader(wiki).load()

    doc = next(d for d in result.docs if d.path.endswith("alternative-scoring.md"))
    conflicts = doc.attrs["conflicts"]

    assert len(conflicts) == 1
    assert conflicts[0].startswith("design-v3 places each attraction")
    assert "v4 removed the slot axis" in conflicts[0]


def test_corpus_specific_fields_ride_in_attrs(wiki: Path):
    result = WikiLoader(wiki).load()

    doc = next(d for d in result.docs if d.path.endswith("alternative-scoring.md"))
    assert doc.attrs["confidence"] == "high"
    assert doc.attrs["contested"] is False
    # And they are not promoted to fields of their own, which is what would let
    # the pipeline start reading them.
    assert not hasattr(doc, "confidence")


def test_a_page_does_not_link_to_itself(wiki: Path):
    result = WikiLoader(wiki).load()

    for doc in result.docs:
        assert doc.path not in doc.links
