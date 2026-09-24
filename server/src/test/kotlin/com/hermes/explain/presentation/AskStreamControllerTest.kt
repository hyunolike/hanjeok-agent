package com.hermes.explain.presentation

import ch.qos.logback.classic.spi.ILoggingEvent
import ch.qos.logback.core.read.ListAppender
import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.databind.ObjectMapper
import com.hermes.context.BundleLoader
import com.hermes.context.CitationValidator
import com.hermes.context.PromptAssembler
import com.hermes.explain.AgentLoop
import com.hermes.explain.CourseQuestionService
import com.hermes.explain.CourseTools
import com.hermes.explain.FailureCause
import com.hermes.explain.ToolArgs
import com.hermes.explain.ToolRunner
import com.hermes.facts.FactsSource
import com.hermes.facts.HanjeokClient
import com.hermes.facts.HanjeokUnavailableException
import com.hermes.llm.AgentStep
import com.hermes.llm.ExplanationProvider
import com.hermes.llm.ProviderResult
import com.hermes.llm.ProviderUsage
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
import org.slf4j.LoggerFactory
import org.springframework.http.MediaType
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.asyncDispatch
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.request
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.status
import org.springframework.test.web.servlet.setup.MockMvcBuilders
import java.time.Clock
import java.util.concurrent.Executors

/**
 * FakeClient 코스(관광지 1001, 2026-09-12)가 허락하는 도구 인자.
 *
 * 경계 밖이면 `CourseTools.parse` 가 거부하고, 거부된 호출에는 `looking` 이
 * 나가지 않는다 — 그러면 이 파일의 테스트가 "도구를 안 부른 것"과 구별되지 않는다.
 */
private const val IN_BOUNDS_ARGS = """{"attractionId":1001,"date":"2026-09-13"}"""

/**
 * AskControllerTest 와 같이 진짜 객체를 조립한다. 가짜는 한적 클라이언트와 프로바이더뿐이다.
 */
class AskStreamControllerTest {

    private val mapper = ObjectMapper()
    private val bundle = BundleLoader.load()
    private val known = bundle.paths().first()
    private val factsExecutor = Executors.newFixedThreadPool(2)

    /** AskControllerTest 의 것과 같은 사실. 두 경로가 같은 코스를 본다. */
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

    /** 조각을 흘린다. explain 이 불리면 스트리밍 경로가 비스트리밍으로 새고 있다는 뜻이다. */
    private class StreamingProvider(
        private val chunks: List<String>,
        private val end: StreamEnd = StreamCompleted(ProviderUsage(0, 0, 0, 0)),
    ) : ExplanationProvider {
        override val name = "streaming"

        override fun explain(systemText: String, userText: String): ProviderResult =
            error("스트리밍 경로에서 explain 이 불리면 안 된다")

        override fun stream(systemText: String, userText: String, onChunk: (String) -> Unit): StreamEnd {
            chunks.forEach(onChunk)
            return end
        }
    }

    /**
     * 첫 호출에 도구를 요청하고, 그 뒤로는 주어진 조각을 흘린다.
     *
     * `stream` 을 막아 둔다 — 이어 묻기가 루프를 타지 않고 예전 한 방 경로로 새면
     * 도구가 통째로 사라지므로, 그 회귀를 여기서 터뜨린다.
     */
    private class ToolThenAnswerProvider(
        private val toolName: String,
        private val argumentsJson: String,
        private val chunks: List<String>,
    ) : ExplanationProvider {
        override val name = "tool-then-answer"
        var calls = 0

        override fun explain(systemText: String, userText: String): ProviderResult =
            error("스트리밍 경로에서 explain 이 불리면 안 된다")

        override fun stream(systemText: String, userText: String, onChunk: (String) -> Unit): StreamEnd =
            error("이어 묻기는 converse 를 타야 한다 — stream 으로 새면 도구가 사라진다")

        override fun converse(
            systemText: String,
            turns: List<Turn>,
            tools: List<ToolSpec>,
            onChunk: (String) -> Unit,
        ): AgentStep {
            if (calls++ == 0) {
                return ToolRequested(
                    listOf(ToolCall("call-1", toolName, argumentsJson)),
                    ProviderUsage(0, 0, 0, 0),
                )
            }
            chunks.forEach(onChunk)
            return Spoke(StreamCompleted(ProviderUsage(0, 0, 0, 0)))
        }
    }

    /** 도구가 실제로 실행됐는지 센다. 결과 JSON 은 한적 혼잡도 응답 모양이면 족하다. */
    private class CountingRunner : ToolRunner {
        var calls = 0
        override fun run(args: ToolArgs): String {
            calls++
            return """{"diagnosis":{"grade":"NORMAL"}}"""
        }
    }

    private fun questionService(provider: ExplanationProvider, runner: ToolRunner): CourseQuestionService {
        val validator = CitationValidator(bundle)
        return CourseQuestionService(
            PromptAssembler(bundle),
            validator,
            provider,
            AgentLoop(provider, validator, runner, Clock.systemUTC()),
        )
    }

