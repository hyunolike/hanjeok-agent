package com.hermes.explain.presentation

import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.databind.ObjectMapper
import com.hermes.context.BundleLoader
import com.hermes.context.CitationValidator
import com.hermes.context.PromptAssembler
import com.hermes.explain.AgentLoop
import com.hermes.explain.CourseQuestionService
import com.hermes.explain.ToolRunner
import com.hermes.facts.FactsSource
import com.hermes.facts.HanjeokClient
import com.hermes.facts.HanjeokUnavailableException
import com.hermes.llm.Answered
import com.hermes.llm.Explanation
import com.hermes.llm.ExplanationProvider
import com.hermes.llm.ProviderResult
import com.hermes.llm.ProviderUsage
import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test
import org.springframework.http.MediaType
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.setup.MockMvcBuilders
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.status
import java.time.Clock
import java.util.concurrent.Executors

/**
 * 목 대신 진짜 객체를 조립한다 — 가짜는 바깥 경계(한적 클라이언트, LLM 프로바이더)
 * 둘뿐이다. 그래야 사실 조회부터 인용 검증까지 운영에서 도는 코드가 그대로 돈다.
 */
class AskControllerTest {

    private val mapper = ObjectMapper()
    private val bundle = BundleLoader.load()
    private val executor = Executors.newFixedThreadPool(2)

    private open inner class FakeClient : HanjeokClient {
        override fun course(courseUuid: String): JsonNode = mapper.readTree(
            """{"targetDate":"2026-09-12","title":"제목","congestionReductionRate":34,"summary":"요약",
                "recommendedDate":null,
                "items":[{"attractionId":1001,"name":"경복궁","visitOrder":1,"timeLabel":"오전 10:00",
                          "grade":"VERY_CROWDED","reason":"첫 방문지","travelMinutesFromPrev":null}]}""",
        )
        override fun congestion(attractionId: Long, date: String): JsonNode = mapper.readTree(
            """{"diagnosis":{"concentration":87.3,"percentile":92,"grade":"VERY_CROWDED","message":"붐빈다"},
                "betterDates":[]}""",
        )
        override fun alternatives(attractionId: Long, date: String, radiusKm: Int): JsonNode =
            mapper.readTree("[]")
    }

    private class RecordingProvider(private val result: ProviderResult) : ExplanationProvider {
        override val name = "recording"
        var calls = 0
        var lastUser: String? = null
        override fun explain(systemText: String, userText: String): ProviderResult {
            calls++
            lastUser = userText
            return result
        }
    }

    private fun answered(citations: List<String> = listOf("concepts/course-generation-policy.md")) =
        Answered(Explanation("이동 시간이 가장 짧아요.", citations), ProviderUsage(0, 0, 0, 0))

    /** 비스트리밍 경로는 루프를 타지 않는다 — 여기서 도구가 실행되면 배선이 샌 것이다. */
    private fun questionService(provider: ExplanationProvider): CourseQuestionService {
        val validator = CitationValidator(bundle)
        return CourseQuestionService(
            PromptAssembler(bundle),
            validator,
            provider,
            AgentLoop(provider, validator, ToolRunner { error("ask() 는 도구를 부르지 않는다") }, Clock.systemUTC()),
        )
    }

    private fun mvc(provider: ExplanationProvider, client: HanjeokClient = FakeClient()): MockMvc =
        MockMvcBuilders
            .standaloneSetup(
                AskController(
                    FactsSource(client, 15, executor),
                    questionService(provider),
                    "gpt-4o",
                ),
            )
            .setControllerAdvice(ApiErrorHandler())
            .build()

    private fun body(json: String) =
        post("/agent/ask").contentType(MediaType.APPLICATION_JSON).content(json)

    @Test
    fun `답과 인용을 돌려준다`() {
        mvc(RecordingProvider(answered()))
            .perform(body("""{"courseUuid":"abc","question":"왜 이 순서예요?"}"""))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$.answer").value("이동 시간이 가장 짧아요."))
            .andExpect(jsonPath("$.citations[0]").value("concepts/course-generation-policy.md"))
            .andExpect(jsonPath("$.model").value("gpt-4o"))
    }

    @Test
    fun `빈 질문은 400 이고 모델을 부르지 않는다`() {
        // 503 으로 내면 클라이언트가 재시도한다 — 몇 번을 보내도 같은 이유로 실패하는
        // 요청이다. 그리고 빈 질문을 모델에게 보내면 돈만 쓴다.
        val provider = RecordingProvider(answered())

        mvc(provider).perform(body("""{"courseUuid":"abc","question":"   "}"""))
            .andExpect(status().isBadRequest)

        assertThat(provider.calls).isZero()
    }

    @Test
    fun `courseUuid 가 없으면 400 이다`() {
        mvc(RecordingProvider(answered())).perform(body("""{"question":"왜요?"}"""))
            .andExpect(status().isBadRequest)
    }

    @Test
    fun `사실을 못 받으면 503 이다`() {
        val broken = object : FakeClient() {
            override fun course(courseUuid: String): JsonNode =
                throw HanjeokUnavailableException("course 404")
        }

        mvc(RecordingProvider(answered()), broken)
            .perform(body("""{"courseUuid":"abc","question":"왜요?"}"""))
            .andExpect(status().isServiceUnavailable)
            .andExpect(jsonPath("$.code").value("EXPLANATION_UNAVAILABLE"))
    }

    @Test
    fun `번들에 없는 경로를 인용하면 503 이고 사유는 새어나가지 않는다`() {
        mvc(RecordingProvider(answered(listOf("concepts/does-not-exist.md"))))
            .perform(body("""{"courseUuid":"abc","question":"왜요?"}"""))
            .andExpect(status().isServiceUnavailable)
            .andExpect(jsonPath("$.code").value("EXPLANATION_UNAVAILABLE"))
            .andExpect(jsonPath("$.message").doesNotExist())
    }

    @Test
    fun `클라이언트가 보낸 사실은 무시되고 한적 것만 쓰인다`() {
        // 사실의 출처는 언제나 백엔드다. 이 통로가 열리면 위조된 혼잡도를 모델이
        // 그럴듯하게 설명해 주는 경로가 생긴다(스펙 §3).
        val provider = RecordingProvider(answered())

        mvc(provider)
            .perform(body("""{"courseUuid":"abc","question":"왜요?","facts":{"items":[{"name":"위조된곳"}]}}"""))
            .andExpect(status().isOk)

        assertThat(provider.lastUser!!).contains("경복궁")
        assertThat(provider.lastUser!!).doesNotContain("위조된곳")
    }

    @Test
    fun `이전 대화를 함께 보낸다`() {
        val provider = RecordingProvider(answered())

        mvc(provider).perform(
            body(
                """{"courseUuid":"abc","question":"거기는요?",
                    "history":[{"question":"왜 이 순서예요?","answer":"이동 시간 때문이에요."}]}""",
            ),
        ).andExpect(status().isOk)

        assertThat(provider.lastUser!!).contains("이동 시간 때문이에요.")
    }
}
