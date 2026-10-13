import type { GuidePath } from '@/lib/guide-schema'
import { dict, type Lang } from '@/lib/i18n'
import { layoutPath, NODE_HEIGHT, NODE_WIDTH, PATH_WIDTH } from './path-layout'

const NODE_FILL = {
  place: 'fill-surface-panel stroke-line-strong',
  event: 'fill-surface-panel stroke-line-strong',
  region: 'fill-surface-subtle stroke-line-normal',
  document: 'fill-cite-policy-soft stroke-line-normal',
} as const

const EDGE_STROKE = {
  alternative: 'stroke-accent-route',
  related: 'stroke-accent-quiet',
  in_region: 'stroke-line-strong',
  explains: 'stroke-accent-gold',
  held_at: 'stroke-line-strong',
} as const

/**
 * 답이 지나온 경로. 그림과, 같은 내용을 담은 목록 둘 다 낸다.
 *
 * 그림은 스크린 리더에 숨긴다. 선과 상자의 좌표를 읽어 주는 것은 정보가 아니고,
 * 바로 아래 목록이 같은 것을 문장으로 말한다. 좁은 화면에서도 목록이 먼저 읽힌다.
 *
 * 여기 나오는 것은 `path` 사건이 실어 온 것 그대로다. 화면이 더하거나 빼지 않는다.
 */
export function PathView({ path, lang }: { path: GuidePath; lang: Lang }) {
  const t = dict(lang).guide
  const layout = layoutPath(path)
  const label = new Map(layout.nodes.map((node) => [node.id, node.label]))
  const places = layout.nodes.filter((node) => node.kind === 'place' || node.kind === 'event')

  return (
    <section className="flex flex-col gap-4" aria-label={t.pathTitle}>
      <h3 className="text-title-2 text-ink-title">{t.pathTitle}</h3>
      <p className="text-caption text-ink-muted">{t.pathRankNote}</p>

      <div className="hidden overflow-x-auto rounded-card border border-line-normal bg-surface-canvas p-2 sm:block">
        <svg viewBox={`0 0 ${PATH_WIDTH} ${layout.height}`} className="h-auto w-full min-w-[560px]" aria-hidden="true">
          {layout.edges.map((edge) => (
            <line
              key={`${edge.from}>${edge.to}:${edge.kind}`}
              x1={edge.x1}
              y1={edge.y1}
              x2={edge.x2}
              y2={edge.y2}
              strokeWidth={edge.kind === 'alternative' || edge.kind === 'related' ? 2 : 1.25}
              strokeDasharray={edge.kind === 'explains' ? '4 4' : undefined}
              className={EDGE_STROKE[edge.kind]}
            />
          ))}
          {layout.nodes.map((node) => (
            <g key={node.id} transform={`translate(${node.x} ${node.y})`}>
              <rect
                width={NODE_WIDTH}
                height={NODE_HEIGHT}
                rx={12}
                strokeWidth={node.isStart ? 2.5 : 1}
                className={node.isStart ? 'fill-brand-soft stroke-brand-primary' : NODE_FILL[node.kind]}
              />
              <text x={12} y={NODE_HEIGHT / 2 + 5} className="fill-ink-title text-[13px] font-medium">
                {node.rank != null ? `${node.rank}. ` : ''}
                {node.label.length > 13 ? `${node.label.slice(0, 12)}…` : node.label}
              </text>
            </g>
          ))}
        </svg>
      </div>

      <div className="flex flex-col gap-3">
        <h4 className="text-body-strong text-ink-title">{t.pathListTitle}</h4>
        <ol className="flex flex-col gap-2" data-testid="path-places">
          {places.map((node) => (
            <li key={node.id} className="rounded-control border border-line-normal bg-surface-panel px-4 py-3">
              <p className="text-body-strong text-ink-title">
                {node.isStart && <span className="text-brand-primary">{t.pathStart} · </span>}
                {node.rank != null && <span className="text-accent-route">{t.pathRank(node.rank)} · </span>}
                {node.label}
              </p>
              {node.region && <p className="text-caption text-ink-muted">{node.region}</p>}
            </li>
          ))}
        </ol>
        <ul className="flex flex-col gap-1 text-caption text-ink-body" data-testid="path-edges">
          {layout.edges.map((edge) => (
            <li key={`${edge.from}>${edge.to}:${edge.kind}`}>
              {label.get(edge.from)} → {label.get(edge.to)} · {t.pathEdge[edge.kind]}
              {edge.rank != null ? ` (${t.pathRank(edge.rank)})` : ''}
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
