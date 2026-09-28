#!/usr/bin/env python3
"""README 의 설명 요청 흐름도를 손그림(스케치) 스타일 SVG 로 그린다.

    python3 docs/images/generate_flow.py   # docs/images/flow.svg, flow.en.svg 를 다시 만든다

로고와 같은 방식이다 — 선을 변위 필터로 흔들고, 같은 선을 두 번 그어 덧그린
느낌을 내고, 종이색 배경을 깔아 깃허브 라이트·다크 어느 쪽에서도 읽히게 한다.

노드 좌표는 아래 LAYOUT 하나에서 나온다. 한국어판과 영어판은 문구만 다르고
배치는 공유한다 — 배치가 갈라지면 한쪽을 고칠 때 다른 쪽이 조용히 어긋난다.
"""
import os

OUT = os.path.dirname(os.path.abspath(__file__))

INK = "#2F2A26"
SUB = "#6B625A"
PAPER = "#FDFAF1"
HAND_FONT = ("'Comic Sans MS','Segoe Print','Bradley Hand','Chalkboard SE',"
             "'Comic Neue','Trebuchet MS',sans-serif")

# 종류별 색 — 자료 / 처리 / 분기 / 실패 / 종점
STYLES = {
    "data": ("#F4EEE0", "#9A8F7E"),
    "step": ("#FEFCF6", "#8A8078"),
    "fork": ("#FBEEDC", "#D97757"),
    "fail": ("#F9E1D9", "#C1553C"),
    "good": ("#E6F0E4", "#3F8B58"),
    "note": ("#FFFFFF", "#C3BAAC"),
}

W, H = 1030, 2050


def defs():
    specs = {
        "line": ("0.022 0.03", 1.9, 11),
        "line2": ("0.026 0.022", 2.3, 37),
        "text": ("0.018 0.024", 1.2, 61),
    }
    out = ["<defs>"]
    for name, (freq, scale, seed) in specs.items():
        out.append(
            f'<filter id="w-{name}" x="-25%" y="-25%" width="150%" height="150%" '
            f'color-interpolation-filters="sRGB">'
            f'<feTurbulence type="fractalNoise" baseFrequency="{freq}" numOctaves="2" '
            f'seed="{seed}" result="n"/>'
            f'<feDisplacementMap in="SourceGraphic" in2="n" scale="{scale}" '
            f'xChannelSelector="R" yChannelSelector="G"/>'
            f"</filter>"
        )
    out.append("</defs>")
    return "".join(out)


def sketch(markup):
    """같은 선을 두 번 — 두 번째는 옅게 살짝 어긋나게."""
    return (f'<g filter="url(#w-line)">{markup}</g>'
            f'<g filter="url(#w-line2)" opacity="0.38" transform="translate(0.8,-0.6)">{markup}</g>')


def text(x, y, s, size=17, color=INK, anchor="middle", weight="normal"):
    return (f'<g filter="url(#w-text)"><text x="{x}" y="{y}" text-anchor="{anchor}" '
            f'font-family={HAND_FONT!r} font-size="{size}" font-weight="{weight}" '
            f'fill="{color}">{s}</text></g>')


def rrect(x, y, w, h, r=14):
    return (f"M{x + r} {y} L{x + w - r} {y} Q{x + w} {y} {x + w} {y + r} "
            f"L{x + w} {y + h - r} Q{x + w} {y + h} {x + w - r} {y + h} "
            f"L{x + r} {y + h} Q{x} {y + h} {x} {y + h - r} "
            f"L{x} {y + r} Q{x} {y} {x + r} {y} Z")


def hexa(x, y, w, h, c=26):
    return (f"M{x + c} {y} L{x + w - c} {y} L{x + w} {y + h / 2} "
            f"L{x + w - c} {y + h} L{x + c} {y + h} L{x} {y + h / 2} Z")


