import { describe, expect, it } from 'vitest'
import { RECORDED_STREAMS } from '@/lib/guide-fixtures'
import { pathEventSchema } from '@/lib/guide-schema'
import { layoutPath } from './path-layout'

const path = pathEventSchema.parse(RECORDED_STREAMS.answered.find((f) => f.event === 'path')!.data)

describe('layoutPath', () => {
  it('장소를 한적의 순위대로 세로로 놓는다', () => {
    const places = layoutPath(path).nodes.filter((n) => n.kind === 'place')
    expect(places.map((n) => n.label)).toEqual(['가람궁', '솔내 한옥마을', '물빛 서원', '달맞이 숲길'])
    expect(places.map((n) => n.rank)).toEqual([null, 1, 2, 3])
    expect(places[0].isStart).toBe(true)
    const ys = places.map((n) => n.y)
    expect([...ys].sort((a, b) => a - b)).toEqual(ys)
  })

  it('받은 순서가 뒤섞여 있어도 순위가 이긴다', () => {
    const shuffled = { ...path, nodes: [...path.nodes].reverse() }
    const places = layoutPath(shuffled).nodes.filter((n) => n.kind === 'place')
    expect(places.map((n) => n.label)).toEqual(['가람궁', '솔내 한옥마을', '물빛 서원', '달맞이 숲길'])
  })

  it('같은 입력에는 같은 그림이 나온다', () => {
    expect(layoutPath(path)).toEqual(layoutPath(path))
  })

  it('받은 것을 빠뜨리지 않고, 받지 않은 것을 더하지 않는다', () => {
    const layout = layoutPath(path)
    expect(layout.nodes.map((n) => n.id).sort()).toEqual(path.nodes.map((n) => n.id).sort())
    expect(layout.edges).toHaveLength(path.edges.length)
  })

  it('한쪽 끝이 없는 간선은 그리지 않는다', () => {
    const dangling = { ...path, edges: [...path.edges, { from: 'hanjeok:place/999', to: 'hanjeok:place/101', kind: 'related' as const, rank: 1 }] }
    expect(layoutPath(dangling).edges).toHaveLength(path.edges.length)
  })
})
