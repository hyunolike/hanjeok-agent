package com.hermes.harness

import com.fasterxml.jackson.databind.ObjectMapper
import com.hermes.context.*
import com.hermes.explain.*
import com.hermes.llm.*
import java.io.File
import java.net.URI
import java.time.Clock
import java.time.LocalDate

/** An external local smoke owns fault injection; this checks actual HTTP FULL recovery. */
fun main(args:Array<String>) {
    require(args.size==3)
    val m=ObjectMapper();val full=BundleLoader.load();val manifest=m.readTree(File(args[0],"manifest.json"))
    val metaHash=java.security.MessageDigest.getInstance("SHA-256").digest(full.metadataJson!!.toByteArray()).joinToString(""){"%02x".format(it)}
    val pin=RetrievalIdentity(full.sha256,metaHash,manifest["indexVersion"].asText(),manifest["vector"]["modelRevision"].asText())
    val port=RetrievalHttpClient(URI(args[1]),RetrievalToken{"local-test"},localTest=true)
    val s=RetrievalContextSelector(full,RetrievalMode.HYBRID_GRAPH,pin,port)
    val start=System.nanoTime();val ctx=s.select("경복궁 혼잡도 기준은?")
    val elapsed=(System.nanoTime()-start)/1_000_000
    check(ctx.decision=="FULL_FALLBACK" && ctx.systemText==full.raw && elapsed<3000)
    var calls=0
    val provider=object:ExplanationProvider {
        override val name="scripted-recovery"
        override fun explain(systemText:String,userText:String):ProviderResult {
            calls++;check(systemText==full.raw)
            return Answered(Explanation("정책만 확인합니다.",RetrievalContextSelector.POLICIES.toList()),ProviderUsage(0,0,0,0))
        }
    }
    val fixture=m.readTree(File("harness/fixtures/course-explanation-request.json"));val facts=BackendFacts(fixture["courseUuid"].asText(),FactsNormalizer.normalize(fixture).toString())
    val v=CitationValidator(full);val assembler=PromptAssembler(full)
    check(ExplanationService(assembler,v,provider,s).explain(facts) is Explained)
    val service=CourseQuestionService(assembler,v,provider,AgentLoop(provider,v,ToolRunner{error("unused")},Clock.systemUTC()),s)
    check(service.ask(facts,"경복궁 혼잡도 기준은?",emptyList()) is Explained)
    val events=mutableListOf<AskStreamEvent>()
    service.askStream(facts,CourseBounds(emptySet(),LocalDate.parse("2026-10-10")),"경복궁 혼잡도 기준은?",emptyList(),events::add)
    check(events.last() is DoneEvent && calls==3)
    check(ctx.validator.validate(listOf("records/weather/invented.json")) is Invalid)
    File(args[2]).writeText(m.writerWithDefaultPrettyPrinter().writeValueAsString(mapOf("actualHttp" to true,"decision" to ctx.decision,"exactOriginalFull" to true,"threeRoutesRecovered" to true,"selectionMillis" to elapsed,"unknownCitationRejected" to true,"providerCalls" to calls,"llmCalls" to 0))+"\n")
    println("Actual HTTP verified FULL recovery: three routes, bounded selection")
}