class Node:
    def __init__(self, x, y, w, h, kind="step", shape="rect"):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.kind, self.shape = kind, shape

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2

    def render(self, lines):
        bg, border = STYLES[self.kind]
        path = hexa(self.x, self.y, self.w, self.h) if self.shape == "hex" \
            else rrect(self.x, self.y, self.w, self.h)
        dashed = ' stroke-dasharray="7 5"' if self.kind == "note" else ""
        out = [f'<path d="{path}" fill="{bg}"/>',
               sketch(f'<path d="{path}" fill="none" stroke="{border}" '
                      f'stroke-width="2.6" stroke-linejoin="round"{dashed}/>')]
        sizes = [17] + [13.5] * (len(lines) - 1)
        if self.kind == "note":
            sizes = [13.5] * len(lines)
        gaps = [0] + [19] * (len(lines) - 1)
        total = sum(sizes[0:1]) + sum(gaps)
        y = self.cy - total / 2 + sizes[0] * 0.72
        for i, line in enumerate(lines):
            y += gaps[i]
            out.append(text(self.cx, y, line, size=sizes[i],
                            color=INK if i == 0 and self.kind != "note" else SUB))
        return "".join(out)


def arrow(pts, color="#6F665E", w=2.6, head=12, label=None, label_at=None, label_dx=0,
          dash=None):
    """꺾인 화살표. pts 는 [(x, y), ...] — 마지막 두 점이 화살촉 방향을 정한다."""
    d = f"M{pts[0][0]} {pts[0][1]}" + "".join(f" L{x} {y}" for x, y in pts[1:])
    (x0, y0), (x1, y1) = pts[-2], pts[-1]
    import math
    ang = math.atan2(y1 - y0, x1 - x0)
    wings = "".join(
        f"M{x1} {y1} L{x1 - head * math.cos(ang - s):.1f} {y1 - head * math.sin(ang - s):.1f}"
        for s in (0.42, -0.42)
    )
    dashes = f' stroke-dasharray="{dash}"' if dash else ""
    out = sketch(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{w}" '
                 f'stroke-linecap="round" stroke-linejoin="round"{dashes}/>'
                 f'<path d="{wings}" fill="none" stroke="{color}" stroke-width="{w}" '
                 f'stroke-linecap="round"/>')
    if label:
        lx, ly = label_at if label_at else ((pts[0][0] + pts[-1][0]) / 2 + label_dx,
                                           (pts[0][1] + pts[-1][1]) / 2)
        half = 4.6 * len(label) + 8
        out += (f'<rect x="{lx - half}" y="{ly - 14}" width="{half * 2}" height="20" rx="6" '
                f'fill="{PAPER}" opacity="0.92"/>'
                + text(lx, ly, label, size=13, color="#8A5A3C"))
    return out


# ── 배치 ───────────────────────────────────────────────────────────────────
LAYOUT = {
    "backend":  Node(52, 74, 372, 76, "data"),
    "bundle":   Node(596, 74, 372, 76, "data"),
    "norm":     Node(52, 196, 372, 76),
    "loader":   Node(596, 196, 372, 76),
    "facts":    Node(52, 318, 372, 62, "data"),
    "assembler": Node(596, 318, 372, 76),
    "service":  Node(300, 434, 420, 62),
    "provider": Node(286, 542, 448, 84, "fork", "hex"),
    "anthropic": Node(28, 548, 240, 72, "note"),
    "openrouter": Node(752, 548, 250, 72, "note"),
    "result":   Node(346, 672, 336, 62),
    "validator": Node(286, 786, 448, 84, "fork", "hex"),
    "unavail":  Node(756, 912, 250, 84, "fail"),
    "explained": Node(326, 920, 378, 62, "good"),
    "forbidden": Node(300, 1026, 430, 76),
    "tally":    Node(300, 1148, 430, 76, "good"),

    # ── 이어 묻기 스트리밍(도구 루프) — 위와 갈라지는 두 번째 진입점 ──────────────
    "ask_entry":   Node(300, 1320, 430, 62),
    "tool_loop":   Node(286, 1420, 448, 84, "fork", "hex"),
    "tool_exec":   Node(52, 1546, 372, 90),
    "looking_note": Node(752, 1428, 200, 76, "note"),
    "ask_gate":    Node(300, 1668, 430, 84, "fork", "hex"),
    "repair":      Node(52, 1788, 372, 76),
    "sse_ok":      Node(52, 1906, 300, 84, "good"),
    "sse_unavail": Node(386, 1906, 300, 84, "fail"),
    "sse_abort":   Node(720, 1906, 258, 84, "fail"),
}

