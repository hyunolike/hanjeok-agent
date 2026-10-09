package com.hermes.explain

import com.hermes.context.CitationValidator
import com.hermes.context.Invalid
import com.hermes.context.PromptAssembler
import com.hermes.context.Valid
import com.hermes.llm.Answered
import com.hermes.llm.Explanation
import com.hermes.llm.ExplanationProvider
import com.hermes.llm.Failed
import com.hermes.llm.Refused

sealed interface ExplainOutcome

data class Explained(val explanation: Explanation) : ExplainOutcome

/** 스펙 §8 — 설명이 없는 것은 안전한 실패다. 한적의 규칙 기반 문구가 남는다. */
data class Unavailable(val reason: String) : ExplainOutcome

class ExplanationService(
    private val assembler: PromptAssembler,
    private val validator: CitationValidator,
    private val provider: ExplanationProvider,
) {

    val bundleSha256: String = sha256(assembler.systemText)

    fun explain(facts: BackendFacts): ExplainOutcome =
        when (val result = provider.explain(assembler.systemText, facts.json)) {
            is Refused -> Unavailable(refusalReason(result.category))
            is Failed -> Unavailable(result.reason)
            is Answered -> when (val citations = validator.validate(result.explanation.citations, result.explanation.explanation)) {
                is Valid -> Explained(result.explanation)
                is Invalid -> Unavailable(invalidCitationReason(citations))
            }
        }
}
