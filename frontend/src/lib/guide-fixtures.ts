/**
 * 녹화해 둔 안내 에이전트 스트림.
 *
 * 서버가 없어도 화면이 모든 상태를 보여 줄 수 있게 한다 — 서버보다 화면을 먼저
 * 만들기 위해서이고, 백엔드 없이 빌드되는 미리보기 배포에서도 데모가 돌게 하기
 * 위해서다. 계약 원문은 `specs/002-hanjeok-guide-agent/contracts/guide-api.md`.
 *
 * **여기 나오는 장소는 전부 지어낸 것이다.** 실재하는 관광지 이름에 가짜 혼잡도를
 * 붙여 두면, 녹화본이라는 안내를 못 본 사람에게는 그것이 사실로 읽힌다.
 */

export type Frame = { event: string; data: unknown }

export const DEMO_KEYS = [
  'answered',
  'partial',
  'ambiguous',
  'no-data',
  'declined',
  'failed',
  'limit',
  'cut',
] as const

export type DemoKey = (typeof DEMO_KEYS)[number]

export function isDemoKey(value: string | null | undefined): value is DemoKey {
  return (DEMO_KEYS as readonly string[]).includes(value ?? '')
}

const AS_OF = { export: '2026-10-13T02:00:00Z', wiki: '2026-10-10T09:00:00Z' }

const visit: Frame = { event: 'visit', data: { visit_id: 'replay-visit', as_of: AS_OF } }

const scopeStep = (summary: string): Frame => ({
  event: 'step',
  data: { index: 0, kind: 'scope', inputs: {}, status: 'ok', produced: [], summary, as_of: null },
})

const resolveGaram: Frame = {
  event: 'step',
  data: {
    index: 1,
    kind: 'resolve',
    inputs: { name: '가람궁' },
    status: 'ok',
    produced: ['hanjeok:place/101'],
    summary: '가람궁 (한빛시 가람구)',
    as_of: AS_OF.export,
  },
}

const congestionGaram: Frame = {
  event: 'step',
  data: {
    index: 2,
    kind: 'congestion',
    inputs: { place_id: 101, date: '2026-10-17' },
    status: 'ok',
    produced: ['hanjeok:congestion/101@2026-10-17', 'wiki:concepts/congestion-diagnosis.md'],
    summary: '10월 17일 예보: 매우혼잡 (상위 8%)',
    as_of: '2026-10-13T14:20:05Z',
  },
}

const answeredPath = {
  nodes: [
    { id: 'hanjeok:place/101', kind: 'place', label: '가람궁', region: '한빛시 가람구' },
    { id: 'hanjeok:place/118', kind: 'place', label: '솔내 한옥마을', region: '한빛시 가람구' },
    { id: 'hanjeok:place/124', kind: 'place', label: '물빛 서원', region: '한빛시 솔내구' },
    { id: 'hanjeok:place/131', kind: 'place', label: '달맞이 숲길', region: '한빛시 솔내구' },
    { id: 'region:11110', kind: 'region', label: '한빛시 가람구', region: null },
    { id: 'region:11140', kind: 'region', label: '한빛시 솔내구', region: null },
    { id: 'wiki:concepts/congestion-diagnosis.md', kind: 'document', label: '혼잡 진단 정책', region: null },
    { id: 'wiki:concepts/alternative-scoring.md', kind: 'document', label: '대안 점수 정책', region: null },
  ],
  edges: [
    { from: 'hanjeok:place/101', to: 'hanjeok:place/118', kind: 'alternative', rank: 1 },
    { from: 'hanjeok:place/101', to: 'hanjeok:place/124', kind: 'alternative', rank: 2 },
    { from: 'hanjeok:place/101', to: 'hanjeok:place/131', kind: 'alternative', rank: 3 },
    { from: 'hanjeok:place/101', to: 'region:11110', kind: 'in_region', rank: null },
    { from: 'hanjeok:place/118', to: 'region:11110', kind: 'in_region', rank: null },
    { from: 'hanjeok:place/124', to: 'region:11140', kind: 'in_region', rank: null },
    { from: 'hanjeok:place/131', to: 'region:11140', kind: 'in_region', rank: null },
    { from: 'wiki:concepts/congestion-diagnosis.md', to: 'hanjeok:place/101', kind: 'explains', rank: null },
    { from: 'wiki:concepts/alternative-scoring.md', to: 'hanjeok:place/118', kind: 'explains', rank: null },
  ],
}

