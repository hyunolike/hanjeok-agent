package com.hermes.explain

import com.hermes.context.BundleLoader
import com.hermes.context.CitationValidator
import com.hermes.context.PromptAssembler
import com.hermes.facts.FactsSource
import com.hermes.facts.HanjeokClient
import com.hermes.facts.HanjeokUnavailableException
import com.hermes.llm.Answered
import com.hermes.llm.Explanation
import com.hermes.llm.ExplanationProvider
import com.hermes.llm.Failed
import com.hermes.llm.ProviderResult
import com.hermes.llm.ProviderUsage
import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.databind.ObjectMapper
import org.assertj.core.api.Assertions.assertThat
import org.assertj.core.api.Assertions.assertThatThrownBy
import org.junit.jupiter.api.Test
import java.util.concurrent.Executors

class CourseExplainerTest {

    private val mapper = ObjectMapper()
    private val bundle = BundleLoader.load()
    private val executor = Executors.newFixedThreadPool(2)

    private val courseJson = """
        {"targetDate":"2026-08-15","title":"제목","congestionReductionRate":34,"summary":"요약",
         "recommendedDate":null,
         "items":[{"attractionId":1001,"name":"경복궁","visitOrder":1,"timeLabel":"오전 10:00",
                   "grade":"VERY_CROWDED","reason":"첫 방문지","travelMinutesFromPrev":null}]}
    """.trimIndent()

    private open inner class FakeClient : HanjeokClient {
        override fun course(courseUuid: String): JsonNode = mapper.readTree(courseJson)
        override fun congestion(attractionId: Long, date: String): JsonNode = mapper.readTree(
            """{"diagnosis":{"concentration":87.3,"percentile":92,"grade":"VERY_CROWDED","message":"붐빈다"},"betterDates":[]}""",
        )
        override fun alternatives(attractionId: Long, date: String, radiusKm: Int): JsonNode = mapper.readTree("[]")
    }

    private class CountingProvider(private val result: ProviderResult) : ExplanationProvider {
        override val name = "counting"
        var calls = 0
        override fun explain(systemText: String, factsJson: String): ProviderResult {
            calls++; return result
        }
    }

    private fun explainer(
        provider: ExplanationProvider,
        client: HanjeokClient = FakeClient(),
        cache: ExplanationCache = ExplanationCache(),
    ) = CourseExplainer(
        factsSource = FactsSource(client, 15, executor),
        service = ExplanationService(PromptAssembler(bundle), CitationValidator(bundle), provider),
        cache = cache,
    )

    private fun answered() = Answered(
        Explanation("경복궁은 붐빕니다.", listOf("concepts/congestion-diagnosis.md")),
        ProviderUsage(0, 0, 0, 0),
    )

    @Test
    fun `설명과 함께 facts 를 돌려준다`() {
        // 프론트가 코스를 그리려면 facts 가 필요하고, 그래야 한적을 직접 안 부른다.
        val result = explainer(CountingProvider(answered())).explain("abc")

        assertThat(result.explanation.explanation).isEqualTo("경복궁은 붐빕니다.")
        assertThat(mapper.readTree(result.factsJson).at("/items/0/name").asText()).isEqualTo("경복궁")
        assertThat(result.cached).isFalse()
    }

    @Test
    fun `같은 uuid 를 다시 물으면 모델을 다시 부르지 않는다`() {
        val provider = CountingProvider(answered())
        val explainer = explainer(provider)

        explainer.explain("abc")
        val second = explainer.explain("abc")

        assertThat(provider.calls).describedAs("facts 가 같을 때만 한 번이면 된다").isEqualTo(1)
        assertThat(second.cached).isTrue()
    }

