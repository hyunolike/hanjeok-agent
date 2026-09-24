package com.hermes.shared.config

import com.hermes.context.Bundle
import com.hermes.context.CitationValidator
import com.hermes.explain.ToolRunner
import com.hermes.llm.ExplanationProvider
import com.hermes.llm.ProviderResult
import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test

/**
 * 운영 빈의 예산을 고정한다.
 *
 * 예산을 키워도 아무것도 깨지지 않는다는 것이 문제다. `AskStreamController` 의
 * 에미터는 90초이므로, 마감이 그보다 길어지면 포기하는 쪽이 우리가 아니라 에미터가
 * 되고 스트림은 종결 이벤트 없이 멈춘다. 라운드를 늘리면 같은 질문 하나가 몇 배로
 * 청구된다. 둘 다 테스트가 아니라 요금 고지서와 장애로만 드러나므로 여기서 잡는다.
 */
class AgentLoopWiringTest {

    private val silent = object : ExplanationProvider {
        override val name = "not-called"
        override fun explain(systemText: String, userText: String): ProviderResult =
            error("이 테스트는 모델을 부르지 않는다")
    }

    @Test
    fun `운영 루프의 예산은 도구 라운드 2회와 마감 60초다`() {
        val loop = HermesConfig().agentLoop(
            silent,
            CitationValidator(Bundle(emptyList(), "")),
            ToolRunner { error("이 테스트는 도구를 부르지 않는다") },
        )

        assertThat(loop.maxToolRounds).isEqualTo(2)
        assertThat(loop.deadlineMs).isEqualTo(60_000L)
        // 마감은 에미터 타임아웃(90초)보다 반드시 짧다.
        assertThat(loop.deadlineMs).isLessThan(90_000L)
    }
}