KO = {
    "backend": ["백엔드 응답 4종 중 3종", "course · congestion · alternatives"],
    "bundle": ["hanjeok-bundle.txt", "문서 9개"],
    "norm": ["FactsNormalizer", "평평한 facts 객체 하나로 정규화"],
    "loader": ["BundleLoader", "FILE 마커 파싱 · 마커 위조 검사"],
    "facts": ["BackendFacts(courseUuid, json)"],
    "assembler": ["PromptAssembler", "systemText = 번들 원문 그대로"],
    "service": ["ExplanationService.explain()"],
    "provider": ["ExplanationProvider", "어느 프로바이더로 물을 것인가"],
    "anthropic": ["anthropic", "1h 캐시 + 구조화 출력"],
    "openrouter": ["openai · openrouter", "response_format 으로 스키마 강제"],
    "result": ["ProviderResult"],
    "validator": ["CitationValidator", "번들에 실재하는 경로인가?"],
    "unavail": ["Unavailable(거절 사유)", "설명 없음 = 안전한 실패"],
    "explained": ["Explained(설명 + 인용)"],
    "forbidden": ["ForbiddenBehaviours.check()", "금지 행동 8종 판정"],
    "tally": ["ViolationTally", "실행당 위반 / 원시 발생 횟수 집계"],
    "title": "설명 요청 흐름 — 순위는 백엔드, 설명은 LLM",
    "edges": {"answered": "Answered", "refused": "Refused · Failed",
              "valid": "Valid", "invalid": "Invalid"},
    "alt": ("설명 요청 흐름도: 백엔드 응답 3종이 FactsNormalizer 를 지나 BackendFacts 로, "
            "hanjeok-bundle.txt 는 BundleLoader 와 PromptAssembler 를 지나 systemText 로 "
            "들어가 ExplanationService.explain() 에서 만난다. ExplanationProvider"
            "(anthropic 또는 openai·openrouter 경로)가 낸 ProviderResult 는 Refused·Failed 면 "
            "Unavailable, Answered 면 CitationValidator 로 간다. 인용이 유효하면 "
            "Explained 가 되어 ForbiddenBehaviours.check() 를 거치고, 두 갈래 모두 "
            "ViolationTally 로 모인다. 아래 두 번째 흐름은 POST /agent/ask/stream 전용 "
            "진입점이다: CourseQuestionService.askStream() 이 AgentLoop 를 돌려, 도구가 "
            "필요하면 congestion·alternatives 를 최대 2라운드(모델 호출 최대 3회, 마감 "
            "60초 공유) 실행하고 예산이 떨어지면 도구 없이 마지막 한 번을 더 부른다. "
            "AskStreamGate 가 인용을 먼저 검증해 통과해야 본문을 내보내고, 인용이 "
            "무효면 도구 없이 한 번만 수리를 시도한다. unavailable 로 끝나는 스트림은 "
            "그 앞에 delta 가 0개다 — 이 불변식은 도구 루프가 생긴 뒤에도 그대로다."),
    "subtitle": "이어 묻기 스트리밍 — 도구 루프 (POST /agent/ask/stream)",
    "ask_entry": ["CourseQuestionService.askStream()", "같은 systemText · 이어 묻기 전용"],
    "tool_loop": ["AgentLoop", "도구 ≤2라운드 · 호출 ≤3회",
                  "마감 60초 · 소진 시 도구 없이 1회 더"],
    "tool_exec": ["congestion · alternatives 실행",
                  "인자 검증: attractionId·date·radiusKm",
                  "거부 사유는 결과로 되먹인다"],
    "looking_note": ["looking 프레임", "도구 이름만 싣는다", "인자는 싣지 않는다"],
    "ask_gate": ["AskStreamGate", "인용 먼저 검증 → 통과해야 본문 방출"],
    "repair": ["수리 1회 (도구 없이)", "실재하는 경로만 인용하라고 재요청"],
    "sse_ok": ["citations → delta* → done", "인용 통과, 본문 방출 시작"],
    "sse_unavail": ["unavailable", "delta 0개 (불변식 유지)"],
    "sse_abort": ["aborted", "본문 미완 — 버려진다"],
    "ask_edges": {"tool_needed": "도구 요청", "tool_loopback": "결과 추가 · 라운드+1",
                  "no_tool": "도구 없이 답", "valid": "유효",
                  "invalid_first": "인용 무효(첫 시도)", "failed": "거절/실패/빈 응답",
                  "broke": "전송 중 끊김", "repaired": "고쳐서 통과",
                  "still_bad": "그래도 무효/실패"},
}

