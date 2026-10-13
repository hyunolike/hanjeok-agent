"""What is decided about a question before any model is asked.

Three things, all by rule: whether the question is one the guide answers at
all, which dates it means, and which places it names. They run first because
they are cheap, because their result is the same every time, and because the
provider is paced — a visitor should see the first step at once, not after a
queue (spec SC-001).

None of this is clever. A rule that is wrong is wrong the same way tomorrow and
can be fixed with a test; the alternative is asking a model whether a question
is in scope and getting a different boundary each run.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

# Hanjeok forecasts today and the 29 days after it.
FORECAST_DAYS = 30

# The guide holds no data for these, and the export deliberately leaves the
# columns out (contracts/hanjeok-export.md). Declining is the correct answer.
_UNSUPPORTED = {
    # "얼마" 는 여기 없다 — "얼마나 붐벼?" 가 요금 질문으로 읽힌다. 아래에서 따로 본다.
    "입장료와 요금": ("입장료", "요금", "가격", "무료", "할인"),
    "운영 시간": ("영업시간", "운영시간", "휴무", "쉬는 날", "휴관", "문 여", "문 닫"),
    "연락처": ("전화", "연락처", "홈페이지", "사이트"),
    "교통과 주차": ("주차", "버스", "지하철", "가는 법", "가는 길", "가는 방법", "교통", "택시"),
    "식당과 숙소": ("맛집", "식당", "카페 추천", "숙소", "호텔", "펜션"),
    "예약": ("예약", "예매", "티켓"),
    "날씨": ("날씨", "비 와", "비와", "기온"),
}

# Attempts to move the ranking or the rules into the conversation.
_OVERRIDE = (
    "순위를 바꿔",
    "순서를 바꿔",
    "순위 바꿔",
    "순서 바꿔",
    "네가 골라",
    "니가 골라",
    "너가 골라",
    "네 생각",
    "규칙을 무시",
    "규칙 무시",
    "지시를 무시",
    "지시 무시",
    "무시하고",
    "시스템 프롬프트",
    "프롬프트를",
    "ignore previous",
    "ignore the",
    "system prompt",
)

# Without a place, a question has to at least be about this.
_DOMAIN = (
    "혼잡",
    "붐비",
    "붐벼",
    "붐빌",
    "한적",
    "한산",
    "조용",
    "사람 많",
    "사람이 많",
    "대안",
    "대신",
    "장소",
    "곳",
    "관광",
    "여행",
    "나들이",
    "산책",
    "행사",
    "축제",
    "전시",
    "정책",
    "기준",
    "등급",
    "순위",
    "점수",
    "추천",
    "비슷",
    "근처",
    "주변",
    "연관",
    "이어진",
    "어디",
    "예보",
)

_REFERENCE = ("거기", "그곳", "그 곳", "그 장소", "저기", "아까 그", "방금 그", "같은 곳")
_DATE_REFERENCE = ("그날", "그 날", "같은 날")

_WEEKDAYS = "월화수목금토일"


@dataclass(frozen=True, slots=True)
class Turn:
    """What an earlier question in this visit was about. No answer text: an
    answer is the model's words, and feeding them back as context would let a
    mistake in one answer become the premise of the next."""

    question: str
    place_ids: tuple[int, ...]
    dates: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Candidate:
    place_id: int
    name: str
    region: str


@dataclass(frozen=True, slots=True)
class Scope:
    outcome: str
    """`proceed`, `declined` or `ask_user`."""

    cause: str | None = None
    message: str | None = None
    place_ids: tuple[int, ...] = ()
    dates: tuple[str, ...] = ()
    candidates: tuple[Candidate, ...] = ()
    summary: str = ""
    notes: tuple[str, ...] = field(default=())


def parse_dates(question: str, today: date) -> list[date]:
    """Every date the question names, in the order it names them.

    Relative words are resolved against `today`, which the caller supplies —
    in an evaluation that is the recording's day, so "this Saturday" means the
    same date in both strategies.
    """
    found: list[tuple[int, date]] = []
    taken: list[tuple[int, int]] = []

    def add(match: re.Match, value: date | None) -> None:
        if value is None or any(a < match.end() and match.start() < b for a, b in taken):
            return
        taken.append(match.span())
        found.append((match.start(), value))

    def build(year: int, month: int, day: int) -> date | None:
        try:
            return date(year, month, day)
        except ValueError:
            return None

    for m in re.finditer(r"(\d{4})-(\d{1,2})-(\d{1,2})", question):
        add(m, build(int(m[1]), int(m[2]), int(m[3])))
    for m in re.finditer(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", question):
        value = build(today.year, int(m[1]), int(m[2]))
        # "1월 3일" asked in December means next January.
        if value is not None and value < today - timedelta(days=180):
            value = build(today.year + 1, int(m[1]), int(m[2]))
        add(m, value)
    for m in re.finditer(r"(?<![\d월])\s?(\d{1,2})\s*일(?!\s*(?:동안|간|째|정도))", question):
        value = build(today.year, today.month, int(m[1]))
        if value is not None and value < today:
            following = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
            value = build(following.year, following.month, int(m[1]))
        add(m, value)

    for m in re.finditer(rf"(이번\s*주|다음\s*주|담주)?\s*([{_WEEKDAYS}])요일", question):
        target = _WEEKDAYS.index(m[2])
        monday = today - timedelta(days=today.weekday())
        if m[1] and m[1].replace(" ", "") in ("다음주", "담주"):
            value = monday + timedelta(days=7 + target)
        elif m[1]:
            value = monday + timedelta(days=target)
        else:
            # A bare weekday is the next one, today included.
            value = today + timedelta(days=(target - today.weekday()) % 7)
        add(m, value)
    for m in re.finditer(r"(이번\s*주|다음\s*주|담주)?\s*주말", question):
        monday = today - timedelta(days=today.weekday())
        saturday = monday + timedelta(days=5)
        if m[1] and m[1].replace(" ", "") in ("다음주", "담주") or not m[1] and saturday < today:
            saturday += timedelta(days=7)
        add(m, saturday)
    # Past days are read too, so that asking about yesterday is declined with
    # the forecast window instead of being answered as if no date was given.
    for word, offset in (("그저께", -2), ("어제", -1), ("모레", 2), ("내일", 1), ("오늘", 0)):
        for m in re.finditer(word, question):
            add(m, today + timedelta(days=offset))

    ordered = [value for _, value in sorted(found, key=lambda pair: pair[0])]
    return list(dict.fromkeys(ordered))


def find_names(
    question: str, gazetteer: dict[str, Sequence[Candidate]]
) -> list[tuple[str, Sequence[Candidate]]]:
    """Place names in the question, longest first, never overlapping.

    Spaces are ignored on both sides, so "솔내한옥마을" and "솔내 한옥마을" are
    the same name. Longest first means "가람궁" inside "가람궁 달빛 야행" does
    not also match a shorter place called "가람".
    """
    text = "".join(question.split())
    hits: list[tuple[int, int, str]] = []
    for key in gazetteer:
        if len(key) < 2:
            continue
        start = text.find(key)
        while start >= 0:
            hits.append((start, start + len(key), key))
            start = text.find(key, start + 1)
    hits.sort(key=lambda hit: (-(hit[1] - hit[0]), hit[0]))
    chosen: list[tuple[int, int, str]] = []
    for hit in hits:
        if all(hit[1] <= other[0] or other[1] <= hit[0] for other in chosen):
            chosen.append(hit)
    chosen.sort(key=lambda hit: hit[0])
    names = list(dict.fromkeys(key for _, _, key in chosen))
    return [(key, gazetteer[key]) for key in names]


def read_question(
    question: str,
    *,
    today: date,
    gazetteer: dict[str, Sequence[Candidate]],
    turns: Sequence[Turn] = (),
    choice: int | None = None,
) -> Scope:
    lowered = question.lower()

    # Rule override first: such a question often also names a place, and
    # answering the rest of it would look like going along with the first half.
    if any(phrase in lowered for phrase in _OVERRIDE):
        return Scope(
            "declined",
            "rule_override",
            "장소의 순서와 등급은 한적 서비스가 정합니다. 제가 바꾸거나 대신 고를 수 없습니다. "
            "어느 장소가 언제 붐비는지, 대신 갈 만한 곳이 어디인지는 물어보실 수 있습니다.",
            summary="순위나 규칙을 바꿔 달라는 요청으로 읽었습니다",
        )
    for topic, words in _UNSUPPORTED.items():
        asks_price = topic == "입장료와 요금" and re.search(r"얼마(?!나)", question)
        if asks_price or any(word in question for word in words):
            return Scope(
                "declined",
                "unsupported_topic",
                f"{topic}은(는) 제가 갖고 있지 않은 정보입니다. "
                "혼잡 예보, 대신 갈 만한 곳, 이어진 장소와 행사는 알려 드릴 수 있습니다.",
                summary=f"답할 수 없는 주제({topic})로 읽었습니다",
            )

    dates = parse_dates(question, today)
    notes: list[str] = []
    if not dates and turns and any(word in question for word in _DATE_REFERENCE):
        dates = [date.fromisoformat(value) for value in turns[-1].dates]
        notes.append("날짜는 앞 질문에서 가져왔습니다")
    last = today + timedelta(days=FORECAST_DAYS - 1)
    if any(value < today or value > last for value in dates):
        return Scope(
            "declined",
            "date_out_of_range",
            f"한적의 혼잡 예보는 오늘({today.isoformat()})부터 {last.isoformat()}까지만 있습니다. "
            "그 안의 날짜로 다시 물어봐 주세요.",
            summary="예보 범위를 벗어난 날짜로 읽었습니다",
        )

    place_ids: list[int] = []
    for _, candidates in find_names(question, gazetteer):
        if len(candidates) == 1:
            place_ids.append(candidates[0].place_id)
            continue
        chosen = next((c for c in candidates if c.place_id == choice), None)
        if chosen is not None:
            place_ids.append(chosen.place_id)
            continue
        # Earlier turns may already have settled which one is meant.
        earlier = {pid for turn in turns for pid in turn.place_ids}
        settled = [c for c in candidates if c.place_id in earlier]
        if len(settled) == 1:
            place_ids.append(settled[0].place_id)
            continue
        return Scope(
            "ask_user",
            "ambiguous_place",
            f"'{candidates[0].name}'(이)라는 이름의 장소가 {len(candidates)}곳 있습니다. 어느 곳인가요?",
            candidates=tuple(candidates),
            dates=tuple(value.isoformat() for value in dates),
            summary=f"'{candidates[0].name}'이(가) {len(candidates)}곳이라 어느 곳인지 물어봅니다",
        )

    if not place_ids and turns and any(word in question for word in _REFERENCE):
        place_ids = list(turns[-1].place_ids)
        if place_ids:
            notes.append("장소는 앞 질문에서 가져왔습니다")

    if not place_ids and not any(word in question for word in _DOMAIN):
        return Scope(
            "declined",
            "off_topic",
            "저는 한적의 장소, 혼잡 예보, 대신 갈 만한 곳에 대해서만 답합니다. "
            "예를 들어 장소 이름과 날짜를 함께 물어봐 주세요.",
            summary="한적이 다루는 주제가 아닌 것으로 읽었습니다",
        )

    parts = [f"장소 {len(place_ids)}곳" if place_ids else "장소 이름 없음"]
    parts.append(
        "날짜 " + ", ".join(value.isoformat() for value in dates) if dates else "날짜 없음"
    )
    return Scope(
        "proceed",
        place_ids=tuple(dict.fromkeys(place_ids)),
        dates=tuple(value.isoformat() for value in dates),
        summary=", ".join(parts) + "(으)로 읽었습니다",
        notes=tuple(notes),
    )
