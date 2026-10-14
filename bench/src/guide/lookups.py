"""The fixed set of lookups the model may choose from.

The model names a lookup and gives arguments. Code checks the arguments, runs
one fixed read, and hands back text with ids. The model never writes a query,
never reaches a place by guessing its id, and never sees a ranking it could
reorder into a different one: lists arrive numbered in Hanjeok's order
(constitution, Principle VI).

A lookup that cannot run is **refused with a reason**, and the refusal is a
step the visitor sees. It is not an error. "The date is outside the forecast
window" is part of how the answer was reached.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from guide import citations as cite
from guide.live import Alternatives, Congestion, LiveClient, LiveError
from guide.scope import FORECAST_DAYS
from guide.sources import Places, Policy

GRADE_KO = {"RELAXED": "여유", "NORMAL": "보통", "CROWDED": "혼잡", "VERY_CROWDED": "매우혼잡"}

# Which wiki pages explain a lookup's result. A table, not a search: the wiki
# is small, a table cannot miss, and a reviewer can read it.
DECLARES = {
    "related_places": ("concepts/alternative-scoring.md",),
    "congestion": ("concepts/congestion-diagnosis.md",),
    "alternatives": ("concepts/alternative-scoring.md", "decisions/keep-llm-out-of-ranking.md"),
}

# Which page a policy question is about, by the words it uses. Same reasoning
# as DECLARES: for a wiki this small a table is reviewable and cannot miss.
POLICY_TOPICS = (
    (("혼잡", "붐비", "등급", "예보", "집중률"), "concepts/congestion-diagnosis.md"),
    (("대안", "대신", "순서", "순위", "점수"), "concepts/alternative-scoring.md"),
    (("순위", "순서", "모델", "AI", "고르", "골라"), "decisions/keep-llm-out-of-ranking.md"),
    (("연관", "이어진", "비슷"), "entities/related-attraction-api.md"),
)

# What the model is told about each lookup. Kept beside the code that
# validates the same arguments, so the two cannot drift apart unnoticed.
DESCRIPTIONS = {
    "search_places": "search_places(query[, region_code]) — 글로 장소를 찾는다. 최대 5곳.",
    "place_detail": "place_detail(place_id) — 이미 나온 장소의 소개.",
    "related_places": "related_places(place_id[, limit]) — 그 장소와 한적이 이어 둔 장소를 순위대로.",
    "congestion": "congestion(place_id, date) — 그 날짜의 혼잡 예보.",
    "alternatives": "alternatives(place_id, date) — 그 날짜에 대신 갈 만한 곳을 한적이 정한 순서대로.",
    "events": "events(place_id[, date]) — 그 장소나 바로 옆에서 열리는 행사.",
    "policy": "policy(query) — 한적이 혼잡과 대안을 어떻게 정하는지 적은 문서를 찾는다.",
}
LOOKUPS = tuple(DESCRIPTIONS)
LIVE = ("congestion", "alternatives")


def offered(strategy: str) -> tuple[str, ...]:
    """The only difference between the two evaluated strategies."""
    if strategy == "graph":
        return LOOKUPS
    if strategy == "vector":
        return tuple(name for name in LOOKUPS if name != "related_places")
    raise ValueError(f"unknown strategy: {strategy}")


@dataclass(frozen=True, slots=True)
class Passage:
    id: str
    label: str
    text: str


@dataclass(frozen=True, slots=True)
class Outcome:
    status: str
    """`ok`, `refused`, `no_data` or `failed`."""

    inputs: dict[str, Any]
    summary: str
    reason: str | None = None
    produced: tuple[str, ...] = ()
    as_of: str | None = None
    cause: str | None = None


@dataclass(slots=True)
class Fetched:
    """Everything this question has been given so far. The citation gate reads
    `labels`; the prompt reads `passages`; the path view reads the rest."""

    passages: list[Passage] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)
    place_ids: set[int] = field(default_factory=set)
    nodes: dict[str, dict] = field(default_factory=dict)
    edges: list[dict] = field(default_factory=list)
    live_records: int = 0

    def add(self, passage: Passage) -> None:
        if passage.id not in self.labels:
            self.passages.append(passage)
            self.labels[passage.id] = passage.label


def _percent_top(percentile: float) -> int:
    return max(1, round(100 - percentile))


def _day(value: str) -> str:
    parsed = date.fromisoformat(value)
    return f"{parsed.month}월 {parsed.day}일"


class Lookups:
    def __init__(
        self,
        places: Places,
        policy: Policy,
        live: LiveClient,
        *,
        today: date,
        strategy: str = "graph",
    ) -> None:
        self.places, self.policy, self.live, self.today = places, policy, live, today
        self.offered = offered(strategy)
        self.fetched = Fetched()
        self._done: set[tuple] = set()
        self._live_cache: dict[tuple, Any] = {}

    # ---- shared pieces ----

    def add_place(self, place) -> str:
        """Record a place as fetched: citable, usable as a lookup argument, and
        drawn in the path."""
        citation = cite.place(place.id)
        category = " ".join(part for part in (place.category_mid, place.category_small) if part)
        head = " · ".join(part for part in (place.name, place.region_label, category) if part)
        coverage = (
            "혼잡 예보 대상"
            if place.has_congestion_data
            else "혼잡 데이터 없음(한적하다는 뜻이 아님)"
        )
        text = f"{head} · place_id {place.id} · {coverage}"
        if place.overview or place.summary:
            text += f"\n{place.overview or place.summary}"
        self.fetched.add(Passage(citation, place.name, text))
        self.fetched.place_ids.add(place.id)
        self.fetched.nodes[citation] = {
            "id": citation,
            "kind": "place",
            "label": place.name,
            "region": place.region_label,
        }
        if place.region_code:
            region = f"region:{place.region_code}"
            self.fetched.nodes[region] = {
                "id": region,
                "kind": "region",
                "label": place.region_label or place.region_code,
                "region": None,
            }
            self._edge(citation, region, "in_region")
        return citation

    def _edge(self, source: str, target: str, kind: str, rank: int | None = None) -> None:
        edge = {"from": source, "to": target, "kind": kind, "rank": rank}
        if edge not in self.fetched.edges:
            self.fetched.edges.append(edge)

    def _declare(self, name: str, about: str) -> list[str]:
        produced = []
        for path in DECLARES.get(name, ()):
            page = self.policy.page(path)
            if page is None:
                continue  # the wiki is not loaded, or the page was renamed
            citation = cite.wiki(page.path)
            self.fetched.add(Passage(citation, page.title, page.text))
            self.fetched.nodes[citation] = {
                "id": citation,
                "kind": "document",
                "label": page.title,
                "region": None,
            }
            self._edge(citation, about, "explains")
            produced.append(citation)
        return produced

    def _refuse(self, inputs: dict, reason: str) -> Outcome:
        return Outcome("refused", inputs, "조회하지 않았습니다", reason=reason)

    def _place_arg(self, args: dict) -> tuple[int | None, str | None]:
        place_id = args.get("place_id")
        if not isinstance(place_id, int) or isinstance(place_id, bool):
            return None, "place_id 가 필요합니다."
        if place_id not in self.fetched.place_ids:
            # The rule that stops a model reaching a place by guessing its id.
            return (
                None,
                "이 질문에서 아직 나오지 않은 장소입니다. 먼저 이름으로 찾거나 연관 장소로 받아야 합니다.",
            )
        return place_id, None

    def _date_arg(self, args: dict, *, required: bool) -> tuple[str | None, str | None]:
        value = args.get("date")
        if value in (None, ""):
            return (None, "date 가 필요합니다. YYYY-MM-DD 로 주세요.") if required else (None, None)
        try:
            parsed = date.fromisoformat(str(value))
        except ValueError:
            return None, "date 는 YYYY-MM-DD 여야 합니다."
        last = self.today + timedelta(days=FORECAST_DAYS - 1)
        if not self.today <= parsed <= last:
            return None, f"예보는 {self.today.isoformat()}부터 {last.isoformat()}까지만 있습니다."
        return parsed.isoformat(), None

    def _text_arg(self, args: dict, limit: int) -> tuple[str | None, str | None]:
        text = args.get("text")
        text = text.strip() if isinstance(text, str) else ""
        if not 1 <= len(text) <= limit:
            return None, f"query 는 1자 이상 {limit}자 이하여야 합니다."
        return text, None

    # ---- dispatch ----

    def run(self, name: str, args: dict) -> Outcome:
        if name not in self.offered:
            # Includes a lookup that exists but is withheld from this strategy.
            return self._refuse({}, "쓸 수 없는 조회입니다.")
        outcome = getattr(self, f"_{name}")(args)
        if outcome.status != "refused":
            key = (name, tuple(sorted(outcome.inputs.items())))
            if key in self._done:
                return self._refuse(
                    outcome.inputs,
                    "같은 조회를 이미 했습니다. 받은 결과로 답하거나 다른 조회를 고르세요.",
                )
            self._done.add(key)
        return outcome

    # ---- the seven ----

    def _search_places(self, args):
        text, problem = self._text_arg(args, 100)
        if problem:
            return self._refuse({}, problem)
        region = args.get("region_code")
        if region is not None and not (isinstance(region, str) and re.fullmatch(r"\d{5}", region)):
            return self._refuse({"text": text}, "region_code 는 숫자 5자리입니다.")
        inputs = {"text": text} | ({"region_code": region} if region else {})
        found = self.places.search(text, limit=5, region_code=region)
        if not found:
            return Outcome("no_data", inputs, "찾은 장소가 없습니다", as_of=self.places.exported_at)
        produced = tuple(self.add_place(place) for place in found)
        names = ", ".join(place.name for place in found)
        return Outcome(
            "ok",
            inputs,
            f"{len(found)}곳: {names}",
            produced=produced,
            as_of=self.places.exported_at,
        )

    def _place_detail(self, args):
        place_id, problem = self._place_arg(args)
        if problem:
            return self._refuse({}, problem)
        place = self.places.detail(place_id)
        if place is None:
            return Outcome(
                "no_data",
                {"place_id": place_id},
                "장소 정보가 없습니다",
                as_of=self.places.exported_at,
            )
        citation = self.add_place(place)
        return Outcome(
            "ok",
            {"place_id": place_id},
            f"{place.name} ({place.region_label or '지역 정보 없음'})",
            produced=(citation,),
            as_of=self.places.exported_at,
        )

    def _related_places(self, args):
        place_id, problem = self._place_arg(args)
        if problem:
            return self._refuse({}, problem)
        limit = args.get("limit")
        if limit is None:
            limit = 5
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 10:
            return self._refuse({"place_id": place_id}, "limit 은 1 이상 10 이하입니다.")
        inputs = {"place_id": place_id, "limit": limit}
        rows = self.places.related(place_id, limit=limit)
        base = self.places.detail(place_id)
        name = base.name if base else str(place_id)
        if not rows:
            return Outcome(
                "no_data",
                inputs,
                f"{name}와(과) 이어 둔 장소가 없습니다",
                as_of=self.places.exported_at,
            )
        source = cite.place(place_id)
        citation = cite.related(place_id)
        lines, produced = [], [citation]
        for position, row in enumerate(rows, start=1):
            target = self.add_place(row.place)
            produced.append(target)
            # Position in Hanjeok's order is the rank the visitor sees, also
            # for a link Hanjeok left unranked, which sorts after ranked ones.
            self._edge(source, target, "related", row.rank or position)
            lines.append(
                f"{position}. {row.place.name} ({row.place.region_label or '지역 정보 없음'}, place_id {row.place.id})"
            )
        self.fetched.add(
            Passage(
                citation,
                f"{name} 연관 장소",
                f"{name}와(과) 이어진 장소. 순서는 한적이 정한 순위다.\n" + "\n".join(lines),
            )
        )
        produced += self._declare("related_places", source)
        return Outcome(
            "ok",
            inputs,
            f"{name}와(과) 이어진 {len(rows)}곳",
            produced=tuple(dict.fromkeys(produced)),
            as_of=self.places.exported_at,
        )

    def _live(self, kind: str, place_id: int, day: str):
        key = (kind, place_id, day)
        if key not in self._live_cache:
            self._live_cache[key] = getattr(self.live, kind)(place_id, day)
        return self._live_cache[key]

    def _congestion(self, args):
        place_id, problem = self._place_arg(args)
        if problem:
            return self._refuse({}, problem)
        day, problem = self._date_arg(args, required=True)
        if problem:
            return self._refuse({"place_id": place_id}, problem)
        inputs = {"place_id": place_id, "date": day}
        try:
            result: Congestion = self._live("congestion", place_id, day)
        except LiveError as error:
            return Outcome(
                "failed",
                inputs,
                "한적 서비스에서 받지 못했습니다",
                reason="한적 서비스에 닿지 못했습니다.",
                cause=error.cause,
            )
        citation = cite.congestion(place_id, day)
        source = cite.place(place_id)
        if not result.has_data:
            # Its own outcome, with its own sentence. Never a grade.
            self.fetched.add(
                Passage(
                    citation,
                    f"{result.name} 혼잡 데이터 없음",
                    f"{result.name}은(는) 한적이 혼잡을 예보하지 않는 장소다. 데이터가 없다는 뜻이며, 한적하다는 뜻이 아니다.",
                )
            )
            self.fetched.live_records += 1
            return Outcome(
                "no_data",
                inputs,
                f"{result.name}: 혼잡 데이터 없음",
                produced=(citation,),
                as_of=result.fetched_at,
            )
        text = (
            f"{result.name} {_day(day)}({day}) 혼잡 예보: {GRADE_KO[result.grade]} "
            f"(전국 대비 상위 {_percent_top(result.percentile)}%, 집중률 {result.concentration:g})"
        )
        if result.better_dates:
            better = ", ".join(
                f"{_day(item.date)}({item.date}) {GRADE_KO[item.grade]}"
                for item in result.better_dates
            )
            text += f"\n그 뒤의 더 한적한 날(한적이 고른 순서): {better}"
        self.fetched.add(Passage(citation, f"{result.name} 혼잡 예보 ({_day(day)})", text))
        self.fetched.live_records += 1
        produced = [citation, *self._declare("congestion", source)]
        return Outcome(
            "ok",
            inputs,
            f"{_day(day)} 예보: {GRADE_KO[result.grade]} (상위 {_percent_top(result.percentile)}%)",
            produced=tuple(produced),
            as_of=result.fetched_at,
        )

    def _alternatives(self, args):
        place_id, problem = self._place_arg(args)
        if problem:
            return self._refuse({}, problem)
        day, problem = self._date_arg(args, required=True)
        if problem:
            return self._refuse({"place_id": place_id}, problem)
        inputs = {"place_id": place_id, "date": day}
        try:
            result: Alternatives = self._live("alternatives", place_id, day)
        except LiveError as error:
            return Outcome(
                "failed",
                inputs,
                "한적 서비스에서 받지 못했습니다",
                reason="한적 서비스에 닿지 못했습니다.",
                cause=error.cause,
            )
        base = self.places.detail(place_id)
        name = base.name if base else str(place_id)
        citation = cite.alternatives(place_id, day)
        source = cite.place(place_id)
        self.fetched.live_records += 1
        if not result.items:
            self.fetched.add(
                Passage(
                    citation,
                    f"{name} 대안 없음 ({_day(day)})",
                    f"{name}의 {_day(day)} 대안으로 한적이 내놓은 곳이 없다.",
                )
            )
            return Outcome(
                "no_data",
                inputs,
                "한적이 내놓은 대안이 없습니다",
                produced=(citation,),
                as_of=result.fetched_at,
            )
        lines, produced = [], [citation]
        for position, item in enumerate(result.items, start=1):
            known = self.places.detail(item.place_id)
            if known is not None:
                target = self.add_place(known)
                produced.append(target)
                self._edge(source, target, "alternative", position)
            distance = f", {item.distance_km:g}km" if item.distance_km is not None else ""
            lines.append(
                f"{position}. {item.name} — {GRADE_KO[item.grade]}{distance} (place_id {item.place_id})"
            )
        self.fetched.add(
            Passage(
                citation,
                f"{name} 대안 ({_day(day)})",
                f"{name} 대신 {_day(day)}({day})에 갈 만한 곳. 순서는 한적이 정했고 바꿀 수 없다.\n"
                + "\n".join(lines),
            )
        )
        produced += self._declare("alternatives", source)
        names = ", ".join(item.name for item in result.items)
        return Outcome(
            "ok",
            inputs,
            f"대안 {len(result.items)}곳: {names}",
            produced=tuple(dict.fromkeys(produced)),
            as_of=result.fetched_at,
        )

    def _events(self, args):
        place_id, problem = self._place_arg(args)
        if problem:
            return self._refuse({}, problem)
        day, problem = self._date_arg(args, required=False)
        if problem:
            return self._refuse({"place_id": place_id}, problem)
        inputs = {"place_id": place_id} | ({"date": day} if day else {})
        rows = self.places.events(place_id, on=day)
        base = self.places.detail(place_id)
        name = base.name if base else str(place_id)
        citation = cite.events(place_id, day)
        when = f"{_day(day)}에 " if day else ""
        if not rows:
            self.fetched.add(
                Passage(
                    citation,
                    f"{name} 행사 없음",
                    f"{name}에서 {when}열리는 행사로 한적에 등록된 것이 없다.",
                )
            )
            return Outcome(
                "no_data",
                inputs,
                "등록된 행사가 없습니다",
                produced=(citation,),
                as_of=self.places.exported_at,
            )
        lines = [f"- {row.name} ({row.start_date} ~ {row.end_date})" for row in rows]
        self.fetched.add(
            Passage(
                citation,
                f"{name} 행사",
                f"{name}이나 바로 옆에서 {when}열리는 행사:\n" + "\n".join(lines),
            )
        )
        for row in rows:
            self.fetched.nodes[row.id] = {
                "id": row.id,
                "kind": "event",
                "label": row.name,
                "region": None,
            }
            self._edge(row.id, cite.place(place_id), "held_at")
        return Outcome(
            "ok",
            inputs,
            f"행사 {len(rows)}건: " + ", ".join(row.name for row in rows),
            produced=(citation,),
            as_of=self.places.exported_at,
        )

    def _policy(self, args):
        text, problem = self._text_arg(args, 200)
        if problem:
            return self._refuse({}, problem)
        # Pages named by a word in the query come first; search fills what is
        # left. The wiki is written in English and questions arrive in Korean:
        # on the first real evaluation, similarity search alone answered "how
        # are congestion grades decided?" with three unrelated pages.
        paths = [path for words, path in POLICY_TOPICS if any(word in text for word in words)]
        pages = [page for page in map(self.policy.page, paths) if page is not None][:3]
        if len(pages) < 3:
            have = {page.path for page in pages}
            found = [page for page in self.policy.search(text, limit=3) if page.path not in have]
            pages += found[: 3 - len(pages)]
        if not pages:
            return Outcome("no_data", {"text": text}, "맞는 정책 문서가 없습니다")
        produced = []
        for page in pages:
            citation = cite.wiki(page.path)
            self.fetched.add(Passage(citation, page.title, page.text))
            self.fetched.nodes[citation] = {
                "id": citation,
                "kind": "document",
                "label": page.title,
                "region": None,
            }
            produced.append(citation)
        return Outcome(
            "ok",
            {"text": text},
            "문서 " + ", ".join(page.title for page in pages),
            produced=tuple(produced),
        )
