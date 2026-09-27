package com.hermes.explain

import com.hermes.context.Bundle
import com.hermes.context.BundleDocument
import com.hermes.context.CitationValidator
import com.hermes.llm.AgentStep
import com.hermes.llm.ExplanationProvider
import com.hermes.llm.ProviderResult
import com.hermes.llm.ProviderUsage
import com.hermes.llm.Spoke
import com.hermes.llm.StreamCompleted
import com.hermes.llm.StreamRefused
import com.hermes.llm.ToolCall
import com.hermes.llm.ToolCallTurn
import com.hermes.llm.ToolRequested
import com.hermes.llm.ToolResultTurn
import com.hermes.llm.ToolSpec
import com.hermes.llm.Turn
import com.hermes.llm.UserTurn
import java.time.Clock
import java.time.Duration
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.ZoneOffset
import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test

private val BUNDLE = Bundle(
    documents = listOf(BundleDocument("concepts/a.md", "내용")),
    raw = "----- FILE: concepts/a.md -----\n내용",
)

private const val INITIAL_FACTS = """{"courseUuid":"abc"}"""

/** 미리 짠 응답을 순서대로 낸다. 각 호출의 tools 인자와 대화를 그 시점 그대로 기록한다. */
private class ScriptedProvider(private val script: List<(onChunk: (String) -> Unit) -> AgentStep>) :
    ExplanationProvider {
    override val name = "scripted"
    val toolsPerCall = mutableListOf<List<String>>()
    val turnsPerCall = mutableListOf<List<Turn>>()
    var calls = 0

    override fun explain(systemText: String, userText: String): ProviderResult =
        error("AgentLoop 은 converse 만 쓴다")

    override fun converse(
        systemText: String,
        turns: List<Turn>,
        tools: List<ToolSpec>,
        onChunk: (String) -> Unit,
    ): AgentStep {
        toolsPerCall.add(tools.map { it.name })
        // 복사하지 않고 그대로 담는다. 루프가 스냅샷을 건네므로 이대로 안전하고,
        // 혹시 살아 있는 리스트를 건네게 되면 turnsPerCall[0] 이 첫 호출이 아니라
        // 마지막 상태를 보여 주게 되어 아래 `hasSize(1)` 단언이 그 자리에서 깨진다.
        turnsPerCall.add(turns)
        return script[calls++](onChunk)
    }
}

private fun answering(citations: String, body: String): (((String) -> Unit) -> AgentStep) = { onChunk ->
    onChunk("""{"citations":[$citations],"explanation":"$body"}""")
    Spoke(StreamCompleted(ProviderUsage(0, 0, 0, 0)))
}

private fun requestingTool(name: String, args: String): (((String) -> Unit) -> AgentStep) = {
    ToolRequested(listOf(ToolCall("call-1", name, args)), ProviderUsage(0, 0, 0, 0))
}

/**
 * 본문을 흘린 **뒤** 도구를 요청한다. 실제 프로바이더는 이러지 않는다 — 도구 델타를
 * onChunk 에 넣지 않으므로 `ToolRequested` 를 낸 호출은 onChunk 를 한 번도 부르지
 * 않는다. 그 불변식은 다른 파일(`SpringAiExplanationProvider`)에 있으므로, 여기서는
 * 일부러 어겨 본다: 그것이 깨져도 루프가 종결 이벤트를 빠뜨리면 안 된다.
 */
private fun answeringThenRequestingTool(
    citations: String,
    body: String,
    args: String,
): (((String) -> Unit) -> AgentStep) = { onChunk ->
    onChunk("""{"citations":[$citations],"explanation":"$body"}""")
    ToolRequested(listOf(ToolCall("call-9", "congestion", args)), ProviderUsage(0, 0, 0, 0))
}

/** 스크립트가 직접 시간을 밀 수 있는 시계. */
private class MovingClock(private var now: Instant) : Clock() {
    override fun getZone(): ZoneId = ZoneOffset.UTC
    override fun withZone(zone: ZoneId?): Clock = this
    override fun instant(): Instant = now
    fun advance(duration: Duration) {
        now = now.plus(duration)
    }
}

