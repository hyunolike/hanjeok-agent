import pytest


@pytest.mark.parametrize(
    "paths", [[], ["made/up.md"], ["raw/source.md"], ["a.md", "missing.md"], ["a.md#0"]]
)
def test_fabricated_or_empty_citations_discard_the_entire_answer(paths):
    from bench.answer.citations import validate

    result = validate("Never expose this rejected answer", paths, {"a.md"}, {"a.md"})
    assert result.outcome == "invalid_citations"
    assert result.answer is None
    assert result.citations == ()
    assert "Never expose" not in repr(result)


def test_existing_but_unsupplied_document_is_not_a_ground():
    from bench.answer.citations import validate

    result = validate("answer", ["b.md"], {"a.md", "b.md"}, {"a.md"})
    assert result.outcome == "invalid_citations"
    assert result.answer is None


def test_valid_answer_keeps_only_unique_paths():
    from bench.answer.citations import validate

    result = validate("grounded answer", ["a.md", "a.md"], {"a.md"}, {"a.md"})
    assert result.outcome == "answered"
    assert result.answer == "grounded answer"
    assert result.citations == ("a.md",)
