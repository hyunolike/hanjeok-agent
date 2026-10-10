package com.hermes.explain

import com.hermes.llm.Explanation
import java.security.MessageDigest
import java.time.Clock
import java.time.Duration
import java.time.Instant

/** Exact bytes sent to the model; a harmless serialization change may cause a safe miss. */
internal fun sha256(text: String): String = MessageDigest.getInstance("SHA-256")
    .digest(text.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }

data class ExplanationKey(val courseUuid: String, val factsSha256: String, val contextIdentity: String = "")
data class CachedExplanation(val explanation: Explanation, val generatedAt: Instant)

/** Process-local model/bundle are fixed. Cache and single-flight share the facts-bound key. */
class ExplanationCache(
    private val maxEntries: Int = 1000,
    private val ttl: Duration = Duration.ofMinutes(5),
    private val clock: Clock = Clock.systemUTC(),
) {
    init {
        require(maxEntries > 0)
        require(!ttl.isNegative && !ttl.isZero)
    }

    private val entries = object : LinkedHashMap<ExplanationKey, CachedExplanation>(16, 0.75f, true) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<ExplanationKey, CachedExplanation>): Boolean =
            size > maxEntries
    }

    @Synchronized
    fun get(key: ExplanationKey): CachedExplanation? {
        val entry = entries[key] ?: return null
        if (!clock.instant().isBefore(entry.generatedAt.plus(ttl))) {
            entries.remove(key)
            return null
        }
        return entry
    }

    @Synchronized
    fun put(key: ExplanationKey, entry: CachedExplanation) {
        entries[key] = entry
    }

    @Synchronized
    fun size(): Int = entries.size
}
