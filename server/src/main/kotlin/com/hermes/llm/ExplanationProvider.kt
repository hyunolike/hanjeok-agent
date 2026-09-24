package com.hermes.llm

import com.fasterxml.jackson.databind.ObjectMapper

data class Explanation(val explanation: String, val citations: List<String>)

data class ProviderUsage(
    val cacheReadTokens: Long,
    val cacheCreationTokens: Long,
    val inputTokens: Long,
    val outputTokens: Long,
)

sealed interface ProviderResult

data class Answered(val explanation: Explanation, val usage: ProviderUsage) : ProviderResult

/** HTTP 200 에 stop_reason=refusal. content 는 비어 있으므로 읽기 전에 갈라야 한다. */
data class Refused(val category: String?) : ProviderResult

data class Failed(val reason: String) : ProviderResult

/** stream() 이 어떻게 끝났는가. 조각은 onChunk 로 이미 나갔다. */
sealed interface StreamEnd

data class StreamCompleted(val usage: ProviderUsage) : StreamEnd

data class StreamRefused(val category: String?) : StreamEnd

data class StreamFailed(val reason: String) : StreamEnd

private val STREAM_MAPPER = ObjectMapper()

/**
 * 프로바이더 교체 지점.
 *
 * 이 포트가 있는 이유는 하나다 — Anthropic 직접 호출과 OpenRouter 무료 티어를
 * **같은 프롬프트와 같은 검증** 아래에서 비교하기 위해서다. 비교가 서로 다른
 * 조립 경로를 타면 측정하는 것은 모델이 아니라 프롬프트가 된다.
 */
interface ExplanationProvider {
    val name: String

    fun explain(systemText: String, userText: String): ProviderResult

    /**
     * 모델이 조각을 보낼 때마다 onChunk 를 부른다. 조각은 모델이 낸 JSON 텍스트 그대로다 —
     * 해독은 AskStreamParser 가, 검증은 AskStreamGate 가 한다.
     *
     * 기본 구현은 explain() 결과를 조각 하나로 낸다. 스트리밍하지 않는 프로바이더와
     * 테스트 페이크가 같은 계약을 쓸 수 있고, 같은 explain() 을 거치므로 프롬프트
     * 조립이 갈라지지 않는다. 인용을 먼저 두는 것은 실제 모델이 스키마 순서대로
     * 내보내는 것과 맞추기 위해서다 — 안전은 이 순서에 의존하지 않는다.
     */
    fun stream(systemText: String, userText: String, onChunk: (String) -> Unit): StreamEnd =
        when (val result = explain(systemText, userText)) {
            is Answered -> {
                onChunk(
                    STREAM_MAPPER.writeValueAsString(
                        linkedMapOf(
                            "citations" to result.explanation.citations,
                            "explanation" to result.explanation.explanation,
                        ),
                    ),
                )
                StreamCompleted(result.usage)
            }
            is Refused -> StreamRefused(result.category)
            is Failed -> StreamFailed(result.reason)
        }

    /**
     * 도구를 쓸 수 있는 대화. 도구를 부르지 않으면 [stream] 과 같은 경로다.
     *
     * 기본 구현은 도구를 무시하고 마지막 사용자 턴만 [stream] 에 넘긴다. 스트리밍만
     * 하고 도구를 모르는 프로바이더와 테스트 페이크가 같은 계약을 쓸 수 있고, 같은
     * explain() 을 거치므로 프롬프트 조립이 갈라지지 않는다.
     */
    fun converse(
        systemText: String,
        turns: List<Turn>,
        tools: List<ToolSpec>,
        onChunk: (String) -> Unit,
    ): AgentStep = Spoke(
        stream(
            systemText,
            turns.filterIsInstance<UserTurn>().lastOrNull()?.text
                ?: error("converse called with no user turn"),
            onChunk,
        ),
    )
}
