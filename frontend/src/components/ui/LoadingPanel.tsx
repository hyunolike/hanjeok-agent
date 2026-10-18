import { Character } from '@/components/guide/Character'

/** Visible only while real work is pending. Skeletons carry no invented progress values. */
export function LoadingPanel({ title, detail, compact = false }: { title: string; detail?: string; compact?: boolean }) {
  return <section className="space-y-4 rounded-card border border-line-normal bg-surface-panel p-5" aria-label={title}>
    <div role="status" aria-label={title} aria-live="polite">
      <Character state="looking" title={title} size="sm">
        {detail && <p className="text-caption text-ink-muted">{detail}</p>}
      </Character>
    </div>
    <div aria-hidden="true" className="space-y-3 motion-safe:animate-pulse" data-testid="loading-skeleton">
      <div className="h-4 w-2/3 rounded-control bg-surface-subtle" />
      <div className="h-4 w-full rounded-control bg-surface-subtle" />
      {!compact && <div className="h-36 rounded-control bg-surface-subtle" />}
    </div>
  </section>
}
