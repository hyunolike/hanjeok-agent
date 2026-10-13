package com.hermes.harness

import com.hermes.context.BundleLoader
import com.hermes.llm.Explanation
import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test
import org.junit.jupiter.params.ParameterizedTest
import org.junit.jupiter.params.provider.ValueSource

class ForbiddenBehavioursTest {

    private val bundle = BundleLoader.load()

    private val factsJson = """
        {"items":[
          {"attractionId":1001,"name":"경복궁","visitOrder":1,"timeLabel":"오전 10:00","grade":"VERY_CROWDED"},
          {"attractionId":1003,"name":"북촌 한옥마을","visitOrder":2,"timeLabel":"오전 11:38","grade":"NORMAL"},
          {"attractionId":1002,"name":"서촌 골목길","visitOrder":3,"timeLabel":"오후 1:14","grade":"RELAXED"}],
         "alternatives":[{"attractionId":1003,"name":"북촌 한옥마을"},{"attractionId":1002,"name":"서촌 골목길"}]}
    """.trimIndent()

    private fun explanation(text: String, vararg citations: String) =
        Explanation(text, citations.toList().ifEmpty { listOf("concepts/congestion-diagnosis.md") })

    @Test
    fun `사실에 근거한 설명은 위반이 없다`() {
        val violations = ForbiddenBehaviours.check(
            explanation("경복궁은 이 날 매우 붐비지만 첫 방문지로 두었어요. 북촌 한옥마을은 한산합니다."),
            factsJson, bundle,
        )

        assertThat(violations).isEmpty()
    }

    @Test
    fun `순서를 뒤바꿔 서술하면 잡는다`() {
        val violations = ForbiddenBehaviours.check(
            explanation("서촌 골목길을 먼저 들르고, 그다음 경복궁으로 갑니다."),
            factsJson, bundle,
        )

        assertThat(violations.map { it.behaviour }).contains(Behaviour.REORDERED_COURSE)
    }

    @Test
    fun `순서 주장이 아닌 언급 순서는 잡지 않는다`() {
        // 실측 오탐. 대안을 나열하거나 혼잡도를 비교하는 문장은 순서 주장이 아닌데,
        // 등장 순서만 보면 위반이 된다. 실제 운영에서 나온 아래 설명은 두 번째 문단에서
        // 방문 순서를 정확히 말한다 — 그런데도 첫 문단의 나열 때문에 걸렸다.
        val violations = ForbiddenBehaviours.check(
            explanation(
                "덕수궁을 첫 방문지로 고정하고, 서촌 골목길과 북촌 한옥마을을 덜 혼잡한 대체지로 추천했어요. " +
                    "북촌 한옥마을은 혼잡도가 84% 낮고, 서촌 골목길도 33% 낮아요. " +
                    "북촌 한옥마을까지는 4분, 이후 서촌 골목길까지는 추가로 12분이 소요돼요.",
            ),
            factsJson, bundle,
        )

        assertThat(violations.map { it.behaviour })
            .describedAs("순서를 맞게 쓴 설명을 위반으로 세면 안 된다")
            .doesNotContain(Behaviour.REORDERED_COURSE)
    }

    @Test
    fun `여러 문장에 걸친 순서 주장도 본다`() {
        // 한 문장에 한 장소씩 나눠 써도 순서 주장은 순서 주장이다.
        val violations = ForbiddenBehaviours.check(
            explanation("첫 번째로 서촌 골목길에 갑니다. 그다음 경복궁으로 이동합니다."),
            factsJson, bundle,
        )

        assertThat(violations.map { it.behaviour }).contains(Behaviour.REORDERED_COURSE)
    }

    @ParameterizedTest
    @ValueSource(strings = [
        "서촌 골목길은 92번째 백분위, 경복궁은 95번째 백분위에 해당합니다.",
        "서촌 골목길은 92 번째 백분위수, 경복궁은 95 번째 백분위수입니다.",
        "서촌 골목길의 92번째 측정값은 33이고 경복궁의 측정값은 87입니다.",
        "서촌 골목길은 92번째로 높은 수치이고 경복궁은 더 높습니다.",
    ])
    fun `수치의 서수는 방문 순서 주장이 아니다`(text: String) {
        assertThat(ForbiddenBehaviours.check(explanation(text), factsJson, bundle))
            .isEmpty()
    }

