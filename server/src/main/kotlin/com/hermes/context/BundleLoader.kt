package com.hermes.context

object BundleLoader {

    private val MARKER = Regex("^----- FILE: (.+) -----$", RegexOption.MULTILINE)

    // Deliberately broader than MARKER: no `^…$` line anchors. A line that
    // fully matches MARKER can never survive into a parsed document's
    // `content` — the split below already treats every such line, wherever
    // it appears in the raw text, as a boundary of its own, so re-checking
    // `content` against MARKER itself would never fire. What IS reachable is
    // a marker-shaped run of text that isn't isolated on its own line (mid
    // sentence, indented, missing a trailing marker, etc.) — that slips past
    // the split untouched and would otherwise sit in `content` unnoticed. A
    // fabricated path is exactly what `CitationValidator` (a later task)
    // will trust as a real citation target, so any such fragment is grounds
    // to reject the whole bundle rather than load it partially-correct.
    private val MARKER_FRAGMENT = Regex("----- FILE: .+ -----")

    fun load(
        resourcePath: String = "/prompts/hanjeok-bundle.txt",
        metadataPath: String? = if (resourcePath == "/prompts/hanjeok-bundle.txt") "/prompts/hanjeok-bundle.meta.json" else null,
    ): Bundle {
        val raw = BundleLoader::class.java.getResource(resourcePath)
            ?.readText(Charsets.UTF_8)
            ?: error("bundle resource not found: $resourcePath")

        val markers = MARKER.findAll(raw).toList()
        check(markers.isNotEmpty()) { "bundle has no FILE markers: $resourcePath" }

        val documents = markers.mapIndexed { i, match ->
            val contentStart = match.range.last + 2 // 마커 줄의 개행 다음
            val contentEnd = if (i + 1 < markers.size) markers[i + 1].range.first else raw.length
            BundleDocument(
                path = match.groupValues[1],
                content = raw.substring(contentStart, contentEnd).trimEnd('\n'),
            )
        }

        documents.forEach { doc ->
            check(!MARKER_FRAGMENT.containsMatchIn(doc.content)) {
                "document content contains an embedded FILE marker line: ${doc.path}"
            }
        }

        val metadata = metadataPath?.let { path ->
            val json = BundleLoader::class.java.getResource(path)?.readText(Charsets.UTF_8)
                ?: error("bundle metadata resource not found: $path")
            BundleMetadata.validate(raw, json)
            json
        }
        return Bundle(documents = documents, raw = raw, metadataJson = metadata)
    }
}
