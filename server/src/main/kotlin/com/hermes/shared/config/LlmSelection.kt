package com.hermes.shared.config

import com.anthropic.client.AnthropicClient
import com.anthropic.client.okhttp.AnthropicOkHttpClient
import com.hermes.llm.ChatClients
import com.hermes.llm.ExplanationProvider
import com.hermes.llm.SpringAiExplanationProvider
import com.openai.client.okhttp.OpenAIOkHttpClient
import com.openai.client.okhttp.OpenAIOkHttpClientAsync
import org.springframework.ai.anthropic.AnthropicChatModel
import org.springframework.ai.openai.OpenAiChatModel

/**
 * 운영 서버의 프로바이더를 설정으로 고른다.
 *
 * 이전에는 `AnthropicExplanationProvider` 로 고정돼 있었다. 그런데 이 프로젝트가
 * 실제로 측정한 것은 전부 OpenAI 다 — 배포하면 한 번도 재본 적 없는 프로바이더가
 * 돌고, 하네스가 낸 "위반율 0%"는 그 서버에 대해 아무것도 말해 주지 않는다.
 * `EvalMain` 과 **같은 세 이름**을 쓰는 이유가 이것이다: 잰 것을 그대로 띄운다.
 *
 * 자격 증명은 `System.getenv` 대신 함수로 받는다 — 테스트가 프로세스 전역
 * 환경변수를 건드리지 않고도 두 상태를 모두 검증할 수 있어야 한다.
 *
 * 세 프로바이더 모두 `hermes.llm.model` 을 따른다. 이전에는 anthropic 만 이 인자를
 * 버리고 모델을 코드에 박아 두어, `docs/deploy.md` 가 약속한 `HERMES_LLM_MODEL` 이
 * 그 경로에서만 조용히 무시됐다. 이제는 모든 분기가 `model` 을 프로바이더 클래스에
 * 박아 두는 대신 `ChatClients` 의 옵션 조립 함수로 그대로 흘려보내므로, 실제로
 * 나가는 요청에 그 값이 실린다.
 */
object LlmSelection {

    fun provider(
        name: String,
        model: String,
        env: (String) -> String?,
        // 운영 경로에는 영향이 없다 — null 이면 지금과 똑같은 프로덕션 baseUrl 을
        // 쓴다. 원래는 `anthropicBaseUrl`이라는 이름으로 anthropic 분기에만
        // 있었는데, 그 한 파라미터를 세 분기 전부가 나눠 쓰도록 일반화했다 —
        // `provider(...)`는 한 번에 이름 하나만 골라 그 분기 하나만 돈다, 그래서
        // "지금 고른 분기의 baseUrl"이라는 뜻으로 값 하나면 충분하고, 분기별로
        // 파라미터를 따로 두면 "둘 다 채워지면 어느 게 이기나"라는 질문이 공짜로
        // 따라온다. 이 값이 존재하는 유일한 이유는 테스트가
        // `LlmSelection.provider(...)` 가 실제로 조립해 내보내는 요청 바이트를
        // 루프백 엔드포인트로 가로챌 수 있게 하는 것뿐이다 —
        // `OpenAiCompatibleExplanationProvider.openAi(apiKey, model, http = null)` 와
        // 같은 자리의 같은 이유다.
        //
        // 이 파라미터가 없던 채로 openai/openrouter 분기를 고쳤을 때(Task 7 3차
        // 재작업 이전) 리뷰어가 `LlmSelection.kt`의
        // `baseUrl = ChatClients.OPENAI_BASE_URL`을
        // `baseUrl = ChatClients.OPENAI_BASE_URL.removeSuffix("/v1")`로 뮤테이션해도
        // `./gradlew build`가 그대로 통과했다 — `SpringAiRequestShapeTest`의 캡처
        // 테스트가 `LlmSelection`을 거치지 않고 클라이언트를 손으로 다시 조립해서
        // 배선 자체는 아무것도 고정하지 않았기 때문이다. `LlmSelectionTest`의
        // end-to-end 캡처 테스트가 이제 그 틈을 닫는다.
        baseUrlOverride: String? = null,
    ): ExplanationProvider =
        when (name) {
            // Anthropic SDK 는 키가 없어도 던지지 않고 인증되지 않은 클라이언트를
            // 만든다. 그 검사는 LlmCredentialHealthIndicator 가 맡는다.
            "anthropic" -> SpringAiExplanationProvider(
                name = "anthropic",
                chatModel = AnthropicChatModel.builder()
                    .anthropicClient(anthropicClient(baseUrlOverride))
                    .options(ChatClients.anthropicOptions(model))
                    .build(),
            )
            // 분기는 자기를 구분하는 것(이름·키·모델·override)만 넘긴다. baseUrl 은
            // `name` 에서 나오므로, 분기가 이름과 다른 URL 을 짝지을 자리가 없다.
            "openai" -> springAiOpenAiCompatible(
                name = "openai",
                apiKey = require(env, "OPENAI_API_KEY"),
                model = model,
                baseUrlOverride = baseUrlOverride,
            )
            "openrouter" -> springAiOpenAiCompatible(
                name = "openrouter",
                apiKey = require(env, "OPENROUTER_API_KEY"),
                model = model,
                baseUrlOverride = baseUrlOverride,
            )
            else -> error(
                "unknown hermes.llm.provider: '$name' (expected anthropic, openai, or openrouter)",
            )
        }