const answered: Frame[] = [
  visit,
  scopeStep('장소 1곳, 날짜 10월 17일(토)로 읽었습니다'),
  resolveGaram,
  congestionGaram,
  {
    event: 'step',
    data: {
      index: 3,
      kind: 'alternatives',
      inputs: { place_id: 101, date: '2026-10-17', radius_km: 15 },
      status: 'ok',
      produced: [
        'hanjeok:alternatives/101@2026-10-17',
        'hanjeok:place/118',
        'hanjeok:place/124',
        'hanjeok:place/131',
        'wiki:concepts/alternative-scoring.md',
      ],
      summary: '한적이 고른 대안 3곳: 솔내 한옥마을, 물빛 서원, 달맞이 숲길',
      as_of: '2026-10-13T14:20:09Z',
    },
  },
  {
    event: 'answer',
    data: {
      text:
        '10월 17일 가람궁은 매우혼잡으로 예보되어 있습니다. 같은 날 한적이 고른 대안은 순서대로 ' +
        '솔내 한옥마을, 물빛 서원, 달맞이 숲길입니다. 세 곳 모두 그날 여유 또는 보통 등급이고, ' +
        '대안 순서는 가람궁과의 연관도와 그날의 한산함, 거리를 함께 본 점수로 한적이 정했습니다.',
      citations: [
        { id: 'hanjeok:congestion/101@2026-10-17', kind: 'record', label: '가람궁 혼잡 예보 · 10월 17일' },
        { id: 'hanjeok:alternatives/101@2026-10-17', kind: 'record', label: '가람궁 대안 · 10월 17일' },
        { id: 'wiki:concepts/congestion-diagnosis.md', kind: 'policy', label: '혼잡 진단 정책' },
        { id: 'wiki:concepts/alternative-scoring.md', kind: 'policy', label: '대안 점수 정책' },
      ],
      partial: false,
    },
  },
  { event: 'path', data: answeredPath },
  {
    event: 'done',
    data: {
      outcome: 'answered',
      model: 'nvidia/nemotron-3-super-120b-a12b',
      elapsed_ms: 14200,
      generated_at: '2026-10-13T14:20:19Z',
    },
  },
]

const partial: Frame[] = [
  visit,
  scopeStep('장소 1곳, 날짜 10월 17일(토)로 읽었습니다'),
  resolveGaram,
  congestionGaram,
  {
    event: 'step',
    data: {
      index: 3,
      kind: 'alternatives',
      inputs: { place_id: 101, date: '2026-10-17', radius_km: 80 },
      status: 'refused',
      reason: 'radius_km 는 1에서 50 사이여야 합니다',
      produced: [],
      summary: '반경이 허용 범위를 벗어나 조회하지 않았습니다',
      as_of: null,
    },
  },
  {
    event: 'answer',
    data: {
      text: '10월 17일 가람궁은 매우혼잡으로 예보되어 있습니다. 대안 장소는 시간 안에 확인하지 못했습니다.',
      citations: [
        { id: 'hanjeok:congestion/101@2026-10-17', kind: 'record', label: '가람궁 혼잡 예보 · 10월 17일' },
        { id: 'wiki:concepts/congestion-diagnosis.md', kind: 'policy', label: '혼잡 진단 정책' },
      ],
      partial: true,
    },
  },
  {
    event: 'path',
    data: {
      nodes: [
        { id: 'hanjeok:place/101', kind: 'place', label: '가람궁', region: '한빛시 가람구' },
        { id: 'wiki:concepts/congestion-diagnosis.md', kind: 'document', label: '혼잡 진단 정책', region: null },
      ],
      edges: [
        { from: 'wiki:concepts/congestion-diagnosis.md', to: 'hanjeok:place/101', kind: 'explains', rank: null },
      ],
    },
  },
  {
    event: 'done',
    data: {
      outcome: 'answered',
      model: 'nvidia/nemotron-3-super-120b-a12b',
      elapsed_ms: 58100,
      generated_at: '2026-10-13T14:21:03Z',
    },
  },
]

const ambiguous: Frame[] = [
  visit,
  scopeStep('장소 1곳, 날짜 10월 17일(토)로 읽었습니다'),
  {
    event: 'step',
    data: {
      index: 1,
      kind: 'resolve',
      inputs: { name: '은행나무길' },
      status: 'ok',
      produced: [],
      summary: '같은 이름의 장소가 2곳 있습니다',
      as_of: AS_OF.export,
    },
  },
  {
    event: 'ask_user',
    data: {
      cause: 'ambiguous_place',
      prompt: '어느 은행나무길을 말씀하시나요?',
      candidates: [
        { place_id: 140, name: '은행나무길', region: '한빛시 가람구' },
        { place_id: 141, name: '은행나무길', region: '한빛시 솔내구' },
      ],
    },
  },
]

const noData: Frame[] = [
  visit,
  scopeStep('장소 1곳, 날짜 10월 17일(토)로 읽었습니다'),
  {
    event: 'step',
    data: {
      index: 1,
      kind: 'resolve',
      inputs: { name: '새벽 등대' },
      status: 'ok',
      produced: ['hanjeok:place/150'],
      summary: '새벽 등대 (한빛시 솔내구)',
      as_of: AS_OF.export,
    },
  },
  {
    event: 'step',
    data: {
      index: 2,
      kind: 'congestion',
      inputs: { place_id: 150, date: '2026-10-17' },
      status: 'no_data',
      produced: [],
      summary: '이 장소는 혼잡 예보 대상이 아닙니다',
      as_of: '2026-10-13T14:22:40Z',
    },
  },
  {
    event: 'stopped',
    data: {
      outcome: 'no_grounds',
      cause: 'no_grounds',
      message:
        '새벽 등대는 한적이 혼잡도를 예보하지 않는 장소라, 그날 붐빌지 한산할지 알 수 없습니다. 한산하다는 뜻이 아닙니다. 예보가 있는 다른 장소를 물어봐 주세요.',
    },
  },
]

