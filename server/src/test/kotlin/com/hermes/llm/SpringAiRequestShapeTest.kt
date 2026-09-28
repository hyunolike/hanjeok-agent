package com.hermes.llm

import com.hermes.context.BundleLoader
import com.hermes.context.PromptAssembler
import com.hermes.shared.config.LlmSelection
import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test
import org.springframework.ai.anthropic.AnthropicChatModel
import com.anthropic.client.okhttp.AnthropicOkHttpClient

/**
 * 실제로 나가는 요청 본문을 검사한다.
 *
 * 구 `AnthropicRequestShapeTest` 가 `buildParams` 라는 순수 함수의 반환값을 보던
 * 자리다. Spring AI 에는 그런 함수가 없어 요청이 모델 안에서 조립되므로, 나가는
 * 바이트를 직접 본다. 이쪽이 더 강하다 — 프레임워크가 무엇을 덧붙이거나 지워도
 * 여기서 잡힌다.
 */
class SpringAiRequestShapeTest {

    private val systemText = PromptAssembler(BundleLoader.load()).systemText
    private val factsJson = """{"courseUuid":"3f6c2b18-9a4d-4c77-8b21-5e0f7c9d1a44"}"""

    private fun provider(baseUrl: String): SpringAiExplanationProvider {
        val client = AnthropicOkHttpClient.builder()
            .apiKey("sk-ant-not-a-real-key")
            .baseUrl(baseUrl)
            .maxRetries(0)
            .build()
        val model = AnthropicChatModel.builder()
            .anthropicClient(client)
            .options(ChatClients.anthropicOptions("claude-opus-5"))
            .build()
        return SpringAiExplanationProvider("anthropic", model)
    }

    // baseUrl 은 이미 /v1 로 끝난 값을 받는다 — 호출부가 endpoint.baseUrl + "/v1" 을 준다.
    //
    // 예전에는 여기서 OpenAiChatModel 을 손으로 다시 조립했다. 그 사본은
    // `LlmSelection` 이 실제로 하는 배선과 같다는 보장이 없어서, openai 분기의
    // baseUrl 이 틀려도 이 파일의 단언은 전부 그린이었다 — 실제로 한 번 그렇게
    // 새어 나갔다. 이제 조립 경로는 운영과 같은 하나뿐이다. `baseUrlOverride` 는
    // 루프백 엔드포인트로 돌리기 위한 것일 뿐, 그 외에는 운영과 같은 코드가 돈다.
    private fun openAiProvider(baseUrl: String, model: String = "gpt-4o"): ExplanationProvider =
        LlmSelection.provider("openai", model, { "sk-not-a-real-key" }, baseUrl)

    @Test
    fun `번들은 system 블록에 1시간 캐시 분기점과 함께 들어간다`() {
        CapturingEndpoint().use { endpoint ->
            provider(endpoint.baseUrl).explain(systemText, factsJson)
            val body = endpoint.capturedBody()

            assertThat(body["system"]).hasSize(1)
            assertThat(body["system"][0]["text"].asText()).isEqualTo(systemText)
            assertThat(body["system"][0]["cache_control"]["ttl"].asText()).isEqualTo("1h")
        }
    }

    @Test
    fun `매 요청 달라지는 사실은 캐시 분기점 뒤 user 턴에 있다`() {
        CapturingEndpoint().use { endpoint ->
            provider(endpoint.baseUrl).explain(systemText, factsJson)
            val body = endpoint.capturedBody()

            assertThat(body["messages"]).hasSize(1)
            assertThat(body["messages"][0]["role"].asText()).isEqualTo("user")
            assertThat(body["messages"][0]["content"].asText()).isEqualTo(factsJson)
        }
    }

    @Test
    fun `모델과 토큰 한도와 effort 가 스펙과 일치한다`() {
        CapturingEndpoint().use { endpoint ->
            provider(endpoint.baseUrl).explain(systemText, factsJson)
            val body = endpoint.capturedBody()

            assertThat(body["model"].asText()).isEqualTo("claude-opus-5")
            assertThat(body["max_tokens"].asInt()).isEqualTo(16000)
            assertThat(body["output_config"]["effort"].asText()).isEqualTo("low")
        }
    }

