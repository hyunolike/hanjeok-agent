package com.hermes.explain

import com.hermes.context.BundleLoader
import com.hermes.context.CitationValidator
import com.hermes.context.PromptAssembler
import com.hermes.llm.Answered
import com.hermes.llm.Explanation
import com.hermes.llm.ExplanationProvider
import com.hermes.llm.Failed
import com.hermes.llm.ProviderResult
import com.hermes.llm.ProviderUsage
import com.hermes.llm.Refused
import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test

class ExplanationServiceTest {

    private val bundle = BundleLoader.load()
    private val facts = BackendFacts("3f6c2b18", """{"targetDate":"2026-08-15"}""")

    private class StubProvider(private val result: ProviderResult) : ExplanationProvider {
        override val name = "stub"
        var receivedFacts: String? = null
        override fun explain(systemText: String, factsJson: String): ProviderResult {
            receivedFacts = factsJson
            return result
        }
    }

    private fun service(result: ProviderResult): Pair<ExplanationService, StubProvider> {
        val provider = StubProvider(result)
        return ExplanationService(
            PromptAssembler(bundle), CitationValidator(bundle), provider,
        ) to provider
    }

    private fun answered(vararg citations: String) = Answered(
        Explanation("경복궁은 8월 15일 매우 붐빕니다.", citations.toList()),
        ProviderUsage(0, 0, 0, 0),
    )

    @Test
    fun `유효한 인용이면 설명을 돌려준다`() {
        val (svc, provider) = service(answered("concepts/congestion-diagnosis.md"))

        val outcome = svc.explain(facts)

        assertThat(outcome).isInstanceOf(Explained::class.java)
        assertThat(provider.receivedFacts).isEqualTo(facts.json)
    }

    @Test
    fun `번들에 없는 문서를 인용하면 설명을 내보내지 않는다`() {
        // 이게 이 루프의 존재 이유다. 그럴듯한 거짓 인용이 사용자에게 나가는 것이
        // 이 저장소가 막으려는 실패다.
        val (svc, _) = service(answered("concepts/made-up.md"))

        val outcome = svc.explain(facts)

        assertThat(outcome).isInstanceOf(Unavailable::class.java)
        assertThat((outcome as Unavailable).reason).contains("concepts/made-up.md")
    }

    @Test
    fun `인용이 비면 설명을 내보내지 않는다`() {
        val (svc, _) = service(answered())

        assertThat(svc.explain(facts)).isInstanceOf(Unavailable::class.java)
    }

    @Test
    fun `거절은 실패와 구분해 이유에 남긴다`() {
        val (svc, _) = service(Refused("cyber"))

        val outcome = svc.explain(facts)

        assertThat((outcome as Unavailable).reason).contains("refusal").contains("cyber")
    }

    @Test
    fun `프로바이더 실패는 그대로 사용 불가로 이어진다`() {
        val (svc, _) = service(Failed("timeout after 8s"))

        assertThat((svc.explain(facts) as Unavailable).reason).contains("timeout after 8s")
    }

    @Test
    fun `존재하는 무관한 인용도 설명을 내보내지 않는다`() {
        val (svc, _) = service(answered("concepts/travel-context-layer.md"))
        assertThat((svc.explain(facts) as Unavailable).reason).startsWith("citations missing policy support:")
    }
}
