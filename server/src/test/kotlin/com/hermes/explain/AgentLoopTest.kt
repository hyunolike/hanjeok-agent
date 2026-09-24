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
        // 루프가 건네는 리스트는 계속 커지는 같은 객체다. 스냅샷을 떠 두지 않으면
        // 나중에 읽는 turnsPerCall[0] 이 첫 호출이 아니라 마지막 상태를 보여 준다.
        turnsPerCall.add(turns.toList())
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
    ): List<AskStreamEvent> {
        val events = mutableListOf<AskStreamEvent>()
        AgentLoop(provider, validator, runner, clock).run(
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
        var now = Instant.parse("2026-10-01T00:00:00Z")
        val movingClock = object : Clock() {
            override fun getZone() = ZoneOffset.UTC
            override fun withZone(zone: ZoneId?) = this
            override fun instant(): Instant = now
        }
        val provider = ScriptedProvider(
            listOf(
                {
                    now = now.plus(Duration.ofSeconds(61))
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
}
