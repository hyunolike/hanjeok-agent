package com.hermes.shared.config

import com.fasterxml.jackson.databind.ObjectMapper
import com.hermes.context.Bundle
import com.hermes.context.BundleLoader
import com.hermes.context.CitationValidator
import com.hermes.context.PromptAssembler
import com.hermes.context.ContextSelection
import com.hermes.context.FullContextSelection
import com.hermes.context.RetrievalContextSelector
import com.hermes.context.RetrievalMode
import com.hermes.context.RetrievalIdentity
import com.hermes.context.RetrievalHttpClient
import com.hermes.context.RetrievalToken
import com.hermes.context.MetadataRetrievalToken
import java.net.URI
import java.security.MessageDigest
import com.hermes.explain.AgentLoop
import com.hermes.explain.Alternatives
import com.hermes.explain.Congestion
import com.hermes.explain.CourseExplainer
import com.hermes.explain.CourseQuestionService
import com.hermes.explain.ExplanationCache
import com.hermes.explain.ExplanationService
import com.hermes.explain.Rejected
import com.hermes.explain.ToolRunner
import com.hermes.explain.presentation.AskStreamExecutor
import com.hermes.facts.FactsSource
import com.hermes.facts.HanjeokClient
import com.hermes.facts.RestHanjeokClient
import com.hermes.llm.ExplanationProvider
import org.springframework.beans.factory.annotation.Value
import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Configuration
import org.springframework.http.client.SimpleClientHttpRequestFactory
import org.springframework.web.client.RestClient
import java.time.Clock
import java.time.Duration
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

/**
 * 애플리케이션 전역 배선. CORS 는 여기 두지 않는다 — `WebMvcConfigurer`/
 * `CorsRegistry` 는 인바운드 웹 타입이고, `ModuleBoundaryTest` 가 presentation
 * 밖에서 그것을 금지한다(예외는 아웃바운드 클라이언트 두 접두사뿐). CORS 설정은
 * `com.hermes.explain.presentation.CorsConfig` 에 있다.
 */
@Configuration
class HermesConfig {

    /** 부팅 시 1회 적재하고 그 뒤로는 파일을 읽지 않는다(08-17 설계문 §5). */
    @Bean
    fun bundle(): Bundle = BundleLoader.load()

    /**
     * `ExplainController` 는 Jackson 2 `ObjectMapper`(`com.fasterxml.jackson.databind`)를
     * 직접 받는다 — 웹 계층 컨버터가 Jackson 3(tools.jackson)라서 이 코드베이스가
     * 자동 구성하는 `ObjectMapper` 빈은 Jackson 3 타입뿐이고, Jackson 2
     * `ObjectMapper` 빈은 자동으로 생기지 않는다. 이 빈이 없으면 컨텍스트가
     * `explainController` 생성에서 `NoSuchBeanDefinitionException`으로 뜨지
     * 않는다(ApplicationContextTest 로 실측 확인).
     */
    @Bean
    fun objectMapper(): ObjectMapper = ObjectMapper()

    @Bean
    fun promptAssembler(bundle: Bundle): PromptAssembler = PromptAssembler(bundle)

    @Bean
    fun citationValidator(bundle: Bundle): CitationValidator = CitationValidator(bundle)

    @Bean
    fun contextSelection(
        bundle: Bundle,
        @Value("\${hermes.retrieval.mode:FULL}") modeName: String,
        @Value("\${hermes.retrieval.url:}") url: String,
        @Value("\${hermes.retrieval.index-version:}") indexVersion: String,
        @Value("\${hermes.retrieval.model-revision:}") modelRevision: String,
        @Value("\${hermes.retrieval.auth-mode:cloud-run-iam}") authMode: String,
    ): ContextSelection {
        val mode = RetrievalMode.valueOf(modeName)
        if (mode == RetrievalMode.FULL) return RetrievalContextSelector(bundle)
        val origin = URI(url)
        require(authMode in setOf("cloud-run-iam", "loopback-test"))
        val token = if (authMode == "loopback-test") {
            require(System.getenv("K_SERVICE").isNullOrBlank()) { "local authentication forbidden on Cloud Run" }
            val value = System.getenv("HERMES_RETRIEVAL_LOCAL_TOKEN") ?: error("local test token required")
            RetrievalToken { value }
        } else MetadataRetrievalToken(origin)
        val metaHash = MessageDigest.getInstance("SHA-256").digest(bundle.metadataJson!!.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }
        return RetrievalContextSelector(bundle, mode, RetrievalIdentity(bundle.sha256, metaHash, indexVersion, modelRevision),
            RetrievalHttpClient(origin, token, localTest = authMode == "loopback-test"))
    }

