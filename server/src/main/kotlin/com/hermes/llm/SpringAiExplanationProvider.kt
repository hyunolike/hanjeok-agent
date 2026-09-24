package com.hermes.llm

import com.fasterxml.jackson.databind.ObjectMapper
import org.slf4j.LoggerFactory
import org.springframework.ai.chat.client.ChatClient
import org.springframework.ai.chat.messages.AssistantMessage
import org.springframework.ai.chat.messages.Message
import org.springframework.ai.chat.messages.SystemMessage
import org.springframework.ai.chat.messages.ToolResponseMessage
import org.springframework.ai.chat.messages.UserMessage
import org.springframework.ai.chat.model.ChatModel
import org.springframework.ai.chat.model.ChatResponse
import org.springframework.ai.chat.model.Generation
import org.springframework.ai.chat.model.ToolContext
import org.springframework.ai.chat.prompt.ChatOptions
import org.springframework.ai.chat.prompt.Prompt
import org.springframework.ai.model.tool.ToolCallingChatOptions
import org.springframework.ai.tool.ToolCallback
import org.springframework.ai.tool.definition.DefaultToolDefinition
import org.springframework.ai.tool.definition.ToolDefinition

/**
 * 포트 뒤의 단일 구현. 프로바이더별 차이는 주입된 `ChatModel` 이 들고 있고,
 * 여기서는 어느 프로바이더인지 알 필요가 없다.
 *
 * 포트를 남긴 이유는 바뀌지 않았다 — "같은 프롬프트와 같은 검증으로 비교한다"는
 * 보장이 프레임워크가 아니라 이 저장소 코드에 남아 있어야 한다.
 */