    @Test
    fun `백분위 언급 뒤 올바른 방문 순서는 오탐하지 않는다`() {
        val text = "서촌 골목길은 92번째 백분위, 경복궁은 95번째 백분위입니다. " +
            "첫 번째로 경복궁에 갑니다. 두 번째로 북촌 한옥마을에 갑니다. " +
            "세 번째로 서촌 골목길에 갑니다."

        assertThat(ForbiddenBehaviours.check(explanation(text), factsJson, bundle)).isEmpty()
    }

    @ParameterizedTest
    @ValueSource(strings = [
        "첫 번째로 서촌 골목길에 갑니다. 두 번째로 경복궁에 갑니다.",
        "1번째는 서촌 골목길, 2번째는 경복궁입니다.",
        "서촌 골목길은 첫 번째 방문지이고 경복궁은 두 번째 방문지입니다.",
        "서촌 골목길에 두 번째로 방문하고 경복궁에 세 번째로 방문합니다.",
        "서촌 골목길은 첫 번째예요. 경복궁은 두 번째예요.",
        "서촌 골목길을 첫 번째로, 경복궁을 두 번째로 갑니다.",
        "서촌 골목길을 첫 번째로 갑니다. 경복궁을 두 번째로 갑니다.",
        "서촌 골목길을 첫 번째로 가요. 경복궁을 두 번째로 가요.",
        "서촌 골목길을 첫 번째로 간다. 경복궁을 두 번째로 간다.",
        "서촌 골목길은 92번째 백분위지만 먼저 들르고, 그다음 경복궁으로 갑니다.",
        "서촌 골목길은 92번째 백분위이며 첫 번째로 방문하고 경복궁은 두 번째로 방문합니다.",
    ])
    fun `방문 서수와 백분위가 섞여도 실제 순서 위반은 잡는다`(text: String) {
        assertThat(ForbiddenBehaviours.check(explanation(text), factsJson, bundle).map { it.behaviour })
            .contains(Behaviour.REORDERED_COURSE)
    }

    @Test
    fun `방문 순서의 목적을 틀리게 말하면 잡는다`() {
        // 실제 실행에서 나온 문장이다. 순서를 정하는 목적은 총 이동 시간 최소화이고
        // (course-generation-policy: "the order minimizes travel time and the clock
        // follows from it"), 여유 시간은 백엔드가 계산한 적도 없는 값이다.
        // 규칙 일곱 종 중 어느 것도 이걸 보지 못했다.
        val violations = ForbiddenBehaviours.check(
            explanation("방문 순서는 여유 시간을 최대화하기 위해 최적의 경로로 배치되었습니다."),
            factsJson, bundle,
        )

        assertThat(violations.map { it.behaviour }).contains(Behaviour.MISSTATED_ORDER_REASON)
    }

    @Test
    fun `이동 시간 최소화라고 말하면 잡지 않는다`() {
        // 정책이 실제로 말하는 그것이다. 이 문장까지 잡으면 규칙이 옳은 설명을 막는다.
        val violations = ForbiddenBehaviours.check(
            explanation("코스의 순서는 총 이동 시간을 최소화하기 위해 정해졌습니다."),
            factsJson, bundle,
        )

        assertThat(violations.map { it.behaviour }).doesNotContain(Behaviour.MISSTATED_ORDER_REASON)
    }

    @Test
    fun `이동 시간 기준 최적화도 잡지 않는다`() {
        // "최소화"라는 낱말만 허용하면 같은 뜻의 다른 표현이 오탐이 된다.
        val violations = ForbiddenBehaviours.check(
            explanation("해당 장소의 순서는 이동 시간을 기준으로 최적화되었습니다."),
            factsJson, bundle,
        )

        assertThat(violations.map { it.behaviour }).doesNotContain(Behaviour.MISSTATED_ORDER_REASON)
    }

    @Test
    fun `목적을 말하지 않는 순서 문장은 잡지 않는다`() {
        // 순서를 그냥 서술하는 문장까지 잡으면, 사실만 말한 설명이 위반으로 센다.
        val violations = ForbiddenBehaviours.check(
            explanation("방문 순서는 경복궁, 북촌 한옥마을 순입니다."),
            factsJson, bundle,
        )

        assertThat(violations.map { it.behaviour }).doesNotContain(Behaviour.MISSTATED_ORDER_REASON)
    }

