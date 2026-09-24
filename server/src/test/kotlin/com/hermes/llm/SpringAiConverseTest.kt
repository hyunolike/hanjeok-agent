package com.hermes.llm

import com.hermes.shared.config.LlmSelection
import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test
import org.springframework.ai.anthropic.AnthropicChatOptions
import org.springframework.ai.chat.messages.AssistantMessage
import org.springframework.ai.chat.model.ChatModel
import org.springframework.ai.chat.model.ChatResponse
import org.springframework.ai.chat.model.Generation
import org.springframework.ai.chat.prompt.Prompt
import org.springframework.ai.model.tool.ToolCallingChatOptions
import reactor.core.publisher.Flux

/**
 * 조각 목록을 그대로 흘리는 `ChatModel`. 네트워크도 SSE 파싱도 끼지 않으므로
 * `converse()` 자신의 분기(도구 호출과 본문의 순서)만 남는다 — 그 분기가
 * `ToolRequested` 계약을 지키는지가 여기서 검사할 전부다.
 */
private class FlowingChatModel(private val chunks: List<ChatResponse>) : ChatModel {
    override fun call(prompt: Prompt): ChatResponse = chunks.last()
    override fun stream(prompt: Prompt): Flux<ChatResponse> = Flux.fromIterable(chunks)
}

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

    private fun textChunk(text: String): ChatResponse =
        ChatResponse(listOf(Generation(AssistantMessage.builder().content(text).build())))

    private fun converseOver(chunks: List<ChatResponse>, onChunk: (String) -> Unit): AgentStep =
        SpringAiExplanationProvider("fake", FlowingChatModel(chunks))
            .converse("sys", listOf(UserTurn("질문")), emptyList(), onChunk)

    /**
     * **`ToolRequested` 계약의 시험.** 이 값이 나왔다면 `onChunk` 는 한 번도 불리지
     * 않았어야 한다. 나중 태스크의 인용 게이트가 통째로 이 불변식 위에 서 있다 —
     * 도구 델타가 `onChunk` 에 새면 검증되지 않은 텍스트가 독자에게 그대로 간다.
     *
     * 도구 호출 뒤에 본문 조각이 따라오는 것은 실제로 일어난다(프로바이더가 도구
     * 블록 뒤에 텍스트 블록을 더 보낼 수 있다). 그 본문은 버려야 한다.
     */
    @Test
    fun `도구 호출이 먼저면 뒤따르는 본문은 onChunk 에 절대 닿지 않는다`() {
        val seen = mutableListOf<String>()

        val step = converseOver(
            listOf(
                responseWithToolCall("call-1", "congestion", """{"attractionId":11}"""),
                textChunk("이 본문은 새면 안 된다"),
            ),
            onChunk = { seen += it },
        )

        assertThat(step).isInstanceOf(ToolRequested::class.java)
        assertThat((step as ToolRequested).calls.map { it.name }).containsExactly("congestion")
        assertThat(seen).describedAs("ToolRequested 면 onChunk 는 한 번도 불리지 않는다").isEmpty()
    }

    /**
     * 혼합 턴 규칙. 본문이 이미 나갔으면 그 턴은 최종 답이고, 같은 턴의 도구 호출은
     * 무시한다 — 반대로 하면 사용자가 읽고 있던 문장을 되감아 지우는 셈이 된다.
     */
    @Test
    fun `본문이 먼저 나갔으면 뒤따르는 도구 호출은 무시되고 본문이 유지된다`() {
        val seen = mutableListOf<String>()

        val step = converseOver(
            listOf(
                textChunk("이미 나간 본문"),
                responseWithToolCall("call-1", "congestion", """{"attractionId":11}"""),
            ),
            onChunk = { seen += it },
        )

        assertThat(step).isInstanceOf(Spoke::class.java)
        assertThat(step).isNotInstanceOf(ToolRequested::class.java)
        assertThat((step as Spoke).end).isInstanceOf(StreamCompleted::class.java)
        assertThat(seen).containsExactly("이미 나간 본문")
    }

    /**
     * 배선 오류는 요청이 나가기도 전에 터진다. 포트 계약상 예외를 밖으로 던지지는
     * 않지만(모든 호출자가 다른 프로바이더는 내지 않는 예외를 처리하게 만들 수 없다),
     * 그 정체는 `StreamFailed` 의 reason 에 남아야 한다 — 로그는 이 경우만 ERROR 다.
     */
    @Test
    fun `프로바이더 옵션이 도구를 실을 수 없으면 정체를 남긴 채 StreamFailed 로 닫힌다`() {
        val provider = SpringAiExplanationProvider("fake", FlowingChatModel(listOf(textChunk("본문"))))

        val step = provider.converse(
            systemText = "sys",
            turns = listOf(UserTurn("질문")),
            // FlowingChatModel 은 ChatModel 기본 구현을 쓰므로 options 가
            // ToolCallingChatOptions 가 아니다 — 도구를 실을 수 없는 배선이다.
            tools = listOf(ToolSpec("congestion", "혼잡도", "{}")),
            onChunk = {},
        )

        assertThat(step).isInstanceOf(Spoke::class.java)
        val end = (step as Spoke).end
        assertThat(end).isInstanceOf(StreamFailed::class.java)
        assertThat((end as StreamFailed).reason).contains("IllegalStateException")
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