class SpringAiExplanationProvider(
    override val name: String,
    private val chatModel: ChatModel,
) : ExplanationProvider {

    private val log = LoggerFactory.getLogger(SpringAiExplanationProvider::class.java)

    // explain()/stream() 은 지금까지와 똑같이 ChatClient 를 쓴다. 기존 경로의 요청
    // 바이트를 건드리지 않기 위해서다 — `ChatClient.create(model)` 는 지금까지
    // LlmSelection 이 세 분기에서 하던 것과 **같은 조립**이다. 달라진 것은 그 호출이
    // 일어나는 자리뿐이다.
    private val chatClient: ChatClient = ChatClient.create(chatModel)

    // 블록 바디다 — 응답이 null 일 때 조기 return 이 필요한데, 식 바디(`= try { ... }`)
    // 에서는 Kotlin 2.2 가 그 return 을 금지한다(컴파일로 확인: "Returns are
    // prohibited in functions with expression body").
    override fun explain(systemText: String, userText: String): ProviderResult {
        return try {
            val response = chatClient
                .prompt(Prompt(listOf(SystemMessage(systemText), UserMessage(userText))))
                .call()
                .chatResponse()
                ?: return Failed("response was null")

            toProviderResult(response)
        } catch (e: Exception) {
            // 예외의 정체를 지우지 않는다 — 영구적 프로그래밍 오류가 소켓 타임아웃과
            // 구분이 안 되면, 호출자가 Failed 를 재시도할 때 전액을 들여 같은 버그를
            // 반복한다. (네트워크 호출 자체가 던지는 예외만 여기서 잡는다 — 응답을
            // ProviderResult 로 바꾸는 로직 자체의 예외는 toProviderResult 가 자체적으로
            // 감싼다.)
            log.warn("$name explain failed", e)
            Failed("${e::class.simpleName}: ${e.message}")
        }
    }

    /**
     * 실제 스트리밍. Reactor 는 여기 가둔다 — 포트는 콜백과 블로킹 반환만 안다.
     *
     * 거절 판정은 `isRefusal` 을 쓴다(아래 설명 참고). **마지막 조각만 보면 안 된다** —
     * 루프백으로 실측했다: Spring AI 의 `OpenAiChatModel.internalStream` 은 원본 SSE
     * 청크를 누적 병합하지 않고 청크마다 독립적으로 `ChatResponse` 를 만들어 내보낸다
     * (`OpenAiChatModel$ChunkMerger.mergeChoices` 가 새 델타의 content/refusal 을
     * 이전 것 위에 이어붙이지 않는 것까지 바이트코드로 확인). 그래서 OpenAI 호환
     * 거절은 `refusal` 필드를 실은 조각과 `finish_reason: "stop"` 을 실은 마지막(대개
     * 빈) 조각이 서로 다를 수 있다 — 마지막 조각만 보면 그 사이 조각의 `refusal` 을
     * 놓친다. 그래서 조각마다 `isRefusal` 을 확인해 하나라도 걸리면 거절로 닫는다.
     * 거절이면 content 가 비어 있어(OpenAI 는 `refusal` 필드로, 본문 content 는
     * 비운다) onChunk 가 불리지 않으므로, 게이트는 delta 없이 unavailable 로 닫는다.
     */
    override fun stream(systemText: String, userText: String, onChunk: (String) -> Unit): StreamEnd = try {
        var last: ChatResponse? = null
        var refused = false
        chatClient
            .prompt(Prompt(listOf(SystemMessage(systemText), UserMessage(userText))))
            .stream()
            .chatResponse()
            .doOnNext { response ->
                last = response
                val generation = response.result
                if (generation != null && isRefusal(generation)) refused = true
                val text = generation?.output?.text
                if (!text.isNullOrEmpty()) onChunk(text)
            }
            .blockLast()

        if (refused) {
            StreamRefused(category = null)
        } else {
            // 스트리밍에서는 프로바이더가 usage 를 안 줄 수 있다. 스트리밍 경로는 usage 를
            // 집계에 쓰지 않으므로 0 으로 둔다 — 하네스는 비스트리밍 explain() 으로 잰다.
            StreamCompleted(last?.let { usageOf(it) } ?: ProviderUsage(0, 0, 0, 0))
        }
    } catch (e: Exception) {
        log.warn("$name stream failed", e)
        StreamFailed("${e::class.simpleName}: ${e.message}")
    }

    /**
     * 도구를 실을 수 있는 대화. **ChatClient 를 우회하고 ChatModel 을 직접 부른다.**
     *
     * Spring AI 2.0.1 에서 도구를 정의해 보내는 일과 실행하는 일이 다른 계층에 있다.
     * `OpenAiChatModel`/`AnthropicChatModel` 은 `resolveToolDefinitions` 만 부르고
     * `executeToolCalls` 는 부르지 않는다(설치된 jar 를 뜯어 확인 — 두 클래스의
     * 바이트코드에 `executeToolCalls` 참조가 0 개다). 실행은 `ToolCallingAdvisor` 가
     * 하고, `DefaultChatClientBuilder` 는 그 어드바이저를 항상 하나 만들어 단다.
     * 그래서 ChatClient 를 타면 도구가 우리 모르게 실행된다 — 예산도, 인자 검증도,
     * 인용 게이트도 거치지 않고. 루프는 AgentLoop 의 것이므로 여기서는 실행되지 않은
     * 도구 호출을 그대로 돌려준다.
     *
     * 도구가 비어 있으면 옵션을 얹지 않는다 — 요청 바이트가 기존 stream() 과 같아야
     * 프롬프트 캐시 접두사가 갈라지지 않는다.
     *
     * 블록 바디다 — 식 바디에서는 Kotlin 이 return 을 금지하는데(`explain` 의 주석
     * 참고), 여기서도 도구 호출을 만나면 나머지 판정을 건너뛰어야 한다.
     */
    override fun converse(
        systemText: String,
        turns: List<Turn>,
        tools: List<ToolSpec>,
        onChunk: (String) -> Unit,
    ): AgentStep {
        return try {
            var last: ChatResponse? = null
            var refused = false
            var toolStep: ToolRequested? = null
            var sawBody = false

            chatModel.stream(promptFor(systemText, turns, tools))
                .doOnNext { response ->
                    last = response
                    val generation = response.result
                    if (generation != null && isRefusal(generation)) refused = true

                    // 본문이 이미 나가기 시작했으면 그 턴은 최종 답이다. 같은 턴의 도구
                    // 호출은 무시한다 — 나간 본문은 게이트가 인용을 검증한 것이고,
                    // 여기서 끊으면 사용자가 읽던 문장이 사라진다.
                    if (!sawBody && toolStep == null) {
                        toolStep = toAgentStep(response) as? ToolRequested
                    }

                    val text = generation?.output?.text
                    if (!text.isNullOrEmpty()) {
                        // 도구 호출로 이미 갈렸으면 본문을 내보내지 않는다 —
                        // ToolRequested 계약이 "onChunk 가 한 번도 안 불렸다" 이기
                        // 때문이다.
                        if (toolStep == null) {
                            sawBody = true
                            onChunk(text)
                        }
                    }
                }
                .blockLast()

            toolStep ?: when {
                refused -> Spoke(StreamRefused(category = null))
                // 스트리밍에서 usage 가 없을 수 있는 것은 stream() 과 같다.
                else -> Spoke(StreamCompleted(last?.let { usageOf(it) } ?: ProviderUsage(0, 0, 0, 0)))
            }
        } catch (e: Exception) {
            log.warn("$name converse failed", e)
            Spoke(StreamFailed("${e::class.simpleName}: ${e.message}"))
        }
    }

    private fun promptFor(systemText: String, turns: List<Turn>, tools: List<ToolSpec>): Prompt {
        val messages = toMessages(systemText, turns)
        // 도구가 없으면 옵션 자리를 비워 둔다. 이 경로의 요청 바이트는 stream() 과
        // 같아야 한다 — 프롬프트 캐시 접두사가 갈라지면 캐시가 통째로 무효가 된다.
        if (tools.isEmpty()) return Prompt(messages)
        return Prompt(messages, withToolCallbacks(chatModel.options, tools))
    }

    /**
     * `system` 블록은 증거 묶음 그대로다 — 여기에 아무것도 덧붙이지 않는다.
     */
    private fun toMessages(systemText: String, turns: List<Turn>): List<Message> =
        buildList {
            add(SystemMessage(systemText))
            turns.forEach { turn ->
                when (turn) {
                    is UserTurn -> add(UserMessage(turn.text))
                    is ToolCallTurn -> add(
                        AssistantMessage.builder()
                            .content("")
                            .toolCalls(
                                turn.calls.map {
                                    AssistantMessage.ToolCall(it.id, "function", it.name, it.argumentsJson)
                                },
                            )
                            .build(),
                    )
                    // 생성자가 아니라 빌더다 — `ToolResponseMessage` 의 유일한 생성자는
                    // protected 라 밖에서 부를 수 없다(javap 로 확인).
                    is ToolResultTurn -> add(
                        ToolResponseMessage.builder()
                            .responses(
                                turn.results.map { ToolResponseMessage.ToolResponse(it.id, "", it.contentJson) },
                            )
                            .build(),
                    )
                }
            }
        }

    // public 이다(companion 자체를 private 로 두지 않는다) — Task 6 리뷰가 요구한
    // "매핑은 손으로 조립한 ChatResponse 로 직접 테스트할 수 있어야 한다" 를 만족하려면
    // SpringAiResponseMappingTest 가 SpringAiExplanationProvider.toProviderResult 를
    // 실제 네트워크 없이 부를 수 있어야 한다.
    companion object {
        private const val REFUSAL = "refusal"
        private val MAPPER = ObjectMapper()

        /**
         * `ChatResponse` 하나를 받아 `ProviderResult` 하나를 내는 순수 함수. 입력 밖의
         * 어떤 것도 만지지 않는다(네트워크 호출도, `this.name`/`this.chatClient` 도) —
         * 그래서 실제 호출 없이, 손으로 조립한 `ChatResponse` 로 바로 테스트할 수 있다.
         *
         * `explain` 이 쥐고 있는 것은 네트워크 호출과 그 바깥 try/catch 뿐이다. 이
         * 함수 자신의 실패(JSON 파싱 등)는 여기서 끝까지 감싸 `Failed` 로 돌려준다 —
         * "malformed content 는 크래시가 아니라 Failed" 라는 요구가 직접 테스트
         * 가능해야 하기 때문이다(explain 의 바깥 catch 를 거치지 않고도).
         */
        fun toProviderResult(response: ChatResponse): ProviderResult {
            val generation = response.result ?: return Failed("response carried no generation")

            // 거절을 content 읽기 전에 가른다. 거절은 HTTP 200 에 빈 content 로 오므로
            // 본문을 무조건 읽는 코드는 여기서 깨진다. 판정은 `isRefusal` 로 뺐다 —
            // 그 함수의 설명 참고.
            if (isRefusal(generation)) {
                return Refused(category = null)
            }

            val text = generation.output?.text
            if (text.isNullOrBlank()) return Failed("response carried no structured content")

            // 구조화 출력(effort+schema) 이 강제하는 계약이라 text 는 Explanation 의
            // JSON 이다. OpenAiCompatibleExplanationProvider 와 같은 방식으로 판다 —
            // 어느 프로바이더가 뒤에 있든 같은 파싱 경로를 타야 비교가 정직하다.
            //
            // 파싱 실패는 여기서 잡아 Failed 로 접는다 — 예외의 정체(클래스명+메시지)는
            // 지우지 않는다.
            val parsed = try {
                MAPPER.readTree(text)
            } catch (e: Exception) {
                return Failed("${e::class.simpleName}: ${e.message}")
            }

            val explanationText = parsed.at("/explanation").asText()
            if (explanationText.isNullOrBlank()) return Failed("structured content had no explanation field")

            return Answered(
                explanation = Explanation(
                    explanation = explanationText,
                    citations = parsed.at("/citations").map { it.asText() },
                ),
                usage = usageOf(response),
            )
        }

        /**
         * 응답에 실행되지 않은 도구 호출이 담겨 있으면 `ToolRequested` 로, 아니면
         * "도구는 없었다"는 뜻의 `Spoke` 자리표시자를 낸다. 순수 함수라 손으로 조립한
         * `ChatResponse` 로 직접 테스트한다 — `toProviderResult` 와 같은 이유다.
         */
        fun toAgentStep(response: ChatResponse): AgentStep {
            val calls = response.result?.output?.toolCalls.orEmpty()
            if (calls.isEmpty()) return Spoke(StreamCompleted(usageOf(response)))
            return ToolRequested(
                calls = calls.map { ToolCall(it.id(), it.name(), it.arguments()) },
                usage = usageOf(response),
            )
        }

        /**
         * 도구 정의만 싣기 위한 콜백. `resolveToolDefinitions` 가 콜백에서 정의를
         * 뽑으므로 콜백 자체는 있어야 하는데, **실행은 AgentLoop 가 한다.**
         * 여기가 불렸다면 ChatClient 를 타고 있다는 뜻이므로 조용히 넘어가지 않고
         * 터뜨린다.
         */
        fun neverExecutedCallback(spec: ToolSpec): ToolCallback = object : ToolCallback {
            override fun getToolDefinition(): ToolDefinition =
                DefaultToolDefinition.builder()
                    .name(spec.name)
                    .description(spec.description)
                    .inputSchema(spec.parametersSchema)
                    .build()

            override fun call(toolInput: String): String =
                error("도구는 AgentLoop 가 실행한다. 이 콜백이 불렸다면 ChatClient 경로를 탄 것이다.")

            override fun call(toolInput: String, toolContext: ToolContext?): String = call(toolInput)
        }

        /**
         * 프로바이더의 **기본 옵션 위에** 도구 콜백만 얹는다. 빈
         * `ToolCallingChatOptions` 를 새로 만들면 안 된다 — 프롬프트에 옵션이 실리면
         * 기본 옵션은 병합되는 게 아니라 **통째로 대체된다**. 두 모델의
         * `buildRequestPrompt` 를 바이트코드로 확인했다: 둘 다
         * `prompt.getOptions() == null` 일 때만 모델의 기본 옵션을 끼워 넣고,
         * 아니면 프롬프트 옵션을 그대로 흘린다. 게다가
         * `AnthropicChatModel.resolveAnthropicOptions` 는 프롬프트 옵션이
         * `AnthropicChatOptions` 가 아니면 **빈** `AnthropicChatOptions` 를 만들어
         * 쓰므로, 빈 옵션을 넘기면 `createRequest` 가 `getMaxTokens().intValue()` 에서
         * NPE 로 죽는다. `mutate()` 로 가면 model/maxTokens/캐시 전략/출력 스키마가
         * 그대로 남는다.
         */
        fun withToolCallbacks(base: ChatOptions, tools: List<ToolSpec>): ChatOptions {
            val callbacks = tools.map { neverExecutedCallback(it) }
            val toolCapable = base as? ToolCallingChatOptions
                ?: error(
                    "provider options ${base::class.simpleName} are not ToolCallingChatOptions — " +
                        "tools cannot be sent without dropping the provider's model and max_tokens",
                )
            return toolCapable.mutate().toolCallbacks(callbacks).build()
        }

        /**
         * 거절 판정. `explain()`(`toProviderResult`) 과 `stream()` 이 같은 로직을 쓴다.
         *
         * finishReason 만으로는 부족하다 — 두 프로바이더가 거절을 싣는 자리가 다르다.
         * javap 로 직접 확인했다(Fix round 1, Important 리뷰 대응):
         *
         * - Anthropic: `com.anthropic.models.messages.StopReason` 에 `REFUSAL` 상수가
         *   실존한다. `AnthropicChatModel` 이 `StopReason.toString()` 을 finishReason
         *   문자열로 그대로 싣는 것은 이미 확인돼 있었다(위 커밋 로그 참고) — 그래서
         *   finishReason == "refusal" 비교는 Anthropic 에서는 원래도 맞았다.
         * - OpenAI 호환: `com.openai.models.chat.completions.ChatCompletionChunk.Choice.
         *   FinishReason` 에는 STOP/LENGTH/TOOL_CALLS/CONTENT_FILTER/FUNCTION_CALL 뿐이고
         *   "refusal" 값 자체가 없다 — 실제 거절은 finish_reason="stop" 에 message 의
         *   별도 `refusal` 필드로 온다(스트리밍은 `delta.refusal`). `OpenAiChatModel.
         *   buildGeneration` 이 이 필드를 `AssistantMessage.metadata["refusal"]` 로
         *   옮겨 놓는 것을, 스트리밍 쪽은 `ChunkMerger.chunkToChatCompletion` 이
         *   `delta.refusal()` 을 병합해 같은 `buildGeneration` 을 타는 것까지 바이트코드로
         *   확인했다 — call() 과 stream() 이 같은 변환 경로를 공유한다.
         *
         * 그래서 finishReason == "refusal" 이 원래 맞았던 것은 Anthropic 뿐이고,
         * OpenAI 호환 경로에서는 이 검사가 한 번도 발동한 적이 없었다(REFUSAL 이 이
         * enum 에 없으므로) — 빈 content 가 그대로 "response carried no structured
         * content" 의 Failed 로 떨어졌다. 두 신호를 모두 보게 고쳤다.
         */
        private fun isRefusal(generation: Generation): Boolean {
            if (generation.metadata?.finishReason.equals(REFUSAL, ignoreCase = true)) return true
            // 타입이 있는 접근자가 없다 — AssistantMessage.getMetadata() 는 Map<String, Object>
            // 라 이 캐스팅은 spring-ai-openai 가 "refusal" 이라는 문자열 키로 값을 넣는다는
            // 관례에 기대고 있다. 다음 Spring AI 업그레이드가 그 키 이름을 바꾸면 여기가
            // grep 할 자리다.
            val refusal = generation.output?.metadata?.get("refusal") as? String
            return !refusal.isNullOrBlank()
        }

        /**
         * `ChatResponse` 에서 usage 를 뽑는다. `explain()`(`toProviderResult`) 과
         * `stream()` 이 같은 로직을 쓴다 — 두 벌 두지 않는다.
         */
        private fun usageOf(response: ChatResponse): ProviderUsage {
            val usage = response.metadata.usage
            return ProviderUsage(
                // usage.nativeUsage 는 프로바이더마다 콘크리트 타입이 다르다
                // (Anthropic 은 com.anthropic.models.messages.Usage — javap 로 확인).
                // 그걸 직접 캐스팅하는 대신, spring-ai-model 의 최상위 Usage 인터페이스가
                // 이미 노출하는 getCacheReadInputTokens()/getCacheWriteInputTokens() 를
                // 쓴다 — AnthropicChatModel.getDefaultUsage(...) 가 nativeUsage 에서
                // 캐시 토큰을 뽑아 DefaultUsage 의 이 필드에 채워 넣는 것까지 바이트코드로
                // 확인했다. OpenAI 계열은 캐시 생성 토큰 개념이 없어 이 필드가 null 로
                // 남고(OpenAiChatModel.getDefaultUsage 확인), 여기서 0L 로 떨어진다 —
                // 캐스팅이 없으니 ClassCastException 도 날 수 없다.
                cacheReadTokens = usage.cacheReadInputTokens ?: 0L,
                cacheCreationTokens = usage.cacheWriteInputTokens ?: 0L,
                inputTokens = (usage.promptTokens ?: 0).toLong(),
                outputTokens = (usage.completionTokens ?: 0).toLong(),
            )
        }
    }
}
