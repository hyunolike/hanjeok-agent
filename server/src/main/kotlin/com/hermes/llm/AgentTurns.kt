package com.hermes.llm

/**
 * 도구 루프가 쌓아 가는 대화. 프레임워크 타입이 아니다 — 포트가 존재하는 이유가
 * 서비스 계층과 테스트 페이크를 Spring AI 없이 돌리는 것이기 때문이다.
 */
sealed interface Turn

data class UserTurn(val text: String) : Turn

/** 모델이 낸 도구 호출. 다음 요청에 그대로 되실어야 모델이 문맥을 잃지 않는다. */
data class ToolCallTurn(val calls: List<ToolCall>) : Turn

data class ToolResultTurn(val results: List<ToolResult>) : Turn

data class ToolCall(val id: String, val name: String, val argumentsJson: String)

data class ToolResult(val id: String, val contentJson: String)

data class ToolSpec(val name: String, val description: String, val parametersSchema: String)

sealed interface AgentStep

/**
 * 모델이 도구를 부르려 한다.
 *
 * **이 값이 나왔다면 onChunk 는 한 번도 불리지 않았다.** 어댑터가 도구 델타를
 * onChunk 에 넣지 않기 때문이고, 그래서 도구 턴은 AskStreamGate 에 도달하지 않는다.
 */
data class ToolRequested(
    val calls: List<ToolCall>,
    /**
     * **예산 집계에 쓰지 마라.** OpenAI 스트리밍에서는 도구 호출로 끝난 턴에 사용량이
     * 실려 오지 않아 네 값이 전부 0 이다. 0 을 그대로 더하면 토큰 예산이나 비용 한도가
     * "아직 한 푼도 안 썼다"고 읽고 그대로 통과시킨다 — 틀린 값을 믿는 쪽이 값이 없는
     * 것보다 나쁘다. 실제 사용량이 필요하면 [Spoke] 로 끝난 턴의 [StreamCompleted] 를
     * 봐야 한다.
     */
    val usage: ProviderUsage,
) : AgentStep

/** 모델이 답했다. 조각은 onChunk 로 이미 나갔다. */
data class Spoke(val end: StreamEnd) : AgentStep
