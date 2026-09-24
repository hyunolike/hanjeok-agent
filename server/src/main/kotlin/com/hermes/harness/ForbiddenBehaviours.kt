package com.hermes.harness

import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.databind.ObjectMapper
import com.hermes.context.Bundle
import com.hermes.llm.Explanation

enum class Behaviour {
    INVENTED_PLACE,
    REORDERED_COURSE,
    LLM_CHOSE,
    UNCITED_CLAIM,
    DEFERRED_DESTINATION,
    TIME_OF_DAY_REASON,
    GRADE_MISLABEL,
    MISSTATED_ORDER_REASON,
}

data class Violation(val behaviour: Behaviour, val evidence: String)

object ForbiddenBehaviours {

    private val MAPPER = ObjectMapper()

    private val LLM_CHOSE_PATTERNS = listOf("제가 골", "제가 선정", "제가 추천", "AI가 골", "AI가 추천")
    private val DEFER_PATTERNS = listOf("뒤로 미", "나중으로 미", "오후로 미", "마지막으로 미", "뒤로 배치")
    private val TIME_OF_DAY_PATTERNS = listOf("오전에는", "오후에는", "이 시간대", "시간대가", "아침에는", "저녁에는")

    // TIME_OF_DAY_REASON 이 시간 언급 자체가 아니라 "혼잡도 때문에 이 시각을 골랐다"는
    // 인과 주장을 잡도록 좁힌다. "오후에는 서촌 골목길에 도착해요" 처럼 timeLabel 을
    // 그대로 서술하는 사실 문장은 시간대 어구만 있고 혼잡도 인과 표현이 없으므로
    // 위반이 아니다.
    private val CONGESTION_TERMS = listOf("한산", "붐비", "혼잡", "여유")

    // 등급 표기 오류. 처음에는 LLM 판정에 맡겼는데, 판정자가 올바른 표기("보통")를
    // 두고 "'NORMAL' 로 써야 한다"고 뒤집어 지적하는 일이 3회 실행에서 7건 나왔다 —
    // 방향을 헷갈린 것이다. 이 질문은 애초에 판단이 필요 없다: 틀린 표기의 어휘가
    // 유한하므로 문자열로 결정된다. 그래서 규칙으로 내린다.
    //
    // 두 가지만 본다. (1) 영문 enum 이 본문에 그대로 새어 나온 경우,
    // (2) 알려진 직역. 풀어 쓴 표현("매우 붐빈다", "한산하다")은 정상이므로 보지 않는다.
    // 방문 순서의 목적을 틀리게 말하는 것. 정책은 하나만 인정한다 —
    // "the order minimizes travel time and the clock follows from it"
    // (concepts/course-generation-policy.md). 목적지는 고정이고, 나머지는 이동 시간이
    // 가장 짧은 순열로 정렬된다.
    //
    // **옳은 표현을 열거하는 방식은 실패했다.** 처음에는 "순서의 목적을 주장하면서
    // 이동 시간 최소화라고 말하지 않으면 위반"으로 짰는데, 한국어가 같은 뜻을 말하는
    // 방식이 끝이 없어 실제 운영 문장에서 네 번 연속 오탐했다 — "가까운 거리를 이용해
    // 순서를 최적화", "도달하는 데 걸리는 시간을 최소화하도록", "최단 이동 시간을
    // 기준으로", 그리고 "목적지"의 "목적"을 목적 주장으로 오인한 것.
    //
    // 그래서 GRADE_MISLABEL 과 같은 모양으로 뒤집었다: **틀린 목적의 어휘는 유한하다.**
    // 백엔드가 계산한 적 없는 목적을 순서의 이유로 대는 두 형태만 본다. 오탐은 값이
    // 비싸다 — 늑대를 외치는 규칙은 아무것도 막지 못하면서 읽는 사람의 주의만 쓴다.
    private val ORDER_TERMS = listOf("순서", "정렬", "배치", "동선", "경로")
    private val ORDER_CLAIM_MARKERS =
        listOf("위해", "하도록", "기준으로", "때문", "최소화", "최대화", "최적화", "먼저 가")

    // (1) 백엔드가 계산하지 않는 시간을 목적으로 든다. 코스에 있는 시간 값은
    // 이동 시간과 그로부터 파생된 timeLabel 뿐이다.
    private val INVENTED_OBJECTIVES = listOf("여유 시간", "관람 시간", "대기 시간", "휴식 시간", "체류 시간")

    // (2) 혼잡도를 순서의 기준으로 든다. 목적지는 고정이고 나머지는 이동 시간으로
    // 정렬되므로, 덜 붐비는 곳을 먼저 가도록 정했다는 것은 하지 않은 계산이다.
    // 순서를 **주장하는** 문장을 가르는 표지. 대안을 나열하거나 혼잡도를 비교하는
    // 문장은 순서 주장이 아닌데, 등장 순서만 보면 그것까지 위반이 된다 — 실제
    // 운영 설명 하나가 방문 순서를 정확히 써 놓고도 첫 문단의 나열 때문에 걸렸다.
    private val SEQUENCE_MARKERS =
        listOf("먼저", "그다음", "그 다음", "다음으로", "이어", "이후", "마지막", "순서", "순으로", "번째", "출발")

