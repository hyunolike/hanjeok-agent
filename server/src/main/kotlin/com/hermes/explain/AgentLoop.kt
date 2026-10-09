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
import org.slf4j.LoggerFactory

/**
 * 검증을 통과한 인자로 실제 한적을 부른다. 결과 JSON 을 그대로 돌려준다.
 *
 * **던져도 된다.** 네트워크 너머를 부르는 구현이라 타임아웃·5xx·빈 본문이 예외로
 * 올라오는 것이 정상이고, [AgentLoop] 이 그것을 잡아 도구 결과 자리로 되먹인다.
 */
fun interface ToolRunner {
    fun run(args: ToolArgs): String
}

/** 루프가 한 일 중 밖에서는 볼 수 없는 것들. [LoopObserver] 참고. */
enum class LoopSignal {
    /** 도구를 실제로 실행하고 한 바퀴 더 돌았다. */
    TOOL_ROUND,

    /** 예산(라운드 또는 마감)이 떨어져 마지막 호출에 도구를 싣지 않았다. 실행당 최대 1회. */
    BUDGET_EXHAUSTED,

    /** 인용 무효를 삼키고 실제로 다시 물었다. 마감 때문에 수리를 포기한 경우는 내지 않는다. */
    REPAIR_ASKED,
}

/**
 * 루프가 무엇을 했는지 밖에 알린다. **운영은 쓰지 않는다** — 기본값이 무동작이고,
 * 이 자리가 있는 이유는 평가 하네스가 도구 라운드·예산 소진·수리 발동을 **관측**해야
 * 하기 때문이다.
 *
 * 밖에서 추론할 수 없어서 둔다. 이벤트 스트림에는 이 셋이 전혀 나타나지 않고(수리는
 * 인용 무효 이벤트를 삼키는 것이 존재 이유다), 프로바이더를 감싸 "도구 없이 나간
 * 호출"을 세면 예산이 떨어진 호출과 수리 호출을 구분할 수 없다. 그 구분을 프롬프트
 * 문자열로 하면 문구를 다듬는 순간 조용히 깨진다 — 이 저장소가 한 번 데인 방식이다.
 *
 * 재지 않으면 하네스의 숫자는 배포된 것에 대해 아무 말도 하지 못한다. 이 저장소는
 * 이미 한 번 그 실수를 했다(잰 프로바이더와 띄운 프로바이더가 달랐다).
 */
