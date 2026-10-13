/**
 * 질문 없이 여는 화면(둘러보기, 평가)의 녹화본. 스트림 녹화본은 `guide-fixtures.ts` 에 있다.
 *
 * **장소도 숫자도 전부 지어낸 것이다.** 평가 점수는 화면이 표를 어떻게 그리는지
 * 보여 주려고 만든 값이고, 실제 측정이 아니다. 화면이 재생 중이라고 말한다.
 */

import {
  EVAL_KINDS,
  EVAL_METRICS,
  FORBIDDEN_BEHAVIOURS,
  type Aggregate,
  type EvalArm,
  type EvalKind,
  type EvalMetric,
  type EvalStrategy,
} from './guide-schema'

const EXPORT_AS_OF = '2026-10-13T02:00:00Z'
const WIKI_AS_OF = '2026-10-10T09:00:00Z'
const GARAM = '한빛시 가람구'
const SOLNAE = '한빛시 솔내구'

type RecordedPlace = {
  place_id: number
  name: string
  region: string
  category: string
  overview: string
  has_congestion_data: boolean
  /** 한적이 정한 순위 순서. */
  related: number[]
  events: { id: string; name: string; start_date: string; end_date: string }[]
}

const PLACES: RecordedPlace[] = [
  {
    place_id: 101,
    name: '가람궁',
    region: GARAM,
    category: '고궁',
    overview: '한빛시 한가운데 있는 옛 궁궐. 주말 낮에는 정문 앞마당부터 사람이 찬다.',
    has_congestion_data: true,
    related: [118, 124, 131],
    events: [{ id: 'festival:garam-night', name: '가람궁 달빛 야행', start_date: '2026-10-16', end_date: '2026-10-25' }],
  },
  {
    place_id: 118,
    name: '솔내 한옥마을',
    region: GARAM,
    category: '전통마을',
    overview: '가람궁 동쪽 담을 따라 이어지는 한옥 골목. 사람이 사는 동네라 조용히 걷는 곳이다.',
    has_congestion_data: true,
    related: [101, 124],
    events: [],
  },
  {
    place_id: 124,
    name: '물빛 서원',
    region: SOLNAE,
    category: '서원',
    overview: '개울을 끼고 앉은 서원. 마루에 앉으면 물소리가 들린다.',
    has_congestion_data: true,
    related: [131, 118],
    events: [],
  },
  {
    place_id: 131,
    name: '달맞이 숲길',
    region: SOLNAE,
    category: '숲길',
    overview: '서원 뒤편 언덕으로 오르는 2km 남짓한 숲길.',
    has_congestion_data: true,
    related: [124],
    events: [],
  },
  {
    place_id: 140,
    name: '은행나무길',
    region: GARAM,
    category: '산책로',
    overview: '가람궁 서쪽 담장 밖의 은행나무 가로수길.',
    has_congestion_data: true,
    related: [101],
    events: [],
  },
  {
    place_id: 141,
    name: '은행나무길',
    region: SOLNAE,
    category: '산책로',
    overview: '달맞이 숲길 입구까지 이어지는 마을 길.',
    has_congestion_data: false,
    related: [131],
    events: [],
  },
  {
    place_id: 150,
    name: '새벽 등대',
    region: SOLNAE,
    category: '등대',
    overview: '솔내구 끝 방파제에 선 작은 등대.',
    has_congestion_data: false,
    related: [],
    events: [],
  },
]

const byId = new Map(PLACES.map((place) => [place.place_id, place]))
const squash = (text: string) => text.replace(/\s+/g, '')

/** 서버와 같은 규칙: 공백을 지우고, 똑같은 이름 → 앞이 같은 이름 → 포함하는 이름 순. 최대 10곳. */
export function searchRecordedPlaces(query: string) {
  const needle = squash(query)
  if (needle === '') return { places: [], as_of: EXPORT_AS_OF }
  const tier = (name: string) => (name === needle ? 0 : name.startsWith(needle) ? 1 : name.includes(needle) ? 2 : 3)
  const places = PLACES.map((place) => ({ place, tier: tier(squash(place.name)) }))
    .filter((hit) => hit.tier < 3)
    .sort((a, b) => a.tier - b.tier)
    .slice(0, 10)
    .map(({ place }) => ({
      place_id: place.place_id,
      name: place.name,
      region: place.region,
      has_congestion_data: place.has_congestion_data,
    }))
  return { places, as_of: EXPORT_AS_OF }
}

