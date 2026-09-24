package com.hermes.explain

import com.hermes.context.BundleLoader
import com.hermes.context.CitationValidator
import com.hermes.context.PromptAssembler
import com.hermes.llm.Answered
import com.hermes.llm.Explanation
import com.hermes.llm.ExplanationProvider
import com.hermes.llm.ProviderResult
import com.hermes.llm.ProviderUsage
import com.hermes.llm.Refused
import com.hermes.llm.StreamCompleted
import com.hermes.llm.StreamEnd
import com.hermes.llm.StreamFailed
import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test

class CourseQuestionStreamTest {

    private val bundle = BundleLoader.load()
    private val known = bundle.paths().first()
    private val facts = BackendFacts("course-1", """{"courseUuid":"course-1"}""")

    /** 두 경로가 받은 텍스트를 기록하고, stream 은 주어진 조각을 흘린다. */
    private class Recorder(
        private val chunks: List<String>,
        private val end: StreamEnd = StreamCompleted(ProviderUsage(0, 0, 0, 0)),
    ) : ExplanationProvider {
        override val name = "recorder"
        val explained = mutableListOf<Pair<String, String>>()
        val streamed = mutableListOf<Pair<String, String>>()

        override fun explain(systemText: String, userText: String): ProviderResult {
            explained += systemText to userText
            return Answered(Explanation("x", listOf("a.md")), ProviderUsage(0, 0, 0, 0))
        }

        override fun stream(systemText: String, userText: String, onChunk: (String) -> Unit): StreamEnd {
            streamed += systemText to userText
            chunks.forEach(onChunk)
            return end
        }
    }

    private fun service(provider: ExplanationProvider) =
        CourseQuestionService(PromptAssembler(bundle), CitationValidator(bundle), provider)

    @Test
    fun `스트리밍과 비스트리밍이 같은 system 과 user 텍스트를 조립한다`() {
        val recorder = Recorder(listOf("""{"citations":["$known"],"explanation":"x"}"""))
        val history = listOf(QuestionTurn("앞 질문", "앞 답"))

        service(recorder).ask(facts, "질문", history)
        service(recorder).askStream(facts, "질문", history) {}

        // 이 동일성이 캐시가 유지되고 하네스 숫자가 스트리밍에도 유효하다는 근거다.
        assertThat(recorder.streamed.single()).isEqualTo(recorder.explained.single())
    }

    @Test
    fun `조각을 해독하고 검증해 이벤트로 낸다`() {
        val recorder = Recorder(listOf("""{"citations":["$known"],""", """"explanation":"가나"}"""))
        val out = mutableListOf<AskStreamEvent>()

        service(recorder).askStream(facts, "질문", emptyList()) { out += it }

        assertThat(out.first()).isEqualTo(CitationsEvent(listOf(known)))
        assertThat(out.filterIsInstance<DeltaEvent>().joinToString("") { it.text }).isEqualTo("가나")
        assertThat(out.last()).isEqualTo(DoneEvent)
    }

    @Test
    fun `무효 인용이면 본문이 한 글자도 나가지 않는다`() {
        val recorder = Recorder(listOf("""{"citations":["not/in/bundle.md"],"explanation":"새면 안 됨"}"""))
        val out = mutableListOf<AskStreamEvent>()

        service(recorder).askStream(facts, "질문", emptyList()) { out += it }

        assertThat(out.filterIsInstance<DeltaEvent>()).isEmpty()
        assertThat(out.single()).isInstanceOf(UnavailableEvent::class.java)
    }

    @Test
    fun `프로바이더가 본문 도중 실패하면 aborted`() {
        val recorder = Recorder(
            listOf("""{"citations":["$known"],"explanation":"미"""),
            end = StreamFailed("IOException: reset"),
        )
        val out = mutableListOf<AskStreamEvent>()

        service(recorder).askStream(facts, "질문", emptyList()) { out += it }

        assertThat(out.last()).isEqualTo(AbortedEvent("IOException: reset", FailureCause.STREAM_FAILED))
    }

    @Test
    fun `스트림이 정상 종료됐는데 JSON 이 안 닫히면 aborted 로 끝난다`() {
        // StreamCompleted (정상 종료) 인데 본문 문자열이 닫히지 않은 채 끝난다 — 모델이
        // max_tokens 로 잘렸을 때의 모양이다. finish 가 parser.complete 를 보지 않으면
        // 미완성 문장을 DoneEvent 로 확정해 버린다.
        val recorder = Recorder(listOf("""{"citations":["$known"],"explanation":"미"""))
        val out = mutableListOf<AskStreamEvent>()

        service(recorder).askStream(facts, "질문", emptyList()) { out += it }

        assertThat(out.last()).isEqualTo(AbortedEvent("truncated response", FailureCause.TRUNCATED))
        assertThat(out).noneMatch { it == DoneEvent }
        assertThat(out.filterIsInstance<DeltaEvent>()).isNotEmpty()
    }

    @Test
    fun `거절 사유 문구가 ask 와 askStream 에서 같다`() {
        // CitationReasons.kt 의 refusalReason() 을 두 경로가 같이 쓰는지 고정한다.
        // 한쪽만 문구를 바꾸면(예: "refusal (...)" -> "refused: ...") 여기서 잡힌다 —
        // 그 전에는 컴파일도 나머지 스위트도 이 드리프트를 못 잡았다.
        val refusing = object : ExplanationProvider {
            override val name = "refusing"
            override fun explain(systemText: String, userText: String): ProviderResult = Refused("cyber")
        }

        val askOutcome = service(refusing).ask(facts, "질문", emptyList())
        val out = mutableListOf<AskStreamEvent>()
        service(refusing).askStream(facts, "질문", emptyList()) { out += it }

        val streamEvent = out.single() as UnavailableEvent
        assertThat((askOutcome as Unavailable).reason).isEqualTo(streamEvent.reason)
        assertThat(streamEvent.reason).isEqualTo("refusal (cyber)")
        assertThat(streamEvent.cause).isEqualTo(FailureCause.REFUSED)
    }

    @Test
    fun `stream 을 재정의하지 않은 프로바이더도 기본 구현으로 돈다`() {
        val plain = object : ExplanationProvider {
            override val name = "plain"
            override fun explain(systemText: String, userText: String): ProviderResult =
                Answered(Explanation("본문", listOf(known)), ProviderUsage(0, 0, 0, 0))
        }
        val out = mutableListOf<AskStreamEvent>()

        service(plain).askStream(facts, "질문", emptyList()) { out += it }

        assertThat(out).containsExactly(CitationsEvent(listOf(known)), DeltaEvent("본문"), DoneEvent)
    }
}
