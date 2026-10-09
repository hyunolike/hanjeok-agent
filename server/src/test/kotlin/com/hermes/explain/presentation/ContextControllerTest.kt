package com.hermes.explain.presentation

import com.hermes.context.BundleLoader
import com.hermes.context.PromptAssembler
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.setup.MockMvcBuilders
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.content
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.status

class ContextControllerTest {

    private val bundle = BundleLoader.load()
    private val mvc: MockMvc = MockMvcBuilders.standaloneSetup(ContextController(bundle)).build()

    @Test
    fun `번들에 담긴 문서 목록을 낸다`() {
        mvc.perform(get("/agent/context"))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$.documents.length()").value(9))
            .andExpect(jsonPath("$.documents[0].path").value("concepts/travel-context-layer.md"))
    }

    @Test
    fun `모델이 받는 바이트는 문서 본문 합계가 아니라 프롬프트 원문 크기다`() {
        // 문서 사이의 FILE 마커 줄은 어느 문서의 본문도 아니지만 프롬프트에는 실린다.
        // 화면이 합계만 놓고 "모델이 보는 전부"라고 말하면 그만큼 틀린 말이 되므로,
        // 재는 쪽에서 둘을 구분해 낸다.
        val contentSum = bundle.documents.sumOf { it.content.toByteArray(Charsets.UTF_8).size }

        mvc.perform(get("/agent/context"))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$.systemTextBytes").value(bundle.byteSize()))

        assertTrue(bundle.byteSize() > contentSum) {
            "마커 줄이 빠진 합계가 프롬프트 원문보다 작지 않다 — 번들 형식이 바뀌었는지 확인할 것"
        }
    }

    @Test
    fun `모델이 받는 바이트는 PromptAssembler 가 보내는 것과 같다`() {
        // 이 값이 systemText 와 갈라지면 화면의 숫자는 아무것도 증명하지 않는다.
        assertEquals(
            PromptAssembler(bundle).systemText.toByteArray(Charsets.UTF_8).size,
            bundle.byteSize(),
        )
    }

    @Test
    fun `문서 본문은 LLM 에 보낸 바이트 그대로다`() {
        val expected = bundle.document("concepts/congestion-diagnosis.md")!!.content

        mvc.perform(get("/agent/context/concepts/congestion-diagnosis.md"))
            .andExpect(status().isOk)
            .andExpect(content().string(expected))
    }

    @Test
    fun `번들에 없는 경로는 404 다`() {
        // 인용 검증을 통과한 경로만 존재한다. 목록 밖은 절대 안 나간다.
        mvc.perform(get("/agent/context/concepts/weather-aware-travel-recommendation.md"))
            .andExpect(status().isNotFound)
    }

    @Test
    fun `상위 디렉터리 탈출을 허용하지 않는다`() {
        mvc.perform(get("/agent/context/../../build.gradle.kts")).andExpect(status().isNotFound)
    }

    @Test
    fun `번들에 연결된 출처 계약은 본문과 별도 JSON 으로 노출한다`() {
        mvc.perform(get("/agent/provenance"))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$.bundleSha256").value(bundle.sha256))
            .andExpect(jsonPath("$.documents.length()").value(9))
            .andExpect(jsonPath("$.documents[0].claims[0].status").value("unverified"))
            .andExpect(content().string(bundle.metadataJson!!))
    }
}
