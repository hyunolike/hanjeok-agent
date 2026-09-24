package com.hermes.llm

import org.junit.jupiter.api.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

private class RecordingProvider(private val result: ProviderResult) : ExplanationProvider {
    override val name = "recording"
    var seenUserText: String? = null
    override fun explain(systemText: String, userText: String): ProviderResult {
        seenUserText = userText
        return result
    }
}

class DefaultConverseTest {

    private val answered = Answered(
        explanation = Explanation("본문", listOf("concepts/a.md")),
        usage = ProviderUsage(0, 0, 0, 0),
    )

    @Test
    fun `기본 구현은 도구를 무시하고 항상 Spoke 를 낸다`() {
        val provider = RecordingProvider(answered)
        val chunks = mutableListOf<String>()

        val step = provider.converse(
            systemText = "SYS",
            turns = listOf(UserTurn("질문")),
            tools = listOf(ToolSpec("congestion", "혼잡도", "{}")),
            onChunk = { chunks.add(it) },
        )

        assertIs<Spoke>(step)
        assertIs<StreamCompleted>(step.end)
        assertTrue(chunks.joinToString("").contains("본문"))
    }

    @Test
    fun `기본 구현은 마지막 사용자 턴의 텍스트를 explain 에 넘긴다`() {
        val provider = RecordingProvider(answered)

        provider.converse(
            systemText = "SYS",
            turns = listOf(
                UserTurn("첫 질문"),
                ToolCallTurn(listOf(ToolCall("id-1", "congestion", "{}"))),
                ToolResultTurn(listOf(ToolResult("id-1", "{}"))),
                UserTurn("마지막 질문"),
            ),
            tools = emptyList(),
            onChunk = {},
        )

        assertEquals("마지막 질문", provider.seenUserText)
    }

    @Test
    fun `거절은 Spoke 안의 StreamRefused 로 온다`() {
        val provider = RecordingProvider(Refused(category = "safety"))

        val step = provider.converse("SYS", listOf(UserTurn("질문")), emptyList()) {}

        assertIs<Spoke>(step)
        assertEquals(StreamRefused("safety"), step.end)
    }
}
