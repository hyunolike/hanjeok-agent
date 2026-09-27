package com.hermes.harness

import com.fasterxml.jackson.databind.ObjectMapper
import com.hermes.context.BundleLoader
import com.hermes.context.CitationValidator
import com.hermes.context.PromptAssembler
import com.hermes.explain.AbortedEvent
import com.hermes.explain.AgentLoop
import com.hermes.explain.AskStreamEvent
import com.hermes.explain.BackendFacts
import com.hermes.explain.CitationsEvent
import com.hermes.explain.CourseBounds
import com.hermes.explain.CourseQuestionService
import com.hermes.explain.DeltaEvent
import com.hermes.explain.DoneEvent
import com.hermes.explain.ExplainOutcome
import com.hermes.explain.ExplanationService
import com.hermes.explain.Explained
import com.hermes.explain.FailureCause
import com.hermes.explain.LookingEvent
import com.hermes.explain.LoopSignal
import com.hermes.explain.Unavailable
import com.hermes.explain.UnavailableEvent
import com.hermes.llm.Explanation
import com.hermes.llm.ExplanationProvider
import com.hermes.facts.FactsSource
import com.hermes.facts.HanjeokClient
import com.hermes.facts.RestHanjeokClient
import com.hermes.shared.config.HermesConfig
import com.hermes.shared.config.LlmSelection
import org.springframework.web.client.RestClient
import java.io.File
import java.time.Clock
import java.util.concurrent.Executors
import kotlin.system.exitProcess

/**
 * 금지 행동 8종을 센다. 실제 API 를 부르므로 돈이 든다.
 *
 * 서버를 띄우지 않는다 — presentation 을 건너뛰고 application 층을 직접 부르므로,
 * 여기서 통과한 프롬프트 조립과 인용 검증이 운영에서 도는 것과 같은 코드다.
 *
 * 정규화(`FactsNormalizer`)와 판정(`ForbiddenBehaviours`)은 `server` 의 main
 * 소스셋에 있다 — 이 파일은 그 둘과 프로바이더를 엮기만 한다. 프로바이더에게
 * 보내는 factsJson 과 `ForbiddenBehaviours.check` 에 넘기는 factsJson 은 반드시
 * 같은 문자열이어야 한다 — 판정기가 `items`/`alternatives` 를 그 최상위에서
 * 읽으므로, 둘이 다른 모양을 보면 판정은 아무것도 검증하지 못한다. 도구 루프를
 * 탈 때는 그 "같은 문자열"이 **합집합**이다(`ToolFacts.unionJson`).
 *
 *   ./gradlew eval --args="anthropic 5"
 *   ./gradlew eval --args="openrouter 5"
 *   ./gradlew eval --args="openai 5"
 *
 * 세 번째 인자로 코스 uuid 를 주면 픽스처 대신 **한적에서 실제 사실을 받아** 잰다
 * (HANJEOK_BASE_URL 필요).
 *
 *   HANJEOK_BASE_URL=https://api.hanjeok.com ./gradlew eval --args="openai 3 <uuid>"
 *
 * `EVAL_ASK` 에 질문을 넣으면 그 위에 **이어 묻기 경로(`AgentLoop`)** 를 한 번 더
 * 돌린다. 운영의 `/agent/ask/stream` 이 타는 코드가 그것이고, 비스트리밍 `explain()`
 * 만 재면 측정한 것과 배포한 것이 갈라진다 — 이 저장소는 이미 한 번 그랬다.
 *
 *   HANJEOK_BASE_URL=… EVAL_ASK="근처에 덜 붐비는 곳 없어?" \
 *     ./gradlew eval --args="openai 3 <uuid>"
 *
 * 픽스처는 한 코스의 한 모양이다. 운영에 올린 뒤 실제 코스로 재 보니 픽스처에서
 * 한 번도 나오지 않던 결함이 나왔다 — 모델이 자기 제약을 해명하는 문장, 없는
 * 이동 수단, 지어낸 명사. 프롬프트를 고칠 때마다 손으로 curl 하지 않으려면
 * 하네스가 실제 코스를 잴 수 있어야 한다.
 *
 * openrouter 와 openai 는 같은 어댑터를 탄다 — 엔드포인트와 키만 다르고 본문
 * 조립은 한 곳이다. 프로바이더마다 다른 어댑터를 쓰면 측정되는 것이 모델인지
 * 요청 조립 방식인지 흐려지기 때문이다.
 */
