from bench.corpus.chunk import split


def test_document_with_no_headings_is_one_chunk():
    chunks = split("a.md", "Just a paragraph.\n\nAnd another.")

    assert len(chunks) == 1
    assert chunks[0].heading_path == ()
    assert "another" in chunks[0].text


def test_nested_headings_carry_their_path():
    body = """\
# Alternative Scoring

Intro text.

## Formula

score = 0.4 * relationScore

### Weights

Provisional.

## Fallback

Nothing nearby.
"""
    chunks = split("a.md", body)
    paths = [c.heading_path for c in chunks]

    assert ("Alternative Scoring",) in paths
    assert ("Alternative Scoring", "Formula") in paths
    assert ("Alternative Scoring", "Formula", "Weights") in paths
    # `## Fallback` pops back to depth 2 rather than nesting under Weights.
    assert ("Alternative Scoring", "Fallback") in paths


def test_short_document_stays_whole():
    chunks = split("a.md", "# Title\n\nOne line.")

    assert len(chunks) == 1


def test_hash_inside_a_code_fence_is_not_a_heading():
    # A shell comment at line start is indistinguishable from an H1 without
    # fence tracking, and splitting there would cut a command from its output.
    body = """\
# Real Heading

```bash
# this is a comment, not a heading
./gradlew build
```

Trailing prose.
"""
    chunks = split("a.md", body)

    assert len(chunks) == 1
    assert "./gradlew build" in chunks[0].text


def test_text_before_the_first_heading_keeps_an_empty_path():
    chunks = split("a.md", "Preamble.\n\n# Later\n\nBody.")

    assert chunks[0].heading_path == ()
    assert chunks[1].heading_path == ("Later",)


def test_chunk_ids_are_stable_and_name_their_document():
    chunks = split("concepts/x.md", "# A\n\nfoo\n\n# B\n\nbar")

    assert [c.id for c in chunks] == ["concepts/x.md#0", "concepts/x.md#1"]
    assert all(c.doc_path == "concepts/x.md" for c in chunks)
