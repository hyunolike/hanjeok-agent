package com.hermes.harness

import com.fasterxml.jackson.databind.ObjectMapper
import com.hermes.context.Bundle
import java.security.MessageDigest

/** Exact inputs, not a claim of reproducible model output. The sidecar carries source revisions. */
data class EvidenceFingerprint(val bundleSha256: String, val provenanceSha256: String?, val factsSha256: String) {
    companion object {
        fun of(bundle: Bundle, factsJson: String): EvidenceFingerprint = EvidenceFingerprint(
            bundle.sha256,
            bundle.metadataJson?.let { ObjectMapper().readTree(it).path("provenanceSha256").asText() },
            MessageDigest.getInstance("SHA-256").digest(factsJson.toByteArray(Charsets.UTF_8))
                .joinToString("") { "%02x".format(it) },
        )
    }
}
