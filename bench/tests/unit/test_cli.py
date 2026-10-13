import json

from bench.answer.pipeline import AnswerResult
from bench.graph.query import Passage


class Runtime:
    def __init__(self):
        self.calls = []

    def ask(self, question, corpus, strategy):
        self.calls.append((question, corpus, strategy))
        return AnswerResult(
            "r",
            "answered",
            "fact",
            ("a.md",),
            (Passage("a.md", "a.md#0", "fact", "A"),),
            "rev",
            10,
            5,
            2,
            0,
        )

    def rebuild(self, name):
        self.calls.append(("rebuild", name))
        return {"name": name, "docs": 1, "chunks": 1, "dropped": []}


def test_cli_shows_supplied_text_and_uses_explicit_corpus_and_strategy(capsys):
    from bench.cli import main

    runtime = Runtime()
    assert (
        main(
            [
                "ask",
                "--question",
                "What?",
                "--corpus",
                "third",
                "--strategy",
                "graph",
                "--show-supplied",
            ],
            runtime=runtime,
        )
        == 0
    )
    assert runtime.calls == [("What?", "third", "graph")]
    assert json.loads(capsys.readouterr().out)["supplied"][0]["text"] == "fact"


def test_load_and_rebuild_use_the_same_clean_rebuild_path(capsys):
    from bench.cli import main

    runtime = Runtime()
    assert main(["corpus", "load", "wiki"], runtime=runtime) == 0
    assert main(["corpus", "rebuild", "wiki"], runtime=runtime) == 0
    assert runtime.calls == [("rebuild", "wiki"), ("rebuild", "wiki")]


def test_invalid_question_does_not_reach_the_model(capsys):
    from bench.cli import main

    runtime = Runtime()
    assert (
        main(["ask", "--question", " ", "--corpus", "wiki", "--strategy", "graph"], runtime=runtime)
        == 2
    )
    assert runtime.calls == []
    assert json.loads(capsys.readouterr().out)["outcome"] == "load_failed"


def test_rejected_answer_cli_has_no_answer_text(capsys):
    from bench.cli import main

    runtime = Runtime()
    runtime.ask = lambda *args: AnswerResult(
        "r",
        "invalid_citations",
        None,
        (),
        (),
        "rev",
        1,
        1,
        1,
        1,
        "invalid citation",
    )
    assert (
        main(
            ["ask", "--question", "What?", "--corpus", "wiki", "--strategy", "graph"],
            runtime=runtime,
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out) == {
        "outcome": "invalid_citations",
        "cause": "invalid citation",
    }
