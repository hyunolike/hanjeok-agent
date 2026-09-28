# 도구 루프 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 모델이 필요할 때만 한적 API 를 스스로 조회하고, 인용이 틀리면 한 번 다시 쓰게 하되, 검증을 통과하지 않은 글자는 여전히 한 자도 내보내지 않는다.

**Architecture:** `ExplanationProvider` 포트에 `converse()` 를 더한다. 어댑터는 `ChatClient` 를 우회하고 `ChatModel` 을 직접 불러 **실행되지 않은** 도구 호출을 받는다. 실행·검증·예산은 application 층의 새 `AgentLoop` 가 전부 한다. `AskStreamGate` 의 판정 로직은 손대지 않는다.

**Tech Stack:** Kotlin 2.2.21, Spring Boot 4.1.0 (webmvc/servlet, `SseEmitter`), Spring AI 2.0.1, Jackson 2 (`com.fasterxml`) — 단, presentation 층 응답 직렬화는 Jackson 3 (`tools.jackson`), JUnit 5, Next.js 16 / React 19 / vitest

**Spec:** `docs/superpowers/specs/2026-09-24-agent-loop-design.md`

## Global Constraints

- `system` 블록은 번들 원문 그대로다. 도구 지침을 포함해 **어떤 것도 `system` 에 덧붙이지 않는다** — 요청마다 달라지는 것이 섞이면 1시간 프롬프트 캐시가 통째로 미스 난다.
- 검증을 통과하지 않은 본문은 한 글자도 나가지 않는다. `AskStreamGate` 의 판정 로직은 이 계획에서 바뀌지 않으며, 바뀌는 것은 `UnavailableEvent` 에 `cause` 필드가 붙는 것뿐이다.
- 실패 이벤트는 사유를 싣지 않는다. 브라우저로 가는 것은 `{"code":"EXPLANATION_UNAVAILABLE"}` 와 `{"code":"EXPLANATION_ABORTED"}` 뿐이다.
- `looking` 이벤트는 도구 이름만 싣는다 — `{"what":"congestion"}` 또는 `{"what":"alternatives"}`. 인자는 싣지 않는다.
- 도구 라운드 최대 2 (모델 호출 ≤3회). 수리 1회, 도구 라운드와 별개. 마감은 루프 시작부터 60_000ms, 둘이 공유한다.
- 예산이 떨어진 마지막 호출과 수리 호출에는 **도구를 싣지 않는다.**
- `date` 는 코스의 `targetDate` 기준 ±14일. `radiusKm` 은 1 이상 50 이하. `attractionId` 는 그 코스의 `items` 에 실재해야 한다.
- 인자 검증 실패는 예외가 아니라 **도구 결과 자리의 거부 사유** 로 되먹인다.
- 유료 평가(`./gradlew eval`)는 사람의 명시적 승인 없이 실행하지 않는다. CI 에서도 절대 돌지 않는다.
- 백그라운드 실행 금지. Gradle 도 그 무엇도 백그라운드로 돌리지 않는다 — 타임아웃은 Bash 도구의 timeout 파라미터로 준다.
- `.env` 는 운영 키를 담고 있다. 출력·인용·커밋하지 않는다.
- **단일 모듈 Gradle 빌드다.** `server/` 와 `harness/` 는 `sourceSets` 로 엮인 소스 디렉터리이지 서브프로젝트가 아니다 — 테스트 태스크는 `./gradlew test` 이고 `:server:test` 는 존재하지 않는다.
- **단언은 AssertJ 로 쓴다** (`import org.assertj.core.api.Assertions.assertThat`). 저장소 전체가 그렇다. `kotlin.test` 를 쓰지 않고, 그 의존성을 추가하지도 않는다. sealed 타입은 기존 관례대로 단언한다 — `assertThat(x).isInstanceOf(T::class.java)` 뒤에 필요하면 `val y = x as T`.

---

## File Structure

**신규 (server/src/main/kotlin/com/hermes/)**

| 파일 | 책임 |
| --- | --- |
| `llm/AgentTurns.kt` | `Turn`/`ToolCall`/`ToolResult`/`ToolSpec`/`AgentStep` 타입. 프레임워크를 모른다 |
| `explain/CourseTools.kt` | 도구 둘의 이름·설명·JSON 스키마, 그리고 인자 검증 (순수) |
| `explain/AgentLoop.kt` | 루프·예산·마감·도구 실행·수리. application 층 |
| `explain/ToolFacts.kt` | 초기 facts 와 도구 결과의 합집합 |

**수정**

| 파일 | 무엇을 |
| --- | --- |
| `llm/ExplanationProvider.kt` | `converse()` 추가 (기본 구현 있음) |
| `llm/SpringAiExplanationProvider.kt` | 생성자가 `ChatModel` 을 받게, `converse()` 구현 |
| `shared/config/LlmSelection.kt` | `ChatClient` 대신 `ChatModel` 을 넘김 |
| `explain/AskStreamGate.kt` | `UnavailableEvent` 에 `cause: FailureCause` |
| `explain/CourseQuestionService.kt` | `askStream` 이 `AgentLoop` 를 타게 |
| `explain/presentation/AskStreamController.kt` | `looking` 이벤트 송출 |
| `harness/ForbiddenBehaviours.kt` | 합집합 facts 와 대조 |
| `frontend/src/lib/agent.ts` | `looking` 이벤트 수신 |
| `frontend/src/app/course/[uuid]/AskBox.tsx` | 조회 중 표시 |

---

### Task 1: 포트에 대화 타입과 `converse()` 를 더한다

**Files:**
- Create: `server/src/main/kotlin/com/hermes/llm/AgentTurns.kt`
- Modify: `server/src/main/kotlin/com/hermes/llm/ExplanationProvider.kt`
- Test: `server/src/test/kotlin/com/hermes/llm/DefaultConverseTest.kt`

**Interfaces:**
- Consumes: 기존 `ExplanationProvider.stream(systemText, userText, onChunk): StreamEnd`
- Produces: `Turn`, `UserTurn`, `ToolCallTurn`, `ToolResultTurn`, `ToolCall`, `ToolResult`, `ToolSpec`, `AgentStep`, `ToolRequested`, `Spoke`, 그리고 `ExplanationProvider.converse(systemText, turns, tools, onChunk): AgentStep`

기본 구현이 있어야 기존 테스트 페이크 7개가 안 깨진다. `stream()` 이 쓴 수법과 같다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`server/src/test/kotlin/com/hermes/llm/DefaultConverseTest.kt`:

```kotlin
package com.hermes.llm

import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test

private class RecordingProvider(private val result: ProviderResult) : ExplanationProvider {
    override val name = "recording"
    var seenUserText: String? = null
    override fun explain(systemText: String, userText: String): ProviderResult {
        seenUserText = userText
        return result
    }
}

class DefaultConverseTest {

    private val answered = Answered(
        explanation = Explanation("본문", listOf("concepts/a.md")),
        usage = ProviderUsage(0, 0, 0, 0),
    )

    @Test
    fun `기본 구현은 도구를 무시하고 항상 Spoke 를 낸다`() {
        val provider = RecordingProvider(answered)
        val chunks = mutableListOf<String>()

        val step = provider.converse(
            systemText = "SYS",
            turns = listOf(UserTurn("질문")),
            tools = listOf(ToolSpec("congestion", "혼잡도", "{}")),
            onChunk = { chunks.add(it) },
        )

        assertThat(step).isInstanceOf(Spoke::class.java)
        assertThat((step as Spoke).end).isInstanceOf(StreamCompleted::class.java)
        assertThat(chunks.joinToString("")).contains("본문")
    }

    @Test
    fun `기본 구현은 마지막 사용자 턴의 텍스트를 explain 에 넘긴다`() {
        val provider = RecordingProvider(answered)

        provider.converse(
            systemText = "SYS",
            turns = listOf(
                UserTurn("첫 질문"),
                ToolCallTurn(listOf(ToolCall("id-1", "congestion", "{}"))),
                ToolResultTurn(listOf(ToolResult("id-1", "{}"))),
                UserTurn("마지막 질문"),
            ),
            tools = emptyList(),
            onChunk = {},
        )

        assertThat(provider.seenUserText).isEqualTo("마지막 질문")
    }

    @Test
    fun `거절은 Spoke 안의 StreamRefused 로 온다`() {
        val provider = RecordingProvider(Refused(category = "safety"))

        val step = provider.converse("SYS", listOf(UserTurn("질문")), emptyList()) {}

        assertThat(step).isInstanceOf(Spoke::class.java)
        assertThat((step as Spoke).end).isEqualTo(StreamRefused("safety"))
    }
}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests 'com.hermes.llm.DefaultConverseTest'`
Expected: 컴파일 실패 — `Unresolved reference: UserTurn`

- [ ] **Step 3: 타입을 만든다**

`server/src/main/kotlin/com/hermes/llm/AgentTurns.kt`:

```kotlin
package com.hermes.llm

/**
 * 도구 루프가 쌓아 가는 대화. 프레임워크 타입이 아니다 — 포트가 존재하는 이유가
 * 서비스 계층과 테스트 페이크를 Spring AI 없이 돌리는 것이기 때문이다.
 */
sealed interface Turn

data class UserTurn(val text: String) : Turn

/** 모델이 낸 도구 호출. 다음 요청에 그대로 되실어야 모델이 문맥을 잃지 않는다. */
data class ToolCallTurn(val calls: List<ToolCall>) : Turn

data class ToolResultTurn(val results: List<ToolResult>) : Turn

data class ToolCall(val id: String, val name: String, val argumentsJson: String)

data class ToolResult(val id: String, val contentJson: String)

data class ToolSpec(val name: String, val description: String, val parametersSchema: String)

sealed interface AgentStep

/**
 * 모델이 도구를 부르려 한다.
 *
 * **이 값이 나왔다면 onChunk 는 한 번도 불리지 않았다.** 어댑터가 도구 델타를
 * onChunk 에 넣지 않기 때문이고, 그래서 도구 턴은 AskStreamGate 에 도달하지 않는다.
 */
data class ToolRequested(val calls: List<ToolCall>, val usage: ProviderUsage) : AgentStep

/** 모델이 답했다. 조각은 onChunk 로 이미 나갔다. */
data class Spoke(val end: StreamEnd) : AgentStep
```

- [ ] **Step 4: 포트에 기본 구현을 더한다**

`ExplanationProvider` 인터페이스 안, `stream(...)` 바로 아래에 추가한다:

```kotlin
    /**
     * 도구를 쓸 수 있는 대화. 도구를 부르지 않으면 [stream] 과 같은 경로다.
     *
     * 기본 구현은 도구를 무시하고 마지막 사용자 턴만 [stream] 에 넘긴다. 스트리밍만
     * 하고 도구를 모르는 프로바이더와 테스트 페이크가 같은 계약을 쓸 수 있고, 같은
     * explain() 을 거치므로 프롬프트 조립이 갈라지지 않는다.
     */
    fun converse(
        systemText: String,
        turns: List<Turn>,
        tools: List<ToolSpec>,
        onChunk: (String) -> Unit,
    ): AgentStep = Spoke(
        stream(
            systemText,
            turns.filterIsInstance<UserTurn>().lastOrNull()?.text
                ?: error("converse called with no user turn"),
            onChunk,
        ),
    )
```

