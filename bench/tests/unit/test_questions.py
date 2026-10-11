import hashlib

import pytest
import yaml

from bench.runtime import BenchError


def row(**changes):
    return {
        "id": "q1",
        "question": "What is the fact?",
        "kind": "single_doc",
        "reference_docs": ["a.md"],
        "must_contain": ["Alpha is a fact."],
        "corpus": "third",
        **changes,
    }


def load(tmp_path, rows):
    from bench.eval.questions import QuestionSetLoader

    path = tmp_path / "sample.yaml"
    path.write_text(yaml.safe_dump({"id": "sample", "questions": rows}))
    return QuestionSetLoader(tmp_path).load("sample"), path


def test_question_set_revision_is_exact_content_hash_and_references_validate(tmp_path):
    questions, path = load(tmp_path, [row()])
    assert questions.revision == "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    questions.validate_corpus("third", {"a.md"})
    with pytest.raises(BenchError):
        questions.validate_corpus("third", {"other.md"})
    before = questions.revision
    path.write_text(path.read_text().replace("Alpha is", "Beta is"))
    from bench.eval.questions import QuestionSetLoader

    assert QuestionSetLoader(tmp_path).load("sample").revision != before


@pytest.mark.parametrize(
    "rows",
    [
        [row(reference_docs=[])],
        [row(must_contain=[])],
        [row(kind="multi_doc")],
        [row(kind="unanswerable")],
        [row(question=" ")],
        [row(kind="wrong")],
        [row(reference_docs=["../outside.md"])],
        [row(reference_docs=["/outside.md"])],
        [row(reference_docs=["a.md", "a.md"])],
        [row(), row()],
        [],
    ],
)
def test_invalid_question_shape_is_rejected_with_no_source_echo(tmp_path, rows):
    with pytest.raises(BenchError) as error:
        load(tmp_path, rows)
    assert error.value.outcome == "load_failed"
    assert "outside" not in str(error.value)


def test_unanswerable_requires_empty_references_and_claims(tmp_path):
    questions, _ = load(tmp_path, [row(kind="unanswerable", reference_docs=[], must_contain=[])])
    assert questions.questions[0].kind == "unanswerable"
    questions.validate_corpus("third", set())


def test_name_cannot_escape_question_directory(tmp_path):
    from bench.eval.questions import QuestionSetLoader

    with pytest.raises(BenchError):
        QuestionSetLoader(tmp_path).load("../secret")
