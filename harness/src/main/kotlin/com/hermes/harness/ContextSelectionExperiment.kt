package com.hermes.harness

import com.fasterxml.jackson.databind.JsonNode
import com.hermes.context.Bundle
import com.hermes.context.BundleDocument
import com.hermes.context.BundleMetadata
import com.hermes.context.PromptAssembler
import com.hermes.explain.QuestionTurn
import java.security.MessageDigest

/** Offline only: never installed as a bean or used by production request wiring. */
enum class ContextArm { FULL, SELECTED_EXPERIMENT }

data class ContextSelection(val bundle: Bundle, val decision: String) {
    val fallback: Boolean get() = decision.startsWith("FALLBACK_")
}

fun experimentSha256(text: String): String = MessageDigest.getInstance("SHA-256")
    .digest(text.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }

/** A pinned, verified snapshot. Raw slices include markers and separators, unchanged. */
class VerifiedExperimentBundle private constructor(
    val full: Bundle,
    private val sections: List<Pair<String, String>>,
    val sourceBytes: Map<String, Int>,
    val requiredPaths: Set<String>,
    val optionalPath: String,
) {
    fun policiesOnly(): Bundle {
        val selected = sections.filter { it.first in requiredPaths }
        // The full sidecar describes the full body. Do not attach it to a different body.
        // Provenance stays with the verified parent; this ephemeral bundle is never published.
        return Bundle(
            documents = selected.map { (path, _) -> BundleDocument(path, full.document(path)!!.content) },
            raw = selected.joinToString("") { it.second },
        )
    }

    companion object {
        val POLICY_PATHS: Set<String> = linkedSetOf(
            "packages/hanjeok/prompt.md", "concepts/travel-context-layer.md",
            "decisions/keep-llm-out-of-ranking.md", "concepts/course-generation-policy.md",
            "concepts/congestion-diagnosis.md", "concepts/alternative-scoring.md",
            "queries/why-this-place-today.md", "records/congestion/grade-policy.json",
        )
        const val OPTIONAL_PATH = "records/places/gyeongbokgung.json"

        fun verify(bundle: Bundle, suite: JsonNode): VerifiedExperimentBundle {
            check(suite.path("schemaVersion").asInt() == 1) { "unsupported fixture schema" }
            val required = suite.path("requiredPaths").map { it.asText() }.toSet()
            check(required == POLICY_PATHS) { "fixture must retain all eight policies" }
            check(suite.path("optionalPath").asText() == OPTIONAL_PATH) { "optional inventory drift" }
            val metadata = checkNotNull(bundle.metadataJson) { "verified sidecar required" }
            check(experimentSha256(bundle.raw) == suite.path("bundleSha256").asText()) { "unpinned body" }
            check(experimentSha256(metadata) == suite.path("metadataSha256").asText()) { "unpinned sidecar" }
            BundleMetadata.validate(bundle.raw, metadata)
            val markers = Regex("^----- FILE: (.+) -----$", RegexOption.MULTILINE).findAll(bundle.raw).toList()
            check(markers.first().range.first == 0) { "unexpected bundle preamble" }
            val paths = markers.map { it.groupValues[1] }
            check(paths.size == 9 && paths.toSet().size == 9 && paths.toSet() == required + OPTIONAL_PATH) {
                "fixed nine-document inventory required"
            }
            check(bundle.documents.map { it.path } == paths) { "parsed document order differs from raw" }
            val sourceBytes = linkedMapOf<String, Int>()
            val sections = markers.mapIndexed { i, marker ->
                val end = markers.getOrNull(i + 1)?.range?.first ?: bundle.raw.length
                val original = bundle.raw.substring(marker.range.last + 2, end).removeSuffix("\n")
                check(original.trimEnd('\n') == bundle.document(paths[i])!!.content) { "parsed document content drift" }
                sourceBytes[paths[i]] = original.toByteArray(Charsets.UTF_8).size
                paths[i] to bundle.raw.substring(marker.range.first, end)
            }
            check(PromptAssembler(bundle).systemText.toByteArray(Charsets.UTF_8)
                .contentEquals(bundle.raw.toByteArray(Charsets.UTF_8))) { "FULL differs from current PromptAssembler" }
            return VerifiedExperimentBundle(bundle, sections, sourceBytes, required, OPTIONAL_PATH)
        }
    }
}

