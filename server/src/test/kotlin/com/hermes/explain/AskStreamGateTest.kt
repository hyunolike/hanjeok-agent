package com.hermes.explain

import com.hermes.context.BundleLoader
import com.hermes.context.CitationValidator
import com.hermes.llm.BodyText
import com.hermes.llm.CitationsClosed
import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test

/**
 * 이 테스트 파일이 이 기능의 존재 이유다: 검증 안 된 글자는 한 글자도 나가지 않는다.
 */
class AskStreamGateTest {

    private val bundle = BundleLoader.load()
    private val known = bundle.paths().first()
    private val validator = CitationValidator(bundle)

    private fun gate(): Pair<AskStreamGate, MutableList<AskStreamEvent>> {
        val out = mutableListOf<AskStreamEvent>()
        return AskStreamGate(validator) { out += it } to out
    }

    private fun deltas(out: List<AskStreamEvent>) = out.filterIsInstance<DeltaEvent>()

    @Test
    fun `인용 먼저 + 유효 — 인용 뒤 본문이 흐르고 끝난다`() {
        val (g, out) = gate()

        g.accept(CitationsClosed(listOf(known)))
        g.accept(BodyText("안"))
        g.accept(BodyText("녕"))
        g.finish(parseComplete = true)

        assertThat(out).containsExactly(
            CitationsEvent(listOf(known)),
            DeltaEvent("안"),
            DeltaEvent("녕"),
            DoneEvent,
        )
    }

    @Test
    fun `인용 먼저 + 무효 — delta 없이 unavailable`() {
        val (g, out) = gate()

        g.accept(CitationsClosed(listOf("not/in/bundle.md")))
        g.accept(BodyText("새면 안 되는 문장"))
        g.finish(parseComplete = true)

        assertThat(deltas(out)).isEmpty()
        assertThat(out).containsExactly(
            UnavailableEvent("citations not in bundle: not/in/bundle.md", FailureCause.INVALID_CITATIONS),
        )
    }

    @Test
    fun `본문 먼저 + 유효 — 쥐고 있다가 인용 검증 뒤 한 번에 낸다`() {
        val (g, out) = gate()

        g.accept(BodyText("앞"))
        g.accept(BodyText("뒤"))
        assertThat(deltas(out)).describedAs("검증 전에는 아무것도 나가지 않는다").isEmpty()

        g.accept(CitationsClosed(listOf(known)))
        g.finish(parseComplete = true)

        assertThat(out).containsExactly(CitationsEvent(listOf(known)), DeltaEvent("앞뒤"), DoneEvent)
    }

    @Test
    fun `본문 먼저 + 무효 — 쥔 본문을 버리고 delta 없이 unavailable`() {
        val (g, out) = gate()

        g.accept(BodyText("새면 안 되는 문장"))
        g.accept(CitationsClosed(listOf("not/in/bundle.md")))
        g.finish(parseComplete = true)

        assertThat(deltas(out)).isEmpty()
        assertThat(out.single()).isInstanceOf(UnavailableEvent::class.java)
    }

    @Test
    fun `빈 인용은 기존과 같은 사유로 unavailable`() {
        val (g, out) = gate()

        g.accept(CitationsClosed(emptyList()))

        assertThat(out).containsExactly(UnavailableEvent("no citations", FailureCause.INVALID_CITATIONS))
    }

    @Test
    fun `본문을 보낸 뒤의 실패는 aborted 다 — unavailable 이 아니다`() {
        val (g, out) = gate()

        g.accept(CitationsClosed(listOf(known)))
        g.accept(BodyText("미완"))
        g.fail("IOException: reset", FailureCause.STREAM_FAILED)

        assertThat(out.last()).isEqualTo(AbortedEvent("IOException: reset", FailureCause.STREAM_FAILED))
    }

    @Test
    fun `본문을 보내기 전의 실패는 unavailable 이다`() {
        val (g, out) = gate()

        g.accept(CitationsClosed(listOf(known)))
        g.fail("refusal (unknown)", FailureCause.REFUSED)

        assertThat(out).containsExactly(
            CitationsEvent(listOf(known)),
            UnavailableEvent("refusal (unknown)", FailureCause.REFUSED),
        )
    }

    @Test
    fun `인용 없이 스트림이 끝나면 잘린 응답으로 unavailable`() {
        val (g, out) = gate()

        g.accept(BodyText("쥔 본문"))
        g.finish(parseComplete = false)

        assertThat(deltas(out)).isEmpty()
        assertThat(out).containsExactly(UnavailableEvent("truncated response", FailureCause.TRUNCATED))
    }

    @Test
    fun `본문이 닫히기 전에 끝나면 보낸 뒤라 aborted`() {
        val (g, out) = gate()

        g.accept(CitationsClosed(listOf(known)))
        g.accept(BodyText("잘리"))
        g.finish(parseComplete = false)

        assertThat(out.last()).isEqualTo(AbortedEvent("truncated response", FailureCause.TRUNCATED))
    }

    @Test
    fun `인용은 유효한데 본문이 한 글자도 없으면 done 이 아니라 unavailable`() {
        // 블로킹 경로(SpringAiExplanationProvider)는 빈 본문을 Failed 로 본다. 여기서
        // DoneEvent 를 내면 두 경로가 같은 입력({"citations":[...],"explanation":""})에
        // 다르게 답하고, 화면은 인용 칩만 있고 글자 없는 "답변완료" 버블을 그린다.
        val (g, out) = gate()

        g.accept(CitationsClosed(listOf(known)))
        g.finish(parseComplete = true)

        assertThat(deltas(out)).isEmpty()
        assertThat(out).containsExactly(
            CitationsEvent(listOf(known)),
            UnavailableEvent("empty answer", FailureCause.EMPTY),
        )
    }

    @Test
    fun `인용이 무효면 cause 가 INVALID_CITATIONS 다`() {
        val events = mutableListOf<AskStreamEvent>()
        val gate = AskStreamGate(validator, events::add)

        gate.accept(CitationsClosed(listOf("concepts/nope.md")))

        val unavailable = events.filterIsInstance<UnavailableEvent>().single()
        assertThat(unavailable.cause).isEqualTo(FailureCause.INVALID_CITATIONS)
    }

    @Test
    fun `본문이 비면 cause 가 EMPTY 다`() {
        val events = mutableListOf<AskStreamEvent>()
        val gate = AskStreamGate(validator, events::add)

        gate.accept(CitationsClosed(listOf(known)))
        gate.finish(parseComplete = true)

        val unavailable = events.filterIsInstance<UnavailableEvent>().single()
        assertThat(unavailable.cause).isEqualTo(FailureCause.EMPTY)
    }

    @Test
    fun `잘린 응답은 cause 가 TRUNCATED 다`() {
        val events = mutableListOf<AskStreamEvent>()
        val gate = AskStreamGate(validator, events::add)

        gate.accept(CitationsClosed(listOf(known)))
        gate.accept(BodyText("일부"))
        gate.finish(parseComplete = false)

        val aborted = events.filterIsInstance<AbortedEvent>().single()
        assertThat(aborted.cause).isEqualTo(FailureCause.TRUNCATED)
    }

    @Test
    fun `끝난 뒤에 온 이벤트는 무시한다`() {
        val (g, out) = gate()

        g.accept(CitationsClosed(listOf("not/in/bundle.md")))
        g.accept(CitationsClosed(listOf(known)))
        g.accept(BodyText("늦게 온 본문"))
        g.finish(parseComplete = true)

        assertThat(out).hasSize(1)
        assertThat(deltas(out)).isEmpty()
    }
}
