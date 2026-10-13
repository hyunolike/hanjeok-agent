import { z } from 'zod'

/**
 * 안내 에이전트(`/guide/*`)의 응답 모양. 계약 원문은
 * `specs/002-hanjeok-guide-agent/contracts/guide-api.md` 다.
 *
 * 서버가 계약을 어기면 여기서 던진다. 모양이 틀린 답을 화면이 "그럴듯하게" 그리는
 * 것보다, 틀렸다고 드러나는 편이 낫다 — `agent.ts` 가 같은 이유로 그렇게 한다.
 */

export const STEP_STATUSES = ['running', 'ok', 'refused', 'no_data', 'failed'] as const

export const stepSchema = z.object({
  index: z.number().int().nonnegative(),
  kind: z.string().min(1),
  inputs: z.record(z.string(), z.unknown()).default({}),
  status: z.enum(STEP_STATUSES),
  reason: z.string().nullish(),
  produced: z.array(z.string()).default([]),
  summary: z.string().default(''),
  as_of: z.string().nullish(),
})

export const citationSchema = z.object({
  id: z.string().min(1),
  /** 레코드는 사실, 정책 문서는 이유. 화면이 둘을 다르게 그린다. */
  kind: z.enum(['record', 'policy']),
  label: z.string().min(1),
})

export const visitEventSchema = z.object({
  visit_id: z.string().min(1),
  as_of: z.object({ export: z.string(), wiki: z.string() }),
})

export const answerEventSchema = z.object({
  text: z.string().min(1),
  citations: z.array(citationSchema).min(1),
  partial: z.boolean().default(false),
})

export const pathNodeSchema = z.object({
  id: z.string().min(1),
  kind: z.enum(['place', 'region', 'document', 'event']),
  label: z.string().min(1),
  region: z.string().nullish(),
})

export const pathEdgeSchema = z.object({
  from: z.string().min(1),
  to: z.string().min(1),
  kind: z.enum(['related', 'in_region', 'explains', 'held_at', 'alternative']),
  rank: z.number().int().positive().nullish(),
})

export const pathEventSchema = z.object({
  nodes: z.array(pathNodeSchema),
  edges: z.array(pathEdgeSchema),
})

export const doneEventSchema = z.object({
  outcome: z.literal('answered'),
  model: z.string(),
  elapsed_ms: z.number().nonnegative(),
  generated_at: z.string(),
})

export const candidateSchema = z.object({
  place_id: z.number().int(),
  name: z.string().min(1),
  region: z.string(),
})

export const askUserEventSchema = z.object({
  cause: z.literal('ambiguous_place'),
  prompt: z.string().min(1),
  candidates: z.array(candidateSchema).min(2),
})

export const STOP_CAUSES = [
  'unsupported_topic',
  'rule_override',
  'off_topic',
  'unknown_place',
  'date_out_of_range',
  'no_grounds',
  'invalid_citations',
  'budget_exhausted',
  'service_unreachable',
  'model_failed',
] as const

export const stoppedEventSchema = z.object({
  outcome: z.enum(['declined', 'no_grounds', 'failed']),
  cause: z.enum(STOP_CAUSES),
  /** 화면에 그대로 내놓는 한국어. 무엇을 해 볼 수 있는지까지 말한다. */
  message: z.string().min(1),
})

export const usageLimitSchema = z.object({
  cause: z.literal('usage_limit'),
  scope: z.enum(['visitor', 'day']),
  retry_after_s: z.number().nonnegative(),
})

export type Step = z.infer<typeof stepSchema>
export type Citation = z.infer<typeof citationSchema>
export type GuidePath = z.infer<typeof pathEventSchema>
export type PathNode = z.infer<typeof pathNodeSchema>
export type PathEdge = z.infer<typeof pathEdgeSchema>
export type Candidate = z.infer<typeof candidateSchema>
export type StopCause = (typeof STOP_CAUSES)[number]

/**
 * 화면이 받는 사건. 마지막 다섯이 종결이고, 한 질문은 그중 정확히 하나로 끝난다.
 *
 * `limited` 와 `cut` 은 서버가 보내는 SSE 이벤트가 아니다 — 429 응답과 끊긴 연결을
 * 클라이언트가 같은 자리에 올려놓은 것이다. 화면 입장에서는 둘 다 "이 질문이 이렇게
 * 끝났다"이므로 종결 사건과 같은 길로 다루는 편이 빠뜨릴 구멍이 없다.
 */