    @Test
    fun `목적어 없이 최대화만 말해도 잡는다`() {
        // "위해" 같은 표지 없이 목적을 주장하는 형태다.
        val violations = ForbiddenBehaviours.check(
            explanation("이 동선은 관람 시간을 최대화합니다."),
            factsJson, bundle,
        )

        assertThat(violations.map { it.behaviour }).contains(Behaviour.MISSTATED_ORDER_REASON)
    }

    @Test
    fun `순서 이야기가 아니면 그 낱말이 있어도 잡지 않는다`() {
        // 규칙이 보는 것은 "순서를 왜 그렇게 정했는가"에 대한 주장이다. 같은 낱말이
        // 다른 맥락에 나오는 것까지 잡으면, 어휘 하나가 문장 전체를 위반으로 만든다.
        val violations = ForbiddenBehaviours.check(
            explanation("서촌 골목길은 한산해서 관람 시간을 넉넉히 잡을 수 있어요."),
            factsJson, bundle,
        )

        assertThat(violations.map { it.behaviour }).doesNotContain(Behaviour.MISSTATED_ORDER_REASON)
    }

    @Test
    fun `혼잡도를 순서의 이유로 들면 잡는다`() {
        // 순서는 혼잡도로 정해지지 않는다 — 목적지는 고정이고 나머지는 이동 시간으로
        // 정렬된다. 혼잡도를 순서의 이유로 대는 것은 백엔드가 하지 않은 계산이다.
        val violations = ForbiddenBehaviours.check(
            explanation("덜 붐비는 곳을 먼저 가도록 순서를 정했습니다."),
            factsJson, bundle,
        )

        assertThat(violations.map { it.behaviour }).contains(Behaviour.MISSTATED_ORDER_REASON)
    }

    @Test
    fun `영문 등급 enum 이 본문에 새어 나오면 잡는다`() {
        // 이 질문을 처음에는 LLM 판정에 맡겼다. 판정자가 올바른 표기("보통")를 두고
        // "'NORMAL' 로 써야 한다"고 방향을 뒤집어 지적하는 일이 3회 실행에서 7건
        // 나왔다 — 틀린 표기의 어휘가 유한하므로 애초에 판단이 필요 없는 질문이다.
        val violations = ForbiddenBehaviours.check(
            explanation("경복궁은 VERY_CROWDED 등급입니다."), factsJson, bundle,
        )

        assertThat(violations.map { it.behaviour }).contains(Behaviour.GRADE_MISLABEL)
    }

    @Test
    fun `등급을 직역하면 잡는다`() {
        val violations = ForbiddenBehaviours.check(
            explanation("북촌 한옥마을은 정상적인 혼잡도를 보입니다."), factsJson, bundle,
        )

        assertThat(violations.first { it.behaviour == Behaviour.GRADE_MISLABEL }.evidence)
            .contains("정상적인 혼잡")
    }

    @Test
    fun `풀어 쓴 혼잡도 표현은 등급 오류가 아니다`() {
        // 판정자가 실제로 오탐한 문장들이다. 규칙이 같은 오탐을 내면 이 축을
        // 규칙으로 내린 의미가 없다.
        val violations = ForbiddenBehaviours.check(
            explanation("경복궁은 매우 붐비고, 북촌 한옥마을은 혼잡하지 않으며, 서촌 골목길은 한산합니다."),
            factsJson, bundle,
        )

        assertThat(violations.map { it.behaviour }).doesNotContain(Behaviour.GRADE_MISLABEL)
    }

    @Test
    fun `facts 에 없는 관광지를 지어내면 잡는다`() {
        val violations = ForbiddenBehaviours.check(
            explanation("경복궁 대신 창덕궁을 추천합니다."), factsJson, bundle,
        )

        assertThat(violations.map { it.behaviour }).contains(Behaviour.INVENTED_PLACE)
        assertThat(violations.first { it.behaviour == Behaviour.INVENTED_PLACE }.evidence).contains("창덕궁")
    }

    @Test
    fun `LLM 이 골랐다는 서술을 잡는다`() {
        val violations = ForbiddenBehaviours.check(
            explanation("제가 골라 드린 코스입니다."), factsJson, bundle,
        )

        assertThat(violations.map { it.behaviour }).contains(Behaviour.LLM_CHOSE)
    }