export function recordedPlace(placeId: number) {
  const place = byId.get(placeId)
  if (!place) return null
  const { related, events, ...fields } = place
  return {
    place: fields,
    related: related.map((id, index) => {
      const other = byId.get(id)!
      return { place_id: id, name: other.name, region: other.region, rank: index + 1 }
    }),
    events,
    as_of: EXPORT_AS_OF,
  }
}

export const RECORDED_STATUS = {
  ready: true,
  as_of: { export: EXPORT_AS_OF, wiki: WIKI_AS_OF },
  counts: {
    places: PLACES.length,
    related: PLACES.reduce((sum, place) => sum + place.related.length, 0),
    events: PLACES.reduce((sum, place) => sum + place.events.length, 0),
    regions: 2,
  },
  generation: 'gen-replay-0001',
  limits: { per_visitor: 20, per_day: 400 },
}

// ---- 평가 ----

type Recorded = {
  id: string
  kind: EvalKind
  question: string
  /** 전략마다: 답(없으면 거절), 건네받은 근거의 id. */
  vector: [string | null, string[]]
  graph: [string | null, string[]]
}

const PASSAGES: Record<string, string> = {
  'hanjeok:place/101': '가람궁 · 고궁 · 한빛시 가람구',
  'hanjeok:place/118': '솔내 한옥마을 · 전통마을 · 한빛시 가람구',
  'hanjeok:place/124': '물빛 서원 · 서원 · 한빛시 솔내구',
  'hanjeok:place/131': '달맞이 숲길 · 숲길 · 한빛시 솔내구',
  'hanjeok:place/150': '새벽 등대 · 등대 · 한빛시 솔내구 · 혼잡 예보 대상 아님',
  'hanjeok:congestion/101@2026-10-17': '가람궁 10월 17일 예보: 매우혼잡 (상위 8%)',
  'hanjeok:congestion/101@2026-10-20': '가람궁 10월 20일 예보: 보통 (상위 46%)',
  'hanjeok:congestion/118@2026-10-17': '솔내 한옥마을 10월 17일 예보: 보통 (상위 52%)',
  'hanjeok:congestion/118@2026-10-18': '솔내 한옥마을 10월 18일 예보: 혼잡 (상위 21%)',
  'hanjeok:alternatives/101@2026-10-17': '가람궁 10월 17일 대안: 1 솔내 한옥마을, 2 물빛 서원, 3 달맞이 숲길',
  'hanjeok:alternatives/124@2026-10-17': '물빛 서원 10월 17일 대안: 1 달맞이 숲길, 2 솔내 한옥마을',
  'hanjeok:related/101': '가람궁의 연관 장소: 1 솔내 한옥마을, 2 물빛 서원, 3 달맞이 숲길',
  'hanjeok:related/124': '물빛 서원의 연관 장소: 1 달맞이 숲길, 2 솔내 한옥마을',
  'hanjeok:event/festival:garam-night': '가람궁 달빛 야행 · 10월 16일–25일 · 가람궁',
  'wiki:concepts/congestion-diagnosis.md': '혼잡 등급은 같은 장소의 지난 방문량 분포에서 그날 예보가 놓이는 자리로 정한다.',
  'wiki:concepts/alternative-scoring.md': '대안 점수는 연관도 0.4, 한적함 0.4, 거리 0.2 를 더한 값이고 순서는 서비스가 정한다.',
}

