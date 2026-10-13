import type { ReactNode } from 'react'

export const BADGE_TONES = [
  'neutral',
  'info',
  'success',
  'warning',
  'danger',
  'relaxed',
  'normal',
  'crowded',
  'very-crowded',
  'unknown',
  'record',
  'policy',
] as const

export type BadgeTone = (typeof BADGE_TONES)[number]

const TONE: Record<BadgeTone, string> = {
  neutral: 'bg-surface-subtle text-ink-body',
  info: 'bg-status-info-soft text-status-info-text',
  success: 'bg-status-success-soft text-status-success-text',
  warning: 'bg-status-warning-soft text-status-warning-text',
  danger: 'bg-status-danger-soft text-status-danger-text',
  relaxed: 'bg-grade-relaxed-soft text-grade-relaxed-text',
  normal: 'bg-grade-normal-soft text-grade-normal-text',
  crowded: 'bg-grade-crowded-soft text-grade-crowded-text',
  'very-crowded': 'bg-grade-very-crowded-soft text-grade-very-crowded-text',
  // "데이터 없음". 등급 색을 빌리지 않는다 — 빌리면 그 등급으로 읽힌다.
  unknown: 'border border-dashed border-line-strong bg-grade-unknown-soft text-grade-unknown-text',
  record: 'bg-cite-record-soft text-cite-record-text',
  policy: 'bg-cite-policy-soft text-cite-policy-text',
}

/** 상태를 보여 주기만 한다. 누를 수 없다. */
export function Badge({ tone = 'neutral', children }: { tone?: BadgeTone; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded-chip px-2.5 py-0.5 text-caption font-medium ${TONE[tone]}`}>
      {children}
    </span>
  )
}
