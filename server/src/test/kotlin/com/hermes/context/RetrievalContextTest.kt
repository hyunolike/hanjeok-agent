package com.hermes.context

import com.fasterxml.jackson.databind.ObjectMapper
import com.hermes.explain.*
import com.hermes.llm.*
import org.assertj.core.api.Assertions.assertThat
import org.assertj.core.api.Assertions.assertThatThrownBy
import org.junit.jupiter.api.Test
import java.time.Clock
import com.sun.net.httpserver.HttpServer
import java.net.InetSocketAddress
import java.net.URI
import java.time.Duration
import java.util.concurrent.Executors

class RetrievalContextTest {
    private val bundle = BundleLoader.load()
    private val mapper = ObjectMapper()
    private val metadata = mapper.readTree(bundle.metadataJson!!)
    private val pin = RetrievalIdentity(bundle.sha256, contentSha256(bundle.metadataJson!!), "1".repeat(64), "tfidf-v1")
    private val seed = "records/places/gyeongbokgung.json"
    private val policy = "concepts/course-generation-policy.md"
    private fun response(ids: List<String>, status: String = "selected"): String = mapper.writeValueAsString(mapOf(
        "schemaVersion" to 1, "mode" to "VECTOR", "identity" to pin, "status" to status,
        "documents" to ids.map { path ->
            val entry = metadata["documents"].first { it["path"].asText() == path }
            mapOf("id" to path, "sha256" to entry["sha256"].asText(), "score" to 0.5,
                "sourceSignatures" to entry["sources"].map { "${it["path"].asText()}@${it["revision"].asText()}@${it["sha256"].asText()}" }.sorted())
        },
    ))
    private fun selection(ids: List<String>) = RetrievalContextSelector(bundle, RetrievalMode.VECTOR, pin,
        RetrievalPort { _, _, _ -> response(ids) })