    @Test
    fun `같은 입력이면 요청 본문이 바이트까지 완전히 같다`() {
        fun capture(): String = CapturingEndpoint().use { endpoint ->
            provider(endpoint.baseUrl).explain(systemText, factsJson)
            endpoint.capturedBody().toString()
        }

        // 접두사가 1바이트만 흔들려도 1시간 프롬프트 캐시는 통째로 미스 난다.
        assertThat(capture()).isEqualTo(capture())
    }

    @Test
    fun `엔드포인트가 죽어도 예외가 아니라 Failed 로 끝난다`() {
        CapturingEndpoint().use { endpoint ->
            val result = provider(endpoint.baseUrl).explain(systemText, factsJson)

            assertThat(result).isInstanceOf(Failed::class.java)
        }
    }

    @Test
    fun `openai 호환 요청은 baseUrl 뒤에 chat completions 만 붙인다`() {
        CapturingEndpoint().use { endpoint ->
            // baseUrl 자체가 /v1 을 지녀야 한다 — SDK 는 그 뒤에 /chat/completions 만
            // 얹는다(ChatClients.OPENAI_BASE_URL 의 주석 참고, openai-java-core 의
            // OpenAiSetup.OPENAI_URL 이 이미 "https://api.openai.com/v1" 임을 javap 로
            // 확인). 이 테스트가 그 SDK 쪽 절반을 고정한다 — 루프백 baseUrl 뒤에 /v1 을
            // 직접 붙여서, 실제 나가는 경로가 baseUrl + "/chat/completions" 인지 본다.
            val baseUrl = "${endpoint.baseUrl}/v1"

            openAiProvider(baseUrl).explain(systemText, factsJson)

            // baseUrl 이 이미 /v1 로 끝나므로, SDK 가 그 뒤에 무엇을 붙이는지만 본다.
            assertThat(endpoint.capturedPath()).isEqualTo("/v1/chat/completions")
            val body = endpoint.capturedBody()
            assertThat(body["model"].asText()).isEqualTo("gpt-4o")
            // maxTokens 는 이 테스트 말고는 어디서도 안 걸린다.
            assertThat(body["max_tokens"].asInt()).isEqualTo(16000)
        }
    }

    @Test
    fun `openai 호환 요청은 response_format 으로 explanation 스키마를 강제한다`() {
        // Task 7 2차 재작업의 원인이 된 결함 — openai 5회 실행 전부 explained=0,
        // JsonParseException("경복궁은..." 산문)으로 끝난 그 결과 — 가 바로 이
        // response_format 이 빠져서였다. 구 프로바이더는 tool_choice 로 스키마를
        // 강제했지만, Spring AI 경로에는 그 대응물이 아예 없었다. 여기서 실제로
        // 나가는 바이트에 response_format 블록이 있는지, 그 스키마가 두 필드를
        // 모두 required 로 요구하는지 "파싱된 구조"로 확인한다 — 문자열
        // 부분일치(contains)는 properties 블록만 있어도 통과하는 헛 검증이라는
        // 것을 ChatClientsTest 의 `유도된 스키마는 두 필드를 모두 요구한다`가 이미
        // 한 번 겪었다(b49570b).
        CapturingEndpoint().use { endpoint ->
            val baseUrl = "${endpoint.baseUrl}/v1"

            openAiProvider(baseUrl).explain(systemText, factsJson)

            val body = endpoint.capturedBody()
            val responseFormat = body["response_format"]
            assertThat(responseFormat).describedAs("response_format 블록 자체가 없다").isNotNull
            assertThat(responseFormat["type"].asText()).isEqualTo("json_schema")

            val schema = responseFormat["json_schema"]["schema"]
            val required = schema["required"].map { it.asText() }
            assertThat(required).containsExactlyInAnyOrder("explanation", "citations")
            // properties 블록도 있어야 문자열 부분일치가 아니라 진짜 파싱임을
            // 보여준다 — required 만 보면 우연히 이름이 겹쳐도 통과할 수 있다.
            assertThat(schema["properties"].fieldNames().asSequence().toList())
                .containsExactlyInAnyOrder("explanation", "citations")
            // strict 가 빠지면 json_schema 는 구속력이 없다 — 모델이 스키마를
            // 참고만 하고 산문으로 답해도 되고, 그러면 toProviderResult 의
            // readTree 가 JsonParseException 으로 깨진다. 위의 required/properties
            // 단언은 그 상태에서도 전부 그린이다(스키마 자체는 그대로 실리므로).
            // 돈을 쓴 측정 한 번이 통째로 explained=0 으로 끝난 원인이 이것이라,
            // 나가는 바이트에서 직접 확인한다.
            assertThat(responseFormat["json_schema"]["strict"].asBoolean())
                .describedAs("strict 가 없거나 false 면 스키마는 구속력이 없다")
                .isTrue()
        }
    }