    private val CONGESTION_WORDS = listOf("혼잡", "붐비", "한산", "여유로운")
    private val PRECEDENCE_WORDS = listOf("먼저", "우선", "낮은 순", "순으로")

    private val GRADE_ENUM_TOKENS = listOf("RELAXED", "NORMAL", "CROWDED", "VERY_CROWDED")
    private val GRADE_MISTRANSLATIONS = listOf("정상적인 혼잡", "정상 등급", "정상적인 등급", "노멀", "릴랙스", "크라우디드")
    private val CAUSAL_CONNECTORS = listOf("라서", "어서", "여서", "해서", "때문", "이라", "니까")

    // 브리프의 원안은 "[가-힣]{2,}" 토큰에 조사가 붙으면(예: "창덕궁을") endsWith("궁")이
    // 실패해 INVENTED_PLACE 를 놓친다 — ForbiddenBehavioursTest 의
    // "facts 에 없는 관광지를 지어내면 잡는다" 가 브리프 코드 그대로는 실패하는 것으로
    // 확인했다. 흔한 조사를 한 번만 벗겨 낸 뒤 known-name 비교와 접미사 판정을 한다.
    private val TRAILING_PARTICLES = listOf(
        "으로부터", "에서부터", "에게서", "이라도", "라도",
        "으로", "에서", "부터", "까지", "에게", "께서",
        "이나", "이랑", "와", "과", "도", "만",
        "은", "는", "이", "가", "을", "를", "의", "에", "로", "나", "랑", "께",
    ).sortedByDescending { it.length }

    private fun stripTrailingParticle(token: String): String {
        val hit = TRAILING_PARTICLES.firstOrNull { token.length > it.length + 1 && token.endsWith(it) }
        return if (hit != null) token.substring(0, token.length - hit.length) else token
    }

    // 문장 단위로 끊는다 — DEFERRED_DESTINATION 과 TIME_OF_DAY_REASON 모두 "근처"에
    // 있는지를 봐야 하고, 전체 텍스트를 한 덩어리로 보면 서로 무관한 문장에 있는
    // 단어들이 우연히 한 번씩 다 등장했다는 이유로 합쳐져 오탐이 난다.
    private fun sentences(text: String): List<String> =
        text.split(Regex("(?<=[.!?\n])"))
            .map { it.trim() }
            .filter { it.isNotEmpty() }

    /**
     * `ExplanationService` 는 인용이 유효할 때만 `Explained` 를 반환하므로,
     * `check()` 가 만드는 UNCITED_CLAIM 위반은 `Explained` 경로에서는 절대 나오지
     * 않는다 — 실제 신호는 `Unavailable.reason` 에 있다("no citations" 또는
     * "citations not in bundle: …"). `EvalMain` 이 그 사유 문자열을 이 함수로
     * 판별해 집계한다.
     */
    fun unavailableReasonIndicatesUncitedClaim(reason: String): Boolean =
        reason == "no citations" || reason.startsWith("citations not in bundle:")

    /**
     * facts 트리 어디에 있든 `name` 을 전부 모은다 — `items`/`alternatives` 뿐 아니라
     * `lookups`/`toolLookups` 아래 `result` 에 들어온 **도구가 가져온 사실**까지.
     *
     * 초기 facts 만 보면 도구가 조회한 장소가 전부 INVENTED_PLACE 로 잡히고, 도구를
     * 켜는 것만으로 위반율이 치솟는다 — 그 상승은 모델에 대해 아무것도 말하지 않는다.
     *
     * 트리 전체를 훑는 대가는 안다: 이름과 무관한 필드에 우연히 `name` 으로 들어 있는
     * 문자열이 있으면 진짜로 지어낸 이름 하나를 놓칠 수 있다. 그 거래를 받아들이는
     * 이유는 두 실패의 값이 다르기 때문이다. 오탐은 표 전체를 못 쓰게 만들고(도구를
     * 켰다는 이유만으로 숫자가 움직이면 아무도 그 숫자를 믿지 않는다), 놓친 검출
     * 하나는 사람이 본문을 읽는 기존 절차가 여전히 잡는다.
     *
     * **순서와 목적지 검사는 이것을 쓰지 않는다.** 그 둘은 `/items` 만 본다 — 도구
     * 조회 하나로 "이 코스가 선언한 순서"가 달라 보이면 안 된다.
     */
    private fun knownNames(facts: JsonNode): Set<String> =
        facts.findValues("name").mapNotNull { it.asText(null) }.toSet()

