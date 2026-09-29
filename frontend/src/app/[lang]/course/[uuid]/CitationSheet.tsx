'use client'

import { useEffect, useRef, useState } from 'react'
import { fetchContextDocument, type Result } from '@/lib/agent'
import { dict, type Lang } from '@/lib/i18n'

/**
 * 인용 문서를 그 자리에서 연다. 화면을 떠나지 않는 것이 요점이다 — 근거를 보려고
 * 코스를 잃으면, 설명과 근거를 나란히 두고 볼 수 없다.
 */
export function CitationSheet({
  path,
  lang,
  onClose,
}: {
  path: string
  lang: Lang
  onClose: () => void
}) {
  const t = dict(lang).citation
  const [state, setState] = useState<Result<string> | null>(null)
  const closeButton = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    let alive = true
    fetchContextDocument(path)
      .then((result) => alive && setState(result))
      .catch(() => alive && setState({ kind: 'unavailable', status: 0 }))
    return () => {
      alive = false
    }
  }, [path])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  // 시트가 열리면 초점을 안으로 옮긴다. 안 옮기면 키보드 사용자의 초점은 뒤에 남은
  // 칩에 그대로 있고, 화면에는 시트가 떠 있는데 Tab 은 그 아래를 돌아다닌다.
  useEffect(() => {
    closeButton.current?.focus()
  }, [])

  return (
    // 배경은 마우스 편의일 뿐이라 role 을 주지 않는다 — 닫는 경로는 Esc 와 닫기
    // 버튼이고 둘 다 키보드로 닿는다. 배경에 role="button" 을 붙이면 스크린 리더가
    // 읽을 이름 없는 버튼이 하나 생길 뿐이다.
    //
    // aria-hidden 도 여기 붙이면 안 된다 — 시트가 이 안에 있으므로 스크린 리더에서
    // 대화상자째로 사라진다. 처음 그렇게 썼고 테스트가 잡았다.
    <div
      className="fixed inset-0 z-10 flex items-end justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={path}
        className="max-h-[75vh] w-full max-w-3xl overflow-auto rounded-t-xl bg-[var(--background)] p-6"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-4 flex items-baseline justify-between gap-4">
          <h2 className="font-mono text-sm">{path}</h2>
          <button
            ref={closeButton}
            type="button"
            onClick={onClose}
            className="text-sm opacity-60 hover:opacity-100"
          >
            {t.close}
          </button>
        </div>

        {state === null && <p className="text-sm opacity-60">{t.loading}</p>}
        {state?.kind === 'unavailable' && (
          // 빈 시트를 띄우면 "문서에 내용이 없다"로 읽힌다. 번들에 없다는 것은
          // 인용이 잘못되었다는 뜻이라 그 자체가 알려야 할 정보다.
          <p className="text-sm opacity-70">{t.notInBundle(state.status)}</p>
        )}
        {state?.kind === 'loaded' && (
          <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-xs leading-relaxed">
            {state.value}
          </pre>
        )}
      </div>
    </div>
  )
}