    @Test fun `FULL never calls remote and preserves original bytes`() {
        val s = RetrievalContextSelector(bundle, RetrievalMode.FULL, port = RetrievalPort { _, _, _ -> error("must not call") })
        val c = s.select("경복궁 혼잡도 기준은?")
        assertThat(c.systemText.toByteArray()).isEqualTo(bundle.raw.toByteArray())
        assertThat(c.userText("facts")).isEqualTo("facts")
        assertThat(c.validator.validate(listOf(seed))).isEqualTo(Valid)
    }
    @Test fun `selected context keeps all policies and moves only retrieved seed to untrusted user data`() {
        val c = selection(listOf(seed)).select("경복궁 방문 순서의 기준은?")
        RetrievalContextSelector.POLICIES.forEach { assertThat(c.systemText).contains("----- FILE: $it -----") }
        assertThat(c.systemText).doesNotContain("----- FILE: $seed -----")
        assertThat(c.userText("facts")).contains("untrusted").contains(seed).contains("경복궁")
        assertThat(c.validator.validate(listOf(seed))).isEqualTo(Valid)
    }
    @Test fun `omitted seed cannot cross citation boundary`() {
        val c = selection(listOf(policy)).select("방문 순서는 어떤 규칙으로 정하나요?")
        assertThat(c.validator.validate(listOf(seed))).isInstanceOf(Invalid::class.java)
        assertThat(c.validator.validate(listOf(policy))).isEqualTo(Valid)
    }
    @Test fun `remote failures and identity source score schema drift return verified FULL`() {
        val good = mapper.readTree(response(listOf(seed)))
        val bad = mutableListOf<String>()
        for (field in listOf("bundleSha256", "metadataSha256", "indexVersion", "modelRevision")) {
            val row = good.deepCopy<com.fasterxml.jackson.databind.node.ObjectNode>();(row["identity"] as com.fasterxml.jackson.databind.node.ObjectNode).put(field,"bad");bad.add(row.toString())
        }
        for (field in listOf("sha256","id")) {
            val row = good.deepCopy<com.fasterxml.jackson.databind.node.ObjectNode>();(row["documents"][0] as com.fasterxml.jackson.databind.node.ObjectNode).put(field,"bad");bad.add(row.toString())
        }
        val negative=good.deepCopy<com.fasterxml.jackson.databind.node.ObjectNode>();(negative["documents"][0] as com.fasterxml.jackson.databind.node.ObjectNode).put("score",-1);bad.add(negative.toString())
        val source=good.deepCopy<com.fasterxml.jackson.databind.node.ObjectNode>();(source["documents"][0] as com.fasterxml.jackson.databind.node.ObjectNode).putArray("sourceSignatures").add("invented@bad@bad");bad.add(source.toString())
        bad += response(listOf(seed)).replace("\"schemaVersion\":1", "\"schemaVersion\":2,\"schemaVersion\":1");bad += response(listOf(seed,seed));bad += "{invalid";bad += "{}"
        for (payload in bad) {
            val c=RetrievalContextSelector(bundle,RetrievalMode.VECTOR,pin,RetrievalPort{_,_,_->payload}).select("경복궁 기준")
            assertThat(c.systemText).isEqualTo(bundle.raw);assertThat(c.decision).isEqualTo("FULL_FALLBACK")
        }
        val c=RetrievalContextSelector(bundle,RetrievalMode.VECTOR,pin,RetrievalPort{_,_,_->throw IllegalStateException("secret")}).select("경복궁 기준")
        assertThat(c.systemText).isEqualTo(bundle.raw);assertThat(c.userText("facts")).doesNotContain("secret")
    }
    @Test fun `corrupt original FULL fails closed before retrieval`() {
        assertThatThrownBy { RetrievalContextSelector(Bundle(bundle.documents.map { if(it.path==seed) it.copy(content="invented") else it },bundle.raw,bundle.metadataJson),RetrievalMode.FULL) }.isInstanceOf(IllegalStateException::class.java)
        assertThatThrownBy { RetrievalContextSelector(Bundle(bundle.documents,bundle.raw+"X",bundle.metadataJson),RetrievalMode.FULL) }.isInstanceOf(IllegalStateException::class.java)
        assertThatThrownBy { RetrievalContextSelector(Bundle(bundle.documents,bundle.raw,bundle.metadataJson!!.replace("\"schemaVersion\": 1","\"schemaVersion\": 2")),RetrievalMode.FULL) }.isInstanceOf(IllegalStateException::class.java)
    }
    @Test fun `blocking ask and explain use the request citation boundary`() {
        val provider=object:ExplanationProvider {
            override val name="scripted"
            override fun explain(systemText:String,userText:String):ProviderResult = Answered(Explanation("seed",listOf(seed)),ProviderUsage(0,0,0,0))
        }
        val validator=CitationValidator(bundle);val s=selection(listOf(policy));val facts=BackendFacts("fixture","{\"items\":[{\"name\":\"경복궁\"}]}")
        val svc=ExplanationService(PromptAssembler(bundle),validator,provider,s)
        assertThat(svc.explain(facts)).isInstanceOf(Unavailable::class.java)
        val loop=AgentLoop(provider,validator,ToolRunner{error("unused")},Clock.systemUTC())
        assertThat(CourseQuestionService(PromptAssembler(bundle),validator,provider,loop,s).ask(facts,"방문 순서는 어떤 규칙으로 정하나요?",emptyList())).isInstanceOf(Unavailable::class.java)
    }
    @Test fun `stream repair retains selected boundary and emits no invalid body`() {
        var calls=0
        val provider=object:ExplanationProvider {
            override val name="scripted"
            override fun explain(systemText:String,userText:String):ProviderResult {calls++;return Answered(Explanation("seed",listOf(seed)),ProviderUsage(0,0,0,0))}
        }
        val v=CitationValidator(bundle);val loop=AgentLoop(provider,v,ToolRunner{error("unused")},Clock.systemUTC());val events=mutableListOf<AskStreamEvent>()
        val service=CourseQuestionService(PromptAssembler(bundle),v,provider,loop,selection(listOf(policy)))
        service.askStream(BackendFacts("fixture","{}"),CourseBounds(emptySet(),java.time.LocalDate.parse("2026-10-10")),"방문 순서는 어떤 규칙으로 정하나요?",emptyList(),events::add)
        assertThat(calls).isEqualTo(2);assertThat(events.filterIsInstance<DeltaEvent>()).isEmpty();assertThat(events.last()).isInstanceOf(UnavailableEvent::class.java)
    }
    @Test fun `abstain does not call model`() {
        val s=RetrievalContextSelector(bundle,RetrievalMode.VECTOR,pin,RetrievalPort{_,_,_->response(emptyList(),"abstain")})
        val p=object:ExplanationProvider{override val name="unused";override fun explain(systemText:String,userText:String):ProviderResult=error("must not call")}
        assertThat(ExplanationService(PromptAssembler(bundle),CitationValidator(bundle),p,s).explain(BackendFacts("fixture","{}"))).isInstanceOf(Unavailable::class.java)
    }
    @Test fun `cache identity separates selection from FULL fallback`() {
        assertThat(selection(listOf(seed)).select("경복궁 기준").identity).isNotEqualTo(selection(listOf(policy)).select("경복궁 기준").identity)
        val keyA=ExplanationKey("same","facts","selected");val keyB=ExplanationKey("same","facts","full")
        assertThat(keyA).isNotEqualTo(keyB)
    }
    @Test fun `HTTP client limits bytes deadline and forbids arbitrary insecure endpoints`() {
        assertThatThrownBy { RetrievalHttpClient(URI("http://example.com"), RetrievalToken{ "test" }, localTest=true) }.isInstanceOf(IllegalArgumentException::class.java)
        val server=HttpServer.create(InetSocketAddress("127.0.0.1",0),0);val executor=Executors.newCachedThreadPool();server.executor=executor
        server.createContext("/v1/retrieve") { exchange ->
            val body=ByteArray(70_000){65};exchange.responseHeaders.set("Content-Type","application/json");exchange.sendResponseHeaders(200,body.size.toLong());exchange.responseBody.use{it.write(body)}
        };server.start()
        try {
            val client=RetrievalHttpClient(URI("http://127.0.0.1:${server.address.port}"),RetrievalToken{"test"},localTest=true,timeout=Duration.ofMillis(100))
            assertThatThrownBy{client.retrieve("경복궁 기준",RetrievalMode.VECTOR,pin)}.isInstanceOf(Exception::class.java)
        } finally {server.stop(0);executor.shutdownNow()}
    }
    @Test fun `actual HTTP stall consumes at most bounded caller time`() {
        val server=HttpServer.create(InetSocketAddress("127.0.0.1",0),0);val executor=Executors.newSingleThreadExecutor();server.executor=executor
        server.createContext("/v1/retrieve") { exchange ->
            Thread.sleep(700);exchange.responseHeaders.set("Content-Type","application/json")
            exchange.sendResponseHeaders(200,2);exchange.responseBody.use{it.write("{}".toByteArray())}
        };server.start()
        try {
            val client=RetrievalHttpClient(URI("http://127.0.0.1:${server.address.port}"),RetrievalToken{"test"},localTest=true,timeout=Duration.ofMillis(100))
            val start=System.nanoTime()
            assertThatThrownBy{client.retrieve("경복궁 기준",RetrievalMode.VECTOR,pin)}.isInstanceOf(Exception::class.java)
            assertThat(Duration.ofNanos(System.nanoTime()-start).toMillis()).isLessThan(500L)
        } finally {server.stop(0);executor.shutdownNow()}
    }
    @Test fun `actual explanation cache does not reuse selected response during FULL recovery`() {
        var state=0;var calls=0
        val selector=RetrievalContextSelector(bundle,RetrievalMode.VECTOR,pin,RetrievalPort{_,_,_->
            when(state) {0->response(listOf(seed));1->response(listOf(policy));else->error("offline")}})
        val provider=object:ExplanationProvider {
            override val name="scripted-cache"
            override fun explain(systemText:String,userText:String):ProviderResult {
                calls++;return Answered(Explanation("정책 확인",RetrievalContextSelector.POLICIES.toList()),ProviderUsage(0,0,0,0))
            }
        }
        val client=object:com.hermes.facts.HanjeokClient {
            override fun course(courseUuid:String)=mapper.readTree("""{"targetDate":"2026-08-15","title":"제목","congestionReductionRate":34,"summary":"요약","recommendedDate":null,"items":[{"attractionId":1001,"name":"경복궁","visitOrder":1,"timeLabel":"오전","grade":"VERY_CROWDED","reason":"첫 방문지","travelMinutesFromPrev":null}]}""")
            override fun congestion(attractionId:Long,date:String)=mapper.readTree("""{"diagnosis":{"concentration":87.3,"percentile":92,"grade":"VERY_CROWDED","message":"붐빈다"},"betterDates":[]}""")
            override fun alternatives(attractionId:Long,date:String,radiusKm:Int)=mapper.readTree("[]")
        }
        val executor=Executors.newFixedThreadPool(2)
        try {
            val service=ExplanationService(PromptAssembler(bundle),CitationValidator(bundle),provider,selector)
            val explainer=CourseExplainer(com.hermes.facts.FactsSource(client,15,executor),service,ExplanationCache())
            assertThat(explainer.explain("same").cached).isFalse()
            assertThat(explainer.explain("same").cached).isTrue()
            state=1;assertThat(explainer.explain("same").cached).isFalse()
            state=2;assertThat(explainer.explain("same").cached).isFalse()
            assertThat(calls).isEqualTo(3)
        } finally {executor.shutdownNow()}
    }