fun interface LoopObserver {
    fun note(signal: LoopSignal)
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
 * 예외로 나가는 길도 없다 — 도구 러너가 던지는 것은 [execute] 가 잡아 되먹인다.
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
    // 예산은 읽을 수 있다. 배선이 이것을 키워도 테스트가 아니라 요금과 멈춘
    // 스트림으로만 드러나므로, 운영 빈의 값을 고정하는 테스트가 읽어야 한다.
    val maxToolRounds: Int = 2,
    val deadlineMs: Long = 60_000L,
    // 기본값은 무동작이다. 운영 배선은 이 인자를 주지 않는다.
    private val observer: LoopObserver = LoopObserver { },
) {

    fun run(
        systemText: String,
        baseUserText: String,
        bounds: CourseBounds,
        facts: ToolFacts,
        citationContext: String = "",
        emit: (AskStreamEvent) -> Unit,
    ) {
        val startedAt = clock.millis()
        val turns = mutableListOf<Turn>(UserTurn(baseUserText))

        var round = 0
        while (true) {
            val outOfBudget = round >= maxToolRounds || pastDeadline(startedAt)
            // 도구를 뺀 호출은 여기서 딱 한 번 나간다 — 그 뒤 attempt 는 Closed 아니면
            // NeedsRepair 이고 둘 다 while 을 빠져나간다.
            if (outOfBudget) observer.note(LoopSignal.BUDGET_EXHAUSTED)
            val tools = if (outOfBudget) emptyList() else CourseTools.specs()

            when (val outcome = attempt(systemText, turns, tools, bounds, facts, citationContext, emit)) {
                is Continued -> {
                    turns.add(ToolCallTurn(outcome.calls))
                    turns.add(ToolResultTurn(outcome.results))
                    round++
                    observer.note(LoopSignal.TOOL_ROUND)
                }
                // 게이트가 done/unavailable/aborted 중 하나를 이미 냈다.
                is Closed -> return
                // 인용이 틀린 것은 사실이 모자라서가 아니라 경로를 잘못 적어서다.
                // 수리는 인용 무효에만 있고, 딱 한 번이며, 도구를 싣지 않는다.
                is NeedsRepair -> {
                    repair(systemText, turns, outcome.reason, startedAt, bounds, facts, citationContext, emit)
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
        startedAt: Long,
        bounds: CourseBounds,
        facts: ToolFacts,
        citationContext: String = "",
        emit: (AskStreamEvent) -> Unit,
    ) {
        // 마감은 도구 라운드와 수리가 **함께** 쓴다. 59초에 시작한 수리는 SSE 에미터의
        // 90초를 넘기기 쉽고, 그러면 포기하는 쪽이 우리가 아니라 에미터가 된다 —
        // 마감이 있는 이유가 바로 그것을 막기 위해서다. 그때는 수리하지 않고 원래의
        // 인용 무효 실패로 닫는다.
        if (pastDeadline(startedAt)) {
            emit(UnavailableEvent(reason, FailureCause.INVALID_CITATIONS))
            return
        }

        // 여기부터가 "수리가 발동했다" 이다. 위에서 마감 때문에 되돌아간 경우는 다시
        // 묻지 않았으므로 세지 않는다.
        observer.note(LoopSignal.REPAIR_ASKED)
        turns.add(UserTurn(repairText(reason)))

        when (val repaired = attempt(systemText, turns, emptyList(), bounds, facts, citationContext, emit)) {
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

    /**
     * 모델을 한 번 부르고, 그 한 번이 무엇으로 끝났는지 돌려준다.
     *
     * 도구를 실행한 [Continued] 말고는 **나가는 문이 `outcome()` 하나다.** 종결 이벤트가
     * 실제로 [emit] 을 통과했는지 여기서 직접 세는 이유는, `gate.fail` 이 **이미 닫힌
     * 게이트에서는 조용한 무동작**이기 때문이다 — 그 경우를 다른 파일의 불변식에 기대
     * 넘기면 아무것도 내지 않고 나가는 길이 생긴다.
     *
     * 기대는 하나 있다: [ToolRequested] 를 낸 호출은 onChunk 를 한 번도 부르지 않는다
     * (`SpringAiExplanationProvider` 가 도구 델타를 onChunk 에 넣지 않는다). 그 불변식이
     * 깨져도 "종결 이벤트 정확히 하나" 는 어긋나지 않는다 — 그때는 게이트가 인용 무효를
     * 삼킨 상태라 `outcome()` 이 [NeedsRepair] 를 내고, 수리 쪽이 종결 이벤트를 낸다.
     * (`인용 무효를 삼킨 호출이 도구까지 부르면...` 테스트가 보는 길이 그것이다.)
     */
    private fun attempt(
        systemText: String,
        turns: List<Turn>,
        tools: List<ToolSpec>,
        bounds: CourseBounds,
        facts: ToolFacts,
        citationContext: String = "",
        emit: (AskStreamEvent) -> Unit,
    ): Attempt {
        val parser = AskStreamParser()
        // 게이트의 출력을 바로 흘리지 않고 한 번 거른다 — 인용 무효면 그 이벤트를
        // 삼키고 수리한다. 분류는 반드시 타입으로 한다. 사유 문자열로 갈랐다가
        // 문구를 다듬는 순간 조용히 깨진 적이 있다.
        var repairReason: String? = null
        var terminated = false
        val gate = AskStreamGate(validator, citationContext) { event ->
            if (event is UnavailableEvent && event.cause == FailureCause.INVALID_CITATIONS) {
                repairReason = event.reason
            } else {
                if (isTerminal(event)) terminated = true
                emit(event)
            }
        }

        fun outcome(): Attempt {
            val reason = repairReason
            return when {
                reason != null -> NeedsRepair(reason)
                terminated -> Closed
                // **오늘 이 가지는 도달 불가다.** 게이트에서 종결 이벤트가 나가는 문은
                // `fail()` 과 `finish()` 둘뿐이고 둘 다 닫으면서 이벤트를 낸다. 그래서
                // "닫혔다" 는 곧 `repairReason != null`(인용 무효를 삼켰다) 아니면
                // `terminated`(하나 내보냈다) 다 — 위 두 갈래가 그것을 전부 먹는다.
                // 증거도 있다: 이 `else` 를 통째로 지워도 스위트가 전부 통과한다.
                // 도구 러너가 던지는 경우도 여기로 오지 않는다 — [execute] 가 잡아
                // 도구 결과로 되먹이므로 그 길은 [Continued] 로 나간다.
                //
                // 그래도 남겨 둔다. "종결 이벤트 정확히 하나" 는 이 파일 밖(게이트의
                // 닫힘 규칙)에 근거를 둔 성질이고, 그 규칙이 바뀌면 여기가 유일하게
                // 남는 그물이다. 값은 `if` 하나다.
                else -> {
                    emit(UnavailableEvent(NO_TERMINAL, FailureCause.STREAM_FAILED))
                    Closed
                }
            }
        }

        // 스냅샷을 건넨다. 이 리스트는 루프가 계속 키우는 것이라, 참조를 넘기면
        // 협력자가 나중에 바뀌는 대화를 들고 있게 된다.
        val step = provider.converse(systemText, turns.toList(), tools) { chunk ->
            parser.feed(chunk).forEach(gate::accept)
        }

        if (step is ToolRequested) {
            // 예산이 떨어진 호출에는 도구를 싣지 않았다. 그런데도 도구를 부른다면
            // 정상 상황이 아니다 — 여기서 실행하거나 다시 물으면 예산 밖에서 끝없이
            // 돈다. 안전한 실패가 무한한 지출보다 낫다.
            if (tools.isEmpty()) {
                gate.fail(UNOFFERED_TOOL, FailureCause.STREAM_FAILED)
                return outcome()
            }
            return Continued(step.calls, execute(step.calls, bounds, facts, emit))
        }

        when (val end = (step as Spoke).end) {
            is StreamCompleted -> gate.finish(parser.complete)
            is StreamRefused -> gate.fail(refusalReason(end.category), FailureCause.REFUSED)
            is StreamFailed -> gate.fail(end.reason, FailureCause.STREAM_FAILED)
        }

        return outcome()
    }

    private fun isTerminal(event: AskStreamEvent): Boolean =
        event is DoneEvent || event is UnavailableEvent || event is AbortedEvent

    private fun pastDeadline(startedAt: Long): Boolean = clock.millis() - startedAt > deadlineMs

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
                // 러너는 네트워크 너머를 부른다. 타임아웃·5xx·빈 본문은 드문 일이 아니고,
                // 그 예외가 여기를 그냥 지나면 run() 이 종결 이벤트를 하나도 내지 못한 채
                // 끝난다 — 독자는 이미 looking 을 본 뒤다. 그 뒤를 프런트엔드가
                // `done` 없는 스트림을 unavailable 로 합성해 덮고 있었는데, 불변식을
                // 그것에 기대는 것이 이 브랜치가 이미 한 번 고친 결함의 모양이다.
                //
                // 그래서 **되먹인다.** 거부된 인자와 같은 처리이고, 설계 문서가 거부에
                // 대해 적은 이유가 그대로 적용된다 — "던지면 한 번 잘못 부른 것이 요청
                // 전체를 죽인다". 조회 하나가 실패했다고 답 전체를 없애는 것보다, 모델이
                // 그 조회 없이 답하게 두는 편이 독자에게 낫다. 실패가 이어져도 예산이
                // 묶는다: 도구 라운드는 여전히 최대 [maxToolRounds] 회다.
                //
                // 타입을 좁히지 않고 Exception 을 잡는다. [ToolRunner] 는 포트이고 루프는
                // 그 너머에 무엇이 있는지 모른다 — 특정 예외만 잡으면 러너를 갈아끼우는
                // 순간 이 불변식이 조용히 다시 깨진다.
                val result = try {
                    toolRunner.run(args)
                } catch (e: Exception) {
                    // 원인이 관찰되는 자리는 이 로그뿐이다. 되먹이는 문구에는 싣지 않는다 —
                    // 모델 문맥에 들어간 내부 사정은 본문으로 새어 나올 자리가 된다.
                    log.warn("tool {} failed; feeding the failure back to the model", call.name, e)
                    null
                }
                // 가져오지 못한 사실은 facts 합집합에 넣지 않는다. 거부와 같은 이유다.
                if (result == null) {
                    ToolResult(call.id, LOOKUP_FAILED)
                } else {
                    facts.add(call.name, call.argumentsJson, result)
                    ToolResult(call.id, result)
                }
            }
        }
    }

    private fun repairText(reason: String): String =
        "직전 답의 인용이 유효하지 않다: $reason\n" +
            "system 블록의 `----- FILE: 경로 -----` 마커에 실제로 있는 경로만 citations 에 넣어 다시 답하라."

    private fun quote(text: String): String = MAPPER.writeValueAsString(text)

    private companion object {
        val MAPPER = ObjectMapper()

        val log = LoggerFactory.getLogger(AgentLoop::class.java)

        /**
         * 도구 호출이 예외로 끝났을 때 모델에게 돌려주는 결과. **고정 문구다** —
         * 러너가 남긴 메시지에는 주소나 상태 코드 같은 내부 사정이 섞이고, 그것이
         * 모델 문맥에 들어가면 본문으로 새어 나올 자리가 생긴다.
         */
        const val LOOKUP_FAILED = """{"unavailable":"lookup failed"}"""

        /** 제안하지 않은 도구를 모델이 부른 경우. 정상 응답이 아니므로 실패로 닫는다. */
        const val UNOFFERED_TOOL = "tool requested when no tools were offered"

        /**
         * 한 호출이 아무 종결 이벤트도 내지 못하고 끝난 경우. 스트림을 열어 둔 채
         * 나가지 않는다. 오늘은 도달 불가다 — `outcome()` 의 주석 참고.
         */
        const val NO_TERMINAL = "stream ended with no terminal event"
    }
}