/**
 * 빈 값을 없는 값과 같이 다룬다.
 *
 * `System.getenv(...) ?: error(...)` 는 null 만 거른다. 키를 넣다 만 파일은 빈
 * 문자열을 주고, 그건 그대로 프로바이더까지 가서 401 로 돌아온다 — 그 401 은
 * "키가 틀렸다"와 "키를 안 넣었다"를 구분해 주지 않아서, 원인을 찾는 데 시간이
 * 든다. 실제로 그 혼동이 한 번 있었다.
 */
private fun requireCredential(name: String): String =
    System.getenv(name)?.takeIf { it.isNotBlank() }
        ?: error("$name is not set (or is empty) — put it in .env at the repository root, or export it")

/**
 * 위반 표. 두 경로(설명·이어 묻기)가 같은 모양으로 찍어야 나란히 읽을 수 있다.
 *
 * rate 의 분모는 runs 가 아니라 `explained` 다 — Refused/Failed/인용 무효로 끝난
 * 실행은 점검할 설명이 없어 분모에 넣으면 위반율이 희석된다(`ViolationTally` 문서
 * 참고). `explained == 0` 이면 `rate()` 가 null 을 내므로 "0%"가 아니라 명시적으로
 * "측정 불가"라고 찍는다 — 그렇지 않으면 "위반 없음"과 "잴 수 없음"이 같은 숫자로
 * 보인다.
 */
private fun printViolations(tally: Tally, explained: Int) {
    println(
        "violations  : rate = runs-with-violation / explained (NOT /runs); " +
            "occurrences = raw count (may exceed explained for INVENTED_PLACE)",
    )
    Behaviour.entries.forEach { behaviour ->
        val runsCount = tally.runsWithViolation.getValue(behaviour)
        val occurrenceCount = tally.occurrences.getValue(behaviour)
        val rateLabel = when (val rate = tally.rate(behaviour)) {
            null -> "rate=UNMEASURED(explained=0)"
            else -> "rate=%.1f%%(%d/explained=%d)".format(rate * 100, runsCount, explained)
        }
        println("  ${behaviour.name.padEnd(22)} $rateLabel".padEnd(60) + "occurrences=$occurrenceCount")
    }
}