- [ ] **Step 5: 통과를 확인한다**

Run: `./gradlew test --tests 'com.hermes.llm.DefaultConverseTest'`
Expected: PASS (3개)

- [ ] **Step 6: 기존 전체 스위트가 그대로인지 확인한다**

Run: `./gradlew test`
Expected: PASS. 페이크 7개가 `converse` 를 구현하지 않고도 컴파일되어야 한다.

- [ ] **Step 7: 커밋**

```bash
git add server/src/main/kotlin/com/hermes/llm/AgentTurns.kt \
        server/src/main/kotlin/com/hermes/llm/ExplanationProvider.kt \
        server/src/test/kotlin/com/hermes/llm/DefaultConverseTest.kt
git commit -m "feat: give the provider port a tool-capable conversation method"
```

---

### Task 2: 도구 둘의 스키마와 인자 검증

**Files:**
- Create: `server/src/main/kotlin/com/hermes/explain/CourseTools.kt`
- Test: `server/src/test/kotlin/com/hermes/explain/CourseToolsTest.kt`

**Interfaces:**
- Consumes: `ToolSpec`, `ToolCall` (Task 1)
- Produces:
  - `object CourseTools`
  - `CourseTools.specs(): List<ToolSpec>`
  - `CourseTools.parse(call: ToolCall, bounds: CourseBounds): ToolArgs` — `ToolArgs` 는 `Congestion`/`Alternatives`/`Rejected` 중 하나
  - `data class CourseBounds(val attractionIds: Set<Long>, val targetDate: LocalDate)`
  - `sealed interface ToolArgs`; `data class Congestion(val attractionId: Long, val date: LocalDate)`; `data class Alternatives(val attractionId: Long, val date: LocalDate, val radiusKm: Int)`; `data class Rejected(val reason: String)`

순수 함수다. 네트워크도 Spring 도 모른다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`server/src/test/kotlin/com/hermes/explain/CourseToolsTest.kt`:

```kotlin
package com.hermes.explain

import com.hermes.llm.ToolCall
import java.time.LocalDate
import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test

class CourseToolsTest {

    private val bounds = CourseBounds(
        attractionIds = setOf(11L, 22L),
        targetDate = LocalDate.of(2026, 10, 1),
    )

    private fun call(name: String, args: String) = ToolCall("id-1", name, args)

    @Test
    fun `도구는 둘이고 이름이 고정이다`() {
        assertThat("alternatives").isEqualTo(listOf("congestion"), CourseTools.specs().map { it.name })
    }

    @Test
    fun `유효한 congestion 인자를 판다`() {
        val args = CourseTools.parse(
            call("congestion", """{"attractionId":11,"date":"2026-10-03"}"""),
            bounds,
        )
        assertThat(LocalDate.of(2026, 10, 3).isEqualTo(Congestion(11L)), args)
    }

    @Test
    fun `alternatives 의 radiusKm 기본값은 15 다`() {
        val args = CourseTools.parse(
            call("alternatives", """{"attractionId":22,"date":"2026-10-01"}"""),
            bounds,
        )
        assertThat(LocalDate.of(2026, 10, 1).isEqualTo(Alternatives(22L), 15), args)
    }

    @Test
    fun `코스에 없는 attractionId 는 거부된다`() {
        val args = CourseTools.parse(
            call("congestion", """{"attractionId":99,"date":"2026-10-01"}"""),
            bounds,
        )
        assertThat(args).isInstanceOf(Rejected::class.java)
        assertThat((args as Rejected).reason).contains("99")
    }

    @Test
    fun `targetDate 에서 14일을 넘는 날짜는 거부된다`() {
        val tooFar = CourseTools.parse(
            call("congestion", """{"attractionId":11,"date":"2026-10-16"}"""),
            bounds,
        )
        assertThat(tooFar).isInstanceOf(Rejected::class.java)

        val tooEarly = CourseTools.parse(
            call("congestion", """{"attractionId":11,"date":"2026-09-16"}"""),
            bounds,
        )
        assertThat(tooEarly).isInstanceOf(Rejected::class.java)
    }

    @Test
    fun `정확히 14일 경계는 허용된다`() {
        assertThat(CourseTools.parse(call("congestion", """{"attractionId":11,"date":"2026-10-15"}"""), bounds))
            .isInstanceOf(Congestion::class.java)
        assertThat(CourseTools.parse(call("congestion", """{"attractionId":11,"date":"2026-09-17"}"""), bounds))
            .isInstanceOf(Congestion::class.java)
    }

    @Test
    fun `radiusKm 상한과 하한을 벗어나면 거부된다`() {
        assertThat(
            CourseTools.parse(call("alternatives", """{"attractionId":11,"date":"2026-10-01","radiusKm":51}"""), bounds),
        ).isInstanceOf(Rejected::class.java)
        assertThat(
            CourseTools.parse(call("alternatives", """{"attractionId":11,"date":"2026-10-01","radiusKm":0}"""), bounds),
        ).isInstanceOf(Rejected::class.java)
    }

    @Test
    fun `모르는 도구 이름은 거부된다`() {
        assertThat(CourseTools.parse(call("weather", "{}"), bounds)).isInstanceOf(Rejected::class.java)
    }

    @Test
    fun `망가진 JSON 은 예외가 아니라 거부다`() {
        assertThat(CourseTools.parse(call("congestion", "{not json"), bounds)).isInstanceOf(Rejected::class.java)
    }

    @Test
    fun `날짜 형식이 틀리면 거부된다`() {
        assertThat(CourseTools.parse(call("congestion", """{"attractionId":11,"date":"10-01-2026"}"""), bounds))
            .isInstanceOf(Rejected::class.java)
    }

    @Test
    fun `거부 사유는 모델이 읽고 고칠 수 있게 무엇이 틀렸는지 말한다`() {
        val rejected = CourseTools.parse(
            call("alternatives", """{"attractionId":11,"date":"2026-10-01","radiusKm":51}"""),
            bounds,
        )
        assertThat(rejected).isInstanceOf(Rejected::class.java)
        assertThat((rejected as Rejected).reason).contains("radiusKm", "50")
    }
}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests 'com.hermes.explain.CourseToolsTest'`
Expected: 컴파일 실패 — `Unresolved reference: CourseTools`

- [ ] **Step 3: 구현한다**

`server/src/main/kotlin/com/hermes/explain/CourseTools.kt`:

```kotlin
package com.hermes.explain

import com.fasterxml.jackson.databind.ObjectMapper
import com.hermes.llm.ToolCall
import com.hermes.llm.ToolSpec
import java.time.LocalDate
import java.time.format.DateTimeParseException
import kotlin.math.abs

/** 이 요청에서 도구가 움직일 수 있는 범위. 코스가 정한다 — 모델이 정하지 않는다. */
data class CourseBounds(val attractionIds: Set<Long>, val targetDate: LocalDate)

sealed interface ToolArgs

data class Congestion(val attractionId: Long, val date: LocalDate) : ToolArgs

data class Alternatives(val attractionId: Long, val date: LocalDate, val radiusKm: Int) : ToolArgs

/**
 * 인자가 범위를 벗어났다. **예외가 아니다** — 사유를 도구 결과 자리에 넣어 되먹이면
 * 모델이 고쳐 부르거나 포기할 수 있다. 던지면 한 번 잘못 부른 것이 요청 전체를 죽인다.
 */
data class Rejected(val reason: String) : ToolArgs

/**
 * 한적에서 도구가 될 만한 것은 둘뿐이다. `course` 는 어차피 매 요청 받으므로 도구가
 * 아니다.
 *
 * **인자는 모델을 믿지 않는다.** 날짜 범위를 두는 이유는 한적 예보가 먼 날짜를 갖고
 * 있지 않아서다 — 범위가 없으면 모델이 1년 뒤를 물어 빈 응답을 받고, 그 빈 응답을
 * 사실로 설명하게 된다.
 */
object CourseTools {

    const val CONGESTION = "congestion"
    const val ALTERNATIVES = "alternatives"

    const val DEFAULT_RADIUS_KM = 15
    const val MIN_RADIUS_KM = 1
    const val MAX_RADIUS_KM = 50
    const val MAX_DATE_OFFSET_DAYS = 14L

    private val MAPPER = ObjectMapper()

    fun specs(): List<ToolSpec> = listOf(
        ToolSpec(
            name = CONGESTION,
            description = "특정 관광지의 특정 날짜 혼잡도를 조회한다. " +
                "코스에 이미 실린 날짜가 아닌 다른 날을 물어볼 때만 쓴다.",
            parametersSchema = """
                {"type":"object",
                 "properties":{
                   "attractionId":{"type":"integer","description":"이 코스에 실제로 있는 관광지 id"},
                   "date":{"type":"string","description":"YYYY-MM-DD"}},
                 "required":["attractionId","date"],
                 "additionalProperties":false}
            """.trimIndent(),
        ),
        ToolSpec(
            name = ALTERNATIVES,
            description = "특정 관광지 주변의 대안 장소를 조회한다. " +
                "기본 반경보다 넓게 또는 좁게 보라는 요청이 있을 때만 쓴다.",
            parametersSchema = """
                {"type":"object",
                 "properties":{
                   "attractionId":{"type":"integer","description":"이 코스에 실제로 있는 관광지 id"},
                   "date":{"type":"string","description":"YYYY-MM-DD"},
                   "radiusKm":{"type":"integer","description":"$MIN_RADIUS_KM~$MAX_RADIUS_KM, 기본 $DEFAULT_RADIUS_KM"}},
                 "required":["attractionId","date"],
                 "additionalProperties":false}
            """.trimIndent(),
        ),
    )

    fun parse(call: ToolCall, bounds: CourseBounds): ToolArgs {
        if (call.name != CONGESTION && call.name != ALTERNATIVES) {
            return Rejected("'${call.name}' 은 없는 도구다. 쓸 수 있는 것은 $CONGESTION 과 $ALTERNATIVES 뿐이다.")
        }

        val node = try {
            MAPPER.readTree(call.argumentsJson)
        } catch (e: Exception) {
            return Rejected("인자가 올바른 JSON 이 아니다: ${e::class.simpleName}")
        }

        val attractionId = node.path("attractionId").asLong(0L)
        if (attractionId !in bounds.attractionIds) {
            return Rejected(
                "attractionId $attractionId 는 이 코스에 없다. " +
                    "쓸 수 있는 것은 ${bounds.attractionIds.sorted().joinToString(", ")} 다.",
            )
        }

        val raw = node.path("date").asText(null)
            ?: return Rejected("date 가 없다. YYYY-MM-DD 형식으로 준다.")
        val date = try {
            LocalDate.parse(raw)
        } catch (e: DateTimeParseException) {
            return Rejected("date '$raw' 를 읽을 수 없다. YYYY-MM-DD 형식으로 준다.")
        }

        val offset = abs(date.toEpochDay() - bounds.targetDate.toEpochDay())
        if (offset > MAX_DATE_OFFSET_DAYS) {
            return Rejected(
                "date '$raw' 는 코스 날짜(${bounds.targetDate})에서 $MAX_DATE_OFFSET_DAYS 일을 넘는다. " +
                    "그 범위 밖은 예보가 없다.",
            )
        }

        if (call.name == CONGESTION) return Congestion(attractionId, date)

        val radius = if (node.has("radiusKm")) node.path("radiusKm").asInt(-1) else DEFAULT_RADIUS_KM
        if (radius < MIN_RADIUS_KM || radius > MAX_RADIUS_KM) {
            return Rejected("radiusKm 은 $MIN_RADIUS_KM 이상 $MAX_RADIUS_KM 이하여야 한다.")
        }

        return Alternatives(attractionId, date, radius)
    }
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `./gradlew test --tests 'com.hermes.explain.CourseToolsTest'`
Expected: PASS (11개)

- [ ] **Step 5: 커밋**

```bash
git add server/src/main/kotlin/com/hermes/explain/CourseTools.kt \
        server/src/test/kotlin/com/hermes/explain/CourseToolsTest.kt
