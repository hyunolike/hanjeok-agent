package com.hermes.harness

import com.hermes.context.BundleLoader
import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test

class EvidenceFingerprintTest {
    @Test
    fun `같은 입력은 같은 버전 식별자를 내며 달라진 facts 를 구분한다`() {
        val bundle = BundleLoader.load()
        val initial = EvidenceFingerprint.of(bundle, """{"hasCongestionData":false}""")
        val changed = EvidenceFingerprint.of(bundle, """{"hasCongestionData":true}""")
        assertThat(initial).isEqualTo(EvidenceFingerprint.of(bundle, """{"hasCongestionData":false}"""))
        assertThat(initial.bundleSha256).isEqualTo(bundle.sha256)
        assertThat(initial.provenanceSha256).hasSize(64)
        assertThat(initial.factsSha256).hasSize(64).isNotEqualTo(changed.factsSha256)
        assertThat(ForbiddenBehaviours.unavailableReasonIndicatesUncitedClaim("citations missing policy support: concepts/congestion-diagnosis.md")).isTrue()
    }
}
