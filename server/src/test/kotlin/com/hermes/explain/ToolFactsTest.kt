package com.hermes.explain

import com.fasterxml.jackson.databind.ObjectMapper
import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test

class ToolFactsTest {

    private val mapper = ObjectMapper()

    @Test
    fun `도구가 안 돌면 합집합은 초기 facts 와 같다`() {
        val facts = ToolFacts("""{"courseUuid":"abc"}""")

        assertThat(mapper.readTree(facts.unionJson()))
            .isEqualTo(mapper.readTree("""{"courseUuid":"abc"}"""))
    }

    @Test
    fun `도구 결과는 lookups 배열에 쌓인다`() {
        val facts = ToolFacts("""{"courseUuid":"abc"}""")
        facts.add("congestion", "attractionId=11 date=2026-10-03", """{"grade":"NORMAL"}""")

        val union = mapper.readTree(facts.unionJson())
        assertThat(union.path("courseUuid").asText()).isEqualTo("abc")
        assertThat(union.path("lookups").size()).isEqualTo(1)
        assertThat(union.at("/lookups/0/tool").asText()).isEqualTo("congestion")
        assertThat(union.at("/lookups/0/result/grade").asText()).isEqualTo("NORMAL")
    }

    @Test
    fun `여러 번 부르면 순서대로 쌓인다`() {
        val facts = ToolFacts("""{"courseUuid":"abc"}""")
        facts.add("congestion", "a", """{"n":1}""")
        facts.add("alternatives", "b", """{"n":2}""")

        val union = mapper.readTree(facts.unionJson())
        assertThat(union.path("lookups").map { it.path("tool").asText() })
            .isEqualTo(listOf("congestion", "alternatives"))
    }

    @Test
    fun `초기 facts 는 덮어써지지 않는다`() {
        val facts = ToolFacts("""{"courseUuid":"abc","lookups":"원래값"}""")
        facts.add("congestion", "a", """{"n":1}""")

        // 이름이 충돌하면 도구 결과가 아니라 초기 facts 가 이긴다 — 한적이 준 사실이
        // 모델이 유도한 조회보다 우선한다.
        val union = mapper.readTree(facts.unionJson())
        assertThat(union.path("lookups").asText()).isEqualTo("원래값")
        assertThat(union.path("toolLookups").size()).isEqualTo(1)
    }
}
