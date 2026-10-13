import type { GuidePath, PathEdge, PathNode } from '@/lib/guide-schema'

export const PATH_WIDTH = 720
export const NODE_WIDTH = 188
export const NODE_HEIGHT = 44
const ROW = 64
const TOP = 32

/** 왼쪽부터 이유(문서) · 장소 · 지역. 사실이 가운데 있고 양옆이 그것을 설명한다. */
const COLUMN_X = { document: 16, place: 266, event: 266, region: 516 } as const

export type PlacedNode = PathNode & { x: number; y: number; rank: number | null; isStart: boolean }
export type PlacedEdge = PathEdge & { x1: number; y1: number; x2: number; y2: number }
export type PathLayout = { nodes: PlacedNode[]; edges: PlacedEdge[]; height: number }

/**
 * 경로를 그릴 자리를 정한다. 같은 입력에는 언제나 같은 그림이 나온다 — 힘 기반
 * 배치는 새로 고칠 때마다 모양이 달라져서, 두 답의 경로를 눈으로 비교할 수 없다.
 *
 * **장소의 세로 순서는 한적이 준 순위다.** 화면이 다시 정렬하지 않는다. 순위가
 * 없는 장소는 받은 순서대로 그 뒤에 온다.
 */
export function layoutPath(path: GuidePath): PathLayout {
  const rankOf = new Map<string, number>()
  const hasOutgoing = new Set<string>()
  for (const edge of path.edges) {
    if (edge.kind !== 'related' && edge.kind !== 'alternative') continue
    hasOutgoing.add(edge.from)
    if (edge.rank != null && !rankOf.has(edge.to)) rankOf.set(edge.to, edge.rank)
  }

  const places = path.nodes.filter((node) => node.kind === 'place' || node.kind === 'event')
  // 시작점은 순위 간선이 나가는 곳이다. 그런 간선이 없으면 처음 받은 장소다.
  const start = places.find((node) => hasOutgoing.has(node.id) && !rankOf.has(node.id)) ?? places[0]

  const ordered = [...places].sort((a, b) => {
    if (a.id === start?.id) return -1
    if (b.id === start?.id) return 1
    const ra = rankOf.get(a.id)
    const rb = rankOf.get(b.id)
    if (ra != null && rb != null) return ra - rb
    if (ra != null) return -1
    if (rb != null) return 1
    return 0
  })

  const column = (nodes: PathNode[], kind: keyof typeof COLUMN_X): PlacedNode[] =>
    nodes.map((node, row) => ({
      ...node,
      x: COLUMN_X[kind],
      y: TOP + row * ROW,
      rank: rankOf.get(node.id) ?? null,
      isStart: node.id === start?.id,
    }))

  const placed = [
    ...column(path.nodes.filter((node) => node.kind === 'document'), 'document'),
    ...column(ordered, 'place'),
    ...column(path.nodes.filter((node) => node.kind === 'region'), 'region'),
  ]
  const at = new Map(placed.map((node) => [node.id, node]))

  const edges: PlacedEdge[] = []
  for (const edge of path.edges) {
    const from = at.get(edge.from)
    const to = at.get(edge.to)
    // 양 끝이 다 있는 간선만 그린다. 한쪽이 없는 선은 허공을 가리킨다.
    if (!from || !to) continue
    const sameColumn = from.x === to.x
    edges.push({
      ...edge,
      x1: sameColumn ? from.x : from.x < to.x ? from.x + NODE_WIDTH : from.x,
      y1: from.y + NODE_HEIGHT / 2,
      x2: sameColumn ? to.x : from.x < to.x ? to.x : to.x + NODE_WIDTH,
      y2: to.y + NODE_HEIGHT / 2,
    })
  }

  const documents = path.nodes.filter((node) => node.kind === 'document').length
  const regions = path.nodes.filter((node) => node.kind === 'region').length
  const rows = Math.max(1, documents, ordered.length, regions)
  return { nodes: placed, edges, height: TOP * 2 + (rows - 1) * ROW + NODE_HEIGHT }
}