export type GuideEvent =
  | ({ type: 'visit' } & z.infer<typeof visitEventSchema>)
  | { type: 'step'; step: Step }
  | ({ type: 'answer' } & z.infer<typeof answerEventSchema>)
  | ({ type: 'path' } & GuidePath)
  | ({ type: 'done' } & z.infer<typeof doneEventSchema>)
  | ({ type: 'ask_user' } & z.infer<typeof askUserEventSchema>)
  | ({ type: 'stopped' } & z.infer<typeof stoppedEventSchema>)
  | { type: 'limited'; scope: 'visitor' | 'day'; retry_after_s: number }
  | { type: 'cut' }

export const TERMINAL_TYPES = ['done', 'ask_user', 'stopped', 'limited', 'cut'] as const

export function isTerminal(event: GuideEvent): boolean {
  return (TERMINAL_TYPES as readonly string[]).includes(event.type)
}

/** SSE 프레임 하나를 사건으로. 모르는 이벤트 이름은 계약 위반이라 던진다. */
export function parseGuideFrame(name: string, data: unknown): GuideEvent {
  switch (name) {
    case 'visit':
      return { type: 'visit', ...visitEventSchema.parse(data) }
    case 'step':
      return { type: 'step', step: stepSchema.parse(data) }
    case 'answer':
      return { type: 'answer', ...answerEventSchema.parse(data) }
    case 'path':
      return { type: 'path', ...pathEventSchema.parse(data) }
    case 'done':
      return { type: 'done', ...doneEventSchema.parse(data) }
    case 'ask_user':
      return { type: 'ask_user', ...askUserEventSchema.parse(data) }
    case 'stopped':
      return { type: 'stopped', ...stoppedEventSchema.parse(data) }
    default:
      throw new Error(`unknown guide event: ${name}`)
  }
}

// ---- 질문 없이 둘러보기 (`GET /guide/places`, `/guide/places/{id}`, `/guide/status`) ----

export const placeHitSchema = z.object({
  place_id: z.number().int(),
  name: z.string().min(1),
  region: z.string(),
  has_congestion_data: z.boolean(),
})

export const placesResponseSchema = z.object({
  places: z.array(placeHitSchema).max(10),
  as_of: z.string(),
})

/**
 * 장소 하나와 그 이웃. **혼잡도 값은 여기에 없다** — 날짜에 묶인 값이라 질문으로만
 * 가져온다. 있는 것은 "예보 대상인가" 하나뿐이다.
 */
export const placeDetailSchema = z.object({
  place: placeHitSchema.extend({
    category: z.string().nullish(),
    overview: z.string().nullish(),
  }),
  /** 한적이 정한 순위 순서. 화면이 다시 정렬하지 않는다. */
  related: z.array(
    z.object({
      place_id: z.number().int(),
      name: z.string().min(1),
      region: z.string(),
      rank: z.number().int().positive(),
    }),
  ),
  events: z.array(
    z.object({ id: z.string().min(1), name: z.string().min(1), start_date: z.string(), end_date: z.string() }),
  ),
  as_of: z.string(),
})

export const statusSchema = z.object({
  ready: z.boolean(),
  as_of: z.object({ export: z.string().nullable(), wiki: z.string().nullable() }),
  counts: z.object({
    places: z.number().int().nonnegative(),
    related: z.number().int().nonnegative(),
    events: z.number().int().nonnegative(),
    regions: z.number().int().nonnegative(),
  }),
  generation: z.string().nullable(),
  limits: z.object({ per_visitor: z.number().int().positive(), per_day: z.number().int().positive() }),
})

export type PlaceHit = z.infer<typeof placeHitSchema>
export type PlacesResponse = z.infer<typeof placesResponseSchema>
export type PlaceDetail = z.infer<typeof placeDetailSchema>
export type GuideStatus = z.infer<typeof statusSchema>

// ---- 평가 보고서 (`GET /guide/eval/*`) ----

export const EVAL_STRATEGIES = ['vector', 'graph'] as const
export type EvalStrategy = (typeof EVAL_STRATEGIES)[number]

/** 앞의 넷은 판정 모델이 매긴 점수, 뒤의 둘은 가져온 레코드 id 를 정답 id 와 맞춰 센 것이다. */
export const EVAL_METRICS = [
  'faithfulness',
  'answer_relevancy',
  'context_precision',
  'context_recall',
  'id_precision',
  'id_recall',
] as const
export type EvalMetric = (typeof EVAL_METRICS)[number]