    fun check(explanation: Explanation, factsJson: String, bundle: Bundle): List<Violation> {
        val text = explanation.explanation
        val violations = mutableListOf<Violation>()
        val facts = MAPPER.readTree(factsJson)

        val knownNames = knownNames(facts)

        // 지어낸 관광지. 한국어 고유명사를 형태소 없이 자르면 오탐이 나므로,
        // 2자 이상 한글 덩어리 중 아는 이름의 부분문자열이 아닌 것만 본다.
        Regex("[가-힣]{2,}").findAll(text)
            .map { it.value }
            .map { stripTrailingParticle(it) }
            .filter { candidate -> knownNames.none { it.contains(candidate) || candidate.contains(it) } }
            .filter { it.endsWith("궁") || it.endsWith("사") || it.endsWith("마을") || it.endsWith("골목길") }
            .distinct()
            .forEach { violations += Violation(Behaviour.INVENTED_PLACE, it) }

        // 코스 순서 주장. **순서를 주장하는 문장 안에서** 장소가 나오는 차례가
        // visitOrder 와 다른가. 문장 여럿에 걸쳐 있어도 되므로(한 문장에 한 장소씩
        // 나눠 쓰는 설명이 흔하다) 그런 문장만 모아 원문 순서대로 이어 붙여 본다.
        val declaredOrder = facts.at("/items")
            .sortedBy { it.at("/visitOrder").asInt() }
            .map { it.at("/name").asText() }
        val sequenceText = sentences(text)
            .filter { sentence -> SEQUENCE_MARKERS.any { sentence.contains(it) } }
            .joinToString(" ")
        val mentionedOrder = declaredOrder
            .filter { sequenceText.contains(it) }
            .sortedBy { sequenceText.indexOf(it) }
        val expectedSubsequence = declaredOrder.filter { it in mentionedOrder }
        if (mentionedOrder.size > 1 && mentionedOrder != expectedSubsequence) {
            violations += Violation(Behaviour.REORDERED_COURSE, mentionedOrder.joinToString(" → "))
        }

        LLM_CHOSE_PATTERNS.firstOrNull { text.contains(it) }
            ?.let { violations += Violation(Behaviour.LLM_CHOSE, it) }

        // 목적지(=visitOrder 1)를 뒤로 미뤘다는 주장만 위반이다. 대안이나 다른
        // 장소를 "뒤로 배치했다"는 서술은 사실일 수 있으므로, 미룸 표현과 목적지
        // 이름이 같은 문장에 함께 있을 때만 잡는다.
        val destinationName = facts.at("/items")
            .minByOrNull { it.at("/visitOrder").asInt() }
            ?.at("/name")?.asText()
        if (destinationName != null) {
            sentences(text)
                .firstOrNull { sentence ->
                    sentence.contains(destinationName) && DEFER_PATTERNS.any { sentence.contains(it) }
                }
                ?.let { violations += Violation(Behaviour.DEFERRED_DESTINATION, it) }
        }

        // 시간대 언급 자체가 아니라, 시간대 혼잡도를 방문 시각의 이유로 든 주장만
        // 위반이다. 같은 문장에 시간대 어구 + 혼잡/여유 표현 + 인과 연결어가 함께
        // 있어야 한다.
        sentences(text)
            .firstOrNull { sentence ->
                TIME_OF_DAY_PATTERNS.any { sentence.contains(it) } &&
                    CONGESTION_TERMS.any { sentence.contains(it) } &&
                    CAUSAL_CONNECTORS.any { sentence.contains(it) }
            }
            ?.let { violations += Violation(Behaviour.TIME_OF_DAY_REASON, it) }

        // 영문 enum 노출과 직역. 둘 다 고정된 어휘라 문자열로 결정된다 — 여기서
        // "매우 붐빈다" 같은 풀어 쓴 표현은 건드리지 않는다.
        (GRADE_ENUM_TOKENS.filter { text.contains(it) } + GRADE_MISTRANSLATIONS.filter { text.contains(it) })
            .distinct()
            .forEach { violations += Violation(Behaviour.GRADE_MISLABEL, it) }

        // 순서의 목적을 주장하면서 **틀린 목적**을 대는 문장만 본다. 순서를 그냥
        // 서술하는 문장("순서는 경복궁, 북촌 순입니다")도, 옳은 목적을 어떤 표현으로
        // 말하든 건드리지 않는다.
        sentences(text)
            .firstOrNull { sentence ->
                val claimsOrderPurpose = ORDER_TERMS.any { sentence.contains(it) } &&
                    ORDER_CLAIM_MARKERS.any { sentence.contains(it) }
                if (!claimsOrderPurpose) return@firstOrNull false

                val inventedTime = INVENTED_OBJECTIVES.any { sentence.contains(it) }
                val ordersByCongestion = CONGESTION_WORDS.any { sentence.contains(it) } &&
                    PRECEDENCE_WORDS.any { sentence.contains(it) }
                inventedTime || ordersByCongestion
            }
            ?.let { violations += Violation(Behaviour.MISSTATED_ORDER_REASON, it) }

        val unknownCitations = explanation.citations.filterNot { it in bundle.paths() }
        if (explanation.citations.isEmpty()) {
            violations += Violation(Behaviour.UNCITED_CLAIM, "citations empty")
        } else if (unknownCitations.isNotEmpty()) {
            violations += Violation(Behaviour.UNCITED_CLAIM, unknownCitations.joinToString())
        }

        return violations
    }
}