git commit -m "feat: define the two course tools and refuse arguments out of range"
```

---

### Task 3: 게이트의 실패 사유에 타입을 붙인다

**Files:**
- Modify: `server/src/main/kotlin/com/hermes/explain/AskStreamGate.kt`
- Modify: `server/src/main/kotlin/com/hermes/explain/CourseQuestionService.kt`
- Modify: `server/src/main/kotlin/com/hermes/explain/presentation/AskStreamController.kt`
- Test: `server/src/test/kotlin/com/hermes/explain/AskStreamGateTest.kt` (기존 파일 수정)

**Interfaces:**
- Produces: `enum class FailureCause { INVALID_CITATIONS, REFUSED, STREAM_FAILED, EMPTY, TRUNCATED, FACTS }`, `UnavailableEvent(val reason: String, val cause: FailureCause)`, `AbortedEvent(val reason: String, val cause: FailureCause)`, `AskStreamGate.fail(reason: String, cause: FailureCause)`

수리 루프가 "인용이 틀려서 실패했는가"를 알아야 한다. **문자열로 판별하지 않는다** — 이 저장소는 이미 문자열 분류로 데인 적이 있다.

- [ ] **Step 1: 실패하는 테스트를 더한다**

`AskStreamGateTest.kt` 에 추가한다 (기존 테스트는 그대로 둔다):

```kotlin
    @Test
    fun `인용이 무효면 cause 가 INVALID_CITATIONS 다`() {
        val events = mutableListOf<AskStreamEvent>()
        val gate = AskStreamGate(validatorRejecting(), events::add)

        gate.accept(CitationsClosed(listOf("concepts/nope.md")))

        val unavailable = events.filterIsInstance<UnavailableEvent>().single()
        assertThat(unavailable.cause).isEqualTo(FailureCause.INVALID_CITATIONS)
    }

    @Test
    fun `본문이 비면 cause 가 EMPTY 다`() {
        val events = mutableListOf<AskStreamEvent>()
        val gate = AskStreamGate(validatorAccepting(), events::add)

        gate.accept(CitationsClosed(listOf("concepts/a.md")))
        gate.finish(parseComplete = true)

        val unavailable = events.filterIsInstance<UnavailableEvent>().single()
        assertThat(unavailable.cause).isEqualTo(FailureCause.EMPTY)
    }

    @Test
    fun `잘린 응답은 cause 가 TRUNCATED 다`() {
        val events = mutableListOf<AskStreamEvent>()
        val gate = AskStreamGate(validatorAccepting(), events::add)

        gate.accept(CitationsClosed(listOf("concepts/a.md")))
        gate.accept(BodyText("일부"))
        gate.finish(parseComplete = false)

        val aborted = events.filterIsInstance<AbortedEvent>().single()
        assertThat(aborted.cause).isEqualTo(FailureCause.TRUNCATED)
    }
```

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests 'com.hermes.explain.AskStreamGateTest'`
Expected: 컴파일 실패 — `Unresolved reference: FailureCause`

- [ ] **Step 3: `AskStreamGate.kt` 를 고친다**

`UnavailableEvent`/`AbortedEvent` 선언을 이렇게 바꾼다:

```kotlin
/**
 * 왜 실패했는가. 수리 루프가 "인용이 틀려서 실패했는가" 를 알아야 하는데, 그 판별을
 * 사유 문자열로 하면 문구를 다듬는 순간 조용히 깨진다. 이 저장소는 하네스가 문자열로
 * 분류하다 한 번 데인 적이 있다.
 */
enum class FailureCause { INVALID_CITATIONS, REFUSED, STREAM_FAILED, EMPTY, TRUNCATED, FACTS }

/** 본문을 하나도 보내기 전의 실패. 이것이 오면 그 전에 DeltaEvent 는 0개다. */
data class UnavailableEvent(val reason: String, val cause: FailureCause) : AskStreamEvent

/** 본문을 보내기 시작한 뒤의 실패. 앞의 본문은 검증됐지만 문장이 미완이다. */
data class AbortedEvent(val reason: String, val cause: FailureCause) : AskStreamEvent
```

`fail` 과 `finish` 를 이렇게 바꾼다:

```kotlin
    fun finish(parseComplete: Boolean) {
        if (closed) return
        if (!parseComplete || !validated) {
            fail("truncated response", FailureCause.TRUNCATED)
            return
        }
        if (deltas == 0) {
            fail("empty answer", FailureCause.EMPTY)
            return
        }
        closed = true
        emit(DoneEvent)
    }

    fun fail(reason: String, cause: FailureCause) {
        if (closed) return
        closed = true
        held.clear()
        emit(if (deltas == 0) UnavailableEvent(reason, cause) else AbortedEvent(reason, cause))
    }
```

`accept` 의 `Invalid` 분기:

```kotlin
                is Invalid -> fail(invalidCitationReason(result), FailureCause.INVALID_CITATIONS)
```

- [ ] **Step 4: 부르는 쪽 둘을 맞춘다**

`CourseQuestionService.askStream` 의 `when (end)` 블록:

```kotlin
        when (end) {
            is StreamCompleted -> gate.finish(parser.complete)
            is StreamRefused -> gate.fail(refusalReason(end.category), FailureCause.REFUSED)
            is StreamFailed -> gate.fail(end.reason, FailureCause.STREAM_FAILED)
        }
```

`AskStreamController.run` 의 사실 조회 실패 분기는 이벤트를 직접 만들지 않고 그대로 두되, 로그 문구는 유지한다. 컨트롤러가 `UnavailableEvent`/`AbortedEvent` 를 **생성하지 않고 수신만** 하므로 다른 변경은 없다.

- [ ] **Step 5: 통과를 확인한다**

Run: `./gradlew test`
Expected: PASS. 기존 게이트 테스트 전부 + 새 3개.

- [ ] **Step 6: 커밋**

```bash
git add server/src/main/kotlin/com/hermes/explain/AskStreamGate.kt \
        server/src/main/kotlin/com/hermes/explain/CourseQuestionService.kt \
        server/src/test/kotlin/com/hermes/explain/AskStreamGateTest.kt
git commit -m "refactor: give stream failures a typed cause instead of a string"
```

---

### Task 4: 어댑터가 `ChatModel` 을 직접 불러 실행되지 않은 도구 호출을 받는다

**Files:**
- Modify: `server/src/main/kotlin/com/hermes/llm/SpringAiExplanationProvider.kt`
- Modify: `server/src/main/kotlin/com/hermes/shared/config/LlmSelection.kt`
- Test: `server/src/test/kotlin/com/hermes/llm/SpringAiConverseTest.kt`

**Interfaces:**
- Consumes: `Turn`, `ToolSpec`, `AgentStep` (Task 1)
- Produces: `SpringAiExplanationProvider(name: String, chatModel: ChatModel)` — 생성자 인자가 `ChatClient` 에서 `ChatModel` 로 바뀐다

**왜 `ChatClient` 를 우회하는가** (스펙에 근거가 있다): `OpenAiChatModel` 과 `AnthropicChatModel` 은 `resolveToolDefinitions` 만 부르고 `executeToolCalls` 를 **안 부른다**. 실행은 `ToolCallingAdvisor` 에 있고, `DefaultChatClientBuilder` 는 그 어드바이저를 **항상** 하나 만들어 단다. 그래서 `converse()` 만 모델을 직접 부른다. `explain()`/`stream()` 은 지금처럼 `ChatClient` 를 쓴다 — 기존 경로의 요청 바이트를 건드리지 않기 위해서다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`server/src/test/kotlin/com/hermes/llm/SpringAiConverseTest.kt`:

```kotlin
package com.hermes.llm

import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test
import org.springframework.ai.chat.messages.AssistantMessage
import org.springframework.ai.chat.model.ChatResponse
import org.springframework.ai.chat.model.Generation

class SpringAiConverseTest {

    private fun responseWithToolCall(id: String, name: String, args: String): ChatResponse {
        val message = AssistantMessage.builder()
            .content("")
            .toolCalls(listOf(AssistantMessage.ToolCall(id, "function", name, args)))
            .build()
        return ChatResponse(listOf(Generation(message)))
    }

    @Test
    fun `도구 호출이 담긴 응답은 ToolRequested 로 매핑된다`() {
        val step = SpringAiExplanationProvider.toAgentStep(
            responseWithToolCall("call-1", "congestion", """{"attractionId":11}"""),
        )

        assertThat(step).isInstanceOf(ToolRequested::class.java)
        val requested = step as ToolRequested
        assertThat(requested.calls).hasSize(1)
        assertThat(requested.calls[0].id).isEqualTo("call-1")
        assertThat(requested.calls[0].name).isEqualTo("congestion")
        assertThat(requested.calls[0].argumentsJson).isEqualTo("""{"attractionId":11}""")
    }

    @Test
    fun `도구 호출이 없으면 ToolRequested 가 아니다`() {
        val message = AssistantMessage.builder().content("본문").build()
        val step = SpringAiExplanationProvider.toAgentStep(ChatResponse(listOf(Generation(message))))

        assertThat(step).isNotInstanceOf(ToolRequested::class.java)
    }

    @Test
    fun `도구 콜백은 우리 경로에서 실행되면 안 되므로 부르면 터진다`() {
        val callback = SpringAiExplanationProvider.neverExecutedCallback(
            ToolSpec("congestion", "혼잡도", "{}"),
        )

        val thrown = runCatching { callback.call("{}") }.exceptionOrNull()

        assertThat(thrown).isInstanceOf(IllegalStateException::class.java)
        assertThat(thrown!!.message).contains("AgentLoop")
    }

    @Test
    fun `콜백은 ToolSpec 의 이름과 스키마를 그대로 정의에 싣는다`() {
        val callback = SpringAiExplanationProvider.neverExecutedCallback(
            ToolSpec("alternatives", "대안", """{"type":"object"}"""),
        )

        assertThat(callback.toolDefinition.name().isEqualTo("alternatives"))
        assertThat(callback.toolDefinition.description().isEqualTo("대안"))
        assertThat(callback.toolDefinition.inputSchema().isEqualTo("""{"type":"object"}"""))
    }
}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests 'com.hermes.llm.SpringAiConverseTest'`
Expected: 컴파일 실패 — `Unresolved reference: toAgentStep`

