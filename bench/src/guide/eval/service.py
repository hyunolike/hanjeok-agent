"""One evaluation, from a question set file to a stored report.

Costs model quota and is started by hand (`guide eval`). Never in CI.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from guide.eval import questions as question_sets
from guide.eval.report import build, score_all
from guide.eval.run import STRATEGIES, PatientModel, run
from guide.eval.store import ReportStore

LIMITATIONS = (
    "판정 모델과 답한 모델이 같은 모델입니다. 판정 점수는 그 모델이 자기 답을 본 결과이고, "
    "레코드 정밀도와 재현율, 금지 행동 건수는 모델 없이 센 값입니다.",
    "'없는 장소를 지어냄'은 내보내기 파일에 있는 장소 이름만 알아봅니다. 한적에 아예 없는 장소 이름은 잡지 못합니다.",
    "근거 정밀도와 재현율의 기준 글은 그 질문에 필요한 레코드의 글을 이어 붙인 것입니다. "
    "사람이 쓴 모범 답안이 아닙니다.",
    "레코드 정밀도는 가져온 것 전부를 분모로 둡니다. 조회가 함께 가져오는 장소 레코드와 정책 문서도 분모에 들어가 "
    "값이 낮게 나옵니다. 두 방식의 차이를 보는 용도입니다.",
)


def evaluate(
    question_set_path: Path | str,
    *,
    model,
    places,
    policy,
    live,
    judge,
    store: ReportStore,
    runs_dir: Path | str,
    generation: str,
    export_sha256: str,
    export_as_of: str,
    export_source: str = "",
    wiki_paths: set[str] | None = None,
    allow_small: bool = False,
    report_id: str | None = None,
    patient: bool = False,
) -> dict:
    place_ids = {c.place_id for candidates in places.gazetteer().values() for c in candidates}
    limits = {"minimum": 1, "minimum_per_kind": 0} if allow_small else {}
    question_set = question_sets.load(
        question_set_path, place_ids=place_ids, wiki_paths=wiki_paths, **limits
    )
    today = live.today()
    report_id = report_id or datetime.now(UTC).strftime("guide-%Y%m%d-%H%M%S")

    runs_path = Path(runs_dir) / f"{report_id}.jsonl"
    runs_path.parent.mkdir(parents=True, exist_ok=True)
    with runs_path.open("a", encoding="utf-8") as stream:

        def keep(record: dict) -> None:
            # Written as each finishes, so an interrupted run leaves what it
            # paid for on disk.
            stamped = {
                **record,
                "export_sha256": export_sha256,
                "generation": generation,
                "report_id": report_id,
            }
            stream.write(json.dumps(stamped, ensure_ascii=False) + "\n")
            stream.flush()

        records, shared = run(
            question_set.on(today),
            # Waits out rate limits outside the question's clock (see PatientModel).
            model=PatientModel(model) if patient else model,
            places=places,
            policy=policy,
            live=live,
            today=today,
            on_run=keep,
        )

    waits = sum(record["rate_limit_waits"] for record in records)
    scores = score_all(records, judge)
    limitations = list(LIMITATIONS)
    if judge is None:
        limitations.insert(
            0, "판정 모델을 돌리지 않았습니다. 판정 점수 네 가지는 전부 '채점 못 함'입니다."
        )
    if allow_small:
        limitations.insert(
            0,
            f"문항이 {len(question_set.questions)}개뿐입니다. 공개 기준(60문항, 종류마다 8문항)에 못 미치는 "
            "점검용 실행이고, 종류별 점수는 문항 하나에 크게 흔들립니다.",
        )
    if "synthetic" in export_source:
        limitations.insert(
            0, "한적의 실제 데이터가 아니라 지어낸 장소로 만든 가상 내보내기 파일로 돌렸습니다."
        )
    if waits:
        limitations.append(
            f"모델 제공자의 요청 한도에 {waits}번 걸려 기다렸습니다. 기다린 시간은 질문의 제한 시간과 소요 시간에서 뺐습니다."
        )
    failed = sum(
        record["outcome"] == "failed" and record["cause"] == "model_failed" for record in records
    )
    if failed:
        limitations.append(
            f"{failed}건은 모델을 쓸 수 없어 답이 나오지 않았습니다. 에이전트의 판단과 무관한 실패입니다."
        )
    if live.mode == "replay":
        limitations.append("한적의 혼잡 예보와 대안은 미리 녹화해 둔 응답을 썼습니다.")

    report, samples = build(
        report_id,
        question_set,
        records,
        scores,
        answer_model=str(model.settings.get("name", "")),
        judge_model=str(judge.settings.get("name", "")) if judge is not None else "(돌리지 않음)",
        generation=generation,
        export_sha256=export_sha256,
        export_as_of=export_as_of,
        live_recorded_at=shared.fetched_at()
        or datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        limitations=limitations,
    )
    if set(report["strategies"]) != set(STRATEGIES):
        raise RuntimeError("an evaluation must cover both strategies")
    store.put(report, samples)
    return report
