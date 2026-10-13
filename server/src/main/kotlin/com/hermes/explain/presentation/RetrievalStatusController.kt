package com.hermes.explain.presentation

import com.hermes.context.ContextSelection
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.RestController

/** Aggregate pins/counters only. No query, token, endpoint or per-user diagnostics. */
@RestController
class RetrievalStatusController(private val selection: ContextSelection) {
    @GetMapping("/agent/retrieval-status")
    fun status(): Map<String, Any> = selection.status() + mapOf(
        "fallbackAvailable" to true, "cloudIamVerifiedLocally" to false,
        "runtimeIndexUpdates" to "manual immutable release only")
}
