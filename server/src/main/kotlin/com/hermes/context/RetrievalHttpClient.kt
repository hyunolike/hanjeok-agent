package com.hermes.context

import com.fasterxml.jackson.databind.ObjectMapper
import java.io.ByteArrayOutputStream
import java.net.URI
import java.net.URLEncoder
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.nio.ByteBuffer
import java.time.Duration
import java.util.concurrent.CompletableFuture
import java.util.concurrent.CompletionStage
import java.util.concurrent.Flow
import java.util.concurrent.Semaphore
import java.util.concurrent.TimeUnit

fun interface RetrievalToken { fun token(): String }

/** Uses an attached identity; never creates credentials/IAM or contacts metadata in FULL mode. */
class MetadataRetrievalToken(private val audience: URI) : RetrievalToken {
    private val client=HttpClient.newBuilder().connectTimeout(Duration.ofMillis(500)).followRedirects(HttpClient.Redirect.NEVER).build()
    init { require(audience.scheme=="https" && audience.host!=null && audience.userInfo==null && audience.query==null && audience.fragment==null && audience.path in listOf("","/")) }
    override fun token(): String {
        val uri=URI("http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience="+URLEncoder.encode(audience.toString(),Charsets.UTF_8)+"&format=full")
        val request=HttpRequest.newBuilder(uri).header("Metadata-Flavor","Google").timeout(Duration.ofMillis(500)).GET().build()
        val future=client.sendAsync(request,HttpResponse.BodyHandler { BoundedBody(8192) })
        try { val r=future.get(500,TimeUnit.MILLISECONDS);check(r.statusCode()==200);return r.body().toString(Charsets.UTF_8).also { check(it.isNotBlank() && !it.contains('\n')) } }
        finally {if(!future.isDone)future.cancel(true)}
    }
}

class RetrievalHttpClient(origin: URI, private val token: RetrievalToken, localTest: Boolean=false,
    private val timeout: Duration=Duration.ofSeconds(2)) : RetrievalPort {
    private val mapper=ObjectMapper()
    private val endpoint: URI
    private val admission=Semaphore(4)
    private val client=HttpClient.newBuilder().connectTimeout(Duration.ofMillis(500)).followRedirects(HttpClient.Redirect.NEVER).build()
    init {
        require(origin.host!=null && origin.userInfo==null && origin.query==null && origin.fragment==null && origin.path in listOf("","/"))
        require(if(localTest) origin.scheme=="http" && origin.host=="127.0.0.1" else origin.scheme=="https")
        require(!timeout.isNegative && !timeout.isZero && timeout<=Duration.ofSeconds(2))
        endpoint=origin.resolve("/v1/retrieve")
    }
    override fun retrieve(query: String,mode: RetrievalMode,identity: RetrievalIdentity): String {
        check(admission.tryAcquire()) { "retrieval admission full" }
        val started=System.nanoTime()
        try {
            val body=mapper.writeValueAsBytes(mapOf("schemaVersion" to 1,"query" to query,"mode" to mode.name,"identity" to identity))
            require(body.size<=8192)
            val auth=token.token();check(auth.isNotBlank() && !auth.contains('\n') && !auth.contains('\r'))
            val remaining=timeout.toNanos()-(System.nanoTime()-started);check(remaining>0)
            val request=HttpRequest.newBuilder(endpoint).timeout(Duration.ofNanos(remaining)).header("Content-Type","application/json")
                .header("Authorization","Bearer $auth").POST(HttpRequest.BodyPublishers.ofByteArray(body)).build()
            val future=client.sendAsync(request,HttpResponse.BodyHandler { BoundedBody(65536) })
            try {
                val r=future.get(remaining,TimeUnit.NANOSECONDS);check(r.statusCode()==200) { "retrieval unavailable" }
                check(r.headers().firstValue("content-type").orElse("").startsWith("application/json"))
                return r.body().toString(Charsets.UTF_8)
            } finally {if(!future.isDone)future.cancel(true)}
        } finally {admission.release()}
    }
}

private class BoundedBody(private val limit: Int) : HttpResponse.BodySubscriber<ByteArray> {
    private val result=CompletableFuture<ByteArray>();private val bytes=ByteArrayOutputStream();private var subscription: Flow.Subscription?=null
    override fun getBody(): CompletionStage<ByteArray> = result
    override fun onSubscribe(s: Flow.Subscription) {subscription=s;s.request(1)}
    override fun onNext(items: List<ByteBuffer>) {
        try {
            val incoming=items.sumOf { it.remaining().toLong() };check(bytes.size().toLong()+incoming<=limit) { "retrieval body exceeds limit" }
            items.forEach { b -> val chunk=ByteArray(b.remaining());b.get(chunk);bytes.write(chunk) };subscription!!.request(1)
        } catch(e:Exception){subscription?.cancel();result.completeExceptionally(e)}
    }
    override fun onError(t: Throwable) {result.completeExceptionally(t)}
    override fun onComplete() {result.complete(bytes.toByteArray())}
}
