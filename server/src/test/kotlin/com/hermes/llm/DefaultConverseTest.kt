package com.hermes.llm

import org.assertj.core.api.Assertions.assertThat
import org.assertj.core.api.Assertions.assertThatThrownBy
import org.junit.jupiter.api.Test

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

        assertThat(step).isInstanceOf(Spoke::class.java)
        assertThat((step as Spoke).end).isInstanceOf(StreamCompleted::class.java)
        assertThat(chunks.joinToString("")).contains("본문")
    }

    @Test
    fun `기본 구현은 사용자 턴을 순서대로 전부 explain 에 넘긴다`() {
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

        assertThat(provider.seenUserText).isEqualTo("첫 질문\n\n마지막 질문")
    }

    @Test
    fun `수리 라운드에서도 원래 질문이 빠지지 않는다`() {
        // AgentLoop 의 수리는 대화 끝에 "인용을 이렇게 고쳐라" 를 UserTurn 으로 붙인다.
        // 마지막 턴만 넘기면 모델이 받는 것은 그 지시뿐이고, 무엇에 대한 답이었는지가
        // 통째로 사라진다 — 프롬프트는 멀쩡해 보이는데 답이 엉뚱해진다.
        val provider = RecordingProvider(answered)

        provider.converse(
            systemText = "SYS",
            turns = listOf(UserTurn("덕수궁 언제 가요?"), UserTurn("직전 답의 인용이 유효하지 않다: ...")),
            tools = emptyList(),
            onChunk = {},
        )

        assertThat(provider.seenUserText).contains("덕수궁 언제 가요?")
        assertThat(provider.seenUserText).contains("직전 답의 인용이 유효하지 않다")
    }

    @Test
    fun `사용자 턴이 하나도 없으면 조용히 빈 질문을 보내지 않는다`() {
        val provider = RecordingProvider(answered)

        assertThatThrownBy {
            provider.converse(
                systemText = "SYS",
                turns = listOf(ToolResultTurn(listOf(ToolResult("id-1", "{}")))),
                tools = emptyList(),
                onChunk = {},
            )
        }.isInstanceOf(IllegalStateException::class.java)
        assertThat(provider.seenUserText).isNull()
    }

    @Test
    fun `거절은 Spoke 안의 StreamRefused 로 온다`() {
        val provider = RecordingProvider(Refused(category = "safety"))

        val step = provider.converse("SYS", listOf(UserTurn("질문")), emptyList()) {}

        assertThat(step).isInstanceOf(Spoke::class.java)
        assertThat((step as Spoke).end).isEqualTo(StreamRefused("safety"))
    }
}
