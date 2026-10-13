package com.hermes.context

import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.databind.node.ObjectNode
import org.assertj.core.api.Assertions.assertThat
import org.assertj.core.api.Assertions.assertThatThrownBy
import org.junit.jupiter.api.Test

class BundleMetadataTest {
    @Test
    fun `full bundle 은 sidecar hash 와 정확한 문서 출처 상태에 연결된다`() {
        val bundle = BundleLoader.load()
        BundleMetadata.validate(bundle.raw, bundle.metadataJson!!)
        val json = ObjectMapper().readTree(bundle.metadataJson)
        assertThat(json.path("bundleSha256").asText()).isEqualTo(bundle.sha256)
        assertThat(json.path("documents").size()).isEqualTo(9)
        val claims = json.path("documents").first().path("claims")
        assertThat(claims.first().path("status").asText()).isEqualTo("unverified")
        assertThat(claims.first().path("sources").first().path("revision").asText()).hasSize(40)
    }

    @Test
    fun `본문 또는 문서 목록이 다르면 적재를 거부한다`() {
        val bundle = BundleLoader.load()
        assertThatThrownBy { BundleMetadata.validate(bundle.raw + "changed", bundle.metadataJson!!) }
            .hasMessageContaining("hash mismatch")
        val json = ObjectMapper().readTree(bundle.metadataJson)
        (json.path("documents").first() as ObjectNode).put("path", "fabricated.md")
        assertThatThrownBy { BundleMetadata.validate(bundle.raw, json.toString()) }
            .hasMessageContaining("path mismatch")
    }
}