const QUESTIONS: Recorded[] = [
  {
    id: 'q01',
    kind: 'place_lookup',
    question: '가람궁은 10월 17일에 얼마나 붐벼?',
    vector: ['10월 17일 가람궁 예보는 매우혼잡입니다.', ['hanjeok:place/101', 'hanjeok:congestion/101@2026-10-17']],
    graph: ['10월 17일 가람궁 예보는 매우혼잡입니다.', ['hanjeok:place/101', 'hanjeok:congestion/101@2026-10-17']],
  },
  {
    id: 'q02',
    kind: 'place_lookup',
    question: '새벽 등대는 이번 토요일에 한적해?',
    vector: ['새벽 등대는 혼잡 예보 대상이 아니어서 알 수 없습니다.', ['hanjeok:place/150']],
    graph: ['새벽 등대는 혼잡 예보 대상이 아니어서 알 수 없습니다.', ['hanjeok:place/150']],
  },
  {
    id: 'q03',
    kind: 'alternatives',
    question: '10월 17일 가람궁 대신 갈 만한 곳은?',
    vector: [
      '한적이 고른 순서로 솔내 한옥마을, 물빛 서원, 달맞이 숲길입니다.',
      ['hanjeok:place/101', 'hanjeok:alternatives/101@2026-10-17'],
    ],
    graph: [
      '한적이 고른 순서로 솔내 한옥마을, 물빛 서원, 달맞이 숲길입니다.',
      ['hanjeok:place/101', 'hanjeok:alternatives/101@2026-10-17', 'wiki:concepts/alternative-scoring.md'],
    ],
  },
  {
    id: 'q04',
    kind: 'alternatives',
    question: '물빛 서원이 붐비면 어디로 가?',
    vector: ['한적이 고른 순서로 달맞이 숲길, 솔내 한옥마을입니다.', ['hanjeok:place/124', 'hanjeok:alternatives/124@2026-10-17']],
    graph: [
      '한적이 고른 순서로 달맞이 숲길, 솔내 한옥마을입니다.',
      ['hanjeok:place/124', 'hanjeok:alternatives/124@2026-10-17', 'hanjeok:related/124'],
    ],
  },
  {
    id: 'q05',
    kind: 'date_comparison',
    question: '가람궁은 토요일과 화요일 중 언제 덜 붐벼?',
    vector: [
      '화요일(10월 20일)이 덜 붐빕니다. 토요일은 매우혼잡, 화요일은 보통입니다.',
      ['hanjeok:congestion/101@2026-10-17', 'hanjeok:congestion/101@2026-10-20'],
    ],
    graph: [
      '화요일(10월 20일)이 덜 붐빕니다. 토요일은 매우혼잡, 화요일은 보통입니다.',
      ['hanjeok:congestion/101@2026-10-17', 'hanjeok:congestion/101@2026-10-20'],
    ],
  },
  {
    id: 'q06',
    kind: 'date_comparison',
    question: '솔내 한옥마을은 17일과 18일 중 언제가 나아?',
    vector: ['17일이 낫습니다. 17일은 보통, 18일은 혼잡입니다.', ['hanjeok:congestion/118@2026-10-17', 'hanjeok:congestion/118@2026-10-18']],
    graph: ['17일이 낫습니다. 17일은 보통, 18일은 혼잡입니다.', ['hanjeok:congestion/118@2026-10-17', 'hanjeok:congestion/118@2026-10-18']],
  },
  {
    id: 'q07',
    kind: 'policy',
    question: '대안 장소는 어떤 기준으로 골라?',
    vector: ['연관도, 한적함, 거리를 더한 점수로 한적이 순서를 정합니다.', ['wiki:concepts/alternative-scoring.md']],
    graph: ['연관도, 한적함, 거리를 더한 점수로 한적이 순서를 정합니다.', ['wiki:concepts/alternative-scoring.md']],
  },
  {
    id: 'q08',
    kind: 'policy',
    question: '혼잡 등급은 어떻게 나눠?',
    vector: ['같은 장소의 지난 방문량 분포에서 그날 예보가 놓이는 자리로 나눕니다.', ['wiki:concepts/congestion-diagnosis.md']],
    graph: ['같은 장소의 지난 방문량 분포에서 그날 예보가 놓이는 자리로 나눕니다.', ['wiki:concepts/congestion-diagnosis.md']],
  },
  {
    id: 'q09',
    kind: 'multi_place',
    question: '가람궁과 이어진 곳 중 솔내구에 있는 곳은?',
    vector: ['확인한 범위에서는 솔내구에 있는 곳을 찾지 못했습니다.', ['hanjeok:place/101', 'hanjeok:place/118']],
    graph: [
      '물빛 서원과 달맞이 숲길이 솔내구에 있습니다.',
      ['hanjeok:place/101', 'hanjeok:related/101', 'hanjeok:place/124', 'hanjeok:place/131'],
    ],
  },
  {
    id: 'q10',
    kind: 'multi_place',
    question: '물빛 서원과 이어진 곳 가까이에서 열리는 행사가 있어?',
    vector: ['물빛 서원 자체에는 등록된 행사가 없습니다.', ['hanjeok:place/124']],
    graph: [
      '물빛 서원과 이어진 솔내 한옥마을 옆 가람궁에서 달빛 야행이 10월 16일부터 25일까지 열립니다.',
      ['hanjeok:place/124', 'hanjeok:related/124', 'hanjeok:place/118', 'hanjeok:event/festival:garam-night'],
    ],
  },
  { id: 'q11', kind: 'unsupported', question: '가람궁 입장료는 얼마야?', vector: [null, []], graph: [null, []] },
  { id: 'q12', kind: 'unsupported', question: '솔내구 맛집 추천해 줘', vector: [null, []], graph: [null, []] },
]

