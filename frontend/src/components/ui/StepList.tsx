import { formatSeoul } from '@/lib/format'
import type { Step } from '@/lib/guide-schema'
import { dict, type Lang } from '@/lib/i18n'
import { Badge, type BadgeTone } from './Badge'

const TONE: Record<Step['status'], BadgeTone> = {
  running: 'info',
  ok: 'success',
  refused: 'warning',
  no_data: 'unknown',
  failed: 'danger',
}

/**
 * 답을 찾으러 간 단계들.
 *
 * 거절된 단계도 지우지 않고 보여 준다. "반경이 범위를 벗어나 조회하지 않았다"는
 * 것은 이 답이 어떻게 나왔는지의 일부이고, 숨기면 에이전트가 한 번에 맞힌 것처럼
 * 보인다.
 */
export function StepList({ steps, lang }: { steps: Step[]; lang: Lang }) {
  const t = dict(lang).guide
  return (
    <ol className="flex flex-col gap-2" aria-label={t.stepsTitle}>
      {steps.map((step) => (
        <li
          key={step.index}
          className="flex flex-col gap-1 rounded-control border border-line-normal bg-surface-panel px-4 py-3"
          data-step-status={step.status}
        >
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-body-strong text-ink-title">{t.stepKind(step.kind)}</span>
            <Badge tone={TONE[step.status]}>{t.stepStatus[step.status]}</Badge>
            {step.as_of && (
              <span className="text-caption text-ink-muted">{t.stepAsOf(formatSeoul(step.as_of, lang))}</span>
            )}
          </div>
          {step.summary && <p className="text-body text-ink-body">{step.summary}</p>}
          {step.reason && step.status === 'refused' && <p className="text-caption text-ink-muted">{step.reason}</p>}
        </li>
      ))}
    </ol>
  )
}
