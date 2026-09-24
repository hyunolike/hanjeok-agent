package com.hermes.llm

import com.hermes.shared.config.LlmSelection
import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test
import org.springframework.ai.anthropic.AnthropicChatOptions
import org.springframework.ai.chat.messages.AssistantMessage
import org.springframework.ai.chat.model.ChatResponse
import org.springframework.ai.chat.model.Generation
import org.springframework.ai.model.tool.ToolCallingChatOptions

class SpringAiConverseTest {

    private fun responseWithToolCall(id: String, name: String, args: String): ChatResponse {
        val message = AssistantMessage.builder()
            .content("")
            .toolCalls(listOf(AssistantMessage.ToolCall(id, "function", name, args)))
            .build()
        return ChatResponse(listOf(Generation(message)))
    }

    @Test
    fun `도구 호출이 담긴 응답은 ToolRequested 로 매핑된다`() {
        val step = SpringAiExplanationProvider.toAgentStep(
            responseWithToolCall("call-1", "congestion", """{"attractionId":11}"""),
        )

        assertThat(step).isInstanceOf(ToolRequested::class.java)
        val requested = step as ToolRequested
        assertThat(requested.calls).hasSize(1)
        assertThat(requested.calls[0].id).isEqualTo("call-1")
        assertThat(requested.calls[0].name).isEqualTo("congestion")
        assertThat(requested.calls[0].argumentsJson).isEqualTo("""{"attractionId":11}""")
    }

    @Test
    fun `도구 호출이 없으면 ToolRequested 가 아니다`() {
        val message = AssistantMessage.builder().content("본문").build()
        val step = SpringAiExplanationProvider.toAgentStep(ChatResponse(listOf(Generation(message))))

        assertThat(step).isNotInstanceOf(ToolRequested::class.java)
    }

    @Test
    fun `도구 콜백은 우리 경로에서 실행되면 안 되므로 부르면 터진다`() {
        val callback = SpringAiExplanationProvider.neverExecutedCallback(
            ToolSpec("congestion", "혼잡도", "{}"),
        )

        val thrown = runCatching { callback.call("{}") }.exceptionOrNull()

        assertThat(thrown).isInstanceOf(IllegalStateException::class.java)
        assertThat(thrown!!.message).contains("AgentLoop")
    }

    @Test
    fun `콜백은 ToolSpec 의 이름과 스키마를 그대로 정의에 싣는다`() {
        val callback = SpringAiExplanationProvider.neverExecutedCallback(
            ToolSpec("alternatives", "대안", """{"type":"object"}"""),
        )

        assertThat(callback.toolDefinition.name()).isEqualTo("alternatives")
        assertThat(callback.toolDefinition.description()).isEqualTo("대안")
        assertThat(callback.toolDefinition.inputSchema()).isEqualTo("""{"type":"object"}""")
    }

    /**
     * 프롬프트에 옵션을 실으면 모델의 기본 옵션이 **통째로 대체된다** — 병합이 아니다.
     * `AnthropicChatModel.buildRequestPrompt` 는 `prompt.getOptions() == null` 일 때만
     * 기본 옵션을 끼워 넣고, 아니면 프롬프트 옵션을 그대로 쓴다(바이트코드로 확인).
     * 그래서 도구를 실을 때 빈 옵션을 새로 만들면 안 되고 기본 옵션을 `mutate()` 해야
     * 한다 — 안 그러면 model/maxTokens/캐시/스키마가 전부 사라진다.
     */
    @Test
    fun `도구 옵션은 프로바이더 기본 옵션을 그대로 보존한다`() {
        val base = ChatClients.anthropicOptions("claude-test-model")

        val withTools = SpringAiExplanationProvider.withToolCallbacks(
            base,
            listOf(ToolSpec("congestion", "혼잡도", "{}")),
        )

        assertThat(withTools).isInstanceOf(AnthropicChatOptions::class.java)
        val anthropic = withTools as AnthropicChatOptions
        assertThat(anthropic.model).isEqualTo("claude-test-model")
        assertThat(anthropic.maxTokens).isEqualTo(ChatClients.MAX_TOKENS)
        assertThat(anthropic.cacheOptions).isEqualTo(base.cacheOptions)
        assertThat(anthropic.outputConfig).isEqualTo(base.outputConfig)
        assertThat(anthropic.toolCallbacks.orEmpty().map { it.toolDefinition.name() })
            .containsExactly("congestion")
        assertThat(withTools).isInstanceOf(ToolCallingChatOptions::class.java)
    }