    @Test
    fun `openai 호환 요청도 번들과 사실이 그대로 실린다`() {
        // anthropic 쪽은 `번들은 system 블록에...`/`매 요청 달라지는 사실은...`
        // 두 테스트가 이미 고정한다. openai 호환 경로는 지금까지 model/baseUrl/
        // response_format 만 봤지 systemText/factsJson 이 실제로 온전히 실리는지는
        // 아무 테스트도 안 봤다 — 리뷰어가 SpringAiExplanationProvider.explain 의
        // openai 분기에서 userText 를 하드코딩해도 전체 스위트가 그린으로
        // 남았다. 운영이 도는 쪽이 openai 인데 그쪽이 anthropic 보다 약하게
        // 고정돼 있던 것을 여기서 닫는다.
        CapturingEndpoint().use { endpoint ->
            val baseUrl = "${endpoint.baseUrl}/v1"

            openAiProvider(baseUrl).explain(systemText, factsJson)

            val body = endpoint.capturedBody()
            assertThat(body["messages"]).hasSize(2)
            assertThat(body["messages"][0]["role"].asText()).isEqualTo("system")
            assertThat(body["messages"][0]["content"].asText()).isEqualTo(systemText)
            assertThat(body["messages"][1]["role"].asText()).isEqualTo("user")
            assertThat(body["messages"][1]["content"].asText()).isEqualTo(factsJson)
        }
    }

    @Test
    fun `openai 호환도 같은 입력이면 요청 본문이 바이트까지 완전히 같다`() {
        // anthropic 쪽 `같은 입력이면 요청 본문이 바이트까지 완전히 같다` 의 짝이다.
        // openai 호환 경로에는 캐시 분기점이 없지만, "같은 입력이면 같은 바이트가
        // 나간다"는 여전히 회귀 하네스가 비교를 정직하게 하기 위한 전제다 — 매
        // 실행마다 본문이 흔들리면 "같은 프롬프트로 비교했다"는 주장 자체가
        // 무너진다.
        fun capture(): String = CapturingEndpoint().use { endpoint ->
            val baseUrl = "${endpoint.baseUrl}/v1"
            openAiProvider(baseUrl).explain(systemText, factsJson)
            endpoint.capturedBody().toString()
        }

        assertThat(capture()).isEqualTo(capture())
    }

    @Test
    fun `OPENAI_BASE_URL 과 OPENROUTER_BASE_URL 은 이미 v1 을 지닌다`() {
        // 위 테스트는 SDK 쪽 절반("baseUrl 뒤에 chat completions 만 붙는다")만
        // 고정한다. 이 상수 자체가 /v1 을 안 지니면(예: 예전처럼
        // "https://api.openai.com") 그 테스트는 여전히 초록일 수 있다 — 루프백
        // baseUrl 에 /v1 을 직접 붙였기 때문이다. 그래서 상수 쪽 절반은 따로
        // 고정해야 한다. 둘을 합쳐야 "실제 요청이 .../v1/chat/completions 에
        // 떨어진다"가 증명된다.
        assertThat(ChatClients.OPENAI_BASE_URL).isEqualTo("https://api.openai.com/v1")
        assertThat(ChatClients.OPENROUTER_BASE_URL).isEqualTo("https://openrouter.ai/api/v1")
    }
}
