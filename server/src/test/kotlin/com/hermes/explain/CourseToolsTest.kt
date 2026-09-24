package com.hermes.explain

import com.hermes.llm.ToolCall
import java.time.LocalDate
import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test

class CourseToolsTest {

    private val bounds = CourseBounds(
        attractionIds = setOf(11L, 22L),
        targetDate = LocalDate.of(2026, 10, 1),
    )

    private fun call(name: String, args: String) = ToolCall("id-1", name, args)

    @Test
    fun `도구는 둘이고 이름이 고정이다`() {
        assertThat(CourseTools.specs().map { it.name }).isEqualTo(listOf("congestion", "alternatives"))
    }

    @Test
    fun `유효한 congestion 인자를 판다`() {
        val args = CourseTools.parse(
            call("congestion", """{"attractionId":11,"date":"2026-10-03"}"""),
            bounds,
        )
        assertThat(args).isEqualTo(Congestion(11L, LocalDate.of(2026, 10, 3)))
    }

    @Test
    fun `alternatives 의 radiusKm 기본값은 15 다`() {
        val args = CourseTools.parse(
            call("alternatives", """{"attractionId":22,"date":"2026-10-01"}"""),
            bounds,
        )
        assertThat(args).isEqualTo(Alternatives(22L, LocalDate.of(2026, 10, 1), 15))
    }

    @Test
    fun `코스에 없는 attractionId 는 거부된다`() {
        val args = CourseTools.parse(
            call("congestion", """{"attractionId":99,"date":"2026-10-01"}"""),
            bounds,
        )
        assertThat(args).isInstanceOf(Rejected::class.java)
        assertThat((args as Rejected).reason).contains("99")
    }

    @Test
    fun `targetDate 에서 14일을 넘는 날짜는 거부된다`() {
        val tooFar = CourseTools.parse(
            call("congestion", """{"attractionId":11,"date":"2026-10-16"}"""),
            bounds,
        )
        assertThat(tooFar).isInstanceOf(Rejected::class.java)

        val tooEarly = CourseTools.parse(
            call("congestion", """{"attractionId":11,"date":"2026-09-16"}"""),
            bounds,
        )
        assertThat(tooEarly).isInstanceOf(Rejected::class.java)
    }

    @Test
    fun `정확히 14일 경계는 허용된다`() {
        assertThat(CourseTools.parse(call("congestion", """{"attractionId":11,"date":"2026-10-15"}"""), bounds))
            .isInstanceOf(Congestion::class.java)
        assertThat(CourseTools.parse(call("congestion", """{"attractionId":11,"date":"2026-09-17"}"""), bounds))
            .isInstanceOf(Congestion::class.java)
    }

    @Test
    fun `radiusKm 상한과 하한을 벗어나면 거부된다`() {
        assertThat(
            CourseTools.parse(call("alternatives", """{"attractionId":11,"date":"2026-10-01","radiusKm":51}"""), bounds),
        ).isInstanceOf(Rejected::class.java)
        assertThat(
            CourseTools.parse(call("alternatives", """{"attractionId":11,"date":"2026-10-01","radiusKm":0}"""), bounds),
        ).isInstanceOf(Rejected::class.java)
    }

    @Test
    fun `모르는 도구 이름은 거부된다`() {
        assertThat(CourseTools.parse(call("weather", "{}"), bounds)).isInstanceOf(Rejected::class.java)
    }

    @Test
    fun `망가진 JSON 은 예외가 아니라 거부다`() {
        assertThat(CourseTools.parse(call("congestion", "{not json"), bounds)).isInstanceOf(Rejected::class.java)
    }

    @Test
    fun `날짜 형식이 틀리면 거부된다`() {
        assertThat(CourseTools.parse(call("congestion", """{"attractionId":11,"date":"10-01-2026"}"""), bounds))
            .isInstanceOf(Rejected::class.java)
    }

    @Test
    fun `거부 사유는 모델이 읽고 고칠 수 있게 무엇이 틀렸는지 말한다`() {
        val rejected = CourseTools.parse(
            call("alternatives", """{"attractionId":11,"date":"2026-10-01","radiusKm":51}"""),
            bounds,
        )
        assertThat(rejected).isInstanceOf(Rejected::class.java)
        assertThat((rejected as Rejected).reason).contains("radiusKm", "50")
    }
}
