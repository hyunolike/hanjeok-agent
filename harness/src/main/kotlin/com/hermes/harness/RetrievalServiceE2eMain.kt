package com.hermes.harness

import com.fasterxml.jackson.databind.ObjectMapper
import com.hermes.context.*
import com.hermes.explain.*
import com.hermes.llm.*
import java.io.File
import java.net.URI
import java.time.Clock
import java.time.LocalDate

/** Real loopback HTTP/search + actual Kotlin citation gate; scripted provider, no LLM. */
fun main(args: Array<String>) {
    require(args.size == 3) { "usage: index-directory http://127.0.0.1:port report.json" }
    val m=ObjectMapper();val full=BundleLoader.load();val manifest=m.readTree(File(args[0],"manifest.json"))
    val pin=RetrievalIdentity(full.sha256,java.security.MessageDigest.getInstance("SHA-256").digest(full.metadataJson!!.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) },manifest["indexVersion"].asText(),manifest["vector"]["modelRevision"].asText())
    val port=RetrievalHttpClient(URI(args[1]),RetrievalToken { "local-test" },localTest=true)
    val s=RetrievalContextSelector(full,RetrievalMode.VECTOR,pin,port)
    val suite=m.readTree(File("harness/fixtures/context-selection/suite.json"))
    val cases=suite["cases"].toList()+m.readTree(File("experiments/retrieval/fixtures/graph-cases.json"))["cases"].toList()
    val rows=cases.map { c ->
        val q=c.path("question").asText().ifBlank { "혼잡도 등급의 기준은 무엇인가요?" }
        val ctx=s.select(q);val second=s.select(q)
        check(ctx.identity==second.identity && ctx.decision==second.decision)
        RetrievalContextSelector.POLICIES.forEach { check(ctx.systemText.contains("----- FILE: $it -----")) }
        c["requiredEvidencePaths"].forEach { check(ctx.validator.validate(listOf(it.asText()))==Valid) }
        check(ctx.validator.validate(listOf("records/weather/invented.json")) is Invalid)
        if(c.path("expectedAbstain").asBoolean()) check(ctx.abstain)
        var calls=0
        val provider=object:ExplanationProvider {
            override val name="scripted-local-E2E"
            override fun explain(systemText:String,userText:String):ProviderResult {
                calls++;check(systemText==ctx.systemText)
                return Answered(Explanation("정책 근거만 확인합니다.",(RetrievalContextSelector.POLICIES+c["requiredEvidencePaths"].map { it.asText() }).toList()),ProviderUsage(0,0,0,0))
            }
        }
        val fixed=object:com.hermes.context.ContextSelection {override fun select(query:String)=ctx}
        val v=CitationValidator(full);val assembler=PromptAssembler(full)
        val facts=BackendFacts("local-scripted-fixture","{}")
        val explanation=ExplanationService(assembler,v,provider,fixed).explain(facts)
        val loop=AgentLoop(provider,v,ToolRunner{error("no backend lookup in this harness")},Clock.systemUTC())
        val svc=CourseQuestionService(assembler,v,provider,loop,fixed)
        val ask=svc.ask(facts,q,emptyList());val events=mutableListOf<AskStreamEvent>()
        svc.askStream(facts,CourseBounds(emptySet(),LocalDate.parse("2026-10-10")),q,emptyList(),events::add)
        if(ctx.abstain) {check(explanation is Unavailable && ask is Unavailable && calls==0);check(events.none{it is DeltaEvent})}
        else {check(explanation is Explained) { c["id"].asText()+": explain" };check(ask is Explained) { c["id"].asText()+": ask" };check(events.last() is DoneEvent) { c["id"].asText()+": stream" };check(calls==3)}
        mapOf("id" to c["id"].asText(),"decision" to ctx.decision,"policyCount" to 8,"requiredEvidenceCovered" to true,"providerCalls" to calls,"threeRoutesVerified" to true)
    }
    val bad=RetrievalContextSelector(full,RetrievalMode.VECTOR,pin.copy(indexVersion="0".repeat(64)),port).select("경복궁 혼잡도 기준은?")
    check(bad.decision=="FULL_FALLBACK" && bad.systemText==full.raw)
    val denied=RetrievalContextSelector(full,RetrievalMode.VECTOR,pin,RetrievalHttpClient(URI(args[1]),RetrievalToken { "invalid-local-token" },localTest=true)).select("경복궁 기준")
    check(denied.decision=="FULL_FALLBACK" && denied.systemText==full.raw)
    val graphDown=RetrievalContextSelector(full,RetrievalMode.HYBRID_GRAPH,pin,port).select("경복궁 기준")
    check(graphDown.decision=="FULL_FALLBACK" && graphDown.systemText==full.raw)
    val fullCtx=RetrievalContextSelector(full).select("anything");check(fullCtx.systemText==full.raw && fullCtx.userText("facts")=="facts")
    val report=mapOf("schemaVersion" to 1,"backend" to manifest["vector"]["backend"].asText(),"identity" to pin,"actualHttpAndSearch" to true,"actualKotlinCitations" to true,"llmJudgeRun" to false,"graphApiRun" to false,"fixtureCount" to rows.size,"routeChecks" to rows.size*3,"deterministicChecks" to rows.size,"staleIndexFullFallback" to true,"authFailureFullFallback" to true,"graphUnavailableFullFallback" to true,"rows" to rows)
    File(args[2]).writeText(m.writerWithDefaultPrettyPrinter().writeValueAsString(report)+"\n")
    println("Real local API E2E: ${rows.size} fixtures, ${rows.size*3} request-route checks; no LLM calls")
}
