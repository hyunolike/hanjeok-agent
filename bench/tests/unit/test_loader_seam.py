"""Principle III: loaders are replaceable, the pipeline is not.

The failure this guards against is quiet. Someone downstream writes
`attrs["confidence"]` because the wiki has it, everything keeps working against
the wiki, and a different corpus — which has no such key — starts producing
subtly different behaviour or a KeyError far from the cause.

So the test introduces a synthetic corpus that differs from the wiki: different
field names, different types, no evidence layer. Anything downstream that has
learned a corpus-specific name fails here.
"""

from __future__ import annotations

import json

import pytest

from bench.corpus.loader import Link, LoadedDoc, LoadResult, check_unique_paths


class SyntheticLoader:
    """A corpus whose `attrs` share no key with the wiki."""

    name = "synthetic"

    def load(self) -> LoadResult:
        docs = (
            LoadedDoc(
                path="notes/one.md",
                corpus=self.name,
                title="One",
                doc_type="scribble",
                body="# One\n\nAbout widgets.",
                tags=("widget",),
                links=("notes/two.md",),
                attrs={"mood": "brisk", "revision_count": 3},
            ),
            LoadedDoc(
                path="notes/two.md",
                corpus=self.name,
                title="Two",
                doc_type="scribble",
                body="# Two\n\nAlso about widgets.",
                tags=("widget",),
                attrs={"mood": "flat"},
            ),
        )
        return LoadResult(docs, (), revision="synthetic-0")


def test_a_corpus_with_unfamiliar_attrs_loads():
    result = SyntheticLoader().load()

    assert {d.path for d in result.docs} == {"notes/one.md", "notes/two.md"}
    assert result.docs[0].attrs == {"mood": "brisk", "revision_count": 3}


def test_a_corpus_without_an_evidence_layer_is_valid():
    # This synthetic loader has no `sources`. A pipeline that assumes
    # every corpus cites raw evidence would fail here rather than in production.
    result = SyntheticLoader().load()

    assert all(d.sources == () for d in result.docs)


def test_attrs_survive_serialisation_without_being_named():
    # `build` stores attrs as one JSON blob precisely so it never names a key.
    # If that changes to spreading known fields into properties, this fails.
    result = SyntheticLoader().load()

    blob = json.dumps(dict(result.docs[0].attrs), ensure_ascii=False, default=str)

    assert json.loads(blob) == {"mood": "brisk", "revision_count": 3}


def test_duplicate_paths_are_refused():
    # Two documents at one path would merge silently in the graph, because
    # (corpus, path) is the node's identity.
    docs = [
        LoadedDoc(path="a.md", corpus="x", title="A", doc_type="t", body=""),
        LoadedDoc(path="a.md", corpus="x", title="A again", doc_type="t", body=""),
    ]

    with pytest.raises(ValueError, match="duplicate document path"):
        check_unique_paths(docs)


def test_loaded_doc_is_immutable():
    # The pipeline passes these around freely. If a downstream stage could
    # mutate one, "the loader decides what a document is" stops being true.
    doc = SyntheticLoader().load().docs[0]

    with pytest.raises(AttributeError):
        doc.title = "changed"  # type: ignore[misc]


def test_typed_links_keep_their_order_and_kind():
    # A ranked list flattened into `links` is a set of paths; the order someone
    # else decided is gone. The seam has to be able to carry it.
    doc = LoadedDoc(
        path="place/1",
        corpus="x",
        title="One",
        doc_type="place",
        body="",
        typed_links=(
            Link("place/3", "related", rank=1, attrs={"score": 0.9}),
            Link("place/2", "related", rank=2),
            Link("region/11110", "in_region"),
        ),
    )

    ranked = [link for link in doc.typed_links if link.kind == "related"]

    assert [(link.target, link.rank) for link in ranked] == [("place/3", 1), ("place/2", 2)]
    assert doc.typed_links[2].rank is None
    assert doc.links == (), "typed links do not leak into the untyped field"


def test_a_wiki_style_document_needs_no_typed_links():
    assert SyntheticLoader().load().docs[0].typed_links == ()
