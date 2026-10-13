package com.hermes.explain

import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.databind.ObjectMapper
import com.hermes.context.BundleLoader
import com.hermes.context.CitationValidator
import com.hermes.context.PromptAssembler
import com.hermes.facts.FactsSource
import com.hermes.facts.HanjeokClient
import com.hermes.facts.HanjeokUnavailableException
import com.hermes.llm.*
import org.assertj.core.api.Assertions.assertThat
import org.assertj.core.api.Assertions.assertThatThrownBy
import org.junit.jupiter.api.AfterEach
import org.junit.jupiter.api.Test
import java.util.concurrent.*
import java.util.concurrent.atomic.AtomicReference

class CacheFreshnessTest {
    private val mapper = ObjectMapper()
    private val executor = Executors.newFixedThreadPool(2)
    private val clock = MutableClock()
    private val title = AtomicReference("old")
    private var diagnosis = """{"diagnosis":{"concentration":87.3,"percentile":92,"grade":"VERY_CROWDED","message":"붐빈다"},"betterDates":[]}"""
    private var alternatives = "[]"
    private var failed = false
    private val client = object : HanjeokClient {
        override fun course(courseUuid: String): JsonNode {
            if (failed) throw HanjeokUnavailableException("down")
            return mapper.readTree("""{"targetDate":"2026-08-15","title":"${title.get()}","congestionReductionRate":34,"summary":"요약","recommendedDate":null,"items":[{"attractionId":1001,"name":"경복궁","visitOrder":1,"timeLabel":"오전 10:00","grade":"VERY_CROWDED","reason":"첫 방문지","travelMinutesFromPrev":null}]}""")
        }
        override fun congestion(attractionId: Long, date: String): JsonNode = mapper.readTree(diagnosis)
        override fun alternatives(attractionId: Long, date: String, radiusKm: Int): JsonNode = mapper.readTree(alternatives)
    }
    private fun response(text: String) = Answered(Explanation(text, listOf("concepts/congestion-diagnosis.md")), ProviderUsage(0, 0, 0, 0))
    private open inner class EchoProvider : ExplanationProvider {
        override val name = "facts-echo"
        var calls = 0
        override fun explain(systemText: String, userText: String): ProviderResult {
            calls++
            return response(sha256(userText))
        }
    }
    private fun explainer(provider: ExplanationProvider): CourseExplainer {
        val bundle = BundleLoader.load()
        return CourseExplainer(FactsSource(client, 15, executor),
            ExplanationService(PromptAssembler(bundle), CitationValidator(bundle), provider),
            ExplanationCache(clock = clock), clock)
    }
    @AfterEach
    fun close() { executor.shutdownNow() }

    @Test
    fun `같은 코스의 혼잡도 부재 대안 변경은 새 설명을 만든다`() {
        val provider = EchoProvider()
        val explainer = explainer(provider)
        val first = explainer.explain("abc")
        diagnosis = diagnosis.replace("87.3", "12.0")
        val changed = explainer.explain("abc")
        diagnosis = """{"hasCongestionData":false,"diagnosis":null,"message":"자료 없음","betterDates":[]}"""
        val absent = explainer.explain("abc")
        alternatives = """[{"attractionId":1002,"name":"대안","grade":"RELAXED","concentration":12.0,"distanceKm":1.0,"relationScore":0,"score":1,"recommendReason":"이유","travelMinutes":5}]"""
        val alternative = explainer.explain("abc")
        assertThat(provider.calls).isEqualTo(4)
        assertThat(listOf(changed, absent, alternative)).allMatch { !it.cached }
        assertThat(changed.explanation).isNotEqualTo(first.explanation)
        assertThat(mapper.readTree(absent.factsJson).at("/congestion/hasCongestionData").asBoolean()).isFalse()
        assertThat(explainer.explain("abc").cached).isTrue()
    }

    @Test
    fun `과거 날짜는 보존하고 TTL 뒤에 새 생성 시각을 기록한다`() {
        val provider = EchoProvider()
        val explainer = explainer(provider)
        val first = explainer.explain("abc")
        clock.now = clock.now.plusSeconds(299)
        val second = explainer.explain("abc")
        assertThat(second.generatedAt).isEqualTo(first.generatedAt)
        assertThat(second.retrievedAt).isAfter(first.retrievedAt)
        assertThat(mapper.readTree(second.factsJson).path("targetDate").asText()).isEqualTo("2026-08-15")
        clock.now = clock.now.plusSeconds(1)
        val expired = explainer.explain("abc")
        assertThat(expired.cached).isFalse()
        assertThat(expired.generatedAt).isEqualTo(clock.now)
        assertThat(provider.calls).isEqualTo(2)
    }

    @Test
    fun `진행 중인 같은 UUID 의 다른 facts 는 예전 설명을 기다리지 않는다`() {
        val started = CountDownLatch(1)
        val release = CountDownLatch(1)
        val provider = object : ExplanationProvider {
            override val name = "slow-echo"
            override fun explain(systemText: String, userText: String): ProviderResult {
                val value = mapper.readTree(userText).path("title").asText()
                if (value == "old") {
                    started.countDown()
                    check(release.await(5, TimeUnit.SECONDS))
                }
                return response(value)
            }
        }
        val explainer = explainer(provider)
        val pool = Executors.newFixedThreadPool(2)
        try {
            val old = pool.submit<CourseExplanation> { explainer.explain("abc") }
            check(started.await(5, TimeUnit.SECONDS))
            title.set("new")
            val newer = pool.submit<CourseExplanation> { explainer.explain("abc") }.get(3, TimeUnit.SECONDS)
            assertThat(newer.explanation.explanation).isEqualTo("new")
            assertThat(mapper.readTree(newer.factsJson).path("title").asText()).isEqualTo("new")
            release.countDown()
            assertThat(old.get(5, TimeUnit.SECONDS).explanation.explanation).isEqualTo("old")
            assertThat(explainer.explain("abc").explanation.explanation).isEqualTo("new")
        } finally {
            release.countDown()
            pool.shutdownNow()
        }
    }

    @Test
    fun `facts 실패는 이미 캐시된 설명으로 숨기지 않는다`() {
        val provider = EchoProvider()
        val explainer = explainer(provider)
        explainer.explain("abc")
        failed = true
        assertThatThrownBy { explainer.explain("abc") }.isInstanceOf(ExplanationUnavailableException::class.java)
        assertThat(provider.calls).isEqualTo(1)
    }
}