/** Narrow deterministic experiment, intentionally conservative outside supported questions. */
class ContextSelectionExperiment(private val verified: VerifiedExperimentBundle) {
    fun select(arm: ContextArm, question: String, history: List<QuestionTurn>, facts: JsonNode): ContextSelection {
        fun full(reason: String) = ContextSelection(verified.full, reason)
        if (arm == ContextArm.FULL) return full("FULL")
        if (question.isBlank()) return full("FALLBACK_UNKNOWN_INTENT")
        if (OVERRIDE.containsMatchIn(question)) return full("FALLBACK_RULE_OVERRIDE")
        if (UNSUPPORTED.containsMatchIn(question)) return full("FALLBACK_UNSUPPORTED_TOPIC")
        val places = facts.path("items").map { it.path("name").asText() }.filter { it.isNotBlank() }.toSet()
        fun names(text: String): Set<String> = places.filter { text.contains(it) }.toSet() +
            if (SEED.containsMatchIn(text)) setOf("경복궁") else emptySet()
        var context = question
        var targets = names(question)
        val position = POSITION.find(question)?.groupValues?.get(1)?.let { if (it in setOf("첫", "first")) 1 else 2 }
        if (position != null && targets.isEmpty()) {
            val matches = facts.path("items").filter { it.path("visitOrder").asInt() == position }
            if (matches.size != 1) return full("FALLBACK_UNRESOLVED_REFERENCE")
            targets = setOf(matches.single().path("name").asText())
        }
        if (targets.isEmpty() && REFERENCE.containsMatchIn(question)) {
            var anchored = false
            for (turn in history.asReversed()) {
                // Assistant answers may be poisoned. They are never read here.
                context += "\n" + turn.question
                val found = names(turn.question)
                if (found.size > 1) return full("FALLBACK_AMBIGUOUS_REFERENCE")
                if (found.size == 1) {
                    targets = found
                    anchored = true
                    break
                }
                if (!REFERENCE.containsMatchIn(turn.question)) break
            }
            if (!anchored) return full("FALLBACK_UNRESOLVED_REFERENCE")
        }
        if (UNSUPPORTED.containsMatchIn(context)) return full("FALLBACK_UNSUPPORTED_TOPIC")
        if (OVERRIDE.containsMatchIn(context)) return full("FALLBACK_RULE_OVERRIDE")
        if (targets.isEmpty() && !GENERIC.matches(question.trim())) return full("FALLBACK_UNKNOWN_INTENT")
        if (!TOPIC.containsMatchIn(context)) return full("FALLBACK_UNKNOWN_INTENT")
        return if ("경복궁" in targets) full("INCLUDE_OPTIONAL")
        else ContextSelection(verified.policiesOnly(), "POLICIES_ONLY")
    }

    private companion object {
        val SEED = Regex("경복궁|\\bGyeongbokgung\\b", RegexOption.IGNORE_CASE)
        val OVERRIDE = Regex("규칙.{0,10}무시|정책.{0,10}무시|ignore.{0,15}(rule|policy)|혼잡도.{0,10}0이라고", RegexOption.IGNORE_CASE)
        val UNSUPPORTED = Regex("날씨|기온|강수|비가|운영시간|영업시간|개장|폐장|weather|opening|hours", RegexOption.IGNORE_CASE)
        val REFERENCE = Regex("그날|거기|그곳|그건|그것|그럼|\\b(that|there)\\b", RegexOption.IGNORE_CASE)
        val POSITION = Regex("(첫|두 번째|first|second)\\s*(방문지|장소|stop)", RegexOption.IGNORE_CASE)
        val TOPIC = Regex("혼잡|백분위|집중률|대안|방문|순서|데이터|기준|crowd|alternative|order|policy", RegexOption.IGNORE_CASE)
        // Scope is deliberately small; unknown generic wording falls back rather than guessing.
        val GENERIC = Regex("혼잡도 등급의 기준은 무엇인가요\\?|대안 점수는 어떻게 계산하나요\\?|방문 순서는 어떤 규칙으로 정하나요\\?")
    }
}