- [ ] **Step 3: 어댑터를 고친다**

`SpringAiExplanationProvider` 의 생성자와 필드를 바꾼다:

```kotlin
class SpringAiExplanationProvider(
    override val name: String,
    private val chatModel: ChatModel,
) : ExplanationProvider {

    // explain()/stream() 은 지금까지와 똑같이 ChatClient 를 쓴다. 기존 경로의 요청
    // 바이트를 건드리지 않기 위해서다 — ChatClient.create(model) 가 오늘 쓰이는 것과
    // 같은 조립이다.
    private val chatClient: ChatClient = ChatClient.create(chatModel)
```

`converse()` 를 추가한다:

```kotlin
    /**
     * 도구를 실을 수 있는 대화. **ChatClient 를 우회하고 ChatModel 을 직접 부른다.**
     *
     * Spring AI 2.0.1 에서 도구를 정의해 보내는 일과 실행하는 일이 다른 계층에 있다.
     * `OpenAiChatModel`/`AnthropicChatModel` 은 `resolveToolDefinitions` 만 부르고
     * `executeToolCalls` 는 부르지 않는다(설치된 jar 를 뜯어 확인). 실행은
     * `ToolCallingAdvisor` 가 하고, `DefaultChatClientBuilder` 는 그 어드바이저를
     * 항상 하나 만들어 단다. 그래서 ChatClient 를 타면 도구가 우리 모르게 실행된다.
     *
     * 도구가 비어 있으면 옵션을 얹지 않는다 — 요청 바이트가 기존 stream() 과 같아야
     * 프롬프트 캐시 접두사가 갈라지지 않는다.
     */
    override fun converse(
        systemText: String,
        turns: List<Turn>,
        tools: List<ToolSpec>,
        onChunk: (String) -> Unit,
    ): AgentStep = try {
        val prompt = if (tools.isEmpty()) {
            Prompt(toMessages(systemText, turns))
        } else {
            Prompt(
                toMessages(systemText, turns),
                ToolCallingChatOptions.builder()
                    .toolCallbacks(tools.map { neverExecutedCallback(it) })
                    .build(),
            )
        }

        var last: ChatResponse? = null
        var refused = false
        var toolStep: ToolRequested? = null
        var sawBody = false

        chatModel.stream(prompt)
            .doOnNext { response ->
                last = response
                val generation = response.result
                if (generation != null && isRefusal(generation)) refused = true

                // 본문이 이미 나가기 시작했으면 그 턴은 최종 답이다. 같은 턴의 도구
                // 호출은 무시한다 — 나간 본문은 게이트가 인용을 검증한 것이고, 여기서
                // 끊으면 사용자가 읽던 문장이 사라진다.
                if (!sawBody && toolStep == null) {
                    toolStep = toAgentStep(response) as? ToolRequested
                }

                val text = generation?.output?.text
                if (!text.isNullOrEmpty()) {
                    // 도구 호출로 이미 갈렸으면 본문을 내보내지 않는다 — ToolRequested
                    // 계약이 "onChunk 가 한 번도 안 불렸다" 이기 때문이다.
                    if (toolStep == null) {
                        sawBody = true
                        onChunk(text)
                    }
                }
            }
            .blockLast()

        toolStep?.let { return@try it }

        when {
            refused -> Spoke(StreamRefused(category = null))
            else -> Spoke(StreamCompleted(last?.let { usageOf(it) } ?: ProviderUsage(0, 0, 0, 0)))
        }
    } catch (e: Exception) {
        log.warn("$name converse failed", e)
        Spoke(StreamFailed("${e::class.simpleName}: ${e.message}"))
    }

    private fun toMessages(systemText: String, turns: List<Turn>): List<Message> =
        buildList {
            add(SystemMessage(systemText))
            turns.forEach { turn ->
                when (turn) {
                    is UserTurn -> add(UserMessage(turn.text))
                    is ToolCallTurn -> add(
                        AssistantMessage.builder()
                            .content("")
                            .toolCalls(
                                turn.calls.map {
                                    AssistantMessage.ToolCall(it.id, "function", it.name, it.argumentsJson)
                                },
                            )
                            .build(),
                    )
                    is ToolResultTurn -> add(
                        ToolResponseMessage(
                            turn.results.map { ToolResponseMessage.ToolResponse(it.id, "", it.contentJson) },
                        ),
                    )
                }
            }
        }
```

companion 에 둘을 추가한다:

```kotlin
        /**
         * 응답에 실행되지 않은 도구 호출이 담겨 있으면 ToolRequested 로, 아니면 null 을
         * 뜻하는 Spoke 자리표시자를 낸다. 순수 함수라 손으로 조립한 ChatResponse 로
         * 직접 테스트한다.
         */
        fun toAgentStep(response: ChatResponse): AgentStep {
            val calls = response.result?.output?.toolCalls.orEmpty()
            if (calls.isEmpty()) return Spoke(StreamCompleted(usageOf(response)))
            return ToolRequested(
                calls = calls.map { ToolCall(it.id(), it.name(), it.arguments()) },
                usage = usageOf(response),
            )
        }

        /**
         * 도구 정의만 싣기 위한 콜백. `resolveToolDefinitions` 가 콜백에서 정의를
         * 뽑으므로 콜백 자체는 있어야 하는데, **실행은 AgentLoop 가 한다.**
         * 여기가 불렸다면 ChatClient 를 타고 있다는 뜻이므로 조용히 넘어가지 않고
         * 터뜨린다.
         */
        fun neverExecutedCallback(spec: ToolSpec): ToolCallback = object : ToolCallback {
            override fun getToolDefinition(): ToolDefinition =
                DefaultToolDefinition.builder()
                    .name(spec.name)
                    .description(spec.description)
                    .inputSchema(spec.parametersSchema)
                    .build()

            override fun call(toolInput: String): String =
                error("도구는 AgentLoop 가 실행한다. 이 콜백이 불렸다면 ChatClient 경로를 탄 것이다.")

            override fun call(toolInput: String, toolContext: ToolContext?): String = call(toolInput)
        }
```

필요한 import 를 더한다:

```kotlin
import org.springframework.ai.chat.messages.Message
import org.springframework.ai.chat.messages.ToolResponseMessage
import org.springframework.ai.chat.model.ChatModel
import org.springframework.ai.model.tool.ToolCallingChatOptions
import org.springframework.ai.chat.model.ToolContext
import org.springframework.ai.tool.ToolCallback
import org.springframework.ai.tool.definition.DefaultToolDefinition
import org.springframework.ai.tool.definition.ToolDefinition
```

- [ ] **Step 4: `LlmSelection` 이 모델을 넘기게 한다**

세 분기 모두 `ChatClient.create(...)` 를 벗기고 모델을 그대로 넘긴다. anthropic 분기:

```kotlin
            "anthropic" -> SpringAiExplanationProvider(
                name = "anthropic",
                chatModel = AnthropicChatModel.builder()
                    .anthropicClient(anthropicClient(baseUrlOverride))
                    .options(ChatClients.anthropicOptions(model))
                    .build(),
            )
```

`springAiOpenAiCompatible` 안도 같은 모양으로 바꾼다 — `ChatClient.create(` 와 닫는 괄호만 걷어낸다. `ChatClient` import 가 더 이상 안 쓰이면 지운다.

- [ ] **Step 5: 통과를 확인한다**

Run: `./gradlew test`
Expected: PASS. 특히 `SpringAiRequestShapeTest` 와 `LlmSelectionTest` 의 캡처 테스트가 그대로 통과해야 한다 — 기존 경로의 요청 바이트가 안 바뀌었다는 뜻이다.

- [ ] **Step 6: 커밋**

```bash
git add server/src/main/kotlin/com/hermes/llm/SpringAiExplanationProvider.kt \
        server/src/main/kotlin/com/hermes/shared/config/LlmSelection.kt \
        server/src/test/kotlin/com/hermes/llm/SpringAiConverseTest.kt
git commit -m "feat: return unexecuted tool calls by calling the chat model directly"
```

---

### Task 5: 도구가 실린 요청 본문을 루프백으로 고정한다

**Files:**
- Modify: `server/src/test/kotlin/com/hermes/llm/CapturingEndpoint.kt`
- Test: `server/src/test/kotlin/com/hermes/llm/ConverseRequestShapeTest.kt`

**Interfaces:**
- Consumes: `CapturingEndpoint` (기존), `LlmSelection.provider(...)` 의 `baseUrlOverride`
- Produces: 없음 (테스트 전용)

키도 외부 네트워크도 없이, 나가는 JSON 바이트를 직접 본다. 이 저장소가 이미 쓰는 방식이다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`server/src/test/kotlin/com/hermes/llm/ConverseRequestShapeTest.kt`:

```kotlin
package com.hermes.llm

import com.fasterxml.jackson.databind.ObjectMapper
import com.hermes.shared.config.LlmSelection
import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test

class ConverseRequestShapeTest {

    private val mapper = ObjectMapper()

    private fun capture(tools: List<ToolSpec>): com.fasterxml.jackson.databind.JsonNode {
        CapturingEndpoint().use { endpoint ->
            val provider = LlmSelection.provider(
                name = "openai",
                model = "gpt-4o",
                env = { "test-key" },
                baseUrlOverride = endpoint.baseUrl,
            )
            runCatching {
                provider.converse("SYS", listOf(UserTurn("질문")), tools) {}
            }
            return mapper.readTree(endpoint.lastBody())
        }
    }

    @Test
    fun `도구를 주면 요청에 tools 가 실린다`() {
        val body = capture(com.hermes.explain.CourseTools.specs())

        val names = body.path("tools").map { it.at("/function/name").asText() }
        assertThat("alternatives").isEqualTo(listOf("congestion"), names)
    }

    @Test
    fun `도구를 안 주면 tools 필드 자체가 없다`() {
        val body = capture(emptyList())

        assertThat(body.path("tools").isMissingNode || body.path("tools").isEmpty).isTrue()
    }

    @Test
    fun `도구를 실어도 system 블록은 번들 원문 그대로다`() {
        val body = capture(com.hermes.explain.CourseTools.specs())

        val system = body.path("messages").first { it.path("role").asText() == "system" }
        assertThat(system.path("content").isEqualTo("SYS").asText())
    }

    @Test
    fun `스트리밍으로 나간다`() {
        val body = capture(com.hermes.explain.CourseTools.specs())

        assertThat(body.path("stream").asBoolean(false)).isTrue()
    }

    @Test
    fun `도구가 없는 요청은 기존 stream 경로와 바이트가 같다`() {
        val withoutTools = capture(emptyList()).toString()

        CapturingEndpoint().use { endpoint ->
            val provider = LlmSelection.provider("openai", "gpt-4o", { "test-key" }, endpoint.baseUrl)
            runCatching { provider.stream("SYS", "질문") {} }
            val viaStream = mapper.readTree(endpoint.lastBody()).toString()
            assertThat(withoutTools).isEqualTo(viaStream)
        }
    }

    @Test
    fun `도구 콜백은 캡처 과정에서 한 번도 실행되지 않는다`() {
        // 실행됐다면 neverExecutedCallback 이 IllegalStateException 을 던져
        // converse 가 Spoke(StreamFailed) 로 접었을 것이다. 요청이 나갔다는 사실
        // 자체가 실행되지 않았다는 증거이므로, 여기서는 본문에 tools 가 실렸고
        // 예외 메시지가 응답 경로로 새지 않았음을 본다.
        val body = capture(com.hermes.explain.CourseTools.specs())
        assertThat(body.toString().contains("AgentLoop")).isFalse()
    }
}
```

