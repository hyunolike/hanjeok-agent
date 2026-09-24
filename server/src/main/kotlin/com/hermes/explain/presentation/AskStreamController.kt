package com.hermes.explain.presentation

import com.hermes.explain.AbortedEvent
import com.hermes.explain.BackendFacts
import com.hermes.explain.CitationsEvent
import com.hermes.explain.CourseQuestionService
import com.hermes.explain.DeltaEvent
import com.hermes.explain.DoneEvent
import com.hermes.explain.LookingEvent
import com.hermes.explain.QuestionTurn
import com.hermes.explain.UnavailableEvent
import com.hermes.facts.FactsSource
import com.hermes.facts.HanjeokUnavailableException
import org.slf4j.LoggerFactory
import org.springframework.beans.factory.annotation.Value
import org.springframework.http.MediaType
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RestController
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter
import java.time.Instant

/**
 * 이어 묻기의 스트리밍 변형. 요청 계약은 `/agent/ask` 와 같다 — 사실은 백엔드에서만 온다.
 *
 * **실패 이벤트는 불투명하다.** 사유는 여기서 로그로 남기고 브라우저에는 코드만 보낸다.
 * `ApiErrorHandler` 가 비스트리밍 응답에 지키는 계약과 같다 — 스트리밍이라고 예외를 두면
 * 인용 경로, 예외 메시지, 거절 범주가 샌다.
 */
@RestController
class AskStreamController(
    private val source: FactsSource,
    private val service: CourseQuestionService,
    private val executor: AskStreamExecutor,
    @param:Value("\${hermes.llm.model}") private val model: String,
) {

    private val log = LoggerFactory.getLogger(AskStreamController::class.java)

    @PostMapping("/agent/ask/stream", produces = [MediaType.TEXT_EVENT_STREAM_VALUE])
    fun stream(@RequestBody request: AskRequest): SseEmitter {
        // 스트림을 열기 전에 거른다 — 열고 나면 상태 코드를 바꿀 수 없다.
        if (request.courseUuid.isBlank()) throw InvalidAskRequestException("courseUuid is blank")
        if (request.question.isBlank()) throw InvalidAskRequestException("question is blank")

        val emitter = SseEmitter(TIMEOUT_MS)
        executor.execute {
            try {
                run(request, emitter)
                emitter.complete()
            } catch (e: Exception) {
                log.warn("ask stream crashed for course {}", request.courseUuid, e)
                emitter.completeWithError(e)
            }
        }
        return emitter
    }

    private fun run(request: AskRequest, emitter: SseEmitter) {
        val facts = try {
            source.fetch(request.courseUuid)
        } catch (e: HanjeokUnavailableException) {
            log.warn("facts unavailable for course {}", request.courseUuid, e)
            send(emitter, "unavailable", UNAVAILABLE)
            return
        }

        val history = request.history.orEmpty().map { QuestionTurn(it.question, it.answer) }

        service.askStream(BackendFacts(facts.courseUuid, facts.json), request.question, history) { event ->
            when (event) {
                is CitationsEvent -> send(emitter, "citations", mapOf("citations" to event.citations))
                is DeltaEvent -> send(emitter, "delta", mapOf("text" to event.text))
                // 도구 이름은 CourseTools 가 아는 둘 중 하나다 — 모델이 부른 이름이
                // 그대로 나가는 것이 아니라, 인자 검증을 통과한 호출만 여기 온다.
                is LookingEvent -> send(emitter, "looking", mapOf("what" to event.what))
                is DoneEvent -> send(
                    emitter,
                    "done",
                    mapOf("generatedAt" to Instant.now().toString(), "model" to model),
                )
                is UnavailableEvent -> {
                    log.warn("answer unavailable for course {}: {}", request.courseUuid, event.reason)
                    send(emitter, "unavailable", UNAVAILABLE)
                }
                is AbortedEvent -> {
                    log.warn("answer aborted for course {}: {}", request.courseUuid, event.reason)
                    send(emitter, "aborted", ABORTED)
                }
            }
        }
    }

    private fun send(emitter: SseEmitter, name: String, data: Any) {
        emitter.send(SseEmitter.event().name(name).data(data, MediaType.APPLICATION_JSON))
    }

    private companion object {
        /** 모델 호출이 수 초이고 사실 조회가 앞에 붙는다. 컨테이너 기본 비동기 타임아웃에 맡기지 않는다. */
        const val TIMEOUT_MS = 90_000L
        val UNAVAILABLE = mapOf("code" to "EXPLANATION_UNAVAILABLE")
        val ABORTED = mapOf("code" to "EXPLANATION_ABORTED")
    }
}