    private fun mvc(
        provider: ExplanationProvider,
        runner: ToolRunner = ToolRunner { error("이 테스트는 도구를 부르지 않는다") },
    ): MockMvc =
        MockMvcBuilders
            .standaloneSetup(
                AskStreamController(
                    FactsSource(FakeClient(), 15, factsExecutor),
                    questionService(provider, runner),
                    AskStreamExecutor(Executors.newSingleThreadExecutor()),
                    "gpt-4o",
                ),
            )
            .setControllerAdvice(ApiErrorHandler())
            .build()

    /** 스트림을 끝까지 받아 본문을 돌려준다. SSE 는 UTF-8 로 읽어야 한글이 안 깨진다. */
    private fun streamed(
        provider: ExplanationProvider,
        runner: ToolRunner = ToolRunner { error("이 테스트는 도구를 부르지 않는다") },
    ): String {
        val mvc = mvc(provider, runner)
        val started = mvc
            .perform(
                post("/agent/ask/stream")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""{"courseUuid":"abc","question":"왜 이 순서예요?"}"""),
            )
            .andExpect(request().asyncStarted())
            .andReturn()
        return mvc.perform(asyncDispatch(started)).andReturn().response.getContentAsString(Charsets.UTF_8)
    }

    /** SSE 프레임 하나씩으로 자른다. 프레임은 빈 줄로 나뉘고 `event:` 로 시작한다. */
    private fun sseFrom(provider: ExplanationProvider, runner: ToolRunner = CountingRunner()): List<String> =
        streamed(provider, runner)
            .split("\n\n")
            .map { it.trim() }
            .filter { it.isNotEmpty() }

    /** 코스에 실제로 있는 관광지와 코스 날짜 근처 — 경계를 통과해야 도구가 실행된다. */
    private fun providerRequestingTool(name: String, args: String) = ToolThenAnswerProvider(
        name,
        args,
        listOf("""{"citations":["$known"],"explanation":"답"}"""),
    )

    private fun providerRequestingToolThenInvalidCitations() = ToolThenAnswerProvider(
        CourseTools.CONGESTION,
        IN_BOUNDS_ARGS,
        listOf("""{"citations":["not/in/bundle.md"],"explanation":"새면 안 되는 문장"}"""),
    )

    @Test
    fun `인용이 유효하면 citations 뒤에 delta 와 done 이 나간다`() {
        val body = streamed(StreamingProvider(listOf("""{"citations":["$known"],""", """"explanation":"가나"}""")))

        assertThat(body).contains("event:citations").contains("event:delta").contains("event:done")
        assertThat(body.indexOf("event:citations")).isLessThan(body.indexOf("event:delta"))
        assertThat(body).contains("가나")
    }

    @Test
    fun `인용이 무효하면 delta 없이 불투명한 unavailable 만 나간다`() {
        val body = streamed(
            StreamingProvider(listOf("""{"citations":["not/in/bundle.md"],"explanation":"새면 안 되는 문장"}""")),
        )

        assertThat(body).doesNotContain("event:delta")
        assertThat(body).contains("event:unavailable").contains("EXPLANATION_UNAVAILABLE")
        // 불투명성: 사유(인용 경로)도 본문도 브라우저로 새면 안 된다.
        assertThat(body).doesNotContain("not/in/bundle.md")
        assertThat(body).doesNotContain("citations not in bundle")
        assertThat(body).doesNotContain("새면 안 되는 문장")
    }

    @Test
    fun `본문 도중 실패하면 불투명한 aborted 가 나간다`() {
        val body = streamed(
            StreamingProvider(
                listOf("""{"citations":["$known"],"explanation":"미"""),
                end = StreamFailed("INTERNAL DETAIL THAT MUST NOT LEAK"),
            ),
        )

