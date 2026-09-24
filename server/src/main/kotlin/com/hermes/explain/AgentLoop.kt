package com.hermes.explain

import com.fasterxml.jackson.databind.ObjectMapper
import com.hermes.context.CitationValidator
import com.hermes.llm.AskStreamParser
import com.hermes.llm.ExplanationProvider
import com.hermes.llm.Spoke
import com.hermes.llm.StreamCompleted
import com.hermes.llm.StreamFailed
import com.hermes.llm.StreamRefused
import com.hermes.llm.ToolCall
import com.hermes.llm.ToolCallTurn
import com.hermes.llm.ToolRequested
import com.hermes.llm.ToolResult
import com.hermes.llm.ToolResultTurn
import com.hermes.llm.ToolSpec
import com.hermes.llm.Turn
import com.hermes.llm.UserTurn
import java.time.Clock

/** 검증을 통과한 인자로 실제 한적을 부른다. 결과 JSON 을 그대로 돌려준다. */
fun interface ToolRunner {
    fun run(args: ToolArgs): String
}

/**
 * 도구 루프. **안전 판단은 하지 않는다** — 그것은 [AskStreamGate] 가 한다.
 * 여기가 정하는 것은 몇 번 더 물을 것인가, 무엇을 실행해도 되는가, 언제 포기하는가다.
 *
 * 예산이 떨어지면 실패가 아니라 "가진 걸로 답하라" 다. 마지막 호출은 도구를 **아예 빼고**
 * 보내므로 모델이 다시 부르는 것이 구조적으로 불가능하다. 그래도 부르면 그건 정상 상황이
 * 아니므로 [FailureCause.STREAM_FAILED] 로 닫는다 — 끝없이 돈을 쓰느니 안전하게 실패한다.
 *
 * **[run] 에서 나가는 모든 길은 종결 이벤트를 정확히 하나 낸 뒤다.** SSE 계약이 그렇다.
 * 그 성질은 [Attempt] 세 갈래가 지킨다:
 * - [Closed] — [attempt] 안에서 게이트가 이미 종결 이벤트를 하나 냈다. 그대로 return.
 * - [NeedsRepair] — 아직 아무것도 내지 않았다. 부르는 쪽이 수리하거나 직접 낸다.
 * - [Continued] — 아직 아무것도 내지 않았다. 루프가 한 바퀴 더 돈다.
 */