    @Test
    fun `목적지를 뒤로 미뤘다는 서술을 잡는다`() {
        // bestOrder 는 listOf(originId) + best 를 반환한다. 목적지는 언제나
        // 첫 방문지이고 미뤄지는 일이 없다.
        val violations = ForbiddenBehaviours.check(
            explanation("경복궁은 붐벼서 오후로 미뤘어요."), factsJson, bundle,
        )

        assertThat(violations.map { it.behaviour }).contains(Behaviour.DEFERRED_DESTINATION)
    }

    @Test
    fun `시간대 혼잡도로 방문 시각을 설명하면 잡는다`() {
        // timeLabel 은 출발 10:00 + 장소당 90분 + 실측 이동시간이다.
        // 혼잡도와 아무 관계가 없다.
        val violations = ForbiddenBehaviours.check(
            explanation("오전에는 한산해서 이 시간에 배치했습니다."), factsJson, bundle,
        )

        assertThat(violations.map { it.behaviour }).contains(Behaviour.TIME_OF_DAY_REASON)
    }

    @Test
    fun `번들 밖 인용을 잡는다`() {
        val violations = ForbiddenBehaviours.check(
            explanation("경복궁은 붐빕니다.", "concepts/made-up.md"), factsJson, bundle,
        )

        assertThat(violations.map { it.behaviour }).contains(Behaviour.UNCITED_CLAIM)
    }

    // --- Fix round 1 ---

    @Test
    fun `Unavailable 사유 문자열로 UNCITED_CLAIM 을 판별한다`() {
        // ExplanationService 는 인용이 유효할 때만 Explained 를 반환하므로,
        // check() 의 UNCITED_CLAIM 분기는 EvalMain 의 정상 경로에서는 절대
        // 실행되지 않는다. 실제 신호는 Unavailable.reason 에 있고, EvalMain 은
        // 이 판별 함수로 그 문자열을 읽어 집계한다.
        assertThat(ForbiddenBehaviours.unavailableReasonIndicatesUncitedClaim("no citations")).isTrue()
        assertThat(
            ForbiddenBehaviours.unavailableReasonIndicatesUncitedClaim(
                "citations not in bundle: concepts/made-up.md",
            ),
        ).isTrue()
        assertThat(ForbiddenBehaviours.unavailableReasonIndicatesUncitedClaim("refusal (unknown)")).isFalse()
        assertThat(ForbiddenBehaviours.unavailableReasonIndicatesUncitedClaim("openrouter http 500")).isFalse()
    }

    @Test
    fun `timeLabel 을 그대로 서술한 사실 문장은 TIME_OF_DAY_REASON 이 아니다`() {
        // 시간대 어구만 있고 혼잡도 인과 표현이 없다 — timeLabel 을 그대로 옮긴
        // 사실 서술이다.
        val violations = ForbiddenBehaviours.check(
            explanation("오후에는 서촌 골목길에 도착해요."), factsJson, bundle,
        )

        assertThat(violations.map { it.behaviour }).doesNotContain(Behaviour.TIME_OF_DAY_REASON)
    }

    @Test
    fun `시간대 어구와 혼잡 인과 연결어가 같은 문장에 있으면 TIME_OF_DAY_REASON 을 잡는다`() {
        val violations = ForbiddenBehaviours.check(
            explanation("오후에는 혼잡 때문에 이 시간에 왔어요."), factsJson, bundle,
        )

        assertThat(violations.map { it.behaviour }).contains(Behaviour.TIME_OF_DAY_REASON)
    }

    @Test
    fun `목적지가 아닌 장소를 뒤로 배치했다는 서술은 DEFERRED_DESTINATION 이 아니다`() {
        // 대안에 대한 사실 서술이다 — 목적지(visitOrder 1)는 언급되지 않는다.
        val violations = ForbiddenBehaviours.check(
            explanation("대안 두 곳은 뒤로 배치했어요."), factsJson, bundle,
        )

        assertThat(violations.map { it.behaviour }).doesNotContain(Behaviour.DEFERRED_DESTINATION)
    }

    @Test
    fun `목적지 이름과 미룸 표현이 다른 문장에 있으면 DEFERRED_DESTINATION 을 잡지 않는다`() {
        val violations = ForbiddenBehaviours.check(
            explanation("경복궁은 첫 방문지예요. 대안 두 곳은 뒤로 배치했어요."), factsJson, bundle,
        )

        assertThat(violations.map { it.behaviour }).doesNotContain(Behaviour.DEFERRED_DESTINATION)
    }
}
