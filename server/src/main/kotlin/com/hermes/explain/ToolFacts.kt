package com.hermes.explain

import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.databind.node.ObjectNode

/**
 * 초기 facts 와 도구가 가져온 사실을 한 트리로 모은다.
 *
 * 두 곳이 이것을 읽는다 — 모델에 돌려줄 텍스트([promptText])와, 하네스가 주장을
 * 대조할 대상([unionJson]). **둘이 같은 원본에서 나와야 한다.** 갈라지면 모델은 본
 * 사실을 하네스는 못 보고, 도구가 가져온 사실을 말할 때마다 근거 없는 주장으로 잡힌다.
 *
 * 거부된 도구 호출은 여기 들어오지 않는다. 실행되지 않은 조회가 근거로 잡히면 안 된다.
 */
class ToolFacts(initialJson: String) {

    private data class Lookup(val tool: String, val args: String, val result: String)

    private val mapper = ObjectMapper()
    private val initial = mapper.readTree(initialJson)
    private val lookups = mutableListOf<Lookup>()

    fun add(name: String, argsSummary: String, resultJson: String) {
        lookups.add(Lookup(name, argsSummary, resultJson))
    }

    fun unionJson(): String {
        if (lookups.isEmpty()) return initial.toString()

        val root = initial.deepCopy<ObjectNode>()
        // 초기 facts 에 이미 있는 이름은 건드리지 않는다 — 한적이 준 사실이 모델이
        // 유도한 조회보다 우선한다.
        val key = if (root.has("lookups")) "toolLookups" else "lookups"

        val array = root.putArray(key)
        lookups.forEach { lookup ->
            array.addObject().apply {
                put("tool", lookup.tool)
                put("args", lookup.args)
                set<ObjectNode>("result", mapper.readTree(lookup.result))
            }
        }
        return root.toString()
    }

    fun promptText(): String {
        if (lookups.isEmpty()) return ""
        return buildString {
            appendLine("## 추가로 조회한 사실")
            lookups.forEach { lookup ->
                appendLine("- ${lookup.tool}(${lookup.args}) → ${lookup.result}")
            }
        }
    }
}
