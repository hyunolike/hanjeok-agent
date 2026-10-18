export default function LoadingCourse() {
  return <div role="status" aria-busy="true" className="space-y-4">
    <p className="text-body text-ink-muted">코스를 불러오는 중이에요 / Loading course</p>
    <div aria-hidden="true" className="h-8 w-2/3 animate-pulse rounded-control bg-surface-subtle" />
    <div aria-hidden="true" className="aspect-[16/10] animate-pulse rounded-card bg-surface-subtle" />
  </div>
}