    /**
     * `baseUrlOverride` 가 없을 때 분기별로 실제로 쓰는 운영 baseUrl 을 고른다.
     * 순수 함수로 뽑아 둔 이유는 `ChatClients` 의 옵션 조립 함수들과 같다 —
     * "openrouter 분기가 실제로 `ChatClients.OPENROUTER_BASE_URL` 을 쓴다"를
     * override 없이, 키 없이 직접 검사할 수 있어야 한다.
     *
     * 이 함수를 따로 떼어내기 전에는 `baseUrlOverride ?: ChatClients.OPENROUTER_BASE_URL`
     * 처럼 상수 선택이 `provider(...)` 안에 박혀 있었는데, 테스트가 전부
     * `baseUrlOverride` 를 채워서 호출했기 때문에 `?:` 가 항상 override 로
     * 단락(short-circuit)되어 그 상수 자체는 한 번도 평가되지 않았다 — 리뷰어가
     * openrouter 분기의 상수를 `OPENAI_BASE_URL` 로 바꿔도 전체 스위트가 그린으로
     * 남은 이유다. `defaultBaseUrl(...)` 을 override 없이 직접 부르면 이 상수
     * 선택 자체가 테스트 대상이 된다.
     *
     * "openai"/"openrouter" 외의 이름은 `provider(...)` 의 `when(name)` 이 이
     * 함수를 부르기 전에 이미 갈라낸다(anthropic 은 `fromEnv()`, 그 외 이름은
     * 위에서 바로 `error()`). 그래도 이 함수가 독립적으로 테스트되는 이상, 모르는
     * 이름을 아무 URL 로 조용히 떨어뜨리는 대신 즉시 죽는다 — 있어선 안 되는
     * 호출이 있어선 안 되는 채로 조용히 넘어가지 않게 한다.
     */
    internal fun defaultBaseUrl(providerName: String): String =
        when (providerName) {
            "openai" -> ChatClients.OPENAI_BASE_URL
            "openrouter" -> ChatClients.OPENROUTER_BASE_URL
            else -> error("defaultBaseUrl has no default for '$providerName' (expected openai or openrouter)")
        }

    /**
     * `openAiClientAsync(...)` 도 같이 준다 — 실측으로 확인한 내용이다. `.build()` 가
     * sync 클라이언트는 우리가 준 것을 그대로 쓰지만(javap 로 확인:
     * `Objects.requireNonNullElseGet` 이 null 이 아니면 supplier 를 안 부른다), async
     * 필드는 안 채우면 `OpenAiSetup.setupAsyncClient(...)` 로 기본 클라이언트를
     * 새로 만들려 하고, 그 기본 조립은 `OpenAiChatOptions.getApiKey()` 에서 키를
     * 찾는다. `ChatClients.openAiCompatibleOptions` 는 순수 함수로 model/baseUrl/
     * maxTokens 만 싣고 apiKey 를 모른다 — 그래서 async 클라이언트를 안 주면
     * `IllegalStateException: At least one credential source must be specified`
     * 로 죽는다(테스트로 확인). `.call()` 만 쓰는 동기 경로에서도 `.build()` 가
     * async 클라이언트를 즉시 필요로 하므로, 같은 키/baseUrl 로 만든 async
     * 클라이언트를 명시적으로 준다.
     */
    private fun springAiOpenAiCompatible(
        name: String,
        apiKey: String,
        model: String,
        baseUrlOverride: String?,
    ): ExplanationProvider {
        // override 가 없으면 프로바이더 이름이 baseUrl 을 정한다 — 분기가 아니라.
        val baseUrl = baseUrlOverride ?: defaultBaseUrl(name)
        return SpringAiExplanationProvider(
            name = name,
            chatModel = OpenAiChatModel.builder()
                .openAiClient(
                    OpenAIOkHttpClient.builder()
                        .apiKey(apiKey)
                        .baseUrl(baseUrl)
                        .build(),
                )
                .openAiClientAsync(
                    OpenAIOkHttpClientAsync.builder()
                        .apiKey(apiKey)
                        .baseUrl(baseUrl)
                        .build(),
                )
                .options(ChatClients.openAiCompatibleOptions(model, baseUrl))
                .build(),
        )
    }

    /**
     * `baseUrl == null` 이면 `AnthropicOkHttpClient.fromEnv()` 와 바이트코드 수준으로
     * 같다 — 그 정적 팩토리 자체가 `builder().fromEnv().build()` 로 구현돼 있다
     * (javap 로 확인). `fromEnv()` 가 키를 못 찾아도 던지지 않는 동작은 그대로
     * 남는다 — 그 검사는 여전히 `LlmCredentialHealthIndicator` 가 맡는다. 테스트가
     * 넘긴 `baseUrl` 이 있을 때만 `fromEnv()` 뒤에 그 값으로 덮어써, 운영 경로의
     * 자격 증명 처리 순서를 건드리지 않는다.
     */
    private fun anthropicClient(baseUrl: String?): AnthropicClient {
        val builder = AnthropicOkHttpClient.builder().fromEnv()
        if (baseUrl != null) builder.baseUrl(baseUrl)
        return builder.build()
    }

    /**
     * 빈 값을 없는 값과 같이 다룬다. 빈 키는 프로바이더까지 가서 401 로 돌아오는데,
     * 그 401 은 "키가 틀렸다"와 "키를 안 넣었다"를 구분해 주지 않는다.
     */
    private fun require(env: (String) -> String?, name: String): String =
        env(name)?.takeIf { it.isNotBlank() }
            ?: error("$name is not set (or is empty) — the '$name' credential is required for this provider")
}
