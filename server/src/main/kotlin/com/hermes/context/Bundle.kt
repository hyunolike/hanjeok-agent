package com.hermes.context

data class BundleDocument(val path: String, val content: String)

class Bundle(val documents: List<BundleDocument>, val raw: String, val metadataJson: String? = null) {
    private val pathSet: Set<String> = documents.map { it.path }.toSet()

    val sha256: String = contentSha256(raw)

    fun paths(): Set<String> = pathSet

    fun byteSize(): Int = raw.toByteArray(Charsets.UTF_8).size

    fun document(path: String): BundleDocument? = documents.firstOrNull { it.path == path }
}
