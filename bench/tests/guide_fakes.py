"""Stand-ins that let the guide's lookups and agent run with no database, no
network and no model. Built from the same synthetic export the integration
tests load into Neo4j, so both kinds of test describe one invented town."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from guide.export import Export, read_export
from guide.graph.read import EventRow, PlaceRow, RelatedRow
from guide.live import LiveClient, Recording
from guide.loader import place_text
from guide.model import ModelFailure
from guide.scope import Candidate
from guide.sources import Page

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 10, 13)  # a Tuesday; the day the live recording was made

PAGES = {
    "concepts/congestion-diagnosis.md": Page(
        "concepts/congestion-diagnosis.md",
        "Congestion Diagnosis",
        "혼잡 등급은 같은 날 전국 분포에서 그 장소가 놓이는 자리로 정한다.",
    ),
    "concepts/alternative-scoring.md": Page(
        "concepts/alternative-scoring.md",
        "Alternative Scoring",
        "대안 점수는 연관도, 한적함, 거리를 더한 값이고 순서는 서비스가 정한다.",
    ),
    "decisions/keep-llm-out-of-ranking.md": Page(
        "decisions/keep-llm-out-of-ranking.md",
        "Keep LLM Out Of Ranking",
        "순위는 모델이 정하지 않는다. 모델은 정해진 순위를 설명만 한다.",
    ),
}


def export() -> Export:
    return read_export(FIXTURES / "hanjeok-export")


class ExportPlaces:
    def __init__(self, source: Export | None = None) -> None:
        self._export = source or export()
        self.exported_at = self._export.exported_at
        self._by_id = {p.id: p for p in self._export.places}
        self.searches: list[str] = []

    def _row(self, place) -> PlaceRow:
        return PlaceRow(**{name: getattr(place, name) for name in PlaceRow.__dataclass_fields__})

    def search(self, text, *, limit, region_code):
        self.searches.append(text)
        words = text.split()
        scored = [
            (sum(word in place_text(p) for word in words), p)
            for p in self._export.places
            if region_code is None or p.region_code == region_code
        ]
        ranked = sorted(
            (pair for pair in scored if pair[0] > 0), key=lambda pair: (-pair[0], pair[1].id)
        )
        return [self._row(place) for _, place in ranked[:limit]]

    def detail(self, place_id):
        place = self._by_id.get(place_id)
        return self._row(place) if place else None

    def match_name(self, name):
        key = "".join(name.split())
        tier = lambda k: 0 if k == key else 1 if k.startswith(key) else 2  # noqa: E731
        hits = [p for p in self._export.places if key and key in "".join(p.name.split())]
        hits.sort(
            key=lambda p: (
                tier("".join(p.name.split())),
                not p.has_congestion_data,
                len(p.name),
                p.id,
            )
        )
        return [self._row(p) for p in hits[:10]]

    def related(self, place_id, *, limit):
        links = [link for link in self._export.related if link.base_id == place_id]
        links.sort(key=lambda link: (link.rank is None, link.rank or 0, -(link.score or 0)))
        return [
            RelatedRow(
                self._row(self._by_id[link.related_id]),
                link.rank,
                link.score,
                link.distance_km,
                link.travel_minutes,
            )
            for link in links[:limit]
        ]

    def events(self, place_id, *, on):
        place = self._by_id[place_id]
        rows = []
        for event in self._export.events:
            tied = event.place_id == place_id
            beside = (
                event.place_id is None
                and event.lat is not None
                and (abs(event.lat - place.lat) < 0.005 and abs(event.lng - place.lng) < 0.005)
            )
            if (tied or beside) and (on is None or event.start_date <= on <= event.end_date):
                rows.append(
                    EventRow(
                        event.id,
                        event.kind,
                        event.name,
                        event.start_date,
                        event.end_date,
                        event.place_text,
                    )
                )
        return rows

    def gazetteer(self):
        grouped: dict[str, list[Candidate]] = {}
        for place in sorted(self._export.places, key=lambda p: (not p.has_congestion_data, p.id)):
            grouped.setdefault("".join(place.name.split()), []).append(
                Candidate(place.id, place.name, place.region_label or "")
            )
        return grouped


class FakePolicy:
    def __init__(self, pages=PAGES) -> None:
        self._pages = dict(pages)

    def page(self, path):
        return self._pages.get(path)

    def search(self, text, *, limit):
        return list(self._pages.values())[:limit]


def replay_live() -> LiveClient:
    return LiveClient(mode="replay", recording=Recording(FIXTURES / "hanjeok-live"))


class ScriptedModel:
    """Returns prepared actions in order and keeps what it was shown."""

    settings = {"name": "scripted"}

    def __init__(self, *replies) -> None:
        self._replies = list(replies)
        self.calls: list[dict] = []

    def decide(self, system, user, schema, *, timeout):
        self.calls.append({"system": system, "user": user, "schema": schema, "timeout": timeout})
        if not self._replies:
            raise AssertionError("the scripted model ran out of replies")
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        allowed = schema["properties"]["action"]["enum"]
        assert reply["action"] in allowed, f"{reply['action']} was not offered: {allowed}"
        return reply


def action(name: str, **args) -> dict:
    blank = dict.fromkeys(("place_id", "date", "text", "region_code", "limit", "answer"))
    return {**blank, "action": name, "citations": [], **args}


def answer(text: str, *citations: str) -> dict:
    return action("answer", answer=text, citations=list(citations))


def model_down(kind: str = "provider_unavailable") -> ModelFailure:
    return ModelFailure(kind)
