package com.hermes.shared.config

import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test
import java.io.File

/**
 * 배포 문서의 환경 변수 목록이 `application.yml` 이 실제로 읽는 것과 같은가.
 *
 * 어긋나면 배포가 조용히 기본값으로 돈다 — 운영자는 설정했다고 믿고, 서버는
 * 다른 값으로 돈다. 그 차이는 요금 고지서나 이상한 응답에서야 드러난다.
 * 이 검사가 없으면 문서는 코드보다 언제나 며칠 뒤처진다.
 */
class DeployDocumentationTest {

    private val yaml = File("server/src/main/resources/application.yml").readText()
    private val doc = File("docs/deploy.md").readText()

    /** `${NAME}` 과 `${NAME:default}` 양쪽을 잡는다. */
    private val referenced: Set<String> =
        Regex("""\$\{([A-Z][A-Z0-9_]*)[:}]""").findAll(yaml).map { it.groupValues[1] }.toSet()

    @Test
    fun `application yml 이 읽는 변수가 문서에 전부 있다`() {
        assertThat(referenced).isNotEmpty()

        val undocumented = referenced.filterNot { doc.contains(it) }

        assertThat(undocumented)
            .describedAs("이 변수들이 docs/deploy.md 에 없다 — 배포하는 사람이 알 방법이 없다")
            .isEmpty()
    }

    @Test
    fun `프로바이더별 키 세 개가 문서에 있다`() {
        // application.yml 에는 없다 — SDK 와 LlmSelection 이 환경에서 직접 읽는다.
        // 그래서 위 검사가 잡지 못하고, 빠뜨리면 기동 실패의 원인을 문서에서 찾을 수 없다.
        assertThat(doc).contains("ANTHROPIC_API_KEY")
        assertThat(doc).contains("OPENAI_API_KEY")
        assertThat(doc).contains("OPENROUTER_API_KEY")
    }

    @Test
    fun `문서가 지어낸 변수를 적지 않는다`() {
        // 없는 변수를 설정하라고 적으면, 설정했는데 아무 일도 일어나지 않는다.
        val documented = Regex("""\| `([A-Z][A-Z0-9_]*)` \|""").findAll(doc).map { it.groupValues[1] }

        val known = referenced + setOf(
            "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
            "OPENAI_API_KEY", "OPENROUTER_API_KEY",
            "PORT", // Docker entrypoint
            "SERVER_PORT", // Spring Boot server.port 환경 바인딩 (로컬 bootRun)
        )

        assertThat(documented.toList()).isSubsetOf(known)
    }
}
