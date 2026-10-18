/** Fixed example IDs. Official saved responses are preserved in recorded-courses/.
 * These examples do not request a forecast for their now-historical visit date.
 * Live UUIDs continue to use the agent API; an API failure is never replaced with an example.
 */
import type { Lang } from './i18n'

export type DemoKind =
  /** 대안 3개가 다 붙어 네 정거장이 되는 코스. */
  | 'four-stops'
  /** 목적지가 매우혼잡이고 대안이 붙은 코스. */
  | 'crowded-with-alternatives'
  /** 대안이 비어 있는 코스 — 점수가 떨어뜨린 게 아니라 후보가 애초에 없었다. */
  | 'no-alternatives'
  /** recommendedDate 가 다른 날을 가리키는 코스. */
  | 'better-date'

export type DemoCourse = { uuid: string; label: string; kind: DemoKind }

/** Visitor-facing descriptions of the preserved examples, in both UI languages. */
export const DEMO_PROVES: Record<Lang, Record<DemoKind, string>> = {
  ko: {
    'crowded-with-alternatives':
      '덕수궁을 먼저 보고 이화여고100주년기념관과 서대문형무소역사관으로 이어지는 하루예요.',
    'no-alternatives':
      '경복궁, 창덕궁과 후원, 북촌한옥마을을 이어요. 세 곳 모두 저장 당시 매우혼잡이었어요.',
    'better-date': '박물관에서 이촌한강공원으로 이어져요. 저장 당시 다른 방문 날짜도 제안된 예시예요.',
    'four-stops': '고궁과 전시 공간을 거쳐 한강까지, 네 곳의 방문 순서를 살펴보세요.',
  },
  en: {
    'crowded-with-alternatives':
      'Start at Deoksugung, then visit Ewha Centennial Memorial Hall and Seodaemun Prison History Hall.',
    'no-alternatives':
      'Connect Gyeongbokgung, Changdeokgung and Bukchon. All three had very crowded grades when saved.',
    'better-date': 'From the National Museum to Ichon Hangang Park, with a historical suggestion for another visit date.',
    'four-stops': 'Explore four saved stops, from the palace through exhibition spaces to the Han River.',
  },
}

export const DEMO_COURSES: DemoCourse[] = [
  {
    uuid: '129efdef-41ec-4044-ac87-303abe4ccdde',
    label: '덕수궁에서 시작하는 정동 나들이',
    kind: 'crowded-with-alternatives',
  },
  {
    // 세 장소가 전부 매우혼잡이라 혼잡도 감소율이 0% 다. 설명이 줄지 않은 혼잡도를
    // 줄었다고 말하면 안 되는 코스 — 이 데모가 실제로 무엇을 검증하는지 보여 준다.
    uuid: 'e66302c6-b413-4a07-88a5-3bd55e61fc2a',
    label: '경복궁과 북촌을 잇는 고궁 산책',
    kind: 'no-alternatives',
  },
  {
    uuid: '5a2eb601-1f2b-499b-83eb-8a0093f4817e',
    label: '국립중앙박물관에서 한강까지',
    kind: 'better-date',
  },
  {
    uuid: 'dfdb93f6-bfc3-478d-8a14-f9fde88e9c2a',
    label: '덕수궁에서 이촌한강공원까지',
    kind: 'four-stops',
  },
]

/** Check scenario coverage, not just the number of examples. */
export function missingKinds(courses: DemoCourse[] = DEMO_COURSES): DemoKind[] {
  const present = new Set(courses.map((course) => course.kind))
  return (
    ['crowded-with-alternatives', 'no-alternatives', 'better-date', 'four-stops'] as const
  ).filter((kind) => !present.has(kind))
}

/** Never re-open the retired mixed-region example through the live UUID path. */
export const EXCLUDED_DEMO_UUIDS = new Set(['b0719488-c2c7-4256-bc83-e8b2cf5734cd'])