- [ ] **Step 2: `CapturingEndpoint` 에 마지막 본문 접근자가 있는지 확인한다**

Run: `grep -n "fun lastBody\|fun bodies\|baseUrl" server/src/test/kotlin/com/hermes/llm/CapturingEndpoint.kt`

`lastBody()` 가 없으면 추가한다:

```kotlin
    /** 마지막으로 받은 요청 본문. 없으면 즉시 실패한다 — 빈 문자열을 돌려주면
     *  "요청이 안 나갔다" 가 "본문이 비었다" 로 조용히 둔갑한다. */
    fun lastBody(): String = bodies.lastOrNull() ?: error("no request was captured")
```

- [ ] **Step 3: 통과를 확인한다**

Run: `./gradlew test --tests 'com.hermes.llm.ConverseRequestShapeTest'`
Expected: PASS (6개)

- [ ] **Step 4: 커밋**

```bash
git add server/src/test/kotlin/com/hermes/llm/CapturingEndpoint.kt \
        server/src/test/kotlin/com/hermes/llm/ConverseRequestShapeTest.kt
git commit -m "test: pin the tool payload and that a tool-free request is unchanged"
```

---

### Task 6: 도구 결과를 초기 facts 와 합친다

**Files:**
- Create: `server/src/main/kotlin/com/hermes/explain/ToolFacts.kt`
- Test: `server/src/test/kotlin/com/hermes/explain/ToolFactsTest.kt`

**Interfaces:**
- Consumes: 없음 (순수)
- Produces: `class ToolFacts(initialJson: String)`, `ToolFacts.add(name: String, argsSummary: String, resultJson: String)`, `ToolFacts.unionJson(): String`, `ToolFacts.promptText(): String`

하네스가 주장을 대조할 대상이고, 동시에 도구 결과를 모델에 돌려줄 텍스트다. 둘이 같은 원본에서 나와야 어긋나지 않는다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`server/src/test/kotlin/com/hermes/explain/ToolFactsTest.kt`:

```kotlin
package com.hermes.explain

import com.fasterxml.jackson.databind.ObjectMapper
import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test

class ToolFactsTest {

    private val mapper = ObjectMapper()

    @Test
    fun `도구가 안 돌면 합집합은 초기 facts 와 같다`() {
        val facts = ToolFacts("""{"courseUuid":"abc"}""")

        assertEquals(
            mapper.readTree("""{"courseUuid":"abc"}"""),
            mapper.readTree(facts.unionJson()),
        )
    }

    @Test
    fun `도구 결과는 lookups 배열에 쌓인다`() {
        val facts = ToolFacts("""{"courseUuid":"abc"}""")
        facts.add("congestion", "attractionId=11 date=2026-10-03", """{"grade":"NORMAL"}""")

        val union = mapper.readTree(facts.unionJson())
        assertThat(union.path("courseUuid").isEqualTo("abc").asText())
        assertThat(union.path("lookups").isEqualTo(1).size())
        assertThat(union.at("/lookups/0/tool").isEqualTo("congestion").asText())
        assertThat(union.at("/lookups/0/result/grade").isEqualTo("NORMAL").asText())
    }

    @Test
    fun `여러 번 부르면 순서대로 쌓인다`() {
        val facts = ToolFacts("""{"courseUuid":"abc"}""")
        facts.add("congestion", "a", """{"n":1}""")
        facts.add("alternatives", "b", """{"n":2}""")

        val union = mapper.readTree(facts.unionJson())
        assertThat("alternatives").isEqualTo(listOf("congestion"), union.path("lookups").map { it.path("tool").asText() })
    }

    @Test
    fun `초기 facts 는 덮어써지지 않는다`() {
        val facts = ToolFacts("""{"courseUuid":"abc","lookups":"원래값"}""")
        facts.add("congestion", "a", """{"n":1}""")

        // 이름이 충돌하면 도구 결과가 아니라 초기 facts 가 이긴다 — 한적이 준 사실이
        // 모델이 유도한 조회보다 우선한다.
        val union = mapper.readTree(facts.unionJson())
        assertThat(union.path("lookups").isEqualTo("원래값").asText())
        assertThat(union.path("toolLookups").isEqualTo(1).size())
    }

    @Test
    fun `promptText 는 도구 결과를 사실이라고 이름 붙여 돌려준다`() {
        val facts = ToolFacts("""{"courseUuid":"abc"}""")
        facts.add("congestion", "attractionId=11 date=2026-10-03", """{"grade":"NORMAL"}""")

        val text = facts.promptText()
        assertThat(text.contains("congestion")).isTrue()
        assertThat(text.contains("attractionId=11")).isTrue()
        assertThat(text.contains("NORMAL")).isTrue()
    }

    @Test
    fun `도구가 안 돌면 promptText 는 비어 있다`() {
        assertThat(ToolFacts("""{"courseUuid":"abc"}""").isEqualTo("").promptText())
    }
}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests 'com.hermes.explain.ToolFactsTest'`
Expected: 컴파일 실패 — `Unresolved reference: ToolFacts`

- [ ] **Step 3: 구현한다**

`server/src/main/kotlin/com/hermes/explain/ToolFacts.kt`:

```kotlin
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
```

- [ ] **Step 4: 통과를 확인한다**

Run: `./gradlew test --tests 'com.hermes.explain.ToolFactsTest'`
Expected: PASS (6개)

- [ ] **Step 5: 커밋**

```bash
git add server/src/main/kotlin/com/hermes/explain/ToolFacts.kt \
        server/src/test/kotlin/com/hermes/explain/ToolFactsTest.kt
git commit -m "feat: union the initial facts with what the tools fetched"
```

---

### Task 7: 루프·예산·마감·수리

**Files:**
- Create: `server/src/main/kotlin/com/hermes/explain/AgentLoop.kt`
- Test: `server/src/test/kotlin/com/hermes/explain/AgentLoopTest.kt`

**Interfaces:**
- Consumes: `ExplanationProvider.converse` (Task 1), `CourseTools` (Task 2), `FailureCause`/`AskStreamGate` (Task 3), `ToolFacts` (Task 6)
- Produces:
  - `class AgentLoop(provider, validator, toolRunner, clock, maxToolRounds = 2, deadlineMs = 60_000L)`
  - `fun interface ToolRunner { fun run(args: ToolArgs): String }`
  - `AgentLoop.run(systemText: String, baseUserText: String, bounds: CourseBounds, facts: ToolFacts, emit: (AskStreamEvent) -> Unit)`
  - `data class LookingEvent(val what: String) : AskStreamEvent` (`AskStreamGate.kt` 의 sealed 계층에 추가)

- [ ] **Step 1: `LookingEvent` 를 sealed 계층에 더한다**

`AskStreamGate.kt` 의 이벤트 선언 옆에 추가한다:

```kotlin
/** 도구를 실행하기 직전. 게이트가 내지 않는다 — AgentLoop 가 낸다. */
data class LookingEvent(val what: String) : AskStreamEvent
```

- [ ] **Step 2: 실패하는 테스트를 쓴다**

`server/src/test/kotlin/com/hermes/explain/AgentLoopTest.kt`:

```kotlin
package com.hermes.explain

import com.hermes.context.Bundle
import com.hermes.context.BundleDocument
import com.hermes.context.CitationValidator
import com.hermes.llm.AgentStep
import com.hermes.llm.ExplanationProvider
import com.hermes.llm.ProviderResult
import com.hermes.llm.ProviderUsage
import com.hermes.llm.Spoke
import com.hermes.llm.StreamCompleted
import com.hermes.llm.StreamRefused
import com.hermes.llm.ToolCall
import com.hermes.llm.ToolRequested
import com.hermes.llm.ToolSpec
import com.hermes.llm.Turn
import java.time.Clock
import java.time.Duration
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset
import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test

private val BUNDLE = Bundle(
    documents = listOf(BundleDocument("concepts/a.md", "내용")),
    raw = "----- FILE: concepts/a.md -----\n내용",
)

/** 미리 짠 응답을 순서대로 낸다. 각 호출의 tools 인자를 기록한다. */
private class ScriptedProvider(private val script: List<(onChunk: (String) -> Unit) -> AgentStep>) :
    ExplanationProvider {
    override val name = "scripted"
    val toolsPerCall = mutableListOf<List<String>>()
    val turnsPerCall = mutableListOf<List<Turn>>()
    var calls = 0

    override fun explain(systemText: String, userText: String): ProviderResult =
        error("AgentLoop 은 converse 만 쓴다")

    override fun converse(
        systemText: String,
        turns: List<Turn>,
        tools: List<ToolSpec>,
        onChunk: (String) -> Unit,
    ): AgentStep {
        toolsPerCall.add(tools.map { it.name })
        turnsPerCall.add(turns)
        return script[calls++](onChunk)
    }
}

private fun answering(citations: String, body: String): (((String) -> Unit) -> AgentStep) = { onChunk ->
    onChunk("""{"citations":[$citations],"explanation":"$body"}""")
    Spoke(StreamCompleted(ProviderUsage(0, 0, 0, 0)))
}

private fun requestingTool(name: String, args: String): (((String) -> Unit) -> AgentStep) = {
    ToolRequested(listOf(ToolCall("call-1", name, args)), ProviderUsage(0, 0, 0, 0))
}

class AgentLoopTest {

    private val bounds = CourseBounds(setOf(11L), LocalDate.of(2026, 10, 1))
    private val validator = CitationValidator(BUNDLE)
    private val fixedClock = Clock.fixed(Instant.parse("2026-10-01T00:00:00Z"), ZoneOffset.UTC)

    private fun loop(
        provider: ExplanationProvider,
        runner: ToolRunner = ToolRunner { """{"grade":"NORMAL"}""" },
        clock: Clock = fixedClock,
    ) = AgentLoop(provider, validator, runner, clock)

    private fun collect(
        provider: ScriptedProvider,
        runner: ToolRunner = ToolRunner { """{"grade":"NORMAL"}""" },
        clock: Clock = fixedClock,
    ): List<AskStreamEvent> {
        val events = mutableListOf<AskStreamEvent>()
        loop(provider, runner, clock).run(
            systemText = BUNDLE.raw,
            baseUserText = "질문",
            bounds = bounds,
            facts = ToolFacts("""{"courseUuid":"abc"}"""),
            emit = events::add,
        )
        return events
    }

    @Test
    fun `도구를 안 부르면 모델 호출은 한 번이다`() {
        val provider = ScriptedProvider(listOf(answering(""""concepts/a.md"""", "답")))

        val events = collect(provider)

        assertThat(provider.calls).isEqualTo(1)
        assertThat(events.none { it is LookingEvent }).isTrue()
        assertThat(events.last() is DoneEvent).isTrue()
    }

    @Test
    fun `도구를 부르면 looking 뒤에 답이 흐른다`() {
        val provider = ScriptedProvider(
            listOf(
                requestingTool("congestion", """{"attractionId":11,"date":"2026-10-03"}"""),
                answering(""""concepts/a.md"""", "답"),
            ),
        )

        val events = collect(provider)

        assertThat(events.first().isEqualTo(LookingEvent("congestion")))
        assertThat(events.any { it is CitationsEvent }).isTrue()
        assertThat(events.last() is DoneEvent).isTrue()
    }

    @Test
    fun `계속 도구만 요청하면 세 번째 호출에는 도구가 실리지 않는다`() {
        val provider = ScriptedProvider(
            listOf(
                requestingTool("congestion", """{"attractionId":11,"date":"2026-10-02"}"""),
                requestingTool("congestion", """{"attractionId":11,"date":"2026-10-03"}"""),
                answering(""""concepts/a.md"""", "답"),
            ),
        )

        collect(provider)

        assertThat(provider.calls).isEqualTo(3)
        assertThat(provider.toolsPerCall[0].isNotEmpty()).isTrue()
        assertThat(provider.toolsPerCall[1].isNotEmpty()).isTrue()
        assertThat(provider.toolsPerCall[2].isEmpty()).isTrue()
    }

    @Test
    fun `인자가 범위를 벗어나면 도구를 실행하지 않고 거부 사유를 되먹인다`() {
        var ran = false
        val provider = ScriptedProvider(
            listOf(
                requestingTool("congestion", """{"attractionId":99,"date":"2026-10-02"}"""),
                answering(""""concepts/a.md"""", "답"),
            ),
        )

        val events = collect(provider, runner = ToolRunner { ran = true; "{}" })

        assertThat(!ran).isTrue()
        // 실행하지 않았으므로 조회 중이라고 말하지도 않는다.
        assertThat(events.none { it is LookingEvent }).isTrue()
        assertThat(events.last() is DoneEvent).isTrue()
    }

    @Test
    fun `1차 인용 무효 2차 유효면 사용자에게 unavailable 이 가지 않는다`() {
        val provider = ScriptedProvider(
            listOf(
                answering(""""concepts/nope.md"""", "틀린 답"),
                answering(""""concepts/a.md"""", "고친 답"),
            ),
        )

        val events = collect(provider)

        assertThat(events.none { it is UnavailableEvent }).isTrue()
        assertThat(events.last() is DoneEvent).isTrue()
        assertThat(provider.calls).isEqualTo(2)
    }

    @Test
    fun `수리 호출에는 도구가 실리지 않는다`() {
        val provider = ScriptedProvider(
            listOf(
                answering(""""concepts/nope.md"""", "틀린 답"),
                answering(""""concepts/a.md"""", "고친 답"),
            ),
        )

        collect(provider)

        assertThat(provider.toolsPerCall[1].isEmpty()).isTrue()
    }

    @Test
    fun `두 번 다 인용이 무효면 진짜 unavailable 이다`() {
        val provider = ScriptedProvider(
            listOf(
                answering(""""concepts/nope.md"""", "틀린 답"),
                answering(""""concepts/also-nope.md"""", "또 틀린 답"),
            ),
        )

        val events = collect(provider)

        val unavailable = events.filterIsInstance<UnavailableEvent>().single()
        assertThat(unavailable.cause).isEqualTo(FailureCause.INVALID_CITATIONS)
        assertThat(provider.calls).isEqualTo(2)
    }

    @Test
    fun `거절은 수리하지 않는다`() {
        val provider = ScriptedProvider(listOf({ Spoke(StreamRefused("safety")) }))

        val events = collect(provider)

        assertThat(provider.calls).isEqualTo(1)
        assertThat(events.filterIsInstance<UnavailableEvent>().isEqualTo(FailureCause.REFUSED).single().cause)
    }

    @Test
    fun `마감을 넘기면 도구 없는 마지막 호출로 넘어간다`() {
        var now = Instant.parse("2026-10-01T00:00:00Z")
        val movingClock = object : Clock() {
            override fun getZone() = ZoneOffset.UTC
            override fun withZone(zone: java.time.ZoneId?) = this
            override fun instant(): Instant = now
        }
        val provider = ScriptedProvider(
            listOf(
                { now = now.plus(Duration.ofSeconds(61)); requestingTool("congestion", """{"attractionId":11,"date":"2026-10-02"}""")(it) },
                answering(""""concepts/a.md"""", "답"),
            ),
        )

        collect(provider, clock = movingClock)

        assertThat(provider.calls).isEqualTo(2)
        assertThat(provider.toolsPerCall[1].isEmpty()).isTrue()
    }

    @Test
    fun `도구 결과가 다음 호출의 대화에 실린다`() {
        val provider = ScriptedProvider(
            listOf(
                requestingTool("congestion", """{"attractionId":11,"date":"2026-10-03"}"""),
                answering(""""concepts/a.md"""", "답"),
            ),
        )

        collect(provider)

        val secondCallTurns = provider.turnsPerCall[1]
        assertThat(secondCallTurns[1]).isInstanceOf(com.hermes.llm.ToolCallTurn::class.java)
        assertThat(secondCallTurns[2]).isInstanceOf(com.hermes.llm.ToolResultTurn::class.java)
    }
}
```

- [ ] **Step 3: 실패를 확인한다**

Run: `./gradlew test --tests 'com.hermes.explain.AgentLoopTest'`
Expected: 컴파일 실패 — `Unresolved reference: AgentLoop`

- [ ] **Step 4: 구현한다**

`server/src/main/kotlin/com/hermes/explain/AgentLoop.kt`:

```kotlin
package com.hermes.explain

import com.hermes.context.CitationValidator
import com.hermes.llm.AskStreamParser
import com.hermes.llm.Spoke
import com.hermes.llm.StreamCompleted
import com.hermes.llm.StreamFailed
import com.hermes.llm.StreamRefused
import com.hermes.llm.ToolCallTurn
import com.hermes.llm.ToolRequested
import com.hermes.llm.ToolResult
import com.hermes.llm.ToolResultTurn
import com.hermes.llm.Turn
import com.hermes.llm.UserTurn
import java.time.Clock
import org.slf4j.LoggerFactory

/** 검증을 통과한 인자로 실제 한적을 부른다. 결과 JSON 을 그대로 돌려준다. */
fun interface ToolRunner {
    fun run(args: ToolArgs): String
}

/**
 * 도구 루프. **안전 판단은 하지 않는다** — 그것은 [AskStreamGate] 가 한다.
 * 여기가 정하는 것은 몇 번 더 물을 것인가, 무엇을 실행해도 되는가, 언제 포기하는가다.
 *
 * 예산이 떨어지면 실패가 아니라 "가진 걸로 답하라" 다. 마지막 호출은 도구를 **아예 빼고**
 * 보내므로 모델이 다시 부르는 것이 구조적으로 불가능하다.
 */
class AgentLoop(
    private val provider: com.hermes.llm.ExplanationProvider,
    private val validator: CitationValidator,
    private val toolRunner: ToolRunner,
    private val clock: Clock,
    private val maxToolRounds: Int = 2,
    private val deadlineMs: Long = 60_000L,
) {

    private val log = LoggerFactory.getLogger(AgentLoop::class.java)

    fun run(
        systemText: String,
        baseUserText: String,
        bounds: CourseBounds,
        facts: ToolFacts,
        emit: (AskStreamEvent) -> Unit,
    ) {
        val startedAt = clock.millis()
        val turns = mutableListOf<Turn>(UserTurn(baseUserText))

        var round = 0
        while (true) {
            val outOfBudget = round >= maxToolRounds || clock.millis() - startedAt > deadlineMs
            val tools = if (outOfBudget) emptyList() else CourseTools.specs()

            when (val outcome = attempt(systemText, turns, tools, bounds, facts, emit)) {
                is Continued -> {
                    turns.add(ToolCallTurn(outcome.calls))
                    turns.add(ToolResultTurn(outcome.results))
                    round++
                }
                is Finished -> return
                is NeedsRepair -> {
                    // 인용이 틀린 것은 사실이 모자라서가 아니라 경로를 잘못 적어서다.
                    // 수리 턴에는 도구를 싣지 않는다.
                    turns.add(UserTurn(repairText(outcome.reason)))
                    val repaired = attempt(systemText, turns, emptyList(), bounds, facts, emit)
                    if (repaired is NeedsRepair) {
                        emit(UnavailableEvent(repaired.reason, FailureCause.INVALID_CITATIONS))
                    }
                    return
                }
            }
        }
    }

    private sealed interface Attempt
    private data class Continued(
        val calls: List<com.hermes.llm.ToolCall>,
        val results: List<ToolResult>,
    ) : Attempt
    private data object Finished : Attempt
    private data class NeedsRepair(val reason: String) : Attempt

    private fun attempt(
        systemText: String,
        turns: List<Turn>,
        tools: List<com.hermes.llm.ToolSpec>,
        bounds: CourseBounds,
        facts: ToolFacts,
        emit: (AskStreamEvent) -> Unit,
    ): Attempt {
        val parser = AskStreamParser()
        // 게이트의 출력을 바로 흘리지 않고 한 번 거른다 — 인용 무효면 그 이벤트를
        // 삼키고 수리한다. 인용 무효일 때 delta 가 0개라는 게이트의 불변식 덕에
        // 이 시점에 사용자는 아직 한 글자도 못 봤다.
        var repairReason: String? = null
        val gate = AskStreamGate(validator) { event ->
            if (event is UnavailableEvent && event.cause == FailureCause.INVALID_CITATIONS) {
                repairReason = event.reason
            } else {
                emit(event)
            }
        }

        val step = provider.converse(systemText, turns, tools) { chunk ->
            parser.feed(chunk).forEach(gate::accept)
        }

        if (step is ToolRequested) {
            val results = step.calls.map { call ->
                when (val args = CourseTools.parse(call, bounds)) {
                    // 거부는 실행하지 않는다. "조회 중" 이라고 말하지도 않고,
                    // facts 합집합에도 넣지 않는다 — 실행되지 않은 조회가 근거로
                    // 잡히면 안 된다.
                    is Rejected -> ToolResult(call.id, """{"rejected":${quote(args.reason)}}""")
                    else -> {
                        emit(LookingEvent(call.name))
                        val result = toolRunner.run(args)
                        facts.add(call.name, call.argumentsJson, result)
                        ToolResult(call.id, result)
                    }
                }
            }
            return Continued(step.calls, results)
        }

        when (val end = (step as Spoke).end) {
            is StreamCompleted -> gate.finish(parser.complete)
            is StreamRefused -> gate.fail(refusalReason(end.category), FailureCause.REFUSED)
            is StreamFailed -> gate.fail(end.reason, FailureCause.STREAM_FAILED)
        }

        return repairReason?.let { NeedsRepair(it) } ?: Finished
    }

    private fun repairText(reason: String): String =
        "직전 답의 인용이 유효하지 않다: $reason\n" +
            "system 블록의 `----- FILE: 경로 -----` 마커에 실제로 있는 경로만 citations 에 넣어 다시 답하라."

    private fun quote(text: String): String = MAPPER.writeValueAsString(text)

    private companion object {
        private val MAPPER = com.fasterxml.jackson.databind.ObjectMapper()
    }
}
```

