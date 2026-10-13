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
