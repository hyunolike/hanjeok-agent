package com.hermes.explain

import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.databind.node.ObjectNode

/**
 * 초기 facts 와 도구가 가져온 사실을 한 트리로 모은다.
 *
 * **읽는 곳은 [unionJson] 하나다.** 모델에게는 이 트리를 다시 넣지 않는다 — 도구
 * 결과는 `ToolResultTurn` 으로 대화에 그대로 실려 돌아가므로, 같은 사실을 프롬프트
 * 문자열로 한 번 더 조립하면 조립 경로가 둘이 된다. 이 합집합이 존재하는 이유는
 * 평가 하네스가 **모델이 본 것과 같은 사실**에 대고 주장을 채점하기 위해서다.
 * 합집합이 대화보다 모자라면, 도구가 가져온 사실을 말할 때마다 근거 없는 주장으로
 * 잡힌다.
 *
 * 거부된 도구 호출과 실패한 도구 호출은 여기 들어오지 않는다. 실행되지 않았거나
 * 결과를 받지 못한 조회가 근거로 잡히면 안 된다.
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
}