const declined: Frame[] = [
  visit,
  {
    event: 'step',
    data: {
      index: 0,
      kind: 'scope',
      inputs: {},
      status: 'refused',
      reason: 'unsupported_topic',
      produced: [],
      summary: '영업시간과 입장료는 한적에 없는 정보입니다',
      as_of: null,
    },
  },
  {
    event: 'stopped',
    data: {
      outcome: 'declined',
      cause: 'unsupported_topic',
      message:
        '영업시간과 입장료는 한적이 갖고 있지 않아 답할 수 없습니다. 특정 날짜에 얼마나 붐비는지, 대신 갈 만한 곳이 있는지는 물어보실 수 있습니다.',
    },
  },
]

const failed: Frame[] = [
  visit,
  scopeStep('장소 1곳, 날짜 10월 17일(토)로 읽었습니다'),
  resolveGaram,
  {
    event: 'step',
    data: {
      index: 2,
      kind: 'congestion',
      inputs: { place_id: 101, date: '2026-10-17' },
      status: 'failed',
      reason: 'service_unreachable',
      produced: [],
      summary: '한적 서비스에 닿지 못했습니다',
      as_of: null,
    },
  },
  {
    event: 'stopped',
    data: {
      outcome: 'failed',
      cause: 'service_unreachable',
      message:
        '지금은 한적 서비스에 연결되지 않아 혼잡도를 확인할 수 없습니다. 저장해 둔 값으로 대신 답하지 않습니다. 잠시 뒤 다시 물어봐 주세요.',
    },
  },
]

/** 답이 오기 전에 연결이 끊긴 녹화본. 종결 이벤트가 없다. */
const cut: Frame[] = [visit, scopeStep('장소 1곳, 날짜 10월 17일(토)로 읽었습니다'), resolveGaram]

/** `limit` 은 스트림이 아니라 429 응답이다. 재생기가 따로 다룬다. */
export const RECORDED_STREAMS: Record<Exclude<DemoKey, 'limit'>, Frame[]> = {
  answered,
  partial,
  ambiguous,
  'no-data': noData,
  declined,
  failed,
  cut,
}

export const RECORDED_LIMIT = { cause: 'usage_limit', scope: 'visitor', retry_after_s: 1800 } as const

/** 후보를 고른 뒤 이어지는 스트림. 고른 장소로 답이 나온다. */
export const RECORDED_AFTER_CHOICE: Frame[] = [
  visit,
  {
    event: 'step',
    data: {
      index: 0,
      kind: 'resolve',
      inputs: { place_id: 140 },
      status: 'ok',
      produced: ['hanjeok:place/140'],
      summary: '은행나무길 (한빛시 가람구)',
      as_of: AS_OF.export,
    },
  },
  {
    event: 'step',
    data: {
      index: 1,
      kind: 'congestion',
      inputs: { place_id: 140, date: '2026-10-17' },
      status: 'ok',
      produced: ['hanjeok:congestion/140@2026-10-17', 'wiki:concepts/congestion-diagnosis.md'],
      summary: '10월 17일 예보: 보통 (상위 46%)',
      as_of: '2026-10-13T14:25:11Z',
    },
  },
  {
    event: 'answer',
    data: {
      text: '10월 17일 가람구 은행나무길은 보통으로 예보되어 있습니다.',
      citations: [
        { id: 'hanjeok:congestion/140@2026-10-17', kind: 'record', label: '은행나무길 혼잡 예보 · 10월 17일' },
        { id: 'wiki:concepts/congestion-diagnosis.md', kind: 'policy', label: '혼잡 진단 정책' },
      ],
      partial: false,
    },
  },
  {
    event: 'path',
    data: {
      nodes: [
        { id: 'hanjeok:place/140', kind: 'place', label: '은행나무길', region: '한빛시 가람구' },
        { id: 'wiki:concepts/congestion-diagnosis.md', kind: 'document', label: '혼잡 진단 정책', region: null },
      ],
      edges: [
        { from: 'wiki:concepts/congestion-diagnosis.md', to: 'hanjeok:place/140', kind: 'explains', rank: null },
      ],
    },
  },
  {
    event: 'done',
    data: {
      outcome: 'answered',
      model: 'nvidia/nemotron-3-super-120b-a12b',
      elapsed_ms: 9800,
      generated_at: '2026-10-13T14:25:20Z',
    },
  },
]
