"""Writes the synthetic Hanjeok export and its broken copy.

    uv run python tests/fixtures/make_hanjeok_export.py

Every place here is invented. The format is `contracts/hanjeok-export.md`,
version 1. The output is committed; this script is kept so the fixture can be
changed by editing data rather than hand-editing hashes.

The first seven ids match the recordings the frontend replays, so a screen and
a service test are talking about the same invented town.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).parent
GARAM = ("11110", "한빛시 가람구")
SOLNAE = ("11140", "한빛시 솔내구")

# id, name, region, category_mid, category_small, lat, lng, covered, overview
PLACES = [
    (
        101,
        "가람궁",
        GARAM,
        "역사",
        "고궁",
        37.5800,
        126.9770,
        True,
        "한빛시 한가운데 있는 옛 궁궐. 주말 낮에는 정문 앞마당부터 사람이 찬다.",
    ),
    (
        118,
        "솔내 한옥마을",
        GARAM,
        "역사",
        "전통마을",
        37.5825,
        126.9850,
        True,
        "가람궁 동쪽 담을 따라 이어지는 한옥 골목. 사람이 사는 동네라 조용히 걷는 곳이다.",
    ),
    (
        124,
        "물빛 서원",
        SOLNAE,
        "역사",
        "서원",
        37.6010,
        127.0150,
        True,
        "개울을 끼고 앉은 서원. 마루에 앉으면 물소리가 들린다.",
    ),
    (
        131,
        "달맞이 숲길",
        SOLNAE,
        "자연",
        "숲길",
        37.6060,
        127.0210,
        True,
        "서원 뒤편 언덕으로 오르는 2km 남짓한 숲길.",
    ),
    (
        140,
        "은행나무길",
        GARAM,
        "자연",
        "산책로",
        37.5790,
        126.9720,
        True,
        "가람궁 서쪽 담장 밖의 은행나무 가로수길.",
    ),
    (
        141,
        "은행나무길",
        SOLNAE,
        "자연",
        "산책로",
        37.6040,
        127.0180,
        False,
        "달맞이 숲길 입구까지 이어지는 마을 길.",
    ),
    (
        150,
        "새벽 등대",
        SOLNAE,
        "자연",
        "등대",
        37.6300,
        127.0600,
        False,
        "솔내구 끝 방파제에 선 작은 등대.",
    ),
    (
        160,
        "가람 시립미술관",
        GARAM,
        "문화",
        "미술관",
        37.5770,
        126.9800,
        True,
        "옛 법원 건물을 고쳐 쓴 미술관. 평일 오전이 한가하다.",
    ),
    (
        161,
        "가람 역사박물관",
        GARAM,
        "문화",
        "박물관",
        37.5760,
        126.9740,
        True,
        "한빛시의 옛 지도와 생활 도구를 모아 둔 박물관.",
    ),
    (
        162,
        "돌담 찻집 거리",
        GARAM,
        "문화",
        "거리",
        37.5830,
        126.9800,
        True,
        "한옥을 고친 찻집이 늘어선 좁은 길.",
    ),
    (
        163,
        "가람 중앙시장",
        GARAM,
        "쇼핑",
        "전통시장",
        37.5710,
        126.9900,
        True,
        "저녁이면 먹거리 골목에 줄이 서는 오래된 시장.",
    ),
    (
        164,
        "별빛 전망대",
        GARAM,
        "자연",
        "전망대",
        37.5880,
        126.9690,
        True,
        "가람구 뒷산 중턱의 전망대. 해 질 무렵에 붐빈다.",
    ),
    (
        165,
        "가람천 산책로",
        GARAM,
        "자연",
        "산책로",
        37.5690,
        126.9780,
        True,
        "가람천을 따라 걷는 평지 산책로.",
    ),
    (
        166,
        "옛 성곽길",
        GARAM,
        "역사",
        "성곽",
        37.5900,
        126.9800,
        True,
        "성곽을 따라 한 시간쯤 걷는 길. 계단이 많다.",
    ),
    (
        167,
        "종소리 광장",
        GARAM,
        "문화",
        "광장",
        37.5740,
        126.9830,
        True,
        "정오마다 종을 치는 광장. 행사가 자주 열린다.",
    ),
    (
        168,
        "가람 공예마을",
        GARAM,
        "문화",
        "공방",
        37.5850,
        126.9900,
        True,
        "도자기와 목공 공방이 모여 있는 골목.",
    ),
    (
        169,
        "한빛 문학관",
        GARAM,
        "문화",
        "문학관",
        37.5870,
        126.9760,
        True,
        "한빛시 출신 작가들의 원고를 보여 주는 작은 문학관.",
    ),
    (
        170,
        "느티나무 쉼터",
        GARAM,
        "자연",
        "공원",
        37.5730,
        126.9700,
        True,
        "삼백 년 된 느티나무 아래의 동네 공원.",
    ),
    (
        171,
        "가람 향교",
        GARAM,
        "역사",
        "향교",
        37.5910,
        126.9870,
        True,
        "봄가을 제례 때만 문을 활짝 여는 향교.",
    ),
    (
        172,
        "달빛 다리",
        GARAM,
        "역사",
        "다리",
        37.5700,
        126.9850,
        True,
        "가람천 위의 돌다리. 밤에 불을 밝힌다.",
    ),
    (
        173,
        "솔내 수목원",
        SOLNAE,
        "자연",
        "수목원",
        37.6100,
        127.0100,
        True,
        "침엽수 숲이 넓은 수목원. 단풍철 주말에 가장 붐빈다.",
    ),
    (
        174,
        "솔내 호수공원",
        SOLNAE,
        "자연",
        "공원",
        37.5980,
        127.0250,
        True,
        "호수를 한 바퀴 도는 3km 길이 있는 공원.",
    ),
    (
        175,
        "물안개 습지",
        SOLNAE,
        "자연",
        "습지",
        37.6150,
        127.0300,
        True,
        "새벽에 물안개가 끼는 습지. 나무 데크로 걷는다.",
    ),
    (
        176,
        "솔내 도자기 가마터",
        SOLNAE,
        "역사",
        "유적",
        37.6080,
        127.0050,
        True,
        "옛 가마터를 발굴해 지붕을 씌워 둔 유적.",
    ),
    (
        177,
        "바람개비 언덕",
        SOLNAE,
        "자연",
        "언덕",
        37.6200,
        127.0400,
        True,
        "바람개비 수백 개가 도는 언덕. 사진 찍으러 많이 온다.",
    ),
    (
        178,
        "솔내 천문대",
        SOLNAE,
        "문화",
        "천문대",
        37.6250,
        127.0200,
        True,
        "예약한 사람만 밤 관측에 들어가는 작은 천문대.",
    ),
    (
        179,
        "대숲 오솔길",
        SOLNAE,
        "자연",
        "숲길",
        37.6030,
        127.0090,
        True,
        "대나무 숲 사이로 난 800m 오솔길.",
    ),
    (
        180,
        "솔내 민속촌",
        SOLNAE,
        "역사",
        "민속마을",
        37.5960,
        127.0120,
        True,
        "초가와 기와집을 옮겨 지은 민속촌.",
    ),
    (
        181,
        "개울가 책방 골목",
        SOLNAE,
        "문화",
        "거리",
        37.6000,
        127.0200,
        True,
        "헌책방 다섯 곳이 모인 골목.",
    ),
    (
        182,
        "솔내 온실 식물원",
        SOLNAE,
        "자연",
        "식물원",
        37.6120,
        127.0160,
        True,
        "유리 온실 세 동이 있는 식물원. 겨울에 찾는 사람이 많다.",
    ),
    (
        183,
        "방파제 산책길",
        SOLNAE,
        "자연",
        "산책로",
        37.6290,
        127.0560,
        True,
        "새벽 등대까지 이어지는 방파제 길.",
    ),
    (
        184,
        "솔내 어시장",
        SOLNAE,
        "쇼핑",
        "전통시장",
        37.6270,
        127.0500,
        True,
        "새벽 경매가 끝나면 한산해지는 어시장.",
    ),
    (
        185,
        "갯바위 전망대",
        SOLNAE,
        "자연",
        "전망대",
        37.6320,
        127.0650,
        False,
        "바위 위에 놓인 나무 전망대.",
    ),
    (
        186,
        "솔내 조각공원",
        SOLNAE,
        "문화",
        "공원",
        37.5990,
        127.0300,
        True,
        "야외 조각 서른 점이 놓인 잔디 공원.",
    ),
    (
        187,
        "은빛 억새밭",
        SOLNAE,
        "자연",
        "들판",
        37.6180,
        127.0350,
        True,
        "가을에 억새가 피는 들판.",
    ),
    (
        188,
        "솔내 향토자료관",
        SOLNAE,
        "문화",
        "박물관",
        37.5970,
        127.0180,
        False,
        "마을 사람들이 기증한 농기구를 모아 둔 자료관.",
    ),
    (
        189,
        "가람 야외극장",
        GARAM,
        "문화",
        "공연장",
        37.5750,
        126.9880,
        True,
        "여름밤 공연이 열리는 계단식 야외극장.",
    ),
    (
        190,
        "옛 우체국 전시관",
        GARAM,
        "문화",
        "전시관",
        37.5780,
        126.9860,
        True,
        "백 년 된 우체국 건물을 전시관으로 쓴다.",
    ),
    (
        191,
        "가람 한지공방",
        GARAM,
        "문화",
        "공방",
        37.5840,
        126.9880,
        False,
        "한지를 직접 떠 볼 수 있는 공방.",
    ),
    (
        192,
        "솔바람 캠핑숲",
        SOLNAE,
        "자연",
        "숲",
        37.6220,
        127.0120,
        True,
        "소나무 숲 안의 야영장과 산책길.",
    ),
]

# base, [(related, score, distance_km, travel_minutes), ...] — rank is the order.
RELATED = {
    101: [
        (118, 0.91, 0.8, 12),
        (124, 0.84, 4.1, 25),
        (131, 0.79, 4.9, 30),
        (166, 0.71, 1.2, 18),
        (160, 0.66, 0.5, 8),
    ],
    118: [(101, 0.91, 0.8, 12), (124, 0.80, 3.6, 22), (162, 0.77, 0.4, 6), (168, 0.70, 0.5, 8)],
    124: [(131, 0.88, 0.8, 12), (118, 0.80, 3.6, 22), (180, 0.74, 0.7, 10), (179, 0.69, 0.6, 9)],
    131: [(124, 0.88, 0.8, 12), (173, 0.76, 1.1, 15), (179, 0.72, 1.1, 16)],
    140: [(101, 0.82, 0.5, 7), (170, 0.70, 0.7, 10)],
    141: [(131, 0.75, 0.4, 6)],
    160: [(161, 0.86, 0.6, 9), (190, 0.78, 0.6, 9), (169, 0.70, 1.2, 16)],
    161: [(160, 0.86, 0.6, 9), (101, 0.74, 0.5, 8)],
    162: [(118, 0.83, 0.4, 6), (168, 0.75, 0.9, 12)],
    163: [(172, 0.72, 0.5, 7), (167, 0.68, 0.7, 10)],
    164: [(166, 0.80, 1.0, 20), (101, 0.62, 1.1, 22)],
    165: [(172, 0.79, 0.6, 8), (170, 0.66, 0.8, 11)],
    166: [(164, 0.80, 1.0, 20), (171, 0.73, 0.6, 9), (101, 0.71, 1.2, 18)],
    167: [(189, 0.74, 0.5, 7), (163, 0.68, 0.7, 10)],
    173: [(182, 0.84, 0.6, 9), (131, 0.76, 1.1, 15), (192, 0.70, 1.4, 20)],
    174: [(186, 0.81, 0.5, 7), (181, 0.66, 0.5, 8)],
    175: [(187, 0.82, 0.6, 9), (177, 0.71, 1.0, 14)],
    177: [(187, 0.78, 0.5, 8), (175, 0.71, 1.0, 14)],
    180: [(124, 0.74, 0.7, 10), (188, 0.69, 0.5, 8), (176, 0.64, 1.4, 19)],
    183: [(150, 0.85, 0.4, 6), (184, 0.77, 0.6, 9), (185, 0.68, 0.9, 13)],
    184: [(183, 0.77, 0.6, 9)],
    # A link with no rank: Hanjeok's column is nullable, so the reader must
    # order these after ranked ones rather than crash or sort them first.
    192: [(178, 0.60, 0.8, 12)],
}
UNRANKED = {(192, 178)}

FESTIVALS = [
    ("garam-night", "가람궁 달빛 야행", "2026-10-16", "2026-10-25", 37.5802, 126.9772),
    ("solnae-reed", "은빛 억새 축제", "2026-10-10", "2026-11-01", 37.6181, 127.0352),
    ("market-food", "가람 중앙시장 야시장", "2026-11-06", "2026-11-08", 37.5711, 126.9901),
]
EXHIBITIONS = [
    (
        "old-maps",
        "한빛의 옛 지도",
        "2026-09-01",
        "2026-12-20",
        "가람 역사박물관",
        37.5760,
        126.9740,
        161,
    ),
    (
        "paper-light",
        "종이와 빛",
        "2026-10-01",
        "2026-10-31",
        "가람 시립미술관",
        37.5770,
        126.9800,
        160,
    ),
]


def lines(rows: list[dict]) -> bytes:
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows).encode("utf-8")


def files() -> dict[str, list[dict]]:
    places = [
        {
            "id": pid,
            "name": name,
            "region_code": region[0],
            "region_label": region[1],
            "content_type": "12",
            "category_mid": mid,
            "category_small": small,
            "summary": overview.split(".")[0] + ".",
            "overview": overview,
            "address": f"{region[1]} {name}길 {pid % 90 + 1}",
            "lat": lat,
            "lng": lng,
            "has_congestion_data": covered,
        }
        for pid, name, region, mid, small, lat, lng, covered, overview in PLACES
    ]
    related = [
        {
            "base_id": base,
            "related_id": rid,
            "rank": None if (base, rid) in UNRANKED else index + 1,
            "score": score,
            "distance_km": km,
            "travel_minutes": minutes,
        }
        for base, targets in RELATED.items()
        for index, (rid, score, km, minutes) in enumerate(targets)
    ]
    festivals = [
        {"id": fid, "name": name, "start_date": start, "end_date": end, "lat": lat, "lng": lng}
        for fid, name, start, end, lat, lng in FESTIVALS
    ]
    exhibitions = [
        {
            "id": eid,
            "name": name,
            "start_date": start,
            "end_date": end,
            "place": place,
            "lat": lat,
            "lng": lng,
            "attraction_id": attraction,
        }
        for eid, name, start, end, place, lat, lng, attraction in EXHIBITIONS
    ]
    return {
        "places.jsonl": places,
        "related.jsonl": related,
        "festivals.jsonl": festivals,
        "exhibitions.jsonl": exhibitions,
    }


def write(target: Path) -> None:
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True)
    manifest = {
        "format_version": 1,
        "exported_at": "2026-10-13T02:00:00Z",
        "source": "hanjeok-synthetic",
        "files": {},
    }
    for name, rows in files().items():
        data = lines(rows)
        (target / name).write_bytes(data)
        manifest["files"][name] = {"rows": len(rows), "sha256": hashlib.sha256(data).hexdigest()}
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    good = HERE / "hanjeok-export"
    write(good)
    # The broken copy: one row lost from related.jsonl after the manifest was
    # written, which is what a truncated transfer looks like.
    broken = HERE / "hanjeok-export-broken"
    shutil.rmtree(broken, ignore_errors=True)
    shutil.copytree(good, broken)
    related = (broken / "related.jsonl").read_bytes().splitlines(keepends=True)
    (broken / "related.jsonl").write_bytes(b"".join(related[:-1]))


# ---- Recorded Hanjeok responses for the same invented places ----
#
# In Hanjeok's own shape, including fields the guide drops (image addresses,
# visitor-feedback tallies), so the tests can show that they are dropped.

RECORDED_TODAY = "2026-10-13"
FETCHED_AT = "2026-10-13T14:20:05Z"
NAMES = {row[0]: row[1] for row in PLACES}

# (place, date) -> (grade, concentration, percentile, better dates)
CONGESTION = {
    (101, "2026-10-17"): (
        "VERY_CROWDED",
        88.0,
        92.0,
        [("2026-10-20", "NORMAL", 44.0), ("2026-10-21", "NORMAL", 47.0)],
    ),
    (101, "2026-10-20"): ("NORMAL", 44.0, 54.0, []),
    (118, "2026-10-17"): ("NORMAL", 49.0, 52.0, []),
    (118, "2026-10-18"): ("CROWDED", 75.0, 79.0, [("2026-10-20", "RELAXED", 31.0)]),
    (124, "2026-10-17"): ("RELAXED", 28.0, 30.0, []),
    (131, "2026-10-17"): ("RELAXED", 22.0, 24.0, []),
}
UNCOVERED = [(150, "2026-10-17"), (141, "2026-10-17")]
# (place, date) -> [(alternative, grade, concentration, km, minutes, score)] in Hanjeok's order
ALTERNATIVES = {
    (101, "2026-10-17"): [
        (118, "NORMAL", 49.0, 0.8, 12, 0.76),
        (124, "RELAXED", 28.0, 4.1, 25, 0.77),
        (131, "RELAXED", 22.0, 4.9, 30, 0.76),
    ],
    (124, "2026-10-17"): [
        (131, "RELAXED", 22.0, 0.8, 12, 0.85),
        (118, "NORMAL", 49.0, 3.6, 22, 0.68),
    ],
    (118, "2026-10-17"): [],
}


def envelope(data) -> dict:
    return {
        "status": 200,
        "fetched_at": FETCHED_AT,
        "body": {"success": True, "data": data, "error": None},
    }


def write_live(target: Path) -> None:
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True)
    (target / "recording.json").write_text(
        json.dumps({"today": RECORDED_TODAY, "recorded_at": FETCHED_AT}) + "\n", "utf-8"
    )

    def save(kind: str, place: int, day: str, payload: dict) -> None:
        (target / f"{kind}-{place}-{day}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=1) + "\n", "utf-8"
        )

    for (place, day), (grade, concentration, percentile, better) in CONGESTION.items():
        save(
            "congestion",
            place,
            day,
            envelope(
                {
                    "hasCongestionData": True,
                    "attraction": {
                        "id": place,
                        "name": NAMES[place],
                        "imageUrl": f"https://img.invalid/{place}.jpg",
                    },
                    "diagnosis": {
                        "date": day,
                        "concentration": concentration,
                        "percentile": percentile,
                        "grade": grade,
                        "message": "녹화한 응답",
                    },
                    "dailyForecasts": [],
                    "betterDates": [
                        {"date": d, "concentration": c, "grade": g, "weather": None}
                        for d, g, c in better
                    ],
                    "nearbyFestivals": [],
                    "feltCongestion": {"moreCrowded": 3, "asForecast": 5, "lessCrowded": 1},
                }
            ),
        )
    for place, day in UNCOVERED:
        save(
            "congestion",
            place,
            day,
            envelope(
                {
                    "hasCongestionData": False,
                    "attraction": {"id": place, "name": NAMES[place], "imageUrl": None},
                    "message": "이 장소는 집중률 예측 데이터가 제공되지 않아요",
                    "nearbyDiagnosable": [],
                }
            ),
        )
    for (place, day), items in ALTERNATIVES.items():
        save(
            "alternatives",
            place,
            day,
            envelope(
                [
                    {
                        "attractionId": alt,
                        "name": NAMES[alt],
                        "imageUrl": None,
                        "latitude": 0.0,
                        "longitude": 0.0,
                        "grade": grade,
                        "concentration": concentration,
                        "distanceKm": km,
                        "relationScore": 0.8,
                        "score": score,
                        "summary": "",
                        "recommendReason": "",
                        "recommendReasons": [],
                        "travelMinutes": minutes,
                        "rating": None,
                    }
                    for alt, grade, concentration, km, minutes, score in items
                ]
            ),
        )
    # A place Hanjeok does not have.
    save(
        "congestion",
        99999,
        "2026-10-17",
        {
            "status": 404,
            "fetched_at": FETCHED_AT,
            "body": {
                "success": False,
                "data": None,
                "error": {"code": "ATTRACTION_NOT_FOUND", "message": "관광지를 찾을 수 없습니다"},
            },
        },
    )


if __name__ == "__main__":
    main()
    write_live(HERE / "hanjeok-live")
