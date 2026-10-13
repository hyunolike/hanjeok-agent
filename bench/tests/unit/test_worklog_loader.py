import json

import pytest

from bench.answer.pipeline import AnswerPipeline, ModelReply
from bench.graph.query import Passage


def write(root, name, body="Fact.", *, status="완료", extra=""):
    path = root / "projects" / "test" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nproject: test\ntype: 설계\ntech: [neo4j]\nstatus: {status}\n"
        f"date: 2026-10-12\n{extra}---\n# {path.stem}\n{body}\n"
    )
    return path


def test_worklog_status_links_and_read_only_boundary_reach_answer(tmp_path):
    from bench.corpus.worklog import WorklogLoader

    a = write(tmp_path, "a.md", "Old decision. [[b|new]] [[missing]]", status="폐기")
    b = write(tmp_path, "b.md", "New decision.")
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (a, b)}
    loaded = WorklogLoader(tmp_path).load()
    old = next(d for d in loaded.docs if d.path.endswith("a.md"))
    assert old.attrs["status"] == "폐기" and old.attrs["project"] == "test"
    assert old.tags == ("neo4j",) and old.doc_type == "설계"
    assert old.sources == () and old.links == ("projects/test/b.md",)
    assert [(d.target, d.kind) for d in loaded.dropped] == [("missing", "link")]
    captured = []

    class Model:
        def complete(self, system, user, **kwargs):
            captured.append(json.loads(user))
            return ModelReply('{"outcome":"no_grounds","answer":null,"citations":[]}')

    AnswerPipeline(
        lambda c, q: [Passage(old.path, "a#0", old.body, old.title, old.attrs)], Model()
    ).ask("Which decision is current?", "worklog", loaded.revision, {old.path})
    assert captured[0]["supplied"][0]["attrs"]["status"] == "폐기"
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (a, b)} == before


def test_sample_plan_is_nested_anchored_content_hashed_and_links_stay_inside(tmp_path):
    from bench.corpus.worklog import WorklogLoader

    for name in ("a.md", "b.md", "c.md", "d.md"):
        write(tmp_path, name, "Fact. [[d]]")
    loader = WorklogLoader(tmp_path, seed=7)
    plan = loader.plan_samples([2, 4], {"projects/test/a.md"})
    again = loader.plan_samples([2, 4], {"projects/test/a.md"})
    assert [p.manifest for p in plan] == [p.manifest for p in again]
    paths = [{d.path for d in p.loaded.docs} for p in plan]
    assert len(paths[0]) == 2 and len(paths[1]) == 4 and paths[0] < paths[1]
    assert "projects/test/a.md" in paths[0]
    assert all(
        set(d.links) <= paths[i] for i, sample in enumerate(plan) for d in sample.loaded.docs
    )
    assert plan[0].manifest["seed"] == 7
    assert plan[0].manifest["required_paths"] == ["projects/test/a.md"]
    assert len(plan[0].manifest["documents"]) == 2
    assert plan[0].loaded.revision != plan[1].loaded.revision
    original = plan[0].loaded.revision
    write(tmp_path, "a.md", "Changed fact.")
    assert loader.plan_samples([2], {"projects/test/a.md"})[0].loaded.revision != original
    assert plan[0].loaded.revision == original  # prepared snapshots do not reread files


@pytest.mark.parametrize(
    "sizes,anchors",
    [
        ([0], set()),
        ([2, 2], set()),
        ([4, 2], set()),
        ([5], set()),
        ([1], {"missing.md"}),
        ([1], {"projects/test/a.md", "projects/test/b.md"}),
    ],
)
def test_invalid_samples_are_rejected_before_rebuild(tmp_path, sizes, anchors):
    from bench.corpus.worklog import WorklogLoader

    for name in ("a.md", "b.md", "c.md", "d.md"):
        write(tmp_path, name)
    with pytest.raises(ValueError):
        WorklogLoader(tmp_path).plan_samples(sizes, anchors)


def test_malformed_credentials_and_outside_symlinks_are_reported_without_body(tmp_path):
    from bench.corpus.worklog import WorklogLoader

    write(tmp_path, "valid.md")
    write(tmp_path, "sensitive.md", "nvapi-" + "A" * 40)
    malformed = write(tmp_path, "malformed.md")
    malformed.write_text("---\nproject: [bad\n---\nsecret malformed body")
    outside = tmp_path.parent / "outside.md"
    outside.write_text("private outside body")
    (tmp_path / "projects/test/link.md").symlink_to(outside)
    loaded = WorklogLoader(tmp_path).load()
    assert [d.path for d in loaded.docs] == ["projects/test/valid.md"]
    assert {d.target for d in loaded.dropped} == {
        "credential_pattern",
        "invalid_frontmatter",
        "outside_root",
    }
    assert "nvapi-" not in repr(loaded) and "private outside" not in repr(loaded)


def test_ambiguous_bare_link_is_dropped_and_exact_path_link_is_resolved(tmp_path):
    from bench.corpus.worklog import WorklogLoader

    write(tmp_path, "a.md", "[[b]] [[projects/test/b.md]]")
    write(tmp_path, "b.md")
    other = tmp_path / "projects/other"
    other.mkdir()
    (other / "b.md").write_bytes((tmp_path / "projects/test/b.md").read_bytes())
    loaded = WorklogLoader(tmp_path).load()
    a = next(d for d in loaded.docs if d.path.endswith("/a.md"))
    assert a.links == ("projects/test/b.md",)
    assert any(d.source_path == a.path and d.target == "b" for d in loaded.dropped)