const NOT_APPLICABLE = '답하지 않는 것이 정답인 질문이라 점수를 매기지 않습니다.'
const JUDGE_FAILED = '판정 모델 호출이 실패해 이 종류의 문항을 채점하지 못했습니다.'

/** 종류별 점수. `[값, 매긴 수]` 이고 대상 수는 종류마다 2 다. 값이 null 이면 못 매긴 것이다. */
type KindScores = Record<EvalMetric, [number | null, number]>
const two = (...values: number[]): KindScores =>
  Object.fromEntries(EVAL_METRICS.map((metric, index) => [metric, [values[index], 2]])) as KindScores

const BY_KIND: Record<EvalStrategy, Record<Exclude<EvalKind, 'unsupported'>, KindScores>> = {
  vector: {
    place_lookup: two(0.96, 0.92, 0.8, 0.85, 0.78, 0.84),
    alternatives: two(0.94, 0.9, 0.74, 0.7, 0.72, 0.68),
    date_comparison: two(0.92, 0.86, 0.72, 0.66, 0.7, 0.64),
    policy: two(0.95, 0.91, 0.78, 0.8, 0.75, 0.8),
    multi_place: { ...two(0.88, 0.8, 0.52, 0.34, 0.5, 0.3), faithfulness: [0.88, 1] },
  },
  graph: {
    place_lookup: two(0.95, 0.92, 0.74, 0.86, 0.72, 0.84),
    alternatives: two(0.93, 0.91, 0.7, 0.84, 0.68, 0.86),
    date_comparison: two(0.92, 0.87, 0.68, 0.78, 0.66, 0.76),
    policy: { ...two(0, 0.9, 0.76, 0.8, 0.74, 0.8), faithfulness: [null, 0] },
    multi_place: two(0.9, 0.89, 0.58, 0.82, 0.56, 0.84),
  },
}

function kindAggregate(strategy: EvalStrategy, kind: EvalKind, metric: EvalMetric): Aggregate {
  if (kind === 'unsupported') return { value: null, n: 0, total: 2, status: 'not_applicable', reason: NOT_APPLICABLE }
  const [value, n] = BY_KIND[strategy][kind][metric]
  return value === null
    ? { value: null, n: 0, total: 2, status: 'unavailable', reason: JUDGE_FAILED }
    : { value, n, total: 2, status: 'ok', reason: null }
}

/** 전체 점수는 종류별 점수에서 계산한다. 따로 적어 두면 두 표가 어긋난다. */
function overall(strategy: EvalStrategy, metric: EvalMetric): Aggregate {
  const parts = EVAL_KINDS.filter((kind) => kind !== 'unsupported').map((kind) => kindAggregate(strategy, kind, metric))
  const n = parts.reduce((sum, part) => sum + part.n, 0)
  const total = parts.reduce((sum, part) => sum + part.total, 0)
  const weighted = parts.reduce((sum, part) => sum + (part.value ?? 0) * part.n, 0)
  return { value: Math.round((weighted / n) * 1000) / 1000, n, total, status: 'ok', reason: null }
}

