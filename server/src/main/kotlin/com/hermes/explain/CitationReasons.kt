package com.hermes.explain

import com.hermes.context.Invalid

/**
 * 인용 무효를 사유 문자열로 만든다.
 *
 * 비스트리밍 두 서비스와 스트리밍 게이트가 모두 이것을 쓴다. 하네스의
 * `unavailableReasonIndicatesUncitedClaim` 이 이 문자열로 UNCITED_CLAIM 을 판별하므로,
 * 세 곳이 각자 문자열을 조립하다 한 곳이 어긋나면 그 경로의 위반이 조용히 안 세어진다.
 */
internal fun invalidCitationReason(invalid: Invalid): String =
    if (invalid.missingPolicyPaths.isNotEmpty()) {
        "citations missing policy support: ${invalid.missingPolicyPaths.joinToString()}"
    } else if (invalid.unknownPaths.isEmpty()) {
        "no citations"
    } else {
        "citations not in bundle: ${invalid.unknownPaths.joinToString()}"
    }

/**
 * 모델의 거절을 사유 문자열로 만든다.
 *
 * `ExplanationService.explain()`, `CourseQuestionService.ask()`, `askStream()` 셋 다
 * 이것을 쓴다. 세 경로가 각자 `"refusal (...)"` 를 조립하면 한 곳만 문구를 바꿔도
 * 컴파일도 테스트도 안 잡고, 그 경로의 거절만 다른 모양으로 새어 나간다 —
 * [invalidCitationReason] 이 막는 것과 같은 종류의 드리프트다.
 */
internal fun refusalReason(category: String?): String = "refusal (${category ?: "unknown"})"
