package com.hermes.explain

import com.hermes.context.BundleLoader
import com.hermes.context.CitationValidator
import com.hermes.context.PromptAssembler
import com.hermes.llm.AgentStep
import com.hermes.llm.Answered
import com.hermes.llm.Explanation
import com.hermes.llm.ExplanationProvider
import com.hermes.llm.ProviderResult
import com.hermes.llm.ProviderUsage
import com.hermes.llm.Refused
import com.hermes.llm.Spoke
import com.hermes.llm.StreamCompleted
import com.hermes.llm.StreamEnd
import com.hermes.llm.StreamFailed
import com.hermes.llm.ToolCall
import com.hermes.llm.ToolRequested
import com.hermes.llm.ToolSpec
import com.hermes.llm.Turn
import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test
import java.time.Clock
import java.time.LocalDate

class CourseQuestionStreamTest {

    private val bundle = BundleLoader.load()
    private val known = bundle.paths().first()
    private val facts = BackendFacts("course-1", """{"courseUuid":"course-1"}""")
    private val bounds = CourseBounds(setOf(11L), LocalDate.of(2026, 10, 1))

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

    private fun service(provider: ExplanationProvider): CourseQuestionService {
        val validator = CitationValidator(bundle)
        val loop = AgentLoop(
            provider,
            validator,
            ToolRunner { error("이 테스트의 프로바이더는 도구를 부르지 않는다") },
            Clock.systemUTC(),
        )
        return CourseQuestionService(PromptAssembler(bundle), validator, provider, loop)
    }

    @Test
    fun `스트리밍과 비스트리밍이 같은 system 을 쓰고 도구 지침은 user 턴에만 붙는다`() {
        val recorder = Recorder(listOf("""{"citations":["$known"],"explanation":"x"}"""))
        val history = listOf(QuestionTurn("앞 질문", "앞 답"))

        service(recorder).ask(facts, "질문", history)
        service(recorder).askStream(facts, bounds, "질문", history) {}

        val (askSystem, askUser) = recorder.explained.single()
        val (streamSystem, streamUser) = recorder.streamed.single()

        // system 이 바이트까지 같아야 1시간 캐시가 유지되고, 하네스가 비스트리밍
        // 경로로 잰 숫자가 스트리밍에도 유효하다. 도구 지침을 system 으로 옮기면
        // 응답은 멀쩡하고 요금만 오른다 — 그 드리프트를 잡는 자리가 여기다.
        assertThat(streamSystem.toByteArray()).isEqualTo(askSystem.toByteArray())
        assertThat(streamSystem).isEqualTo(bundle.raw)
        assertThat(streamSystem).doesNotContain("## 도구")

        // user 턴은 같은 조립에 도구 지침만 뒤에 붙은 것이다.
        assertThat(streamUser).startsWith(askUser)
        assertThat(streamUser).contains("## 도구")
        assertThat(streamUser.indexOf("질문")).isLessThan(streamUser.indexOf("## 도구"))
    }

    /** 도구 한 번을 요청한 뒤 답한다. `converse` 를 직접 구현해 [ToolRequested] 를 낸다. */
    private class ToolThenAnswerProvider(private val citedPath: String) : ExplanationProvider {
        override val name = "tool-then-answer"
        var calls = 0

        override fun explain(systemText: String, userText: String): ProviderResult =
            error("이 테스트는 converse 만 쓴다")

        override fun converse(
            systemText: String,
            turns: List<Turn>,
            tools: List<ToolSpec>,
            onChunk: (String) -> Unit,
        ): AgentStep {
            calls++
            return if (calls == 1) {
                ToolRequested(
                    listOf(ToolCall("call-1", "congestion", """{"attractionId":11,"date":"2026-10-02"}""")),
                    ProviderUsage(0, 0, 0, 0),
                )
            } else {
                onChunk("""{"citations":["$citedPath"],"explanation":"답"}""")
                Spoke(StreamCompleted(ProviderUsage(0, 0, 0, 0)))
            }
        }
    }

    @Test
    fun `askStream 이 돌려주는 factsJson 은 도구가 가져온 사실까지 포함한 합집합이다`() {
        // CourseQuestionService.askStream 이 내부 union 을 만들고도 초기 facts.json 을
        // 그대로 돌려주면(합집합을 만들지 않으면) 이 테스트만 그것을 잡는다 — 아래
        // service() 헬퍼의 AgentLoop 은 도구를 부르면 에러를 내므로 여기서는 직접
        // 조립한다.
        val provider = ToolThenAnswerProvider(citedPath = known)
        val validator = CitationValidator(bundle)
        val loop = AgentLoop(provider, validator, ToolRunner { """{"grade":"BUSY"}""" }, Clock.systemUTC())
        val service = CourseQuestionService(PromptAssembler(bundle), validator, provider, loop)

        val union = service.askStream(facts, bounds, "질문", emptyList()) {}

        assertThat(union).contains("BUSY")
        assertThat(union).isNotEqualTo(facts.json)
    }

    @Test
    fun `조각을 해독하고 검증해 이벤트로 낸다`() {
        val recorder = Recorder(listOf("""{"citations":["$known"],""", """"explanation":"가나"}"""))
        val out = mutableListOf<AskStreamEvent>()

        service(recorder).askStream(facts, bounds, "질문", emptyList()) { out += it }

        assertThat(out.first()).isEqualTo(CitationsEvent(listOf(known)))
        assertThat(out.filterIsInstance<DeltaEvent>().joinToString("") { it.text }).isEqualTo("가나")
        assertThat(out.last()).isEqualTo(DoneEvent)
    }

    @Test
    fun `무효 인용이면 본문이 한 글자도 나가지 않는다`() {
        val recorder = Recorder(listOf("""{"citations":["not/in/bundle.md"],"explanation":"새면 안 됨"}"""))
        val out = mutableListOf<AskStreamEvent>()

        service(recorder).askStream(facts, bounds, "질문", emptyList()) { out += it }

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

        service(recorder).askStream(facts, bounds, "질문", emptyList()) { out += it }

        assertThat(out.last()).isEqualTo(AbortedEvent("IOException: reset", FailureCause.STREAM_FAILED))
    }

    @Test
    fun `스트림이 정상 종료됐는데 JSON 이 안 닫히면 aborted 로 끝난다`() {
        // StreamCompleted (정상 종료) 인데 본문 문자열이 닫히지 않은 채 끝난다 — 모델이
        // max_tokens 로 잘렸을 때의 모양이다. finish 가 parser.complete 를 보지 않으면
        // 미완성 문장을 DoneEvent 로 확정해 버린다.
        val recorder = Recorder(listOf("""{"citations":["$known"],"explanation":"미"""))
        val out = mutableListOf<AskStreamEvent>()

        service(recorder).askStream(facts, bounds, "질문", emptyList()) { out += it }

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
        service(refusing).askStream(facts, bounds, "질문", emptyList()) { out += it }

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

        service(plain).askStream(facts, bounds, "질문", emptyList()) { out += it }

        assertThat(out).containsExactly(CitationsEvent(listOf(known)), DeltaEvent("본문"), DoneEvent)
    }
}