    @Test fun `overlapping selected and FULL recovery never share cache or single flight`() {
        val entered=java.util.concurrent.CountDownLatch(2);val release=java.util.concurrent.CountDownLatch(1)
        val calls=java.util.concurrent.atomic.AtomicInteger()
        val selector=RetrievalContextSelector(bundle,RetrievalMode.VECTOR,pin,RetrievalPort{_,_,_->
            if(Thread.currentThread().name.startsWith("selected-request")) response(listOf(seed)) else error("offline")})
        val provider=object:ExplanationProvider {
            override val name="scripted-overlap"
            override fun explain(systemText:String,userText:String):ProviderResult {
                calls.incrementAndGet();entered.countDown();check(release.await(3,java.util.concurrent.TimeUnit.SECONDS))
                val text=if(systemText.contains("----- FILE: $seed -----")) "FULL response" else "selected response"
                return Answered(Explanation(text,RetrievalContextSelector.POLICIES.toList()),ProviderUsage(0,0,0,0))
            }
        }
        val client=object:com.hermes.facts.HanjeokClient {
            override fun course(courseUuid:String)=mapper.readTree("""{"targetDate":"2026-08-15","title":"동일 facts","congestionReductionRate":34,"summary":"요약","recommendedDate":null,"items":[{"attractionId":1001,"name":"경복궁","visitOrder":1,"timeLabel":"오전","grade":"VERY_CROWDED","reason":"첫 방문지","travelMinutesFromPrev":null}]}""")
            override fun congestion(attractionId:Long,date:String)=mapper.readTree("""{"diagnosis":{"concentration":87.3,"percentile":92,"grade":"VERY_CROWDED","message":"fixture"},"betterDates":[]}""")
            override fun alternatives(attractionId:Long,date:String,radiusKm:Int)=mapper.readTree("[]")
        }
        val backend=Executors.newFixedThreadPool(2);val requests=Executors.newFixedThreadPool(2)
        val service=ExplanationService(PromptAssembler(bundle),CitationValidator(bundle),provider,selector)
        val explainer=CourseExplainer(com.hermes.facts.FactsSource(client,15,backend),service,ExplanationCache())
        try {
            val a=requests.submit<CourseExplanation>{Thread.currentThread().name="selected-request";explainer.explain("same-course")}
            val b=requests.submit<CourseExplanation>{Thread.currentThread().name="fallback-request";explainer.explain("same-course")}
            assertThat(entered.await(2,java.util.concurrent.TimeUnit.SECONDS)).describedAs("both context identities must independently reach provider").isTrue()
            release.countDown()
            assertThat(a.get(2,java.util.concurrent.TimeUnit.SECONDS).explanation.explanation).isEqualTo("selected response")
            assertThat(b.get(2,java.util.concurrent.TimeUnit.SECONDS).explanation.explanation).isEqualTo("FULL response")
            assertThat(calls.get()).isEqualTo(2)
            val selected=requests.submit<CourseExplanation>{Thread.currentThread().name="selected-request";explainer.explain("same-course")}.get(2,java.util.concurrent.TimeUnit.SECONDS)
            val fallback=requests.submit<CourseExplanation>{Thread.currentThread().name="fallback-request";explainer.explain("same-course")}.get(2,java.util.concurrent.TimeUnit.SECONDS)
            assertThat(selected.cached && fallback.cached).isTrue()
            assertThat(selected.explanation.explanation).isEqualTo("selected response");assertThat(fallback.explanation.explanation).isEqualTo("FULL response")
            assertThat(calls.get()).isEqualTo(2)
        } finally {release.countDown();requests.shutdownNow();backend.shutdownNow()}
    }

    @Test fun `retrieval HTTP client uses ASGI HTTP1 without upgrade negotiation`() {
        val server=HttpServer.create(InetSocketAddress("127.0.0.1",0),0)
        val upgrade=java.util.concurrent.atomic.AtomicReference<String>()
        server.createContext("/v1/retrieve") { exchange ->
            upgrade.set(exchange.requestHeaders.getFirst("Upgrade"))
            exchange.responseHeaders.set("Content-Type","application/json")
            val body=response(listOf(seed)).toByteArray();exchange.sendResponseHeaders(200,body.size.toLong());exchange.responseBody.use{it.write(body)}
        };server.start()
        try {
            val client=RetrievalHttpClient(URI("http://127.0.0.1:${server.address.port}"),RetrievalToken{"test"},localTest=true)
            assertThat(client.retrieve("경복궁 기준",RetrievalMode.VECTOR,pin)).contains("selected")
            assertThat(upgrade.get()).isNull()
        } finally {server.stop(0)}
    }

}
