import { describe, expect, it } from 'vitest'
import { DEMO_COURSES, missingKinds } from './demo-courses'

describe('데모 코스', () => {
  it('검증된 서울 여행 코스 네 개를 제공한다', () => {
    // 개수가 아니라 종류가 기준이다. 셋은 각각 번들의 다른 문서를 인용하게 되므로,
    // 인용 검증이 실제로 작동하는지가 데모에서 드러난다.
    expect(missingKinds()).toEqual([])
    expect(DEMO_COURSES).toHaveLength(4)
  })

  it('uuid 가 서로 다르다', () => {
    // 같은 uuid 를 두 번 넣으면 목록은 셋인데 데모는 하나다.
    expect(new Set(DEMO_COURSES.map((c) => c.uuid)).size).toBe(DEMO_COURSES.length)
  })

  it('빠진 종류를 센다', () => {
    expect(missingKinds([])).toHaveLength(4)
    expect(
      missingKinds([
        { uuid: 'a', label: 'a', kind: 'crowded-with-alternatives' },
        { uuid: 'b', label: 'b', kind: 'no-alternatives' },
        { uuid: 'c', label: 'c', kind: 'better-date' },
        { uuid: 'e', label: 'e', kind: 'four-stops' },
      ]),
    ).toEqual([])
  })

  it('같은 종류를 셋 넣어도 채워진 것으로 보지 않는다', () => {
    // 개수만 세면 종류가 겹친 데모가 통과한다. 그런 데모는 인용 검증이 실제로
    // 작동하는지 보여 주지 못한다.
    const sameKind = ['a', 'b', 'c'].map((uuid) => ({
      uuid,
      label: uuid,
      kind: 'better-date' as const,
    }))

    expect(missingKinds(sameKind)).toHaveLength(3)
  })
})

it('울산 동명 장소가 섞인 코스는 데모 목록에서 제외한다', () => {
  expect(DEMO_COURSES.some(course => course.uuid === 'b0719488-c2c7-4256-bc83-e8b2cf5734cd')).toBe(false)
})
