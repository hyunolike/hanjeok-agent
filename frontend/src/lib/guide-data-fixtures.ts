/**
 * 질문 없이 여는 화면(둘러보기, 평가)의 녹화본. 스트림 녹화본은 `guide-fixtures.ts` 에 있다.
 *
 * **장소는 전부 지어낸 것이다.** 평가 보고서만은 예외로, 실제 실행 결과를 옮겨 온
 * 파일이다 (아래 `RECORDED_EVAL_REPORT`).
 */

import recordedReport from './recorded-eval/report.json'
import recordedSamples from './recorded-eval/samples.json'

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

/**
 * 저장해 둔 평가 보고서. **이것은 지어낸 것이 아니다** — `guide eval` 이 실제로 만든
 * 보고서와 그 문항별 기록을 `bench/reports/guide/` 에서 그대로 옮겨 온 파일이다.
 * 어떤 데이터로 몇 문항을 쟀는지는 보고서의 한계 목록이 직접 말한다.
 *
 * 공개한 보고서가 바뀌면 두 파일을 다시 복사한다. `guide-contract.test.ts` 가
 * 복사본이 원본과 같은지 본다.
 */
export const RECORDED_EVAL_REPORT: unknown = recordedReport
export const RECORDED_REPORT_ID: string = recordedReport.report_id

export function recordedEvalSample(questionId: string): unknown {
  return (recordedSamples as Record<string, unknown>)[questionId] ?? null
}