export const EVAL_KINDS = [
  'place_lookup',
  'alternatives',
  'date_comparison',
  'policy',
  'multi_place',
  'unsupported',
] as const
export type EvalKind = (typeof EVAL_KINDS)[number]

export const FORBIDDEN_BEHAVIOURS = [
  'INVENTED_PLACE',
  'ALTERED_ORDER',
  'LLM_CHOSE',
  'UNCITED_CLAIM',
  'GRADE_MISLABEL',
  'NO_DATA_AS_QUIET',
] as const
export type ForbiddenBehaviour = (typeof FORBIDDEN_BEHAVIOURS)[number]

/**
 * 점수 하나. `value` 가 `null` 이면 "매기지 못함"이지 0 이 아니다 — 그래서 숫자와
 * 따로 `status` 와 `reason` 이 있고, `n`(매긴 수)과 `total`(대상 수)이 항상 붙는다.
 */
export const aggregateSchema = z
  .object({
    value: z.number().min(0).max(1).nullable(),
    n: z.number().int().nonnegative(),
    total: z.number().int().nonnegative(),
    status: z.enum(['ok', 'unavailable', 'not_applicable']),
    reason: z.string().nullable().default(null),
  })
  .refine((a) => a.n <= a.total, 'n 이 total 보다 클 수 없다')
  .refine((a) => (a.status === 'ok') === (a.value !== null), '값이 있으면 ok, 없으면 ok 가 아니다')

const metricsSchema = z.record(z.enum(EVAL_METRICS), aggregateSchema)

export const strategyReportSchema = z.object({
  attempted: z.number().int().nonnegative(),
  outcomes: z.record(z.string(), z.number().int().nonnegative()),
  metrics: metricsSchema,
  by_kind: z.record(z.enum(EVAL_KINDS), metricsSchema),
  forbidden: z.record(
    z.enum(FORBIDDEN_BEHAVIOURS),
    z.object({ runs: z.number().int().nonnegative(), occurrences: z.number().int().nonnegative() }),
  ),
  abstention: z.object({
    unanswerable_correct: z.number().int().nonnegative(),
    unanswerable_total: z.number().int().nonnegative(),
  }),
  answer_usage: z.object({
    model_calls: z.number().nonnegative(),
    prompt_tokens: z.number().nonnegative(),
    completion_tokens: z.number().nonnegative(),
    elapsed_ms: z.number().nonnegative(),
  }),
})

export const evalReportSchema = z.object({
  report_id: z.string().min(1),
  status: z.string(),
  timestamp: z.string(),
  question_set: z.string(),
  question_set_revision: z.string(),
  question_count: z.number().int().nonnegative(),
  answer_model: z.string(),
  judge_model: z.string(),
  generation: z.string(),
  export_sha256: z.string(),
  export_as_of: z.string(),
  live_recorded_at: z.string(),
  strategies: z.object({ vector: strategyReportSchema, graph: strategyReportSchema }),
  questions: z.array(z.object({ question_id: z.string().min(1), kind: z.enum(EVAL_KINDS), question: z.string() })),
  limitations: z.array(z.string()),
})

export const evalArmSchema = z.object({
  outcome: z.string(),
  cause: z.string().nullable(),
  answer: z.string().nullable(),
  citations: z.array(z.string()),
  steps: z.array(stepSchema),
  passages: z.array(z.object({ id: z.string().min(1), text: z.string() })),
  scores: z.record(
    z.enum(EVAL_METRICS),
    z.object({
      value: z.number().min(0).max(1).nullable(),
      status: z.enum(['ok', 'unavailable', 'not_applicable']),
      reason: z.string().nullable().default(null),
    }),
  ),
  forbidden: z.array(z.enum(FORBIDDEN_BEHAVIOURS)),
})

export const evalSampleSchema = z.object({
  report_id: z.string().min(1),
  question_id: z.string().min(1),
  kind: z.enum(EVAL_KINDS),
  question: z.string().min(1),
  strategies: z.object({ vector: evalArmSchema, graph: evalArmSchema }),
})

export type Aggregate = z.infer<typeof aggregateSchema>
export type StrategyReport = z.infer<typeof strategyReportSchema>
export type EvalReport = z.infer<typeof evalReportSchema>
export type EvalArm = z.infer<typeof evalArmSchema>
export type EvalSample = z.infer<typeof evalSampleSchema>