        assertThat(body).contains("event:aborted").contains("EXPLANATION_ABORTED")
        assertThat(body).doesNotContain("INTERNAL DETAIL THAT MUST NOT LEAK")
    }

    /**
     * 컨트롤러가 남긴 로그를 이 블록 동안만 붙잡는다.
     *
     * 실패 프레임은 코드만 싣는 계약이므로 [FailureCause] 는 SSE 본문에 절대 나오지
     * 않는다. 그래서 원인이 관찰되는 곳은 로그 한 줄뿐이고, 그 줄을 보지 않으면
     * FACTS 를 STREAM_FAILED 로 바꿔도 아무 테스트가 울지 않는다.
     */
    private fun <T> withControllerLogs(block: () -> T): Pair<T, List<String>> {
        val logger = LoggerFactory.getLogger(AskStreamController::class.java) as ch.qos.logback.classic.Logger
        val appender = ListAppender<ILoggingEvent>()
        appender.start()
        logger.addAppender(appender)
        try {
            val result = block()
            return result to appender.list.map { it.formattedMessage }
        } finally {
            logger.detachAppender(appender)
            appender.stop()
        }
    }

    @Test
    fun `사실을 못 받으면 불투명한 unavailable 만 나가고 사유는 FACTS 로 기록된다`() {
        val broken = object : FakeClient() {
            override fun course(courseUuid: String): JsonNode =
                throw HanjeokUnavailableException("SENTINEL COURSE 404 DETAIL")
        }
        val mvc = MockMvcBuilders
            .standaloneSetup(
                AskStreamController(
                    FactsSource(broken, 15, factsExecutor),
                    questionService(
                        StreamingProvider(emptyList()),
                        ToolRunner { error("사실을 못 받으면 모델도 도구도 부르지 않는다") },
                    ),
                    AskStreamExecutor(Executors.newSingleThreadExecutor()),
                    "gpt-4o",
                ),
            )
            .setControllerAdvice(ApiErrorHandler())
            .build()

        val (body, logs) = withControllerLogs {
            val started = mvc
                .perform(
                    post("/agent/ask/stream")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""{"courseUuid":"abc","question":"왜 이 순서예요?"}"""),
                )
                .andExpect(request().asyncStarted())
                .andReturn()
            mvc.perform(asyncDispatch(started)).andReturn().response.getContentAsString(Charsets.UTF_8)
        }

        assertThat(body).contains("event:unavailable").contains("EXPLANATION_UNAVAILABLE")
        assertThat(body).doesNotContain("SENTINEL COURSE 404 DETAIL")
        // 사실 조회 실패는 FACTS 다 — 이 경로가 그 원인의 유일한 생산자이고,
        // 프레임이 불투명한 만큼 로그가 유일한 관찰 지점이다.
        assertThat(logs).anyMatch { it.contains(FailureCause.FACTS.name) }
        assertThat(logs).noneMatch { it.contains(FailureCause.STREAM_FAILED.name) }
        // 사유는 브라우저에는 안 가지만 로그에는 남아야 진단이 된다.
        assertThat(logs).anyMatch { it.contains("SENTINEL COURSE 404 DETAIL") }
    }

    @Test
    fun `질문이 비어 있으면 스트림을 열지 않고 400`() {
        mvc(StreamingProvider(emptyList()))
            .perform(
                post("/agent/ask/stream")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""{"courseUuid":"abc","question":"   "}"""),
            )
            .andExpect(status().isBadRequest)
    }

    @Test
    fun `looking 이벤트는 도구 이름만 싣는다`() {
        // 인자에는 질문에서 유도된 값이 섞인다. 화면에 필요한 것은 "무엇을 조회
        // 중인가" 뿐이므로 프레임에는 도구 이름 말고 아무것도 싣지 않는다.
        val provider = providerRequestingTool(CourseTools.CONGESTION, IN_BOUNDS_ARGS)
        val runner = CountingRunner()

        val events = sseFrom(provider = provider, runner = runner)

        val looking = events.single { it.startsWith("event:looking") }
        assertThat(looking).contains(CourseTools.CONGESTION)
        assertThat(looking).doesNotContain("attractionId")
        assertThat(looking).doesNotContain("1001")
        assertThat(looking).doesNotContain("2026-09-13")
        // 도구를 실제로 실행했고, 예산 안이다 — 도구 라운드 1회에 모델 호출 2회.
        assertThat(runner.calls).isEqualTo(1)
        assertThat(provider.calls).isEqualTo(2)
        assertThat(events.last()).startsWith("event:done")
    }

    @Test
    fun `looking 이 온 뒤에도 unavailable 앞의 delta 는 0개다`() {
        // looking 은 delta 가 아니다. 도구 프레임이 섞여도 "본문을 한 글자도 보내기
        // 전에 실패한다" 는 불변식은 그대로여야 한다.
        val events = sseFrom(provider = providerRequestingToolThenInvalidCitations())

        val deltaIndexes = events.withIndex().filter { it.value.startsWith("event:delta") }.map { it.index }
        val unavailableIndex = events.indexOfFirst { it.startsWith("event:unavailable") }

        assertThat(unavailableIndex).isNotNegative()
        assertThat(events.any { it.startsWith("event:looking") }).isTrue()
        assertThat(deltaIndexes.filter { it < unavailableIndex }).isEmpty()
        assertThat(events.joinToString("\n")).doesNotContain("새면 안 되는 문장")
    }

    @Test
    fun `courseUuid 가 비어 있으면 스트림을 열지 않고 400`() {
        // 200 SSE unavailable 로 내리면 클라이언트가 재시도한다 — 몇 번을 보내도 같은
        // 이유로 실패하는 요청이라 재시도 폭풍이 된다. AskController(비스트리밍)는
        // 이 경우를 이미 400으로 막는다.
        mvc(StreamingProvider(emptyList()))
            .perform(
                post("/agent/ask/stream")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""{"courseUuid":"   ","question":"왜 이 순서예요?"}"""),
            )
            .andExpect(status().isBadRequest)
    }
}
