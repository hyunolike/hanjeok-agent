package com.hermes.explain

import com.fasterxml.jackson.databind.ObjectMapper
import com.hermes.llm.ToolCall
import com.hermes.llm.ToolSpec
import java.time.LocalDate
import java.time.format.DateTimeParseException
import kotlin.math.abs

/** 이 요청에서 도구가 움직일 수 있는 범위. 코스가 정한다 — 모델이 정하지 않는다. */
data class CourseBounds(val attractionIds: Set<Long>, val targetDate: LocalDate)

sealed interface ToolArgs

data class Congestion(val attractionId: Long, val date: LocalDate) : ToolArgs

data class Alternatives(val attractionId: Long, val date: LocalDate, val radiusKm: Int) : ToolArgs

/**
 * 인자가 범위를 벗어났다. **예외가 아니다** — 사유를 도구 결과 자리에 넣어 되먹이면
 * 모델이 고쳐 부르거나 포기할 수 있다. 던지면 한 번 잘못 부른 것이 요청 전체를 죽인다.
 */
data class Rejected(val reason: String) : ToolArgs

/**
 * 한적에서 도구가 될 만한 것은 둘뿐이다. `course` 는 어차피 매 요청 받으므로 도구가
 * 아니다.
 *
 * **인자는 모델을 믿지 않는다.** 날짜 범위를 두는 이유는 한적 예보가 먼 날짜를 갖고
 * 있지 않아서다 — 범위가 없으면 모델이 1년 뒤를 물어 빈 응답을 받고, 그 빈 응답을
 * 사실로 설명하게 된다.
 */
object CourseTools {

    const val CONGESTION = "congestion"
    const val ALTERNATIVES = "alternatives"

    const val DEFAULT_RADIUS_KM = 15
    const val MIN_RADIUS_KM = 1
    const val MAX_RADIUS_KM = 50
    const val MAX_DATE_OFFSET_DAYS = 14L

    private val MAPPER = ObjectMapper()

    fun specs(): List<ToolSpec> = listOf(
        ToolSpec(
            name = CONGESTION,
            description = "특정 관광지의 특정 날짜 혼잡도를 조회한다. " +
                "코스에 이미 실린 날짜가 아닌 다른 날을 물어볼 때만 쓴다.",
            parametersSchema = """
                {"type":"object",
                 "properties":{
                   "attractionId":{"type":"integer","description":"이 코스에 실제로 있는 관광지 id"},
                   "date":{"type":"string","description":"YYYY-MM-DD"}},
                 "required":["attractionId","date"],
                 "additionalProperties":false}
            """.trimIndent(),
        ),
        ToolSpec(
            name = ALTERNATIVES,
            description = "특정 관광지 주변의 대안 장소를 조회한다. " +
                "기본 반경보다 넓게 또는 좁게 보라는 요청이 있을 때만 쓴다.",
            parametersSchema = """
                {"type":"object",
                 "properties":{
                   "attractionId":{"type":"integer","description":"이 코스에 실제로 있는 관광지 id"},
                   "date":{"type":"string","description":"YYYY-MM-DD"},
                   "radiusKm":{"type":"integer","description":"$MIN_RADIUS_KM~$MAX_RADIUS_KM, 기본 $DEFAULT_RADIUS_KM"}},
                 "required":["attractionId","date"],
                 "additionalProperties":false}
            """.trimIndent(),
        ),
    )

    fun parse(call: ToolCall, bounds: CourseBounds): ToolArgs {
        if (call.name != CONGESTION && call.name != ALTERNATIVES) {
            return Rejected("'${call.name}' 은 없는 도구다. 쓸 수 있는 것은 $CONGESTION 과 $ALTERNATIVES 뿐이다.")
        }

        val node = try {
            MAPPER.readTree(call.argumentsJson)
        } catch (e: Exception) {
            return Rejected("인자가 올바른 JSON 이 아니다: ${e::class.simpleName}")
        }

        val attractionId = node.path("attractionId").asLong(0L)
        if (attractionId !in bounds.attractionIds) {
            return Rejected(
                "attractionId $attractionId 는 이 코스에 없다. " +
                    "쓸 수 있는 것은 ${bounds.attractionIds.sorted().joinToString(", ")} 다.",
            )
        }

        val raw = node.path("date").asText(null)
            ?: return Rejected("date 가 없다. YYYY-MM-DD 형식으로 준다.")
        val date = try {
            LocalDate.parse(raw)
        } catch (e: DateTimeParseException) {
            return Rejected("date '$raw' 를 읽을 수 없다. YYYY-MM-DD 형식으로 준다.")
        }

        val offset = abs(date.toEpochDay() - bounds.targetDate.toEpochDay())
        if (offset > MAX_DATE_OFFSET_DAYS) {
            return Rejected(
                "date '$raw' 는 코스 날짜(${bounds.targetDate})에서 $MAX_DATE_OFFSET_DAYS 일을 넘는다. " +
                    "그 범위 밖은 예보가 없다.",
            )
        }

        if (call.name == CONGESTION) return Congestion(attractionId, date)

        val radius = if (node.has("radiusKm")) node.path("radiusKm").asInt(-1) else DEFAULT_RADIUS_KM
        if (radius < MIN_RADIUS_KM || radius > MAX_RADIUS_KM) {
            return Rejected("radiusKm 은 $MIN_RADIUS_KM 이상 $MAX_RADIUS_KM 이하여야 한다.")
        }

        return Alternatives(attractionId, date, radius)
    }
}
