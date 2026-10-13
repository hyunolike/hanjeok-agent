package com.hermes.harness

import com.fasterxml.jackson.databind.ObjectMapper
import com.hermes.context.Bundle
import com.hermes.context.BundleLoader
import com.hermes.context.CitationValidator
import com.hermes.context.Valid
import java.io.File

/** Offline-only bridge: validate exported Python contexts with the production citation gate. */
fun main(args: Array<String>) {
    require(args.size == 2) { "usage: results.json citation-validation.json" }
    val mapper = ObjectMapper()
    val full = BundleLoader.load()
    val results = mapper.readTree(File(args[0]))
    check(results.path("provenance").path("bundleSha256").asText() == full.sha256)
    val required = VerifiedExperimentBundle.POLICY_PATHS
    val checked = results.path("rows").map { row ->
        val paths = row.path("contextIds").map { it.asText() }.toSet()
        check(paths.containsAll(required) && full.paths().containsAll(paths))
        val selected = Bundle(full.documents.filter { it.path in paths }, "")
        val validator = CitationValidator(selected)
        val citations = row.path("citations").map { it.asText() }
        val valid = validator.validate(citations, row.path("response").asText()) == Valid
        check(valid == row.path("citationValid").asBoolean()) {
            "Python/Kotlin citation contract mismatch: ${row.path("id")} ${row.path("arm")}" }
        check(validator.validate(emptyList()) != Valid)
        check(validator.validate(listOf("records/weather/invented.json")) != Valid)
        val seedOmitted = VerifiedExperimentBundle.OPTIONAL_PATH !in paths
        if (seedOmitted) check(validator.validate(listOf(VerifiedExperimentBundle.OPTIONAL_PATH)) != Valid)
        mapOf("id" to row.path("id").asText(), "arm" to row.path("arm").asText(),
            "matchesPython" to true, "citationValid" to valid, "omittedSeedProbeRejected" to seedOmitted)
    }
    val report = mapOf("validator" to "actual production CitationValidator; not an LLM judge",
        "rows" to checked.size, "contractsMatched" to checked.size,
        "emptyAndUnknownProbeRejections" to checked.size * 2,
        "omittedSeedProbeRejections" to checked.count { it["omittedSeedProbeRejected"] == true },
        "checks" to checked)
    File(args[1]).writeText(mapper.writerWithDefaultPrettyPrinter().writeValueAsString(report) + "\n")
    println("Production citation contracts matched: ${checked.size}; empty/unknown probes rejected: ${checked.size * 2}")
}
