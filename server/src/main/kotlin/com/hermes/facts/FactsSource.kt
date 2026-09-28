package com.hermes.facts

import com.fasterxml.jackson.databind.JsonNode
import com.hermes.explain.BackendFacts
import com.hermes.explain.CourseBounds
import com.hermes.explain.FactsProjection
import java.time.LocalDate
import java.time.format.DateTimeParseException
import java.util.concurrent.CompletableFuture
import java.util.concurrent.CompletionException
import java.util.concurrent.ExecutorService
import java.util.concurrent.RejectedExecutionException

/**
 * 사실과, 같은 파싱에서 뽑은 도구 경계. 이어 묻기는 둘 다 필요하고, 설명 경로는
 * 사실만 필요하다.
 */
data class FetchedFacts(val facts: BackendFacts, val bounds: CourseBounds)

/**
 * 한적에서 사실을 모은다 — 호출 3회, 왕복 2회.
 *
 * 코스를 먼저 받아야 대상 관광지와 날짜를 알 수 있고, 그 둘이 정해지면 혼잡도와
 * 대안은 서로를 기다릴 이유가 없으므로 병렬로 간다.
 *
 * 목적지는 언제나 `visitOrder` 가 가장 작은 항목이다. `CourseRoutePolicy.bestOrder`
 * 가 `listOf(originId) + best` 를 반환하므로 목적지는 늘 첫 방문지이고 뒤로 밀리지
 * 않는다(concepts/travel-context-layer.md).
 */
