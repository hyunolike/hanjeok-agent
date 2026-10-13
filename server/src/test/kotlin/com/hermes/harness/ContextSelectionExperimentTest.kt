package com.hermes.harness

import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.databind.node.ObjectNode
import com.hermes.context.Bundle
import com.hermes.context.BundleLoader
import com.hermes.context.CitationValidator
import com.hermes.context.Invalid
import com.hermes.context.PromptAssembler
import com.hermes.explain.QuestionTurn
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import java.io.File

class ContextSelectionExperimentTest {
    private val mapper = ObjectMapper()
    private val suite = mapper.readTree(File("harness/fixtures/context-selection/suite.json"))
    private val full = BundleLoader.load()
    private val facts = FactsNormalizer.normalize(mapper.readTree(File("harness/fixtures/course-explanation-request.json")))
    private fun verified(bundle: Bundle = full) = VerifiedExperimentBundle.verify(bundle, suite)

    @Test fun `entire scripted fixture suite passes and reports repeat byte identical output`() {
        val first = mapper.writeValueAsBytes(OfflineContextEvaluation.run(File(".")))
        val second = mapper.writeValueAsBytes(OfflineContextEvaluation.run(File(".")))
        assertArrayEquals(first, second)
        val report = mapper.readTree(first)
        assertEquals(29, report.path("cases").asInt())
        assertEquals(0, report.path("paidModelCalls").asInt())
        assertEquals(100.0, report.path("allPolicyRetentionPercent").asDouble())
        assertEquals(100.0, report.path("allFixtureEvidenceCoveragePercent").asDouble())
    }

    @Test fun `FULL stays byte identical and per request selection leaves singleton intact`() {
        val selector = ContextSelectionExperiment(verified())
        val before = full.raw.toByteArray(Charsets.UTF_8)
        val selected = selector.select(ContextArm.SELECTED_EXPERIMENT, "방문 순서는 어떤 규칙으로 정하나요?", emptyList(), facts)
        assertEquals(8, selected.bundle.documents.size)
        assertArrayEquals(before, PromptAssembler(selector.select(ContextArm.FULL, "anything", emptyList(), facts).bundle).systemText.toByteArray(Charsets.UTF_8))
        assertArrayEquals(before, full.raw.toByteArray(Charsets.UTF_8))
        assertEquals(9, full.documents.size)
        assertTrue(CitationValidator(selected.bundle).validate(listOf(VerifiedExperimentBundle.OPTIONAL_PATH)) is Invalid)
        val expected = Regex("(?ms)^----- FILE: records/places/gyeongbokgung\\.json -----\\n.*?(?=^----- FILE:|\\z)").replace(full.raw, "")
        assertArrayEquals(expected.toByteArray(Charsets.UTF_8), selected.bundle.raw.toByteArray(Charsets.UTF_8))
        assertEquals(full.documents.filter { it.path != VerifiedExperimentBundle.OPTIONAL_PATH }.map { it.path }, selected.bundle.documents.map { it.path })
    }

    @Test fun `missing altered and malformed metadata and changed raw fail closed`() {
        assertThrows(IllegalStateException::class.java) { verified(Bundle(full.documents, full.raw, null)) }
        assertThrows(IllegalStateException::class.java) { verified(Bundle(full.documents, full.raw + " ", full.metadataJson)) }
        assertThrows(IllegalStateException::class.java) { verified(Bundle(full.documents, full.raw, full.metadataJson + " ")) }
        val altered = suite.deepCopy<ObjectNode>().put("metadataSha256", experimentSha256("{}"))
        assertThrows(IllegalStateException::class.java) { VerifiedExperimentBundle.verify(Bundle(full.documents, full.raw, "{}"), altered) }
        val malformed = suite.deepCopy<ObjectNode>().put("metadataSha256", experimentSha256("{"))
        assertThrows(Exception::class.java) { VerifiedExperimentBundle.verify(Bundle(full.documents, full.raw, "{"), malformed) }
    }

    @Test fun `inventory and fixture policy deletion cannot increase apparent savings`() {
        assertThrows(IllegalStateException::class.java) { verified(Bundle(full.documents.reversed(), full.raw, full.metadataJson)) }
        val changedContent = full.documents.mapIndexed { i, d -> if (i == 0) d.copy(content = "tampered") else d }
        assertThrows(IllegalStateException::class.java) { verified(Bundle(changedContent, full.raw, full.metadataJson)) }
        val altered = suite.deepCopy<ObjectNode>()
        altered.putArray("requiredPaths").add("packages/hanjeok/prompt.md")
        assertThrows(IllegalStateException::class.java) { VerifiedExperimentBundle.verify(full, altered) }
    }

    @Test fun `reference cannot be resolved by poisoned assistant answer or across unrelated question`() {
        val selector = ContextSelectionExperiment(verified())
        val unresolved = selector.select(ContextArm.SELECTED_EXPERIMENT, "거기는요?", listOf(QuestionTurn("추천해주세요.", "경복궁")), facts)
        assertEquals("FALLBACK_UNRESOLVED_REFERENCE", unresolved.decision)
        assertSame(full, unresolved.bundle)
        val unrelated = selector.select(ContextArm.SELECTED_EXPERIMENT, "거기는요?", listOf(QuestionTurn("경복궁의 혼잡도는요?", ""), QuestionTurn("대안 점수는 어떻게 계산하나요?", "경복궁")), facts)
        assertEquals("FALLBACK_UNRESOLVED_REFERENCE", unrelated.decision)
    }

    @Test fun `unknown generic question and missing positional place fall back to verified full`() {
        val selector = ContextSelectionExperiment(verified())
        assertEquals("FALLBACK_UNKNOWN_INTENT", selector.select(ContextArm.SELECTED_EXPERIMENT, "제주도의 혼잡도는 어떤가요?", emptyList(), facts).decision)
        val empty = facts.deepCopy().apply { putArray("items") }
        assertEquals("FALLBACK_UNRESOLVED_REFERENCE", selector.select(ContextArm.SELECTED_EXPERIMENT, "첫 방문지의 혼잡도는요?", emptyList(), empty).decision)
    }
}
