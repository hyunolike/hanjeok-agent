package com.hermes.context

import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test

class CitationValidatorTest {

    private val validator = CitationValidator(BundleLoader.load())

    @Test
    fun `번들에 있는 경로만 인용하면 통과한다`() {
        val result = validator.validate(
            listOf("concepts/congestion-diagnosis.md", "records/congestion/grade-policy.json"),
        )

        assertThat(result).isEqualTo(Valid)
    }

    @Test
    fun `번들에 없는 경로를 인용하면 그 경로를 지목해 거절한다`() {
        // 이게 이 클래스가 존재하는 이유다. LLM 이 그럴듯한 위키 경로를 지어내면
        // 응답이 나가기 전에 여기서 잡힌다.
        val result = validator.validate(
            listOf("concepts/congestion-diagnosis.md", "concepts/weather-aware-travel-recommendation.md"),
        )

        assertThat(result).isEqualTo(Invalid(listOf("concepts/weather-aware-travel-recommendation.md")))
    }

    @Test
    fun `인용이 비면 거절한다`() {
        // 근거 없는 설명은 이 서비스가 낼 수 있는 것이 아니다.
        assertThat(validator.validate(emptyList())).isEqualTo(Invalid(emptyList()))
    }

    @Test
    fun `같은 경로를 여러 번 인용해도 한 번만 문제 삼는다`() {
        val result = validator.validate(listOf("concepts/nope.md", "concepts/nope.md"))

        assertThat(result).isEqualTo(Invalid(listOf("concepts/nope.md")))
    }

    @Test
    fun `유효하지만 무관한 경로는 혼잡도 주장을 뒷받침하지 못한다`() {
        assertThat(validator.validate(listOf("concepts/travel-context-layer.md"), "백분위 92로 혼잡합니다"))
            .isEqualTo(Invalid(emptyList(), listOf("concepts/congestion-diagnosis.md")))
        assertThat(validator.validate(listOf("concepts/congestion-diagnosis.md"), "백분위 92로 혼잡합니다"))
            .isEqualTo(Valid)
    }

    @Test
    fun `대안 가중치 정책은 대안 정책 경로를 요구한다`() {
        assertThat(validator.validate(listOf("concepts/congestion-diagnosis.md"), "대안 점수의 가중치"))
            .isEqualTo(Invalid(emptyList(), listOf("concepts/alternative-scoring.md")))
    }
}
