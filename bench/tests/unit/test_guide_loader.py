from __future__ import annotations

from pathlib import Path

from guide.export import Place, read_export
from guide.loader import HanjeokLoader, place_text

GOOD = Path(__file__).parents[1] / "fixtures" / "hanjeok-export"


def test_every_place_and_event_becomes_one_document():
    export = read_export(GOOD)
    result = HanjeokLoader(export).load()

    assert len(result.docs) == len(export.places) + len(export.events)
    assert result.revision == export.sha256
    assert result.dropped == ()


def test_related_links_keep_hanjeoks_rank_and_resolve():
    result = HanjeokLoader(GOOD).load()
    paths = {doc.path for doc in result.docs}
    garam = next(doc for doc in result.docs if doc.path == "place/101")

    related = [link for link in garam.typed_links if link.kind == "related"]

    assert [(link.target, link.rank) for link in related] == [
        ("place/118", 1),
        ("place/124", 2),
        ("place/131", 3),
        ("place/166", 4),
        ("place/160", 5),
    ]
    assert related[0].attrs["score"] == 0.91
    assert all(link.target in paths for doc in result.docs for link in doc.typed_links)


def test_an_exhibition_points_at_its_place():
    result = HanjeokLoader(GOOD).load()
    exhibition = next(doc for doc in result.docs if doc.path == "event/exhibition:old-maps")

    assert [(link.target, link.kind) for link in exhibition.typed_links] == [
        ("place/161", "held_at")
    ]
    assert exhibition.doc_type == "exhibition"


def test_place_text_leaves_absent_fields_out():
    bare = Place(
        1, "이름만 있는 곳", None, None, None, None, None, None, None, None, None, None, False
    )

    assert place_text(bare) == "이름만 있는 곳"
    assert "None" not in place_text(bare)


def test_place_text_says_where_and_what():
    garam = next(p for p in read_export(GOOD).places if p.id == 101)

    assert place_text(garam).splitlines()[0] == "가람궁 · 한빛시 가람구 · 역사 고궁"
    assert "옛 궁궐" in place_text(garam)
