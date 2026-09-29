import { z } from 'zod'
import { GRADES } from './grades'

/**
 * 서버 응답을 해석하는 유일한 지점.
 *
 * 화면이 `any`를 받아 곧바로 그리면, 서버가 필드 이름을 바꿔도 화면은 빈 칸을
 * 그리며 멀쩡한 척한다. 여기서 파싱을 실패시키면 그 순간에 드러난다.
 *
 * 필드는 서버 `FactsProjection`이 확정한 것을 그대로 따른다 — 프론트가 목록을
 * 새로 정하면 두 곳이 갈라지고, 갈라진 것을 알려 주는 것이 아무것도 없다.
 */
export const gradeSchema = z.enum(GRADES)

export const courseItemSchema = z.object({
  attractionId: z.number(),
  name: z.string(),
  visitOrder: z.number(),
  timeLabel: z.string(),
  // 예보 커버리지가 없는 장소는 등급이 없다. null 을 거부하면 그 코스 전체가
  // 화면에서 사라진다 — 없는 것은 결함이 아니라 제품 상태다.
  grade: gradeSchema.nullable(),
  reason: z.string(),
  // 첫 방문지는 이전 장소가 없다.
  travelMinutesFromPrev: z.number().nullable(),
})

export const alternativeSchema = z.object({
  attractionId: z.number(),
  name: z.string(),
  grade: gradeSchema,
  concentration: z.number(),
  distanceKm: z.number(),
  relationScore: z.number(),
  score: z.number(),
  recommendReason: z.string(),
  travelMinutes: z.number(),
})

const betterDatesSchema = z.array(
  z.object({ date: z.string(), concentration: z.number(), grade: gradeSchema }),
)

/**
 * 진단이 있는 경우와 없는 경우를 **플래그로** 가른다. 필드의 부재로 가르면 화면이
 * 부재를 해석해야 하고, 부재는 해석하기 나쁜 신호다 — 서버도 같은 이유로
 * `hasCongestionData` 를 양쪽에 싣는다.
 */
export const congestionSchema = z.discriminatedUnion('hasCongestionData', [
  z.object({
    hasCongestionData: z.literal(true),
    concentration: z.number(),
    percentile: z.number(),
    grade: gradeSchema,
    message: z.string(),
    betterDates: betterDatesSchema,
  }),
  z.object({
    hasCongestionData: z.literal(false),
    message: z.string(),
    betterDates: betterDatesSchema,
  }),
])

export const factsSchema = z.object({
  items: z.array(courseItemSchema),
  // 빈 배열은 "점수가 후보를 떨어뜨렸다"가 아니라 "조용한 실내 후보가 애초에
  // 없었다"는 뜻이다(concepts/alternative-scoring.md). 화면이 이 둘을 같은
  // 문구로 덮으면 위키가 막으려는 오해를 화면이 만든다.
  alternatives: z.array(alternativeSchema),
  targetDate: z.string(),
  title: z.string(),
  congestionReductionRate: z.number(),
  summary: z.string(),
  recommendedDate: z
    .object({ date: z.string(), congestionReductionRate: z.number() })
    .nullable(),
  congestion: congestionSchema,
})

export const factsResponseSchema = z.object({
  courseUuid: z.string(),
  facts: factsSchema,
})

export const explainResponseSchema = z.object({
  explanation: z.string(),
  citations: z.array(z.string()),
  facts: factsSchema,
  generatedAt: z.string(),
  model: z.string(),
})

export const contextEntrySchema = z.object({ path: z.string(), bytes: z.number() })

/**
 * 문서별 크기와, **모델이 실제로 받는 바이트**를 따로 받는다.
 *
 * `bytes` 의 합은 `systemTextBytes` 보다 작다 — 문서 사이의 `----- FILE: … -----`
 * 줄은 어느 문서의 본문도 아니지만 프롬프트에는 실린다. 화면이 합계 하나만 들고
 * "모델이 보는 전부"라고 말하면 그 차이만큼 틀린 말이 된다.
 */
export const contextListingSchema = z.object({
  documents: z.array(contextEntrySchema),
  systemTextBytes: z.number(),
})

export type Facts = z.infer<typeof factsSchema>
export type CourseItem = z.infer<typeof courseItemSchema>
export type ExplainResponse = z.infer<typeof explainResponseSchema>
export type ContextEntry = z.infer<typeof contextEntrySchema>
export type ContextListing = z.infer<typeof contextListingSchema>