class FactsSource(
    private val client: HanjeokClient,
    private val radiusKm: Int = 15,
    private val executor: ExecutorService,
) {

    /**
     * 사실만 필요한 쪽(설명 경로)이 쓴다.
     *
     * **경계를 계산하지 않는다.** 경계는 `targetDate` 를 `LocalDate` 로 파싱하는데,
     * 사실 조립(`FactsProjection`)은 그 필드를 문자열로만 읽는다 — 즉 ISO 가 아닌
     * 날짜로도 설명은 멀쩡히 나간다. 여기서 파싱하면 그 코스들이 도구와 아무 상관
     * 없이 500 으로 죽는다. `/agent/ask`, `/agent/explain`, `/agent/facts` 셋이
     * 이 함수를 탄다.
     */
    fun fetch(courseUuid: String): BackendFacts = gather(courseUuid).facts

    /**
     * 사실과 함께 이 코스의 도구 경계를 돌려준다. 이어 묻기의 스트리밍 경로만 쓴다.
     *
     * 경계를 따로 뽑는 함수를 두지 않는 이유는 코스 JSON 을 두 번 파싱하지 않기
     * 위해서다 — 한적을 한 번 더 부르는 것은 왕복 하나를 그냥 버리는 것이다.
     *
     * 날짜가 ISO 가 아니면 [HanjeokUnavailableException] 이다. 위층이 아는 실패
     * 타입은 그것 하나뿐이라, 파싱 예외가 그대로 새면 안전한 unavailable 프레임
     * 대신 처리되지 않은 500 이 된다.
     */
    fun fetchWithBounds(courseUuid: String): FetchedFacts {
        val gathered = gather(courseUuid)
        return FetchedFacts(facts = gathered.facts, bounds = boundsFor(gathered.course))
    }

    /** 코스 원문과 사실을 함께 들고 있는 중간 결과. 경계는 필요한 쪽만 뽑는다. */
    private class Gathered(val course: JsonNode, val facts: BackendFacts)

    private fun gather(courseUuid: String): Gathered {
        val course = client.course(courseUuid)

        val items = course.get("items")
        if (items == null || !items.isArray || items.isEmpty) {
            throw HanjeokUnavailableException("course $courseUuid carried no items")
        }

        val destination = items.minByOrNull { it.path("visitOrder").asInt(Int.MAX_VALUE) }
            ?: throw HanjeokUnavailableException("course $courseUuid has no destination item")
        val attractionId = destination.path("attractionId").asLong(0L)
        if (attractionId == 0L) throw HanjeokUnavailableException("destination item has no attractionId")

        val date = course.path("targetDate").asText(null)
            ?: throw HanjeokUnavailableException("course $courseUuid has no targetDate")

        // supplyAsync 는 executor 가 종료됐거나 포화 상태면 Future 밖에서,
        // 이 호출 스레드에서 곧바로 RejectedExecutionException 을 던진다 —
        // join() 의 catch 는 Future 안에서 일어난 실패만 보므로 그쪽으로는
        // 절대 걸리지 않는다. 나중 태스크가 이 executor 를
        // destroyMethod = "shutdown" 인 Spring 빈으로 등록하므로, 종료 중에
        // 도착한 요청이 정확히 이 경로를 탄다. 여기서 잡지 않으면 위층이
        // 알고 있는 유일한 실패 타입(HanjeokUnavailableException)이 아닌
        // 예외가 새어나가 안전한 503 대신 처리되지 않은 에러가 된다.
        val congestionFuture: CompletableFuture<JsonNode>
        val alternativesFuture: CompletableFuture<JsonNode>
        try {
            congestionFuture = CompletableFuture.supplyAsync({ client.congestion(attractionId, date) }, executor)
            alternativesFuture =
                CompletableFuture.supplyAsync({ client.alternatives(attractionId, date, radiusKm) }, executor)
        } catch (e: RejectedExecutionException) {
            throw HanjeokUnavailableException("hanjeok call was rejected by the executor (it may be shutting down)", e)
        }

        val congestion = join(congestionFuture, "congestion")
        val alternatives = join(alternativesFuture, "alternatives")

        val facts = try {
            FactsProjection.assemble(course = course, alternatives = alternatives, congestion = congestion)
        } catch (e: IllegalStateException) {
            // 투영은 필드가 빠지면 error() 를 던진다. 반쪽짜리 facts 로 설명을
            // 만들면 없는 근거를 지어내라고 시키는 것과 같으므로 여기서 멈춘다.
            throw HanjeokUnavailableException("hanjeok response did not carry the expected fields: ${e.message}", e)
        }

        return Gathered(course, BackendFacts(courseUuid = courseUuid, json = facts.toString()))
    }

    /**
     * 이 코스에서 도구가 움직일 수 있는 범위. [fetchWithBounds] 가 이미 파싱한 것을
     * 다시 파싱하지 않도록, 코스 JSON 을 받아 경계만 뽑는 순수 함수로 둔다.
     *
     * 범위는 코스가 정한다 — 모델이 정하지 않는다. `CourseTools.parse` 가 이 집합
     * 밖의 인자를 거부하므로, 여기서 빠진 관광지는 도구로 조회되지 않는다.
     *
     * 파싱 실패를 여기서 [HanjeokUnavailableException] 으로 바꾼다. 부르는 쪽마다
     * 감싸게 하면 한 곳이 빠졌을 때 그 경로만 500 이 되고, 그 차이는 테스트가
     * 아니라 운영에서 드러난다.
     */
    fun boundsFor(course: JsonNode): CourseBounds {
        val ids = course.path("items")
            .mapNotNull { it.path("attractionId").asLong(0L).takeIf { id -> id != 0L } }
            .toSet()
        val date = course.path("targetDate").asText(null)
            ?: throw HanjeokUnavailableException("course has no targetDate")
        val targetDate = try {
            LocalDate.parse(date)
        } catch (e: DateTimeParseException) {
            throw HanjeokUnavailableException("course targetDate is not an ISO date", e)
        }
        return CourseBounds(attractionIds = ids, targetDate = targetDate)
    }

    private fun join(future: CompletableFuture<JsonNode>, what: String): JsonNode = try {
        future.join()
    } catch (e: CompletionException) {
        val cause = e.cause
        if (cause is HanjeokUnavailableException) throw cause
        throw HanjeokUnavailableException("hanjeok $what call failed: ${cause?.let { it::class.simpleName }}", cause)
    }
}
