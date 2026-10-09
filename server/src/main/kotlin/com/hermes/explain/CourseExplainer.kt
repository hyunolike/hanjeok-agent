package com.hermes.explain

import com.hermes.facts.FactsSource
import com.hermes.facts.HanjeokUnavailableException
import com.hermes.llm.Explanation
import org.slf4j.LoggerFactory
import java.time.Clock
import java.time.Instant
import java.util.concurrent.CompletableFuture
import java.util.concurrent.ConcurrentHashMap

data class CourseExplanation(
    val explanation: Explanation,
    val factsJson: String,
    val cached: Boolean,
    val generatedAt: Instant,
    val retrievedAt: Instant,
    val factsSha256: String,
    val bundleSha256: String,
)

/**
 * facts는 매 요청 새로 조회한다. 캐시가 생략하는 것은 LLM 호출뿐이며 한적의 3회
 * 조회 부하는 줄지 않는다. 동일한 facts 바이트를 가진 요청만 설명 생성을 공유한다.
 * 실패한 조회/생성은 캐시에 넣거나 예전 설명으로 숨기지 않는다.
 */
class CourseExplainer(
    private val factsSource: FactsSource,
    private val service: ExplanationService,
    private val cache: ExplanationCache,
    private val clock: Clock = Clock.systemUTC(),
) {

    private val log = LoggerFactory.getLogger(CourseExplainer::class.java)

    /** facts-bound key → 진행 중인 설명 생성. 끝나면 즉시 제거된다. */
    private val inFlight = ConcurrentHashMap<ExplanationKey, CompletableFuture<CachedExplanation>>()

    fun explain(courseUuid: String): CourseExplanation {
        val facts = try {
            factsSource.fetch(courseUuid)
        } catch (e: HanjeokUnavailableException) {
            log.warn("facts unavailable for course {}", courseUuid, e)
            throw ExplanationUnavailableException("facts: ${e.message}")
        }

        val retrievedAt = clock.instant()
        val key = ExplanationKey(courseUuid, sha256(facts.json))
        val cached = cache.get(key)
        val (entry, reusedCache) = cached?.let { it to true } ?: explanationFor(key, facts)
        return CourseExplanation(
            explanation = entry.explanation,
            factsJson = facts.json,
            cached = reusedCache,
            generatedAt = entry.generatedAt,
            retrievedAt = retrievedAt,
            factsSha256 = key.factsSha256,
            bundleSha256 = service.bundleSha256,
        )
    }

    private fun explanationFor(key: ExplanationKey, facts: BackendFacts): Pair<CachedExplanation, Boolean> {
        var leader = false
        val pending = inFlight.computeIfAbsent(key) {
            leader = true
            CompletableFuture()
        }

        if (!leader) {
            // 남의 호출을 기다린다. 그쪽이 실패하면 같은 예외를 받는다 — 같은 순간의
            // 요청이 서로 다른 결과를 받으면 재현할 수 없는 버그가 된다.
            return try {
                pending.join() to false
            } catch (e: java.util.concurrent.CompletionException) {
                throw e.cause ?: e
            }
        }

        try {
            // A request can pass the first cache read just before a leader completes.
            cache.get(key)?.let {
                pending.complete(it)
                return it to true
            }
            when (val outcome = service.explain(facts)) {
                is Explained -> {
                    // 실패는 캐시하지 않는다 — 일시적 장애가 그 코스에 영구히 눌어붙는다.
                    val entry = CachedExplanation(outcome.explanation, clock.instant())
                    cache.put(key, entry)
                    pending.complete(entry)
                    return entry to false
                }
                is Unavailable -> {
                    log.warn("explanation unavailable for course {}: {}", key.courseUuid, outcome.reason)
                    val failure = ExplanationUnavailableException(outcome.reason)
                    pending.completeExceptionally(failure)
                    throw failure
                }
            }
        } catch (e: Throwable) {
            // 예상 못 한 예외로 빠져나가도 기다리는 쪽을 매달아 두지 않는다.
            pending.completeExceptionally(e)
            throw e
        } finally {
            // 자리를 비우는 것이 실패를 캐시하지 않는다는 규칙의 나머지 절반이다.
            inFlight.remove(key, pending)
        }
    }
}