/**
 * 루프의 예산·마감·수리. **안전은 여기 없다** — 그것은 AskStreamGateTest 가 지킨다.
 * 여기가 지키는 것은 몇 번 부르는가, 무엇을 실행하는가, 그리고 어느 길로 나가든
 * 종결 이벤트가 정확히 하나라는 것이다.
 */
class AgentLoopTest {

    private val bounds = CourseBounds(setOf(11L), LocalDate.of(2026, 10, 1))
    private val validator = CitationValidator(BUNDLE)
    private val fixedClock = Clock.fixed(Instant.parse("2026-10-01T00:00:00Z"), ZoneOffset.UTC)

    private fun collect(
        provider: ScriptedProvider,
        runner: ToolRunner = ToolRunner { """{"grade":"NORMAL"}""" },
        clock: Clock = fixedClock,
        facts: ToolFacts = ToolFacts(INITIAL_FACTS),
        observer: LoopObserver = LoopObserver { },
    ): List<AskStreamEvent> {
        val events = mutableListOf<AskStreamEvent>()
        AgentLoop(provider, validator, runner, clock, observer = observer).run(
            systemText = BUNDLE.raw,
            baseUserText = "질문",
            bounds = bounds,
            facts = facts,
            emit = events::add,
        )
        // 모든 시나리오가 이것을 진다: SSE 계약은 스트림이 종결 이벤트 하나로 끝나는 것이다.
        assertThat(events.filter { it is DoneEvent || it is UnavailableEvent || it is AbortedEvent })
            .describedAs("종결 이벤트는 정확히 하나여야 한다: %s", events)
            .hasSize(1)
        return events
    }

