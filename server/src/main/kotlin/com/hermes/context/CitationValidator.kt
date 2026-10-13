package com.hermes.context

sealed interface CitationResult

data object Valid : CitationResult

data class Invalid(val unknownPaths: List<String>, val missingPolicyPaths: List<String> = emptyList()) : CitationResult

/**
 * 응답의 citations 배열이 번들에 실재하는 문서만 가리키는지 본다.
 *
 * 이 검사는 테스트가 아니라 런타임 방어선이다. 화면의 인용 칩은 번들 사본을 열기
 * 때문에, 번들에 없는 경로가 통과하면 사용자는 404 를 보게 된다.
 */
class CitationValidator(private val bundle: Bundle) {

    fun validate(citations: List<String>, policyText: String = ""): CitationResult {
        if (citations.isEmpty()) return Invalid(emptyList())

        val known = bundle.paths()
        val unknown = citations.distinct().filterNot { it in known }

        if (unknown.isNotEmpty()) return Invalid(unknown)
        val required = policyPaths(policyText)
        val missing = required.filterNot { it in citations }
        return if (missing.isEmpty()) Valid else Invalid(emptyList(), missing)
    }

    /** Bounded topic association, not semantic entailment. No model or scoring service is called. */
    private fun policyPaths(text: String): List<String> = buildList {
        if (Regex("백분위|집중률|혼잡|붐비|붐빕|percentile|crowd", RegexOption.IGNORE_CASE).containsMatchIn(text)) {
            add("concepts/congestion-diagnosis.md")
        }
        if (Regex("가중치|연관도|대안.{0,12}점수|점수.{0,12}대안|alternative.{0,12}scor", RegexOption.IGNORE_CASE).containsMatchIn(text)) {
            add("concepts/alternative-scoring.md")
        }
    }
}