fun main(args: Array<String>) {
    val providerName = args.getOrNull(0) ?: "anthropic"
    val runs = args.getOrNull(1)?.toIntOrNull() ?: 5
    val courseUuid = args.getOrNull(2)?.takeIf { it.isNotBlank() }

    // 이어 묻기(도구 루프)는 기본으로 꺼져 있다 — 켜면 실행당 모델 호출이 최소 두 번이
    // 되고, 모델이 도구를 부르면 라운드마다 더 는다. JUDGE_MODEL 과 같은 규칙이다:
    // 환경변수를 넣는 행위가 그 비용에 대한 동의다.
    val askQuestion = System.getenv("EVAL_ASK")?.takeIf { it.isNotBlank() }

    // 도구는 한적을 부른다. 픽스처에는 모델이 물어볼 조회의 답이 들어 있지 않고,
    // 대역으로 지어낸 결과를 돌려주면 그 뒤의 숫자는 제품이 아니라 대역에 대한
    // 이야기가 된다. 그래서 루프 모드는 실제 코스를 요구한다.
    if (askQuestion != null && courseUuid == null) {
        error(
            "EVAL_ASK is set but no course uuid was given. The tool loop's tools call 한적, and the " +
                "fixture has no answers for the lookups a model would make — a stubbed tool result " +
                "would make these numbers describe the stub, not the product. Run it as: " +
                "HANJEOK_BASE_URL=… EVAL_ASK=\"…\" ./gradlew eval --args=\"$providerName $runs <uuid>\"",
        )
    }

    val bundle = BundleLoader.load()
    // 프로바이더 조립은 LlmSelection 하나에만 둔다. 여기에 분기를 복제하면
    // 하네스가 재는 것과 서버가 띄우는 것이 조용히 갈라진다 — 이 저장소가
    // 한 번 겪은 일이다.
    val model = when (providerName) {
        "anthropic" -> System.getenv("ANTHROPIC_MODEL") ?: "claude-opus-5"
        // 기본값을 두지 않는다. 여기 있던 `nvidia/nemotron-nano-9b-v2:free` 는
        // 상류에서 내려가 이제 404 로 돌아온다 — 기본값이 있는 채로 죽으면
        // "설정한 적 없는 모델"이 실패의 원인이라는 사실이 로그 어디에도 안
        // 보인다. 다른 무료 모델로 갈아 끼워도 같은 방식으로 다시 썩으므로,
        // 잴 모델을 부르는 쪽이 이름으로 말하게 한다.
        "openrouter" -> System.getenv("OPENROUTER_MODEL")?.takeIf { it.isNotBlank() }
            ?: error(
                "OPENROUTER_MODEL is not set (or is empty) — the openrouter provider has no " +
                    "default model. The previous default (nvidia/nemotron-nano-9b-v2:free) was " +
                    "withdrawn upstream and now 404s, and any free-tier substitute would rot the " +
                    "same way, so name the model you mean to measure: " +
                    "./gradlew eval --args=\"openrouter 5\" with OPENROUTER_MODEL=<model> in .env.",
            )
        "openai" -> System.getenv("OPENAI_MODEL") ?: "gpt-4o-mini"
        else -> error("unknown provider: $providerName (expected anthropic, openrouter, or openai)")
    }
    val provider: ExplanationProvider = LlmSelection.provider(providerName, model, System::getenv)

    val assembler = PromptAssembler(bundle)
    val validator = CitationValidator(bundle)
    val service = ExplanationService(assembler, validator, provider)

    // 세 번째 인자가 있으면 한적에서 실제 사실을 받는다. 없으면 픽스처를 쓴다 —
    // 기본 경로가 네트워크를 타면 평가가 한적 가용성에 묶인다.
    val hanjeokBaseUrl = courseUuid?.let { requireCredential("HANJEOK_BASE_URL") }
    val hanjeokClient: HanjeokClient? = hanjeokBaseUrl?.let {
        RestHanjeokClient(RestClient.builder().baseUrl(it).build())
    }

    var fetchedBounds: CourseBounds? = null
    val facts: BackendFacts = if (courseUuid != null && hanjeokClient != null) {
        val executor = Executors.newFixedThreadPool(4)
        try {
            val source = FactsSource(hanjeokClient, 15, executor)
            // 경계는 루프 모드에서만 뽑는다. `boundsFor` 는 targetDate 를 ISO 로
            // 파싱하는데 사실 조립은 그 필드를 문자열로만 읽으므로, 설명 경로가
            // 그것을 타면 ISO 가 아닌 날짜를 가진 코스가 도구와 아무 상관 없이
            // 죽는다(FactsSource.fetch 문서 참고).
            val backendFacts = if (askQuestion == null) {
                source.fetch(courseUuid)
            } else {
                source.fetchWithBounds(courseUuid).also { fetchedBounds = it.bounds }.facts
            }
            println("facts: 한적 $hanjeokBaseUrl, 코스 $courseUuid (${backendFacts.json.length}자)")
            backendFacts
        } finally {
            executor.shutdown()
        }
    } else {
        val fixture = ObjectMapper().readTree(File("harness/fixtures/course-explanation-request.json"))
        println("facts: 픽스처 (실제 코스로 재려면 세 번째 인자에 uuid)")
        BackendFacts(fixture.get("courseUuid").asText(), FactsNormalizer.normalize(fixture).toString())
    }
    val factsJson = facts.json

    // 실행마다 그 실행에서 있었던 위반의 전체 다중집합을 모아 뒀다가, 루프가
    // 끝난 뒤 ViolationTally.aggregate 로 한 번에 집계한다 — "실행당 최대 1"과
    // "원시 발생 횟수"를 같은 자리에서 섞지 않기 위해서다(ViolationTallyTest 가
    // 그 구분을 직접 검증한다).
    val perRunViolations = mutableListOf<List<Behaviour>>()
    var explained = 0
    var unavailable = 0

    // 판정은 기본으로 꺼져 있다 — 켜면 실행당 LLM 호출이 두 번이 되어 비용이
    // 두 배다. JUDGE_MODEL 을 넣는 행위가 그 비용에 대한 동의다.
    val judge = System.getenv("JUDGE_MODEL")?.takeIf { it.isNotBlank() }?.let { model ->
        QualityJudge(OpenAiCompatibleJudgeProvider.openAi(requireCredential("OPENAI_API_KEY"), model))
    }
    val verdicts = mutableListOf<JudgeVerdict>()

    // ── 이어 묻기 배선 ──
    // 루프의 협력자와 예산은 **운영 빈에서 가져온다.** 여기에 숫자를 적어 넣으면
    // 하네스가 잰 루프와 서버가 도는 루프가 조용히 갈라진다.
    val askBounds = fetchedBounds
    val signals = mutableListOf<LoopSignal>()
    val questionService = if (askQuestion != null && askBounds != null && hanjeokClient != null) {
        val config = HermesConfig()
        val toolRunner = config.toolRunner(hanjeokClient)
        val productionLoop = config.agentLoop(provider, validator, toolRunner)
        CourseQuestionService(
            assembler,
            validator,
            provider,
            AgentLoop(
                provider = provider,
                validator = validator,
                toolRunner = toolRunner,
                clock = Clock.systemUTC(),
                maxToolRounds = productionLoop.maxToolRounds,
                deadlineMs = productionLoop.deadlineMs,
            ) { signal -> signals += signal },
        )
    } else {
        null
    }

    val askViolations = mutableListOf<List<Behaviour>>()
    var askAnswered = 0
    var askUnavailable = 0
    var toolRounds = 0
    var budgetExhausted = 0
    var repairsAsked = 0
    var repairsSucceeded = 0

    repeat(runs) { i ->
        when (val outcome: ExplainOutcome = service.explain(facts)) {
            is Explained -> {
                explained++
                val violations = ForbiddenBehaviours.check(outcome.explanation, factsJson, bundle)
                perRunViolations += violations.map { it.behaviour }
                println("[$i] explained — violations: ${violations.ifEmpty { "none" }}")

                // 본문과 인용을 찍는다. 이 표의 0% 는 "위반이 없다"가 아니라 "이
                // 여덟 검사가 보는 범위에서 안 걸렸다"는 뜻이고, 둘을 가르는 것은
                // 결국 사람이 문장을 읽는 일이다. 검사들이 못 보는 것이 실제로
                // 있다 — INVENTED_PLACE 는 궁/사/마을/골목길로 끝나는 이름만 보고,
                // TIME_OF_DAY_REASON 은 문장을 넘는 인과를 놓치며,
                // DEFERRED_DESTINATION 은 대명사만 쓴 회피를 못 잡는다. 숫자만
                // 보여 주고 본문을 감추면 그 한계가 통과로 읽힌다.
                outcome.explanation.explanation.lineSequence().forEach { println("      $it") }
                println("      └ 인용: ${outcome.explanation.citations.joinToString(", ")}")

                judge?.let { verdicts += it.judge(outcome.explanation, factsJson, bundle) }
                println()
            }
            is Unavailable -> {
                unavailable++
                // ExplanationService 는 인용이 유효할 때만 Explained 를 반환한다 —
                // 그래서 UNCITED_CLAIM 신호는 여기, Unavailable.reason 에 있다.
                // ForbiddenBehaviours.check 쪽의 UNCITED_CLAIM 분기는 이 경로에서는
                // 절대 실행되지 않는다(직접 단위 테스트에서만 닿는다).
                perRunViolations += if (ForbiddenBehaviours.unavailableReasonIndicatesUncitedClaim(outcome.reason)) {
                    listOf(Behaviour.UNCITED_CLAIM)
                } else {
                    emptyList()
                }
                println("[$i] unavailable — ${outcome.reason}")
            }
        }

        if (questionService != null && askQuestion != null && askBounds != null) {
            signals.clear()
            val events = mutableListOf<AskStreamEvent>()
            // 판정 대상은 **합집합**이다. 초기 facts 하고만 대조하면 도구가 가져온
            // 사실을 말하는 문장이 전부 근거 없는 주장으로 잡혀, 도구를 켰다는
            // 이유만으로 위반율이 오른다 — 그 상승은 모델에 대해 아무 말도 하지
            // 않는다.
            val unionJson = questionService.askStream(facts, askBounds, askQuestion, emptyList()) { events += it }

            toolRounds += signals.count { it == LoopSignal.TOOL_ROUND }
            if (signals.contains(LoopSignal.BUDGET_EXHAUSTED)) budgetExhausted++
            val repaired = signals.contains(LoopSignal.REPAIR_ASKED)
            if (repaired) repairsAsked++

            val lookups = events.filterIsInstance<LookingEvent>().map { it.what }
            if (events.any { it is DoneEvent }) {
                askAnswered++
                // 수리는 성공했을 때 보이지 않는다(그것이 존재 이유다). 발동 사실은
                // 루프가 알려 주고, 성공 여부는 그 실행이 done 으로 끝났는가로 가른다.
                if (repaired) repairsSucceeded++
                val citations = events.filterIsInstance<CitationsEvent>().flatMap { it.citations }
                val body = events.filterIsInstance<DeltaEvent>().joinToString("") { it.text }
                val violations = ForbiddenBehaviours.check(Explanation(body, citations), unionJson, bundle)
                askViolations += violations.map { it.behaviour }
                println(
                    "[$i] ask — violations: ${violations.ifEmpty { "none" }} " +
                        "(도구 ${lookups.ifEmpty { "없음" }}, 합집합 ${unionJson.length}자)",
                )
                body.lineSequence().forEach { println("      $it") }
                println("      └ 인용: ${citations.joinToString(", ")}")
                println()
            } else {
                askUnavailable++
                // 스트리밍 경로의 인용 무효는 사유 문자열이 아니라 FailureCause 로
                // 온다. 문자열로 분류하면 문구를 다듬는 순간 조용히 깨진다.
                val terminal = events.lastOrNull()
                val invalidCitations = (terminal as? UnavailableEvent)?.cause == FailureCause.INVALID_CITATIONS ||
                    (terminal as? AbortedEvent)?.cause == FailureCause.INVALID_CITATIONS
                askViolations += if (invalidCitations) listOf(Behaviour.UNCITED_CLAIM) else emptyList()
                println("[$i] ask unavailable — $terminal (도구 ${lookups.ifEmpty { "없음" }})")
            }
        }
    }

    val tally = ViolationTally.aggregate(perRunViolations, explained)

    println()
    println("provider    : ${provider.name}")
    println("runs        : $runs")
    println("explained   : $explained")
    println("unavailable : $unavailable")
    printViolations(tally, explained)

    // ── 이어 묻기(도구 루프) ──
    // 위 표와 **합치지 않는다.** 두 경로는 프롬프트도 호출 횟수도 다르고, 한 실행에
    // 설명 하나와 답 하나가 따로 있다 — 한 분모에 섞으면 그 비율은 둘 중 어느 것도
    // 말하지 않는다.
    println()
    if (questionService == null) {
        println("agent loop  : 안 돎 (EVAL_ASK 미설정 — 켜면 실행당 모델 호출이 최소 2배다)")
        println("              위 표는 비스트리밍 explain 경로만 잰 것이다. 운영의")
        println("              /agent/ask/stream 은 AgentLoop 을 타므로, 이 표는 그 경로의")
        println("              도구 사용·예산·수리에 대해 아무것도 말하지 않는다.")
    } else {
        val askTally = ViolationTally.aggregate(askViolations, askAnswered)
        println("── 이어 묻기 (AgentLoop · 위 표와 별개) ──")
        println("question    : $askQuestion")
        println("answered    : $askAnswered")
        println("unavailable : $askUnavailable")
        // 유료 실행의 증거는 휘발된다. 이 네 숫자가 없으면 "도구를 켜고 쟀다"는 말과
        // "도구가 한 번도 안 불렸다"가 같은 출력으로 보인다.
        println(
            "tool rounds: $toolRounds, budget exhausted: $budgetExhausted/$runs, " +
                "repairs: $repairsAsked/$repairsSucceeded (발동/성공)",
        )
        printViolations(askTally, askAnswered)
    }

    // 판정 결과는 위 표와 **합치지 않는다.** 위는 결정론적이라 같은 입력에 같은
    // 답을 내고, 아래는 모델이 내는 의견이라 실행마다 달라질 수 있다. 둘을 한
    // 숫자로 묶으면 그 숫자는 재현되지 않으면서 재현되는 것처럼 보인다.
    if (judge == null) {
        println()
        println("quality     : 판정 안 함 (JUDGE_MODEL 미설정 — 켜면 실행당 LLM 호출이 2배가 된다)")
    } else {
        val notJudged = verdicts.filterIsInstance<NotJudged>()
        val all = verdicts.filterIsInstance<Judged>().flatMap { it.findings }
        // 인용문이 본문에 없는 지적은 무엇을 고칠지 가리키지 못한다. 버리지 않고
        // 따로 센다 — 실제 지적과 섞으면 개수만 부풀고, 감추면 판정자가 헛도는
        // 것을 알 수 없다.
        val (findings, unanchored) = all.partition { it.evidenceFound }

        println()
        println("── 품질 판정 (LLM · 위 표와 별개, 차단하지 않음) ──")
        println("judge model : ${System.getenv("JUDGE_MODEL")}")
        // "지적 없음"과 "판정 불가"를 절대 같은 줄에 두지 않는다 — 판정이 멈춘
        // 것을 깨끗한 결과로 읽으면 이 축이 있는 의미가 없어진다.
        println("판정함      : ${verdicts.size - notJudged.size}/${verdicts.size}")
        if (notJudged.isNotEmpty()) {
            println("판정 불가   : ${notJudged.size} — ${notJudged.map { it.reason }.distinct().joinToString("; ")}")
        }
        if (unanchored.isNotEmpty()) {
            println("확인 불가   : ${unanchored.size} — 인용문이 본문에 없다(판정자가 요약했거나 자리표시자를 냈다)")
        }
        if (findings.isEmpty()) {
            println("지적        : 없음")
        } else {
            QualityIssue.entries.forEach { issue ->
                val count = findings.count { it.issue == issue }
                if (count > 0) println("  ${issue.name.padEnd(22)} $count")
            }
            println()
            // 지적은 인용문과 함께 찍는다. 개수만 보면 무엇을 고칠지 알 수 없고,
            // 이 프로젝트의 프롬프트 결함 셋은 전부 문장을 읽어서 고쳤다.
            findings.forEach { finding ->
                println("  [${finding.issue}] \"${finding.evidence}\"")
                println("      └ ${finding.why}")
            }
        }
    }

    if (explained == 0) {
        System.err.println()
        System.err.println("all $runs runs were unavailable — nothing was explained, no violation count is trustworthy")
        exitProcess(1)
    }
    if (questionService != null && askAnswered == 0) {
        System.err.println()
        System.err.println(
            "all $runs ask runs ended without an answer — the loop numbers above describe failures, " +
                "not the deployed behaviour",
        )
        exitProcess(1)
    }
}
