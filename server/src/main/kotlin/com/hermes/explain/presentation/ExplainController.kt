package com.hermes.explain.presentation

import com.fasterxml.jackson.databind.ObjectMapper
import com.hermes.explain.CourseExplainer
import org.springframework.beans.factory.annotation.Value
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RestController
import tools.jackson.databind.util.RawValue

data class ExplainRequest(val courseUuid: String)

/**
 * `facts` 는 `tools.jackson.databind.util.RawValue` 로 감싼다 — Jackson 2 타입인
 * `com.fasterxml.jackson.databind.JsonNode` 를 그대로 두면, 이 웹 계층의 JSON
 * 변환기(Jackson 3, tools.jackson)가 그 값을 트리로 인식하지 못하고 평범한
 * POJO 로 취급해 `isArray()/isObject()/...` 같은 getter 를 직렬화해 버린다
 * (실측: `{"array":false,"object":true,"nodeType":"OBJECT",...}`, `facts.items`
 * 는 아예 없어진다). `RawValue` 는 두 Jackson 버전 모두와 무관하게 문자열을
 * 파싱하지 않고 그대로 출력 스트림에 흘려보내므로, FactsProjection 이 이미
 * 확정한 필드 순서(§BackendFacts 문서 참고 — 재직렬화하면 순서가 흔들린다)를
 * 건드리지 않고도 `facts` 가 문자열이 아닌 JSON 객체로 도착한다.
 */
data class ExplainResponse(
    val explanation: String,
    val citations: List<String>,
    val facts: RawValue,
    val generatedAt: String,
    val model: String,
    val retrievedAt: String,
    val cached: Boolean,
    val factsSha256: String,
    val bundleSha256: String,
)

@RestController
class ExplainController(
    private val explainer: CourseExplainer,
    @param:Value("\${hermes.llm.model}") private val model: String,
    private val mapper: ObjectMapper,
) {

    /**
     * 클라이언트는 `courseUuid` 만 보낸다. facts 를 실어 보내게 두면 위조된
     * 혼잡도를 LLM 이 그럴듯하게 설명해 주는 경로가 생긴다 — 사실의 출처는
     * 언제나 백엔드여야 한다(스펙 §3).
     */
    @PostMapping("/agent/explain")
    fun explain(@RequestBody request: ExplainRequest): ExplainResponse {
        val result = explainer.explain(request.courseUuid)

        // 파싱한 트리는 버리고 원본 문자열만 그대로 내보낸다 — 목적은 오직
        // "이게 유효한 JSON 이 맞는가" 검증이다. 재직렬화해서 쓰면 필드 순서가
        // 흔들릴 수 있다는 게 BackendFacts 의 명시적 계약이라 여기서도 지킨다.
        mapper.readTree(result.factsJson)

        return ExplainResponse(
            explanation = result.explanation.explanation,
            citations = result.explanation.citations,
            facts = RawValue(result.factsJson),
            generatedAt = result.generatedAt.toString(),
            model = model,
            retrievedAt = result.retrievedAt.toString(),
            cached = result.cached,
            factsSha256 = result.factsSha256,
            bundleSha256 = result.bundleSha256,
        )
    }
}