    @Test
    fun `도구를 안 부르면 모델 호출은 한 번이다`() {
        val provider = ScriptedProvider(listOf(answering(""""concepts/a.md"""", "답")))

        val events = collect(provider)

        assertThat(provider.calls).isEqualTo(1)
        assertThat(events.none { it is LookingEvent }).isTrue()
        assertThat(events.last()).isEqualTo(DoneEvent)
    }

    @Test
    fun `도구를 부르면 looking 뒤에 답이 흐른다`() {
        val provider = ScriptedProvider(
            listOf(
                requestingTool("congestion", """{"attractionId":11,"date":"2026-10-03"}"""),
                answering(""""concepts/a.md"""", "답"),
            ),
        )

        val events = collect(provider)

        assertThat(events.first()).isEqualTo(LookingEvent("congestion"))
        assertThat(events.any { it is CitationsEvent }).isTrue()
        assertThat(events.last()).isEqualTo(DoneEvent)
    }

    @Test
    fun `계속 도구만 요청하면 세 번째 호출에는 도구가 실리지 않는다`() {
        val provider = ScriptedProvider(
            listOf(
                requestingTool("congestion", """{"attractionId":11,"date":"2026-10-02"}"""),
                requestingTool("congestion", """{"attractionId":11,"date":"2026-10-03"}"""),
                answering(""""concepts/a.md"""", "답"),
            ),
        )

        collect(provider)

        assertThat(provider.calls).isEqualTo(3)
        assertThat(provider.toolsPerCall[0]).isNotEmpty()
        assertThat(provider.toolsPerCall[1]).isNotEmpty()
        assertThat(provider.toolsPerCall[2]).isEmpty()
    }

    @Test
    fun `예산이 떨어진 호출에서 또 도구를 부르면 실패로 닫고 멈춘다`() {
        val provider = ScriptedProvider(
            listOf(
                requestingTool("congestion", """{"attractionId":11,"date":"2026-10-02"}"""),
                requestingTool("congestion", """{"attractionId":11,"date":"2026-10-03"}"""),
                requestingTool("congestion", """{"attractionId":11,"date":"2026-10-04"}"""),
            ),
        )

        val events = collect(provider)

        // 끝없이 다시 묻지 않는다. 모델 호출은 예산대로 세 번에서 멈춘다.
        assertThat(provider.calls).isEqualTo(3)
        assertThat(events.filterIsInstance<UnavailableEvent>().single().cause)
            .isEqualTo(FailureCause.STREAM_FAILED)
        // 싣지도 않은 도구를 부른 세 번째 요청은 실행하지 않았다.
        assertThat(events.filterIsInstance<LookingEvent>()).hasSize(2)
    }

    @Test
    fun `인자가 범위를 벗어나면 도구를 실행하지 않고 거부 사유를 되먹인다`() {
        var ran = false
        val provider = ScriptedProvider(
            listOf(
                requestingTool("congestion", """{"attractionId":99,"date":"2026-10-02"}"""),
                answering(""""concepts/a.md"""", "답"),
            ),
        )

        val events = collect(provider, runner = ToolRunner { ran = true; "{}" })

        assertThat(ran).isFalse()
        // 실행하지 않았으므로 조회 중이라고 말하지도 않는다.
        assertThat(events.none { it is LookingEvent }).isTrue()
        assertThat(events.last()).isEqualTo(DoneEvent)
        val fedBack = provider.turnsPerCall[1].filterIsInstance<ToolResultTurn>().single()
        assertThat(fedBack.results.single().contentJson).contains("rejected")
    }

    @Test
    fun `거부된 호출은 facts 에 들어가지 않는다`() {
        val facts = ToolFacts(INITIAL_FACTS)
        val provider = ScriptedProvider(
            listOf(
                requestingTool("congestion", """{"attractionId":99,"date":"2026-10-02"}"""),
                answering(""""concepts/a.md"""", "답"),
            ),
        )

        collect(provider, runner = ToolRunner { "{}" }, facts = facts)

        // 실행되지 않은 조회가 근거로 잡히면 안 된다.
        assertThat(facts.unionJson()).isEqualTo(INITIAL_FACTS)
        assertThat(facts.promptText()).isEmpty()
    }

    @Test
    fun `실행된 호출은 facts 에 들어간다`() {
        val facts = ToolFacts(INITIAL_FACTS)
        val provider = ScriptedProvider(
            listOf(
                requestingTool("congestion", """{"attractionId":11,"date":"2026-10-02"}"""),
                answering(""""concepts/a.md"""", "답"),
            ),
        )

        collect(provider, runner = ToolRunner { """{"grade":"BUSY"}""" }, facts = facts)

        assertThat(facts.unionJson()).contains("BUSY")
        assertThat(facts.promptText()).contains("congestion")
    }

    @Test
    fun `1차 인용 무효 2차 유효면 사용자에게 unavailable 이 가지 않는다`() {
        val provider = ScriptedProvider(
            listOf(
                answering(""""concepts/nope.md"""", "틀린 답"),
                answering(""""concepts/a.md"""", "고친 답"),
            ),
        )

        val events = collect(provider)

        assertThat(events.none { it is UnavailableEvent }).isTrue()
        // 틀린 답은 한 글자도 나가지 않았다 — 게이트가 delta 를 0개로 막았기 때문에
        // 그 이벤트를 삼키는 것이 화면에서 티가 나지 않는다.
        assertThat(events.filterIsInstance<DeltaEvent>().joinToString("") { it.text }).isEqualTo("고친 답")
        assertThat(events.last()).isEqualTo(DoneEvent)
        assertThat(provider.calls).isEqualTo(2)
    }

    @Test
    fun `수리 호출에는 도구가 실리지 않는다`() {
        val provider = ScriptedProvider(
            listOf(
                answering(""""concepts/nope.md"""", "틀린 답"),
                answering(""""concepts/a.md"""", "고친 답"),
            ),
        )

        collect(provider)

        assertThat(provider.toolsPerCall[1]).isEmpty()
        assertThat(provider.turnsPerCall[1].last()).isInstanceOf(UserTurn::class.java)
    }

    @Test
    fun `두 번 다 인용이 무효면 진짜 unavailable 이다`() {
        val provider = ScriptedProvider(
            listOf(
                answering(""""concepts/nope.md"""", "틀린 답"),
                answering(""""concepts/also-nope.md"""", "또 틀린 답"),
            ),
        )

        val events = collect(provider)

        val unavailable = events.filterIsInstance<UnavailableEvent>().single()
        assertThat(unavailable.cause).isEqualTo(FailureCause.INVALID_CITATIONS)
        // 수리는 한 번뿐이다.
        assertThat(provider.calls).isEqualTo(2)
    }

    @Test
    fun `수리 호출이 도구를 부르면 실패로 닫는다`() {
        val provider = ScriptedProvider(
            listOf(
                answering(""""concepts/nope.md"""", "틀린 답"),
                requestingTool("congestion", """{"attractionId":11,"date":"2026-10-02"}"""),
            ),
        )

        val events = collect(provider)

        // 아무것도 내지 않고 끝나는 길은 없다.
        assertThat(events.filterIsInstance<UnavailableEvent>().single().cause)
            .isEqualTo(FailureCause.STREAM_FAILED)
        assertThat(events.none { it is LookingEvent }).isTrue()
        assertThat(provider.calls).isEqualTo(2)
    }

    @Test
    fun `거절은 수리하지 않는다`() {
        val provider = ScriptedProvider(
            listOf(
                { Spoke(StreamRefused("safety")) },
                answering(""""concepts/a.md"""", "고친 답"),
            ),
        )

        val events = collect(provider)

        // 수리는 인용 무효에만 있다. 사유 문자열이 아니라 타입으로 갈라야 한다.
        assertThat(provider.calls).isEqualTo(1)
        assertThat(events.filterIsInstance<UnavailableEvent>().single().cause)
            .isEqualTo(FailureCause.REFUSED)
    }

    @Test
    fun `마감을 넘기면 도구 없는 마지막 호출로 넘어간다`() {
        val movingClock = MovingClock(Instant.parse("2026-10-01T00:00:00Z"))
        val provider = ScriptedProvider(
            listOf(
                {
                    movingClock.advance(Duration.ofSeconds(61))
                    requestingTool("congestion", """{"attractionId":11,"date":"2026-10-02"}""")(it)
                },
                answering(""""concepts/a.md"""", "답"),
            ),
        )

        collect(provider, clock = movingClock)

        assertThat(provider.calls).isEqualTo(2)
        assertThat(provider.toolsPerCall[0]).isNotEmpty()
        assertThat(provider.toolsPerCall[1]).isEmpty()
    }

    @Test
    fun `도구 결과가 다음 호출의 대화에 실린다`() {
        val provider = ScriptedProvider(
            listOf(
                requestingTool("congestion", """{"attractionId":11,"date":"2026-10-03"}"""),
                answering(""""concepts/a.md"""", "답"),
            ),
        )

        collect(provider)

        assertThat(provider.turnsPerCall[0]).hasSize(1)
        val secondCallTurns = provider.turnsPerCall[1]
        assertThat(secondCallTurns[1]).isInstanceOf(ToolCallTurn::class.java)
        assertThat(secondCallTurns[2]).isInstanceOf(ToolResultTurn::class.java)
        assertThat((secondCallTurns[2] as ToolResultTurn).results.single().contentJson)
            .isEqualTo("""{"grade":"NORMAL"}""")
    }

    @Test
    fun `인용 무효를 삼킨 호출이 도구까지 부르면 종결 이벤트 없이 나가지 않는다`() {
        val provider = ScriptedProvider(
            listOf(
                requestingTool("congestion", """{"attractionId":11,"date":"2026-10-02"}"""),
                requestingTool("congestion", """{"attractionId":11,"date":"2026-10-03"}"""),
                // 예산이 떨어진 호출. 인용 무효를 흘린 뒤 도구까지 부른다 —
                // 게이트가 이미 닫혀 있어 STREAM_FAILED 로 닫으려는 시도가 무동작이 된다.
                answeringThenRequestingTool(""""concepts/nope.md"""", "틀린 답", """{"attractionId":11,"date":"2026-10-04"}"""),
                answering(""""concepts/a.md"""", "고친 답"),
            ),
        )

        val events = collect(provider)

        // 삼킨 인용 무효는 사라지지 않는다 — 수리로 이어지고, 수리가 종결 이벤트를 낸다.
        assertThat(events.last()).isEqualTo(DoneEvent)
        assertThat(provider.calls).isEqualTo(4)
        assertThat(provider.toolsPerCall[3]).isEmpty()
        // 싣지도 않은 도구를 부른 호출은 실행하지 않았다.
        assertThat(events.filterIsInstance<LookingEvent>()).hasSize(2)
    }

    @Test
    fun `마감을 넘겼으면 수리하지 않는다`() {
        val movingClock = MovingClock(Instant.parse("2026-10-01T00:00:00Z"))
        val provider = ScriptedProvider(
            listOf(
                {
                    movingClock.advance(Duration.ofSeconds(61))
                    answering(""""concepts/nope.md"""", "틀린 답")(it)
                },
                answering(""""concepts/a.md"""", "고친 답"),
            ),
        )

        val events = collect(provider, clock = movingClock)

        // 마감은 도구 라운드와 수리가 함께 쓴다. 59초에 시작한 수리는 SSE 에미터(90초)를
        // 넘기기 쉽다 — 포기하는 쪽이 에미터가 되면 마감이 있는 이유가 없어진다.
        assertThat(provider.calls).isEqualTo(1)
        assertThat(events.filterIsInstance<UnavailableEvent>().single().cause)
            .isEqualTo(FailureCause.INVALID_CITATIONS)
    }

    // ── LoopObserver ──
    // EvalMain 이 찍는 "tool rounds / budget exhausted / repairs" 는 이 신호들을 그대로
    // 센 것이다. 신호가 실제로 맞는 순간에만 오는지 여기서 직접 본다 — 그렇지 않으면
    // 하네스의 숫자는 관측 대신 우연을 세는 것이 된다.

    @Test
    fun `도구 라운드마다 TOOL_ROUND 가 한 번씩 온다`() {
        // maxToolRounds 는 기본 2다. 라운드 하나만 쓰고 답하면(round 는 그 뒤 1) 아직
        // 예산 안이므로 마지막 호출도 도구를 실은 채 나가고, BUDGET_EXHAUSTED 는 나지
        // 않는다 — 그래서 이 시나리오가 TOOL_ROUND 만 보는 데 맞다.
        val signals = mutableListOf<LoopSignal>()
        val provider = ScriptedProvider(
            listOf(
                requestingTool("congestion", """{"attractionId":11,"date":"2026-10-03"}"""),
                answering(""""concepts/a.md"""", "답"),
            ),
        )

        collect(provider, observer = LoopObserver { signals += it })

        assertThat(signals).containsExactly(LoopSignal.TOOL_ROUND)
    }

    @Test
    fun `BUDGET_EXHAUSTED 는 실행당 최대 한 번이다`() {
        val signals = mutableListOf<LoopSignal>()
        val provider = ScriptedProvider(
            listOf(
                requestingTool("congestion", """{"attractionId":11,"date":"2026-10-02"}"""),
                requestingTool("congestion", """{"attractionId":11,"date":"2026-10-03"}"""),
                // 예산이 떨어진 세 번째 호출. 도구를 또 부르면 실패로 닫는다 — 그래도
                // BUDGET_EXHAUSTED 는 그 루프 턴에서 딱 한 번만 났어야 한다.
                requestingTool("congestion", """{"attractionId":11,"date":"2026-10-04"}"""),
            ),
        )

        collect(provider, observer = LoopObserver { signals += it })

        assertThat(signals.count { it == LoopSignal.BUDGET_EXHAUSTED }).isEqualTo(1)
    }

    @Test
    fun `수리가 실제로 다시 물으면 REPAIR_ASKED 가 온다`() {
        val signals = mutableListOf<LoopSignal>()
        val provider = ScriptedProvider(
            listOf(
                answering(""""concepts/nope.md"""", "틀린 답"),
                answering(""""concepts/a.md"""", "고친 답"),
            ),
        )

        collect(provider, observer = LoopObserver { signals += it })

        assertThat(signals).containsExactly(LoopSignal.REPAIR_ASKED)
    }

    @Test
    fun `마감 때문에 수리를 포기하면 REPAIR_ASKED 는 안 온다`() {
        val signals = mutableListOf<LoopSignal>()
        val movingClock = MovingClock(Instant.parse("2026-10-01T00:00:00Z"))
        val provider = ScriptedProvider(
            listOf(
                {
                    movingClock.advance(Duration.ofSeconds(61))
                    answering(""""concepts/nope.md"""", "틀린 답")(it)
                },
                answering(""""concepts/a.md"""", "고친 답"),
            ),
        )

        collect(provider, clock = movingClock, observer = LoopObserver { signals += it })

        assertThat(signals).doesNotContain(LoopSignal.REPAIR_ASKED)
    }
}