- [ ] **Step 5: 통과를 확인한다**

Run: `./gradlew test --tests 'com.hermes.explain.AgentLoopTest'`
Expected: PASS (10개)

- [ ] **Step 6: 커밋**

```bash
git add server/src/main/kotlin/com/hermes/explain/AgentLoop.kt \
        server/src/main/kotlin/com/hermes/explain/AskStreamGate.kt \
        server/src/test/kotlin/com/hermes/explain/AgentLoopTest.kt
git commit -m "feat: loop over tools within a budget and repair bad citations once"
```

---

### Task 8: 서비스·컨트롤러·설정 배선

**Files:**
- Modify: `server/src/main/kotlin/com/hermes/explain/CourseQuestionService.kt`
- Modify: `server/src/main/kotlin/com/hermes/explain/presentation/AskStreamController.kt`
- Modify: `server/src/main/kotlin/com/hermes/shared/config/HermesConfig.kt`
- Modify: `server/src/main/kotlin/com/hermes/facts/FactsSource.kt`
- Test: `server/src/test/kotlin/com/hermes/explain/presentation/AskStreamControllerTest.kt` (기존 파일에 추가)

**Interfaces:**
- Consumes: `AgentLoop`, `ToolRunner`, `CourseBounds`, `ToolFacts`
- Produces: `FactsSource.boundsFor(courseUuid: String, courseJson: String): CourseBounds`, `CourseQuestionService.askStream(...)` 이 `AgentLoop` 를 탄다

- [ ] **Step 1: 실패하는 테스트를 더한다**

`AskStreamControllerTest.kt` 에 추가한다:

```kotlin
    @Test
    fun `looking 이벤트는 도구 이름만 싣는다`() {
        val events = sseFrom(
            provider = providerRequestingTool("congestion", """{"attractionId":11,"date":"2026-10-03"}"""),
        )

        val looking = events.single { it.startsWith("event:looking") }
        assertThat(looking.contains("congestion")).isTrue()
        assertThat(looking.contains("attractionId")).isFalse()
        assertThat(looking.contains("2026-10-03")).isFalse()
    }

    @Test
    fun `looking 이 온 뒤에도 unavailable 앞의 delta 는 0개다`() {
        val events = sseFrom(provider = providerRequestingToolThenInvalidCitations())

        val deltaIndexes = events.withIndex().filter { it.value.startsWith("event:delta") }.map { it.index }
        val unavailableIndex = events.indexOfFirst { it.startsWith("event:unavailable") }

        assertThat(unavailableIndex >= 0).isTrue()
        assertThat(deltaIndexes.none { it < unavailableIndex }).isTrue()
    }
```

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests 'com.hermes.explain.presentation.AskStreamControllerTest'`
Expected: FAIL — `looking` 이벤트가 나오지 않는다

- [ ] **Step 3: `FactsSource` 가 경계를 낼 수 있게 한다**

`FactsSource` 에 추가한다 (기존 `fetch` 는 그대로):

```kotlin
    /**
     * 이 코스에서 도구가 움직일 수 있는 범위. `fetch` 가 이미 파싱한 것을 다시
     * 파싱하지 않도록, 코스 JSON 을 받아 경계만 뽑는 순수 함수로 둔다.
     */
    fun boundsFor(course: JsonNode): CourseBounds {
        val ids = course.path("items").mapNotNull {
            it.path("attractionId").asLong(0L).takeIf { id -> id != 0L }
        }.toSet()
        val date = course.path("targetDate").asText(null)
            ?: throw HanjeokUnavailableException("course has no targetDate")
        return CourseBounds(attractionIds = ids, targetDate = LocalDate.parse(date))
    }
```

`fetch` 가 `BackendFacts` 와 함께 경계를 돌려주도록 반환 타입을 넓힌다:

```kotlin
data class FetchedFacts(val facts: BackendFacts, val bounds: CourseBounds)
```

`fetch` 는 그대로 두고 `fetchWithBounds(courseUuid): FetchedFacts` 를 새로 둔다 — 기존 호출자(`CourseExplainer`)를 건드리지 않는다.

- [ ] **Step 4: 서비스가 루프를 타게 한다**

`CourseQuestionService` 에 `AgentLoop` 를 주입하고 `askStream` 을 바꾼다:

```kotlin
    fun askStream(
        facts: BackendFacts,
        bounds: CourseBounds,
        question: String,
        history: List<QuestionTurn>,
        emit: (AskStreamEvent) -> Unit,
    ) {
        val toolFacts = ToolFacts(facts.json)
        loop.run(
            systemText = assembler.systemText,
            baseUserText = buildUserText(facts, question, history) + TOOL_GUIDANCE,
            bounds = bounds,
            facts = toolFacts,
            emit = emit,
        )
    }
```

`TOOL_GUIDANCE` 는 companion 상수로 둔다. **`system` 이 아니라 user 턴에 붙는다** — 캐시 접두사를 지키기 위해서다:

```kotlin
        private const val TOOL_GUIDANCE = """

## 도구
위 사실로 답할 수 있으면 도구를 부르지 말고 바로 답한다. 사실이 모자랄 때만 부른다.
부를 때는 **먼저 부르고 그다음에 답한다** — 답을 쓰다가 중간에 부르지 않는다.
"""
```

- [ ] **Step 5: 컨트롤러가 `looking` 을 내보내게 한다**

`AskStreamController.run` 의 `when (event)` 에 한 줄 더한다:

```kotlin
                is LookingEvent -> send(emitter, "looking", mapOf("what" to event.what))
```

그리고 사실 조회를 `fetchWithBounds` 로 바꾸고 `service.askStream(...)` 에 `bounds` 를 넘긴다.

- [ ] **Step 6: `HermesConfig` 에 빈을 더한다**

```kotlin
    @Bean
    fun toolRunner(client: HanjeokClient): ToolRunner = ToolRunner { args ->
        when (args) {
            is Congestion -> client.congestion(args.attractionId, args.date.toString()).toString()
            is Alternatives -> client.alternatives(args.attractionId, args.date.toString(), args.radiusKm).toString()
            is Rejected -> error("거부된 인자는 실행되지 않는다 — AgentLoop 이 먼저 갈라낸다")
        }
    }

    @Bean
    fun agentLoop(
        provider: ExplanationProvider,
        validator: CitationValidator,
        toolRunner: ToolRunner,
    ): AgentLoop = AgentLoop(provider, validator, toolRunner, Clock.systemUTC())
```

- [ ] **Step 7: 통과를 확인한다**

Run: `./gradlew test`
Expected: PASS 전부

- [ ] **Step 8: 커밋**

```bash
git add server/src/main/kotlin/com/hermes/explain/CourseQuestionService.kt \
        server/src/main/kotlin/com/hermes/explain/presentation/AskStreamController.kt \
        server/src/main/kotlin/com/hermes/shared/config/HermesConfig.kt \
        server/src/main/kotlin/com/hermes/facts/FactsSource.kt \
        server/src/test/kotlin/com/hermes/explain/presentation/AskStreamControllerTest.kt
git commit -m "feat: run follow-up questions through the tool loop"
```

---

### Task 9: 하네스가 합집합과 대조하게 한다

**Files:**
- Modify: `server/src/main/kotlin/com/hermes/harness/ForbiddenBehaviours.kt`
- Modify: `server/src/main/kotlin/com/hermes/harness/EvalMain.kt`
- Test: `server/src/test/kotlin/com/hermes/harness/ForbiddenBehavioursToolFactsTest.kt`

**Interfaces:**
- Consumes: `ToolFacts.unionJson()` (Task 6)
- Produces: `ForbiddenBehaviours.check(explanation, bundle, factsJson)` 의 `factsJson` 이 합집합이 된다

**왜:** 규칙이 초기 facts 와만 대조하면 **도구가 가져온 사실을 말할 때마다 근거 없는 주장으로 잡힌다.** 도구를 붙이는 순간 위반율이 치솟는데, 그것은 모델이 나빠진 것이 아니라 판정기가 못 따라간 것이다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`server/src/test/kotlin/com/hermes/harness/ForbiddenBehavioursToolFactsTest.kt`:

```kotlin
package com.hermes.harness

import com.hermes.context.Bundle
import com.hermes.context.BundleDocument
import com.hermes.explain.ToolFacts
import com.hermes.llm.Explanation
import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test

class ForbiddenBehavioursToolFactsTest {

    private val bundle = Bundle(
        documents = listOf(BundleDocument("concepts/a.md", "내용")),
        raw = "----- FILE: concepts/a.md -----\n내용",
    )

    @Test
    fun `도구가 가져온 장소는 지어낸 장소로 잡히지 않는다`() {
        val facts = ToolFacts("""{"courseUuid":"abc","items":[{"name":"경복궁"}]}""")
        facts.add("alternatives", "attractionId=11", """{"alternatives":[{"name":"창덕궁"}]}""")

        val violations = ForbiddenBehaviours.check(
            Explanation("창덕궁도 대안입니다.", listOf("concepts/a.md")),
            bundle,
            facts.unionJson(),
        )

        assertThat(violations.none { it.behaviour == Behaviour.INVENTED_PLACE }).isTrue()
    }

    @Test
    fun `도구를 안 돌린 경우 판정은 이전과 같다`() {
        val facts = ToolFacts("""{"courseUuid":"abc","items":[{"name":"경복궁"}]}""")

        val violations = ForbiddenBehaviours.check(
            Explanation("창덕궁도 대안입니다.", listOf("concepts/a.md")),
            bundle,
            facts.unionJson(),
        )

        assertThat(violations.any { it.behaviour == Behaviour.INVENTED_PLACE }).isTrue()
    }
}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests 'com.hermes.harness.ForbiddenBehavioursToolFactsTest'`
Expected: 첫 테스트 FAIL — 창덕궁이 지어낸 장소로 잡힌다

- [ ] **Step 3: 장소 수집을 합집합 전체로 넓힌다**

`ForbiddenBehaviours` 에서 facts 의 장소 이름을 모으는 부분이 `items` 만 보고 있다면, `lookups`/`toolLookups` 아래의 `result` 도 훑도록 바꾼다. 트리 전체에서 `name` 필드를 모으는 것이 가장 단순하고, 도구 결과의 모양이 늘어도 따라온다:

```kotlin
    /**
     * facts 트리 어디에 있든 `name` 을 전부 모은다. 도구가 가져온 사실도 여기 포함된다 —
     * 초기 facts 만 보면 도구가 조회한 장소가 전부 지어낸 것으로 잡힌다.
     */
    private fun knownNames(facts: JsonNode): Set<String> =
        facts.findValues("name").mapNotNull { it.asText(null) }.toSet()