    private fun openAiProvider(endpoint: CapturingEndpoint): ExplanationProvider =
        LlmSelection.provider("openai", "gpt-4o", { "sk-not-a-real-key" }, endpoint.baseUrl)

    /**
     * 도구가 없을 때 `converse()` 가 내보내는 바이트는 `stream()` 과 **같아야** 한다.
     * 다르면 프롬프트 캐시 접두사가 두 갈래로 갈라져 캐시가 통째로 무효가 된다.
     * 두 경로가 서로 다른 계층(ChatModel 직접 / ChatClient)을 타므로 눈으로는
     * 보장되지 않는다 — 나가는 바이트를 직접 맞춰 본다.
     */
    @Test
    fun `도구가 없으면 converse 의 요청 바이트가 stream 과 같다`() {
        val streamed = CapturingEndpoint().use { endpoint ->
            openAiProvider(endpoint).stream("sys", "user") {}
            endpoint.capturedBody()
        }
        val conversed = CapturingEndpoint().use { endpoint ->
            openAiProvider(endpoint).converse("sys", listOf(UserTurn("user")), emptyList()) {}
            endpoint.capturedBody()
        }

        assertThat(conversed).isEqualTo(streamed)
    }

    /**
     * 도구를 실어도 프로바이더의 기본 옵션이 살아 있어야 한다. 프롬프트 옵션은
     * 기본 옵션과 병합되지 않고 **대체**되므로, 빈 옵션을 새로 만들면 여기서
     * model/max_tokens/response_format 이 통째로 사라진다.
     */
    @Test
    fun `도구를 실어도 모델과 max_tokens 와 출력 스키마가 그대로 나간다`() {
        CapturingEndpoint().use { endpoint ->
            openAiProvider(endpoint).converse(
                systemText = "sys",
                turns = listOf(UserTurn("user")),
                tools = listOf(ToolSpec("congestion", "혼잡도", """{"type":"object","properties":{}}""")),
                onChunk = {},
            )
            val body = endpoint.capturedBody()

            assertThat(body["model"].asText()).isEqualTo("gpt-4o")
            assertThat(body["max_tokens"].asInt()).isEqualTo(ChatClients.MAX_TOKENS)
            assertThat(body["response_format"]["type"].asText()).isEqualTo("json_schema")
            assertThat(body["tools"]).hasSize(1)
            assertThat(body["tools"][0]["function"]["name"].asText()).isEqualTo("congestion")
            assertThat(body["tools"][0]["function"]["description"].asText()).isEqualTo("혼잡도")
        }
    }

    /** 증거 묶음은 그대로 system 블록에 실린다 — 도구가 붙어도 아무것도 덧붙지 않는다. */
    @Test
    fun `system 블록은 도구가 있어도 증거 묶음 그대로다`() {
        CapturingEndpoint().use { endpoint ->
            openAiProvider(endpoint).converse(
                systemText = "번들 원문",
                turns = listOf(UserTurn("질문")),
                tools = listOf(ToolSpec("congestion", "혼잡도", """{"type":"object","properties":{}}""")),
                onChunk = {},
            )
            val body = endpoint.capturedBody()

            assertThat(body["messages"][0]["role"].asText()).isEqualTo("system")
            assertThat(body["messages"][0]["content"].asText()).isEqualTo("번들 원문")
        }
    }
}
