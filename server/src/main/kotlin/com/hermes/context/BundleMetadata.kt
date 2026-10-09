package com.hermes.context

import com.fasterxml.jackson.databind.ObjectMapper
import java.security.MessageDigest

internal fun contentSha256(text: String): String = MessageDigest.getInstance("SHA-256")
    .digest(text.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }

/** Verifies sidecar integrity, not the meaning of a claim or legitimacy of a review. */
object BundleMetadata {
    fun validate(raw: String, metadataJson: String) {
        val metadata = ObjectMapper().readTree(metadataJson)
        check(metadata.path("schemaVersion").asInt() == 1) { "unsupported bundle metadata version" }
        check(metadata.path("bundleSha256").asText() == contentSha256(raw)) { "bundle metadata hash mismatch" }
        check(Regex("[0-9a-f]{64}").matches(metadata.path("provenanceSha256").asText())) { "invalid provenance hash" }
        val markers = Regex("^----- FILE: (.+) -----$", RegexOption.MULTILINE).findAll(raw).toList()
        val documents = metadata.path("documents")
        check(documents.isArray && documents.size() == markers.size) { "bundle metadata inventory mismatch" }
        markers.forEachIndexed { i, marker ->
            val end = if (i + 1 < markers.size) markers[i + 1].range.first else raw.length
            // The assembler appends exactly one newline after each original file.
            val original = raw.substring(marker.range.last + 2, end).removeSuffix("\n")
            val entry = documents[i]
            check(entry.path("path").asText() == marker.groupValues[1]) { "bundle metadata path mismatch" }
            check(entry.path("sha256").asText() == contentSha256(original)) { "bundle document hash mismatch" }
            val claims = entry.path("claims")
            check(claims.isArray && !claims.isEmpty) { "bundle metadata claims missing" }
            claims.forEach { claim ->
                check(claim.path("status").asText() in setOf("unverified", "needs-review", "reviewed")) { "invalid claim state" }
            }
        }
    }
}
