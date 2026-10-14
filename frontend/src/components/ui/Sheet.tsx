'use client'

import { useEffect, useRef, type ReactNode } from 'react'

/**
 * 화면을 떠나지 않고 여는 바닥 시트. `CitationSheet` 가 하던 세 가지를 그대로 한다:
 * Esc 로 닫히고, 배경을 눌러도 닫히고, 열리면 초점이 안으로 들어온다.
 *
 * 배경에는 role 도 aria-hidden 도 주지 않는다. role="button" 은 이름 없는 버튼을
 * 하나 만들 뿐이고, aria-hidden 은 그 안에 있는 대화상자까지 스크린 리더에서 지운다.
 */
export function Sheet({
  title,
  closeLabel,
  onClose,
  children,
}: {
  title: string
  closeLabel: string
  onClose: () => void
  children: ReactNode
}) {
  const closeButton = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  useEffect(() => {
    closeButton.current?.focus()
  }, [])

  return (
    <div className="fixed inset-0 z-10 flex items-end justify-center bg-surface-scrim" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="max-h-[75vh] w-full max-w-3xl overflow-auto rounded-t-card bg-surface-panel p-6"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <h2 className="text-title-2 break-all text-ink-title">{title}</h2>
          <button
            ref={closeButton}
            type="button"
            onClick={onClose}
            className="min-h-control-sm shrink-0 rounded-control px-3 text-body text-ink-muted hover:text-ink-title focus-visible:outline-2 focus-visible:outline-brand-primary"
          >
            {closeLabel}
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
