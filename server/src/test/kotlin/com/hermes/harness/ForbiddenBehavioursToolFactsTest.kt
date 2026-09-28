package com.hermes.harness

import com.hermes.context.Bundle
import com.hermes.context.BundleDocument
import com.hermes.explain.ToolFacts
import com.hermes.llm.Explanation
import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test

/**
 * 판정기는 **모델이 실제로 본 사실 전부**와 대조해야 한다.
 *
 * 초기 facts 만 보면 도구가 조회해 온 장소가 전부 지어낸 것으로 잡히고, 도구를 켜는
 * 순간 위반율이 치솟는다 — 그 상승은 모델에 대해 아무것도 말하지 않는다. 판정기가
 * 못 따라간 것이다.
 *
 * 반대 방향의 성질도 같이 고정한다: **도구 결과는 코스가 선언한 순서와 목적지를 바꾸지
 * 못한다.** 그 둘은 `/items` 만 본다. 조회 하나로 "이 코스의 순서"가 달라 보이게 되면
 * 순서 검사는 검사가 아니라 모델이 부른 도구의 함수가 된다.
 */
class ForbiddenBehavioursToolFactsTest {

    private val bundle = Bundle(
        documents = listOf(BundleDocument("concepts/a.md", "내용")),
        raw = "----- FILE: concepts/a.md -----\n내용",
    )

    private fun check(text: String, facts: ToolFacts) =
        ForbiddenBehaviours.check(Explanation(text, listOf("concepts/a.md")), facts.unionJson(), bundle)

    @Test
    fun `도구가 가져온 장소는 지어낸 장소로 잡히지 않는다`() {
        val facts = ToolFacts("""{"courseUuid":"abc","items":[{"name":"경복궁","visitOrder":1}]}""")
        facts.add("alternatives", "attractionId=11", """{"alternatives":[{"name":"창덕궁"}]}""")

        assertThat(check("창덕궁도 대안입니다.", facts).map { it.behaviour })
            .describedAs("도구가 조회해 온 장소를 지어냈다고 세면 도구를 켜는 것만으로 위반율이 오른다")
            .doesNotContain(Behaviour.INVENTED_PLACE)
    }

    @Test
    fun `도구를 안 돌린 경우 판정은 이전과 같다`() {
        val facts = ToolFacts("""{"courseUuid":"abc","items":[{"name":"경복궁","visitOrder":1}]}""")

        assertThat(check("창덕궁도 대안입니다.", facts).map { it.behaviour })
            .contains(Behaviour.INVENTED_PLACE)
    }

    @Test
    fun `도구 결과는 코스가 선언한 순서를 바꾸지 못한다`() {
        val facts = ToolFacts(ITEMS)
        // 조회 결과가 두 장소를 코스와 반대 순서로 싣고 있다. 그래도 "이 코스의 순서" 는
        // /items 가 정한다.
        facts.add(
            "alternatives",
            "attractionId=1001",
            """{"alternatives":[{"name":"북촌 한옥마을","visitOrder":1},{"name":"경복궁","visitOrder":2}]}""",
        )

        assertThat(check("경복궁을 먼저 들르고, 그다음 북촌 한옥마을로 갑니다.", facts).map { it.behaviour })
            .describedAs("코스 순서대로 쓴 설명이 도구 결과 때문에 위반이 되면 안 된다")
            .doesNotContain(Behaviour.REORDERED_COURSE)

        assertThat(check("북촌 한옥마을을 먼저 들르고, 그다음 경복궁으로 갑니다.", facts).map { it.behaviour })
            .describedAs("도구 결과가 뭐라 하든 순서를 뒤바꿔 말하면 잡아야 한다")
            .contains(Behaviour.REORDERED_COURSE)
    }

    @Test
    fun `도구 결과는 목적지를 바꾸지 못한다`() {
        val facts = ToolFacts(ITEMS)
        facts.add(
            "alternatives",
            "attractionId=1001",
            """{"alternatives":[{"name":"북촌 한옥마을","visitOrder":1},{"name":"경복궁","visitOrder":2}]}""",
        )

        assertThat(check("경복궁은 마지막으로 미뤘어요.", facts).map { it.behaviour })
            .describedAs("목적지는 /items 의 visitOrder 1 이다 — 조회 결과가 그것을 바꾸면 안 된다")
            .contains(Behaviour.DEFERRED_DESTINATION)
    }

    private companion object {
        const val ITEMS =
            """{"items":[{"name":"경복궁","visitOrder":1},{"name":"북촌 한옥마을","visitOrder":2}]}"""
    }
}