EN = {
    "backend": ["3 of 4 backend responses", "course · congestion · alternatives"],
    "bundle": ["hanjeok-bundle.txt", "9 documents"],
    "norm": ["FactsNormalizer", "flattened into one facts object"],
    "loader": ["BundleLoader", "parse FILE markers · reject forged ones"],
    "facts": ["BackendFacts(courseUuid, json)"],
    "assembler": ["PromptAssembler", "systemText = the bundle, verbatim"],
    "service": ["ExplanationService.explain()"],
    "provider": ["ExplanationProvider", "which provider gets asked"],
    "anthropic": ["anthropic", "1h cache + structured output"],
    "openrouter": ["openai · openrouter", "schema forced via response_format"],
    "result": ["ProviderResult"],
    "validator": ["CitationValidator", "does the path exist in the bundle?"],
    "unavail": ["Unavailable(reason)", "no explanation = the safe failure"],
    "explained": ["Explained(text + citations)"],
    "forbidden": ["ForbiddenBehaviours.check()", "judge the eight behaviours"],
    "tally": ["ViolationTally", "runs-with-violation / raw occurrences"],
    "title": "Explanation request flow — backend ranks, the LLM explains",
    "edges": {"answered": "Answered", "refused": "Refused · Failed",
              "valid": "Valid", "invalid": "Invalid"},
    "alt": ("Explanation request flow: three backend responses pass through "
            "FactsNormalizer into BackendFacts, while hanjeok-bundle.txt passes through "
            "BundleLoader and PromptAssembler into systemText; both meet in "
            "ExplanationService.explain(). The ProviderResult from ExplanationProvider "
            "(anthropic or the openai-compatible path) becomes Unavailable when Refused or Failed, and "
            "goes to CitationValidator when Answered. Valid citations make it Explained, "
            "which ForbiddenBehaviours.check() judges; both branches end in ViolationTally. "
            "The second flow below is a separate entry point, for POST /agent/ask/stream only: "
            "CourseQuestionService.askStream() runs AgentLoop, which executes congestion and "
            "alternatives for up to 2 tool rounds (at most 3 model calls, a 60s deadline shared "
            "across them) when the model needs them, and asks once more with no tools when the "
            "budget runs out. AskStreamGate validates citations before releasing any body text, "
            "and repairs invalid citations once, with no tools. A stream that ends unavailable "
            "still has zero delta events before it — that invariant holds with the tool loop too."),
    "subtitle": "Follow-up streaming — the tool loop (POST /agent/ask/stream)",
    "ask_entry": ["CourseQuestionService.askStream()", "same systemText · follow-ups only"],
    "tool_loop": ["AgentLoop", "tool rounds ≤2 · model calls ≤3",
                  "60s deadline · budget out → no tools, once"],
    "tool_exec": ["execute congestion · alternatives",
                  "checks attractionId · date · radiusKm",
                  "a rejection feeds back as the result"],
    "looking_note": ["the looking frame", "carries the tool name only", "never the arguments"],
    "ask_gate": ["AskStreamGate", "validates citations first, then releases body"],
    "repair": ["one repair (no tools)", "asks again for real bundle paths"],
    "sse_ok": ["citations → delta* → done", "citations passed, body flows"],
    "sse_unavail": ["unavailable", "zero delta before it, still"],
    "sse_abort": ["aborted", "sentence unfinished — dropped"],
    "ask_edges": {"tool_needed": "tool requested", "tool_loopback": "result added, round+1",
                  "no_tool": "answers with no tools", "valid": "Valid",
                  "invalid_first": "invalid citations (1st try)", "failed": "refused/failed/empty",
                  "broke": "broke mid-stream", "repaired": "repaired, now valid",
                  "still_bad": "still invalid/failed"},
}


