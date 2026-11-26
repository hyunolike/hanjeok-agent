from types import SimpleNamespace

from bench.eval.judge import embedding_settings


def test_judge_embedding_settings_describe_the_actual_adapter():
    expected = {"name": "remote", "model_id": "remote@1024", "input_type": "query"}
    assert embedding_settings(SimpleNamespace(settings=expected)) == expected
    assert embedding_settings(None) == {"model_id": None}
