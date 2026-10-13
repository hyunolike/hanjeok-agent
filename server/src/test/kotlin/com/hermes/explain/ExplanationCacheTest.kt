package com.hermes.explain

import com.hermes.llm.Explanation
import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test
import java.time.Clock
import java.time.Duration
import java.time.Instant
import java.time.ZoneId
import java.time.ZoneOffset

internal class MutableClock(var now: Instant = Instant.parse("2026-10-09T00:00:00Z")) : Clock() {
    override fun getZone(): ZoneId = ZoneOffset.UTC
    override fun withZone(zone: ZoneId): Clock = this
    override fun instant(): Instant = now
}

class ExplanationCacheTest {
    private val clock = MutableClock()
    private fun key(course: String, facts: String = "facts") = ExplanationKey(course, sha256(facts))
    private fun entry(text: String) = CachedExplanation(Explanation(text, listOf("concepts/congestion-diagnosis.md")), clock.instant())

    @Test
    fun `동일 facts 만 재사용하며 생성 시각을 보존한다`() {
        val cache = ExplanationCache(clock = clock)
        val generated = entry("A")
        cache.put(key("a"), generated)
        clock.now = clock.now.plusSeconds(60)
        assertThat(cache.get(key("a"))).isEqualTo(generated)
        assertThat(cache.get(key("a", "changed"))).isNull()
        assertThat(cache.get(key("b"))).isNull()
    }

    @Test
    fun `조회는 TTL 을 연장하지 않고 정확한 만료 경계에서 버린다`() {
        val cache = ExplanationCache(ttl = Duration.ofMinutes(5), clock = clock)
        cache.put(key("a"), entry("A"))
        clock.now = clock.now.plusSeconds(299)
        assertThat(cache.get(key("a"))).isNotNull()
        clock.now = clock.now.plusSeconds(1)
        assertThat(cache.get(key("a"))).isNull()
        assertThat(cache.size()).isZero()
    }

    @Test
    fun `LRU 상한을 유지한다`() {
        val cache = ExplanationCache(maxEntries = 2, clock = clock)
        cache.put(key("a"), entry("A"))
        cache.put(key("b"), entry("B"))
        cache.get(key("a"))
        cache.put(key("c"), entry("C"))
        assertThat(cache.size()).isEqualTo(2)
        assertThat(cache.get(key("b"))).isNull()
        assertThat(cache.get(key("a"))).isNotNull()
    }
}