def render(words):
    n = LAYOUT
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
        f'height="{H}" role="img" aria-label="{words["alt"]}">',
        defs(),
        f'<rect width="{W}" height="{H}" rx="20" fill="{PAPER}"/>',
        sketch(f'<rect x="8" y="8" width="{W - 16}" height="{H - 16}" rx="18" fill="none" '
               f'stroke="#C9BFAE" stroke-width="2.5"/>'),
        text(W / 2, 46, words["title"], size=23),
        sketch(f'<path d="M{W / 2 - 250} 60 Q{W / 2} 70 {W / 2 + 250} 58" fill="none" '
               f'stroke="#D97757" stroke-width="3" stroke-linecap="round"/>'),
    ]

    # 두 갈래 입력 — 사실(facts)과 근거(bundle)
    for a, b in (("backend", "norm"), ("norm", "facts"), ("bundle", "loader"),
                 ("loader", "assembler")):
        parts.append(arrow([(n[a].cx, n[a].y + n[a].h), (n[b].cx, n[b].y - 6)]))

    # 둘이 만나는 곳
    parts.append(arrow([(n["facts"].cx, n["facts"].y + n["facts"].h),
                        (n["facts"].cx, 412), (n["service"].x + 90, 412),
                        (n["service"].x + 90, n["service"].y - 6)]))
    parts.append(arrow([(n["assembler"].cx, n["assembler"].y + n["assembler"].h),
                        (n["assembler"].cx, 412), (n["service"].x + n["service"].w - 90, 412),
                        (n["service"].x + n["service"].w - 90, n["service"].y - 6)]))

    parts.append(arrow([(n["service"].cx, n["service"].y + n["service"].h),
                        (n["provider"].cx, n["provider"].y - 6)]))

    # 프로바이더 두 갈래는 어댑터 안의 차이일 뿐이라 점선 메모로 붙인다
    for side in ("anthropic", "openrouter"):
        note = n[side]
        near = (note.x + note.w + 4, note.cy) if side == "anthropic" else (note.x - 4, note.cy)
        far = (n["provider"].x - 2, note.cy) if side == "anthropic" \
            else (n["provider"].x + n["provider"].w + 2, note.cy)
        parts.append(sketch(f'<path d="M{near[0]} {near[1]} L{far[0]} {far[1]}" fill="none" '
                            f'stroke="#C3BAAC" stroke-width="2.2" stroke-dasharray="6 5"/>'))

    parts.append(arrow([(n["provider"].cx, n["provider"].y + n["provider"].h),
                        (n["result"].cx, n["result"].y - 6)]))

    # 실패 갈래 — 거절과 통신 실패는 같은 곳으로 간다
    parts.append(arrow(
        [(n["result"].x + n["result"].w, n["result"].cy), (970, n["result"].cy),
         (970, n["unavail"].y - 6)],
        label=words["edges"]["refused"], label_at=(806, n["result"].cy - 10)))

    parts.append(arrow(
        [(n["result"].cx, n["result"].y + n["result"].h),
         (n["validator"].cx, n["validator"].y - 6)],
        label=words["edges"]["answered"], label_at=(n["result"].cx, 762)))

    # 인용이 하나라도 어긋나면 설명 전체가 되돌려진다
    parts.append(arrow(
        [(n["validator"].x + n["validator"].w, n["validator"].cy),
         (858, n["validator"].cy), (858, n["unavail"].y - 6)],
        label=words["edges"]["invalid"], label_at=(788, n["validator"].cy - 10)))

    parts.append(arrow(
        [(n["validator"].cx, n["validator"].y + n["validator"].h),
         (n["explained"].cx, n["explained"].y - 6)],
        label=words["edges"]["valid"], label_at=(n["validator"].cx, 899)))

    parts.append(arrow([(n["explained"].cx, n["explained"].y + n["explained"].h),
                        (n["forbidden"].cx, n["forbidden"].y - 6)]))
    parts.append(arrow([(n["forbidden"].cx - 60, n["forbidden"].y + n["forbidden"].h),
                        (n["forbidden"].cx - 60, n["tally"].y - 6)]))

    # 설명이 안 나간 실행도 센다 — 세지 않으면 전멸한 실행이 무결점으로 읽힌다
    parts.append(arrow([(n["unavail"].cx, n["unavail"].y + n["unavail"].h),
                        (n["unavail"].cx, 1122), (n["tally"].cx + 125, 1122),
                        (n["tally"].cx + 125, n["tally"].y - 6)]))

    # ── 두 번째 진입점: 이어 묻기 스트리밍의 도구 루프 ──────────────────────
    # 위 흐름과 코드로 이어지지 않는다(다른 컨트롤러 · 다른 서비스) — 구분선과
    # 소제목으로 갈라 그린다. 공유하는 것은 같은 systemText 와 같은 인용 검증뿐이다.
    ae, tl, tx, ln, ag, rp = (n["ask_entry"], n["tool_loop"], n["tool_exec"],
                              n["looking_note"], n["ask_gate"], n["repair"])
    ok, ua, ab = n["sse_ok"], n["sse_unavail"], n["sse_abort"]
    ax = words["ask_edges"]

    parts.append(sketch(f'<path d="M60 {ae.y - 44} Q{W / 2} {ae.y - 36} 970 {ae.y - 46}" '
                        f'fill="none" stroke="#C9BFAE" stroke-width="2.2" stroke-dasharray="2 7" '
                        f'stroke-linecap="round"/>'))
    parts.append(text(W / 2, ae.y - 18, words["subtitle"], size=20, color="#8A5A3C"))

    parts.append(arrow([(ae.cx, ae.y + ae.h), (tl.cx, tl.y - 6)]))

    # 도구 필요 → 실행 → 대화에 결과를 더하고 한 바퀴 더(최대 2라운드). 루프백은
    # 오른쪽 여백을 돌아 tool_loop 의 아래쪽으로 들어온다 — looking_note 를
    # 가로지르지 않기 위해서다.
    parts.append(arrow([(tl.x + 90, tl.y + tl.h), (tx.cx, tx.y - 6)], label=ax["tool_needed"]))
    parts.append(arrow(
        [(tx.x + tx.w, tx.cy), (940, tx.cy), (940, tl.y + tl.h + 14),
         (tl.x + tl.w - 40, tl.y + tl.h + 14), (tl.x + tl.w - 40, tl.y + tl.h)],
        label=ax["tool_loopback"], label_at=(940, (tx.cy + tl.y + tl.h) / 2)))

    # looking 프레임은 도구 실행 자체가 아니라 tool_loop 가 여는 도구 라운드에
    # 딸린 메모다 — provider 옆의 anthropic·openrouter 메모와 같은 손법.
    parts.append(sketch(f'<path d="M{ln.x - 4} {ln.cy} L{tl.x + tl.w + 2} {ln.cy}" fill="none" '
                        f'stroke="#C3BAAC" stroke-width="2.2" stroke-dasharray="6 5"/>'))

    parts.append(arrow([(tl.cx, tl.y + tl.h), (ag.cx, ag.y - 6)], label=ax["no_tool"]))

    parts.append(arrow([(ag.x + 70, ag.y + ag.h), (ok.cx, ok.y - 6)], label=ax["valid"]))
    parts.append(arrow([(ag.x + 140, ag.y + ag.h), (rp.cx, rp.y - 6)], label=ax["invalid_first"]))
    parts.append(arrow(
        [(ag.x + ag.w, ag.cy), (940, ag.cy), (940, 1880), (ua.cx, 1880), (ua.cx, ua.y - 6)],
        label=ax["failed"], label_at=(940, ag.cy - 16)))
    parts.append(arrow([(ag.x + ag.w - 40, ag.y + ag.h), (ab.cx, ab.y - 6)], label=ax["broke"]))

    parts.append(arrow([(rp.x + 60, rp.y + rp.h), (ok.cx, ok.y - 6)], label=ax["repaired"]))
    parts.append(arrow([(rp.x + rp.w - 60, rp.y + rp.h), (ua.cx, ua.y - 6)], label=ax["still_bad"]))

    for key, node in n.items():
        parts.append(node.render(words[key]))

    parts.append("</svg>")
    return "".join(parts)


if __name__ == "__main__":
    for name, words in (("flow.svg", KO), ("flow.en.svg", EN)):
        with open(os.path.join(OUT, name), "w") as fp:
            fp.write(render(words))
        print("wrote", name)