    /**
     * 하네스가 잰 프로바이더를 그대로 띄울 수 있어야 한다 — `EvalMain` 과 같은
     * 세 이름(anthropic·openai·openrouter)을 쓴다. 고정돼 있던 동안은 측정한
     * 프로바이더(OpenAI)와 도는 프로바이더(Anthropic)가 서로 달랐다.
     */
    @Bean
    fun explanationProvider(
        @Value("\${hermes.llm.provider}") provider: String,
        @Value("\${hermes.llm.model}") model: String,
    ): ExplanationProvider = LlmSelection.provider(provider, model, System::getenv)

    @Bean
    fun hanjeokRestClient(
        @Value("\${hermes.hanjeok.base-url}") baseUrl: String,
        @Value("\${hermes.hanjeok.timeout-seconds}") timeoutSeconds: Long,
    ): RestClient = RestClient.builder()
        .baseUrl(baseUrl)
        .requestFactory(
            SimpleClientHttpRequestFactory().apply {
                setConnectTimeout(Duration.ofSeconds(timeoutSeconds))
                setReadTimeout(Duration.ofSeconds(timeoutSeconds))
            },
        )
        .build()

    @Bean
    fun hanjeokClient(hanjeokRestClient: RestClient): HanjeokClient = RestHanjeokClient(hanjeokRestClient)

    /** 병렬 호출은 둘뿐이다. 스레드를 넉넉히 잡을 이유가 없다. */
    @Bean(destroyMethod = "shutdown")
    fun factsExecutor(): ExecutorService = Executors.newFixedThreadPool(4)

    @Bean
    fun factsSource(
        hanjeokClient: HanjeokClient,
        @Value("\${hermes.hanjeok.radius-km}") radiusKm: Int,
        factsExecutor: ExecutorService,
    ): FactsSource = FactsSource(hanjeokClient, radiusKm, factsExecutor)

    @Bean
    fun explanationCache(): ExplanationCache = ExplanationCache()

    @Bean
    fun explanationService(
        promptAssembler: PromptAssembler,
        citationValidator: CitationValidator,
        explanationProvider: ExplanationProvider,
        contextSelection: ContextSelection = FullContextSelection(promptAssembler, citationValidator),
    ): ExplanationService = ExplanationService(promptAssembler, citationValidator, explanationProvider, contextSelection)

    /**
     * 검증을 통과한 인자만 여기 온다 — [AgentLoop] 이 [Rejected] 를 먼저 갈라내고
     * 실행하지 않는다. 그래서 이 람다는 경계를 다시 보지 않는다.
     */
    @Bean
    fun toolRunner(hanjeokClient: HanjeokClient): ToolRunner = ToolRunner { args ->
        when (args) {
            is Congestion -> hanjeokClient.congestion(args.attractionId, args.date.toString()).toString()
            is Alternatives ->
                hanjeokClient.alternatives(args.attractionId, args.date.toString(), args.radiusKm).toString()
            is Rejected -> error("거부된 인자는 실행되지 않는다 — AgentLoop 이 먼저 갈라낸다")
        }
    }

    /** 예산은 [AgentLoop] 기본값이다 — 도구 라운드 2회, 마감 60초. 여기서 늘리지 않는다. */
    @Bean
    fun agentLoop(
        explanationProvider: ExplanationProvider,
        citationValidator: CitationValidator,
        toolRunner: ToolRunner,
    ): AgentLoop = AgentLoop(explanationProvider, citationValidator, toolRunner, Clock.systemUTC())

    @Bean
    fun courseQuestionService(
        promptAssembler: PromptAssembler,
        citationValidator: CitationValidator,
        explanationProvider: ExplanationProvider,
        agentLoop: AgentLoop,
        contextSelection: ContextSelection = FullContextSelection(promptAssembler, citationValidator),
    ): CourseQuestionService =
        CourseQuestionService(promptAssembler, citationValidator, explanationProvider, agentLoop, contextSelection)

    @Bean
    fun courseExplainer(
        factsSource: FactsSource,
        explanationService: ExplanationService,
        explanationCache: ExplanationCache,
    ): CourseExplainer = CourseExplainer(factsSource, explanationService, explanationCache)

    @Bean
    fun demoCourses(@Value("\${hermes.demo.courses}") raw: String): DemoCourses = DemoCourses.parse(raw)

    /** 스트림은 I/O 대기라 스레드를 조금 넉넉히 둔다. Cloud Run 인스턴스당 동시 요청이 적다. */
    @Bean
    fun askStreamExecutor(): AskStreamExecutor = AskStreamExecutor(Executors.newFixedThreadPool(8))
}
