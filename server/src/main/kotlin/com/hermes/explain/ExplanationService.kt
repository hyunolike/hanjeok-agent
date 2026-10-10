package com.hermes.explain

import com.hermes.context.CitationValidator
import com.hermes.context.Invalid
import com.hermes.context.PromptAssembler
import com.hermes.context.ContextSelection
import com.hermes.context.FullContextSelection
import com.hermes.context.RequestContext
import com.fasterxml.jackson.databind.ObjectMapper
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
    private val selection: ContextSelection = FullContextSelection(assembler, validator),
) {

    val bundleSha256: String = sha256(assembler.systemText)

    fun context(facts: BackendFacts): RequestContext {
        if (selection.status()["mode"] == "FULL") return selection.select("")
        val names = try { ObjectMapper().readTree(facts.json).path("items").take(3).map { it.path("name").asText().take(100) } } catch (_: Exception) { emptyList() }
        val query = if (names.isEmpty()) "방문 순서는 어떤 규칙으로 정하나요?" else names.joinToString(" ") + " 혼잡도 방문 순서 설명"
        return selection.select(query)
    }

    fun explain(facts: BackendFacts, request: RequestContext = context(facts)): ExplainOutcome {
        if (request.abstain) return Unavailable("unsupported retrieval scope")
        return when (val result = provider.explain(request.systemText, request.userText(facts.json))) {
            is Refused -> Unavailable(refusalReason(result.category))
            is Failed -> Unavailable(result.reason)
            is Answered -> when (val citations = request.validator.validate(result.explanation.citations, result.explanation.explanation)) {
                is Valid -> Explained(result.explanation)
                is Invalid -> Unavailable(invalidCitationReason(citations))
            }
        }
    }
}