    @Test
    fun `같은 uuid 를 동시에 물어도 모델은 한 번만 부른다`() {
        // 캐시는 **끝난** 호출만 막는다. 아직 진행 중인 호출은 못 막으므로, 처음
        // 보는 코스에 요청이 몰리면 전부 캐시 미스로 각자 유료 호출을 낸다.
        // Cloud Run 기본 동시성이 80 이라 콜드 코스 하나가 80 번 청구될 수 있다.
        val started = java.util.concurrent.CountDownLatch(1)
        val release = java.util.concurrent.CountDownLatch(1)
        val provider = object : ExplanationProvider {
            override val name = "slow"
            val calls = java.util.concurrent.atomic.AtomicInteger()
            override fun explain(systemText: String, factsJson: String): ProviderResult {
                calls.incrementAndGet()
                started.countDown()
                // 첫 호출을 붙잡아 두는 동안 나머지가 도착하게 한다 — 이 겹침이
                // 없으면 테스트는 순차 실행이 되어 아무것도 검증하지 못한다.
                release.await(5, java.util.concurrent.TimeUnit.SECONDS)
                return answered()
            }
        }
        val explainer = explainer(provider)
        val pool = Executors.newFixedThreadPool(8)

        val results = (1..8).map { pool.submit<CourseExplanation> { explainer.explain("abc") } }
        started.await(5, java.util.concurrent.TimeUnit.SECONDS)
        release.countDown()
        results.forEach { it.get(10, java.util.concurrent.TimeUnit.SECONDS) }
        pool.shutdown()

        assertThat(provider.calls.get())
            .describedAs("동시 요청 8건이 유료 호출 8번이 되면 안 된다")
            .isEqualTo(1)
    }

    @Test
    fun `동시 요청 중 하나가 실패하면 모두 같은 실패를 받는다`() {
        // 실패를 캐시하지 않는 규칙은 그대로다. 다만 같은 순간의 요청들은 같은
        // 호출을 기다렸으므로 같은 결과를 받아야 한다 — 일부만 성공한 것처럼
        // 보이면 재현할 수 없는 버그가 된다.
        val provider = CountingProvider(Failed("boom"))
        val explainer = explainer(provider)
        val pool = Executors.newFixedThreadPool(4)

        val results = (1..4).map {
            pool.submit<Result<CourseExplanation>> { runCatching { explainer.explain("abc") } }
        }
        val outcomes = results.map { it.get(10, java.util.concurrent.TimeUnit.SECONDS) }
        pool.shutdown()

        assertThat(outcomes).allMatch { it.isFailure }
        assertThat(outcomes.map { it.exceptionOrNull()!!::class })
            .containsOnly(ExplanationUnavailableException::class)
    }

    @Test
    fun `실패한 뒤에는 다시 부를 수 있다`() {
        // 진행 중 호출을 붙잡아 두는 자리를 정리하지 않으면, 한 번 실패한 코스가
        // 영원히 그 실패에 묶인다 — 실패를 캐시하지 않기로 한 이유가 무너진다.
        val provider = object : ExplanationProvider {
            override val name = "flaky"
            var calls = 0
            override fun explain(systemText: String, factsJson: String): ProviderResult {
                calls++
                return if (calls == 1) Failed("boom") else answered()
            }
        }
        val explainer = explainer(provider)

        assertThatThrownBy { explainer.explain("abc") }.isInstanceOf(ExplanationUnavailableException::class.java)
        val second = explainer.explain("abc")

        assertThat(second.explanation.explanation).isEqualTo("경복궁은 붐빕니다.")
        assertThat(provider.calls).isEqualTo(2)
    }

    @Test
    fun `한적이 실패하면 설명 불가로 바뀐다`() {
        val client = object : FakeClient() {
            override fun course(courseUuid: String): JsonNode = throw HanjeokUnavailableException("down")
        }

        assertThatThrownBy { explainer(CountingProvider(answered()), client).explain("abc") }
            .isInstanceOf(ExplanationUnavailableException::class.java)
    }

    @Test
    fun `설명 생성이 실패하면 캐시에 넣지 않는다`() {
        // 실패를 캐시하면 일시적 장애가 그 코스에 영구히 눌어붙는다.
        val provider = CountingProvider(Failed("timeout"))
        val cache = ExplanationCache()
        val explainer = explainer(provider, cache = cache)

        assertThatThrownBy { explainer.explain("abc") }.isInstanceOf(ExplanationUnavailableException::class.java)

        assertThat(cache.size()).isZero()
        assertThat(cache.get(ExplanationKey("abc", "unused"))).isNull()
    }
}
