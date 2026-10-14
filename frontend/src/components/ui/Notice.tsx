import type { ReactNode } from 'react'

type Tone = 'info' | 'success' | 'warning' | 'danger'

const TONE: Record<Tone, string> = {
  info: 'bg-status-info-soft text-status-info-text',
  success: 'bg-status-success-soft text-status-success-text',
  warning: 'bg-status-warning-soft text-status-warning-text',
  danger: 'bg-status-danger-soft text-status-danger-text',
}

/**
 * 화면이 사용자에게 알려야 하는 한 줄.
 *
 * `danger` 만 `alert` 다. `alert` 는 스크린 리더가 하던 말을 끊고 읽으므로, "녹화본을
 * 재생 중입니다" 같은 안내까지 그렇게 읽히면 소음이 된다.
 */
export function Notice({ tone = 'info', title, children }: { tone?: Tone; title?: string; children: ReactNode }) {
  return (
    <div role={tone === 'danger' ? 'alert' : 'status'} className={`rounded-control px-4 py-3 text-body ${TONE[tone]}`}>
      {title && <p className="text-body-strong">{title}</p>}
      <div>{children}</div>
    </div>
  )
}