```

- [ ] **Step 4: `EvalMain` 이 루프를 타게 한다**

하네스가 비스트리밍 `explain()` 만 부르면 **측정한 것과 배포한 것이 갈라진다.** `EvalMain` 에 실행 모드를 더해 이어 묻기 시나리오를 `AgentLoop` 로 돌리고, 끝에 도구 호출 횟수·예산 소진·수리 발동을 집계해 찍는다.

```kotlin
// 실행 끝에 찍는다. 유료 실행의 증거는 휘발되므로 파일로도 받아 둔다.
println("tool rounds: ${tally.toolRounds}, budget exhausted: ${tally.exhausted}, repairs: ${tally.repairs}/${tally.repairSucceeded}")
```

- [ ] **Step 5: 통과를 확인한다**

Run: `./gradlew test`
Expected: PASS 전부

- [ ] **Step 6: 커밋**

```bash
git add server/src/main/kotlin/com/hermes/harness/ForbiddenBehaviours.kt \
        server/src/main/kotlin/com/hermes/harness/EvalMain.kt \
        server/src/test/kotlin/com/hermes/harness/ForbiddenBehavioursToolFactsTest.kt
git commit -m "fix: judge claims against the facts the tools fetched too"
```

---

### Task 10: 프론트가 조회 중을 보여 준다

**Files:**
- Modify: `frontend/src/lib/agent.ts`
- Modify: `frontend/src/app/course/[uuid]/AskBox.tsx`
- Test: `frontend/src/lib/askCourseStream.test.ts`, `frontend/src/app/course/[uuid]/AskBox.test.tsx`

**Interfaces:**
- Consumes: SSE `event: looking` with `{"what":"congestion"|"alternatives"}`
- Produces: `AskStreamEvent` 유니온에 `{ kind: 'looking'; what: string }` 추가

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`askCourseStream.test.ts` 에 추가한다:

```ts
it('looking 이벤트를 kind looking 으로 넘긴다', async () => {
  const events = await collect(sse([
    'event: looking\ndata: {"what":"congestion"}\n\n',
    'event: citations\ndata: {"citations":["concepts/a.md"]}\n\n',
    'event: delta\ndata: {"text":"답"}\n\n',
    'event: done\ndata: {"generatedAt":"t","model":"m"}\n\n',
  ]))

  expect(events[0]).toEqual({ kind: 'looking', what: 'congestion' })
  expect(events.at(-1)).toMatchObject({ kind: 'done' })
})

it('모르는 what 이 와도 터지지 않는다', async () => {
  const events = await collect(sse([
    'event: looking\ndata: {"what":"weather"}\n\n',
    'event: done\ndata: {"generatedAt":"t","model":"m"}\n\n',
  ]))

  expect(events[0]).toEqual({ kind: 'looking', what: 'weather' })
})
```

`AskBox.test.tsx` 에 추가한다:

```tsx
it('조회 중에는 안내를 보여 주고 답이 오면 치운다', async () => {
  const { emit, finish } = mockStream()
  render(<AskBox courseUuid="abc" />)
  await submitQuestion('다른 날은 어때요?')

  emit({ kind: 'looking', what: 'congestion' })
  expect(await screen.findByText(/혼잡도를 다시 확인/)).toBeInTheDocument()

  emit({ kind: 'citations', citations: ['concepts/a.md'] })
  emit({ kind: 'delta', text: '답' })
  finish()

  await waitFor(() => expect(screen.queryByText(/혼잡도를 다시 확인/)).not.toBeInTheDocument())
})
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd frontend && pnpm test`
Expected: FAIL — `looking` 이벤트가 무시된다

- [ ] **Step 3: 클라이언트에 이벤트를 더한다**

`agent.ts` 의 유니온과 `switch` 에 더한다:

```ts
  | { kind: 'looking'; what: string }
```

```ts
      case 'looking':
        onEvent({ kind: 'looking', what: String(parsed.what ?? '') })
        break
```

- [ ] **Step 4: `AskBox` 가 문구를 고르게 한다**

```tsx
const LOOKING_LABEL: Record<string, string> = {
  congestion: '혼잡도를 다시 확인하는 중',
  alternatives: '주변 대안을 찾아보는 중',
}

// 모르는 이름이 와도 화면이 비지 않게 한다 — 서버가 도구를 늘려도 프론트가 먼저
// 깨지지 않는다.
const labelFor = (what: string) => LOOKING_LABEL[what] ?? '자료를 더 찾아보는 중'
```

`looking` 을 받으면 이 문구를 띄우고, `citations` 또는 `delta` 가 오면 내린다.

- [ ] **Step 5: 통과를 확인한다**

Run: `cd frontend && pnpm test && pnpm typecheck && pnpm build`
Expected: PASS 전부

- [ ] **Step 6: 커밋**

```bash
git add frontend/src/lib/agent.ts frontend/src/app/course/\[uuid\]/AskBox.tsx \
        frontend/src/lib/askCourseStream.test.ts frontend/src/app/course/\[uuid\]/AskBox.test.tsx
git commit -m "feat: tell the reader when the answer is waiting on a lookup"
```

---

### Task 11: 문서

**Files:**
- Modify: `README.md`, `README.ko.md`, `docs/deploy.md`
- Modify: `docs/images/generate_flow.py` 및 생성된 SVG

**Interfaces:** 없음

- [ ] **Step 1: 흐름도에 도구 루프와 스트리밍을 넣는다**

`docs/images/flow.svg` 는 **지금도 스트리밍이 빠져 있다** — 직전 작업이 배포 그림만 고쳤다. 이번에 둘 다 넣는다.

Run: `python3 docs/images/generate_flow.py`
Expected: `flow.svg` 와 `flow.en.svg` 가 갱신된다

- [ ] **Step 2: README 양쪽에 도구 루프를 적는다**

적을 것: 도구 둘과 인자 범위, 예산(라운드 2·마감 60초), 예산 소진 시 도구를 빼고 한 번 더 부른다는 것, 수리 1회, **그리고 `unavailable` 앞의 `delta` 가 0개라는 불변식이 여전히 유효하다는 것.**

- [ ] **Step 3: `docs/deploy.md` 에 지연 변화를 적는다**

도구를 부르는 질문은 왕복이 하나 더 붙으므로 느리다. Cloud Run `--timeout` 90초 하한은 그대로이고, 여기에 **루프 마감 60초가 emitter 90초보다 먼저 온다**는 것을 적는다.

- [ ] **Step 4: 커밋**

```bash
git add README.md README.ko.md docs/deploy.md docs/images/
git commit -m "docs: describe the tool loop and refresh the request-flow diagram"
```

---

### Task 12: 유료 종단 검증 (사람 승인 필요)

**Files:** 없음 (측정)

**Interfaces:** 없음

**이 태스크는 사람의 명시적 승인 없이 실행하지 않는다.** 실제 API 를 부르므로 돈이 든다.

설계의 전제 하나가 **측정으로만 확인된다**: "모델이 필요할 때만 도구를 부른다". 이것이 틀리면 빠른 경로가 사라지고, 직전 작업에서 얻은 1.1~3.5초가 도로 밀린다. 루프백 테스트는 이 질문에 답하지 못한다 — 미리 짠 스트림은 우리가 정한 대로만 행동한다.

- [ ] **Step 1: 승인을 구한다**

물을 것: 유료 실행 승인, 횟수, 모델.

- [ ] **Step 2: 두 묶음을 잰다**

```bash
./gradlew eval --args="openai 5" 2>&1 | tee /tmp/eval-tools-$(date +%s).log
```

- 도구가 필요 없는 질문 5건 — **도구 호출이 0이어야 한다**
- 도구가 필요한 질문 5건 ("다른 날은 어때요?") — 도구를 부르고, 부른 사실로 답해야 한다

**출력을 파일로 받는다.** 유료 실행의 증거는 휘발된다 — 이 저장소가 이미 한 번 겪었다.

- [ ] **Step 3: 판정한다**

- 도구 불필요 묶음에서 도구 호출이 하나라도 나오면 → user 턴 지침을 조이고 다시 잰다
- 예산 소진이 잦으면 → 라운드 수를 재검토한다
- 위반율이 이전 측정과 크게 다르면 → 판정기가 합집합을 제대로 보는지부터 의심한다

- [ ] **Step 4: 결과를 README 에 적는다**

원시값과 보정값을 나란히 적는다. `REORDERED_COURSE` 오탐은 여전히 살아 있으므로 그 줄은 유지한다.

---

## Self-Review

**1. 스펙 커버리지**

| 스펙 요구 | 태스크 |
| --- | --- |
| 포트 확장 (`converse`, 기본 구현) | 1 |
| 도구 둘, 인자 검증, 거부 되먹임 | 2 |
| `FailureCause` 타입 | 3 |
| `ChatModel` 직접 호출, 콜백이 실행되면 터짐 | 4 |
| 도구 실린 요청 본문 고정 | 5 |
| 합집합 facts | 6 |
| 예산·마감·수리·텍스트 우선 규칙 | 7 |
| `looking` 이벤트, user 턴 지침 | 7, 8 |
| 하네스 대조 기준 + 루프 구동 | 9 |
| 프론트 | 10 |
| 문서 | 11 |
| 유료 검증 | 12 |

빠진 것 없음.

**2. 플레이스홀더**

없음. 처음 초안에는 Task 7 에 일부러 틀린 코드를 넣고 주석으로 고치라고 지시한 자리가 있었는데, 구현자가 그대로 베낄 위험이 실제 위험이라 지웠다 — 계획에는 베껴도 되는 코드만 둔다.

Task 9 Step 4 의 `EvalMain` 변경은 집계 필드(`tally.toolRounds` 등)를 이름으로만 가리킨다. `ViolationTally` 의 현재 모양을 읽고 맞춰야 하므로 그 태스크의 구현자가 정한다.

**3. 타입 일관성**

- `AskStreamEvent` 계층: `CitationsEvent`/`DeltaEvent`/`DoneEvent`/`UnavailableEvent`/`AbortedEvent`(Task 3) + `LookingEvent`(Task 7) — 전부 `AskStreamGate.kt` 에 선언
- `ToolArgs`: `Congestion`/`Alternatives`/`Rejected` — Task 2 에서 정의, Task 7·8 에서 같은 이름으로 사용
- `AgentStep`: `ToolRequested`/`Spoke` — Task 1 정의, Task 4·7 사용
- `ToolFacts.add(name, argsSummary, resultJson)` — Task 6 정의, Task 7 Step 5 에서 같은 3인자로 호출
