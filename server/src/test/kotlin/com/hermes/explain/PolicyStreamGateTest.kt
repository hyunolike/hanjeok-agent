package com.hermes.explain

import com.hermes.context.BundleLoader
import com.hermes.context.CitationValidator
import com.hermes.llm.BodyText
import com.hermes.llm.CitationsClosed
import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test

class PolicyStreamGateTest {
    @Test
    fun `본문 전에 무관한 유효 인용을 거부한다`() {
        val events = mutableListOf<AskStreamEvent>()
        val gate = AskStreamGate(CitationValidator(BundleLoader.load()), "혼잡도는요?", events::add)
        gate.accept(BodyText("자료로 뒷받침되지 않은 답"))
        gate.accept(CitationsClosed(listOf("concepts/travel-context-layer.md")))
        gate.finish(true)
        assertThat(events).hasSize(1)
        assertThat(events.single()).isInstanceOf(UnavailableEvent::class.java)
        assertThat((events.single() as UnavailableEvent).cause).isEqualTo(FailureCause.INVALID_CITATIONS)
    }
}