function strategyReport(strategy: EvalStrategy, flagged: Partial<Record<(typeof FORBIDDEN_BEHAVIOURS)[number], number>>) {
  const each = <T>(pick: (metric: EvalMetric) => T) =>
    Object.fromEntries(EVAL_METRICS.map((metric) => [metric, pick(metric)])) as Record<EvalMetric, T>
  return {
    attempted: QUESTIONS.length,
    outcomes: { answered: 10, declined: 2 },
    metrics: each((metric) => overall(strategy, metric)),
    by_kind: Object.fromEntries(
      EVAL_KINDS.map((kind) => [kind, each((metric) => kindAggregate(strategy, kind, metric))]),
    ) as Record<EvalKind, Record<EvalMetric, Aggregate>>,
    forbidden: Object.fromEntries(
      FORBIDDEN_BEHAVIOURS.map((behaviour) => [behaviour, { runs: QUESTIONS.length, occurrences: flagged[behaviour] ?? 0 }]),
    ) as Record<(typeof FORBIDDEN_BEHAVIOURS)[number], { runs: number; occurrences: number }>,
    abstention: { unanswerable_correct: 2, unanswerable_total: 2 },
    answer_usage:
      strategy === 'vector'
        ? { model_calls: 31, prompt_tokens: 41200, completion_tokens: 3900, elapsed_ms: 148000 }
        : { model_calls: 36, prompt_tokens: 52800, completion_tokens: 4300, elapsed_ms: 171000 },
  }
}

export const RECORDED_REPORT_ID = 'replay-report'

export const RECORDED_EVAL_REPORT = {
  report_id: RECORDED_REPORT_ID,
  status: 'completed',
  timestamp: '2026-10-13T15:10:00Z',
  question_set: 'hanjeok-replay',
  question_set_revision: 'r1',
  question_count: QUESTIONS.length,
  answer_model: 'nvidia/nemotron (녹화본)',
  judge_model: 'nvidia/nemotron (녹화본)',
  generation: RECORDED_STATUS.generation,
  export_sha256: '0000000000000000000000000000000000000000000000000000000000000000',
  export_as_of: EXPORT_AS_OF,
  live_recorded_at: '2026-10-13T14:20:05Z',
  strategies: {
    vector: strategyReport('vector', { UNCITED_CLAIM: 1 }),
    graph: strategyReport('graph', {}),
  },
  questions: QUESTIONS.map(({ id, kind, question }) => ({ question_id: id, kind, question })),
  limitations: [
    '이 보고서는 화면을 보여 주려고 지어낸 12문항짜리 녹화본입니다. 실제 측정이 아닙니다.',
    '문항이 종류마다 2개뿐이라, 종류별 점수는 문항 하나에 크게 흔들립니다.',
    '혼잡 예보와 대안은 평가 시점에 한 번 녹화한 응답을 두 전략이 함께 썼습니다.',
  ],
}

function arm(strategy: EvalStrategy, recorded: Recorded): EvalArm {
  const [answer, passageIds] = recorded[strategy]
  const declined = answer === null
  return {
    outcome: declined ? 'declined' : 'answered',
    cause: declined ? 'unsupported_topic' : null,
    answer,
    citations: passageIds,
    steps: [
      {
        index: 0,
        kind: 'scope',
        inputs: {},
        status: declined ? 'refused' : 'ok',
        reason: declined ? '한적이 갖고 있지 않은 정보입니다' : null,
        produced: [],
        summary: declined ? '답할 수 없는 주제로 읽었습니다' : '질문을 읽었습니다',
        as_of: null,
      },
      ...(declined
        ? []
        : [
            {
              index: 1,
              kind: strategy === 'graph' && recorded.kind === 'multi_place' ? 'related_places' : 'search_places',
              inputs: {},
              status: 'ok' as const,
              reason: null,
              produced: passageIds,
              summary: `근거 ${passageIds.length}건을 가져왔습니다`,
              as_of: EXPORT_AS_OF,
            },
          ]),
    ],
    passages: passageIds.map((id) => ({ id, text: PASSAGES[id] })),
    scores: Object.fromEntries(
      EVAL_METRICS.map((metric) => {
        const cell = kindAggregate(strategy, recorded.kind, metric)
        return [metric, { value: cell.value, status: cell.status, reason: cell.reason }]
      }),
    ) as EvalArm['scores'],
    forbidden: strategy === 'vector' && recorded.id === 'q10' ? ['UNCITED_CLAIM'] : [],
  }
}

export function recordedEvalSample(questionId: string) {
  const recorded = QUESTIONS.find((question) => question.id === questionId)
  if (!recorded) return null
  return {
    report_id: RECORDED_REPORT_ID,
    question_id: recorded.id,
    kind: recorded.kind,
    question: recorded.question,
    strategies: { vector: arm('vector', recorded), graph: arm('graph', recorded) },
  }
}