class AgentLoop(
    private val provider: ExplanationProvider,
    private val validator: CitationValidator,
    private val toolRunner: ToolRunner,
    private val clock: Clock,
    private val maxToolRounds: Int = 2,
    private val deadlineMs: Long = 60_000L,
) {

    fun run(
        systemText: String,
        baseUserText: String,
        bounds: CourseBounds,
        facts: ToolFacts,
        emit: (AskStreamEvent) -> Unit,
    ) {
        val startedAt = clock.millis()
        val turns = mutableListOf<Turn>(UserTurn(baseUserText))

        var round = 0
        while (true) {
            val outOfBudget = round >= maxToolRounds || clock.millis() - startedAt > deadlineMs
            val tools = if (outOfBudget) emptyList() else CourseTools.specs()

            when (val outcome = attempt(systemText, turns, tools, bounds, facts, emit)) {
                is Continued -> {
                    turns.add(ToolCallTurn(outcome.calls))
                    turns.add(ToolResultTurn(outcome.results))
                    round++
                }
                // 게이트가 done/unavailable/aborted 중 하나를 이미 냈다.
                is Closed -> return
                // 인용이 틀린 것은 사실이 모자라서가 아니라 경로를 잘못 적어서다.
                // 수리는 인용 무효에만 있고, 딱 한 번이며, 도구를 싣지 않는다.
                is NeedsRepair -> {
                    repair(systemText, turns, outcome.reason, bounds, facts, emit)
                    return
                }
            }
        }
    }

    /**
     * 수리 턴. 도구는 싣지 않는다 — 여기서 나가는 세 갈래도 전부 종결 이벤트를 하나 낸다.
     *
     * 이것이 사용자에게 보이지 않는 이유는 게이트의 불변식이다: 인용이 무효일 때 그
     * 앞의 [DeltaEvent] 는 0개다. 사용자는 아직 한 글자도 못 봤으므로 그 이벤트 하나를
     * 삼키고 다시 묻는 것이 화면에서 티가 나지 않는다.
     */
    private fun repair(
        systemText: String,
        turns: MutableList<Turn>,
        reason: String,
        bounds: CourseBounds,
        facts: ToolFacts,
        emit: (AskStreamEvent) -> Unit,
    ) {
        turns.add(UserTurn(repairText(reason)))

        when (val repaired = attempt(systemText, turns, emptyList(), bounds, facts, emit)) {
            // 두 번째도 인용이 무효다. 이번엔 삼키지 않는다 — 수리는 한 번뿐이다.
            is NeedsRepair -> emit(UnavailableEvent(repaired.reason, FailureCause.INVALID_CITATIONS))
            is Closed -> Unit
            // 도구를 싣지 않았으므로 attempt 는 여기서 Continued 를 내지 못한다(냈다면
            // 도구 요청을 STREAM_FAILED 로 닫았을 것이다). 그래도 남겨 둔다 — 이 가지가
            // 도달 불가라는 사실보다 "모든 길이 종결 이벤트를 낸다"는 성질이 중요하다.
            is Continued -> emit(UnavailableEvent(UNOFFERED_TOOL, FailureCause.STREAM_FAILED))
        }
    }

    private sealed interface Attempt

    /** 도구를 실행했다. 아직 종결 이벤트는 없다. */
    private data class Continued(val calls: List<ToolCall>, val results: List<ToolResult>) : Attempt

    /** 게이트가 종결 이벤트를 하나 냈다. 더 할 일이 없다. */
    private data object Closed : Attempt

    /** 인용 무효를 삼켰다. 종결 이벤트는 아직 없고, 부르는 쪽이 반드시 하나 내야 한다. */
    private data class NeedsRepair(val reason: String) : Attempt

    private fun attempt(
        systemText: String,
        turns: List<Turn>,
        tools: List<ToolSpec>,
        bounds: CourseBounds,
        facts: ToolFacts,
        emit: (AskStreamEvent) -> Unit,
    ): Attempt {
        val parser = AskStreamParser()
        // 게이트의 출력을 바로 흘리지 않고 한 번 거른다 — 인용 무효면 그 이벤트를
        // 삼키고 수리한다. 분류는 반드시 타입으로 한다. 사유 문자열로 갈랐다가
        // 문구를 다듬는 순간 조용히 깨진 적이 있다.
        var repairReason: String? = null
        val gate = AskStreamGate(validator) { event ->
            if (event is UnavailableEvent && event.cause == FailureCause.INVALID_CITATIONS) {
                repairReason = event.reason
            } else {
                emit(event)
            }
        }

        val step = provider.converse(systemText, turns, tools) { chunk ->
            parser.feed(chunk).forEach(gate::accept)
        }

        if (step is ToolRequested) {
            // 예산이 떨어진 호출에는 도구를 싣지 않았다. 그런데도 도구를 부른다면
            // 정상 상황이 아니다 — 여기서 실행하거나 다시 물으면 예산 밖에서 끝없이
            // 돈다. 안전한 실패가 무한한 지출보다 낫다.
            if (tools.isEmpty()) {
                gate.fail(UNOFFERED_TOOL, FailureCause.STREAM_FAILED)
                return Closed
            }
            return Continued(step.calls, execute(step.calls, bounds, facts, emit))
        }

        when (val end = (step as Spoke).end) {
            is StreamCompleted -> gate.finish(parser.complete)
            is StreamRefused -> gate.fail(refusalReason(end.category), FailureCause.REFUSED)
            is StreamFailed -> gate.fail(end.reason, FailureCause.STREAM_FAILED)
        }

        return repairReason?.let { NeedsRepair(it) } ?: Closed
    }

    private fun execute(
        calls: List<ToolCall>,
        bounds: CourseBounds,
        facts: ToolFacts,
        emit: (AskStreamEvent) -> Unit,
    ): List<ToolResult> = calls.map { call ->
        when (val args = CourseTools.parse(call, bounds)) {
            // 거부는 실행하지 않는다. "조회 중" 이라고 말하지도 않고, facts 합집합에도
            // 넣지 않는다 — 실행되지 않은 조회가 근거로 잡히면 안 된다.
            is Rejected -> ToolResult(call.id, """{"rejected":${quote(args.reason)}}""")
            else -> {
                emit(LookingEvent(call.name))
                val result = toolRunner.run(args)
                facts.add(call.name, call.argumentsJson, result)
                ToolResult(call.id, result)
            }
        }
    }

    private fun repairText(reason: String): String =
        "직전 답의 인용이 유효하지 않다: $reason\n" +
            "system 블록의 `----- FILE: 경로 -----` 마커에 실제로 있는 경로만 citations 에 넣어 다시 답하라."

    private fun quote(text: String): String = MAPPER.writeValueAsString(text)

    private companion object {
        val MAPPER = ObjectMapper()

        /** 제안하지 않은 도구를 모델이 부른 경우. 정상 응답이 아니므로 실패로 닫는다. */
        const val UNOFFERED_TOOL = "tool requested when no tools were offered"
    }
}
