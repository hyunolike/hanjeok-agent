'use client'

import { LoadingPanel } from '@/components/ui/LoadingPanel'
import { Button } from '@/components/ui/Button'
import { useEffect, useState } from 'react'
import { fetchContextDocument, type Result } from '@/lib/agent'
import { dict, type Lang } from '@/lib/i18n'
import type { ContextEntry } from '@/lib/schema'

/**
 * 번들에 담긴 문서 전부. **위키 전체가 아니다.**
 *
 * 이 화면이 증명하려는 것은 "LLM이 볼 수 있었던 것이 이만큼"이라는 사실이고,
 * 총 바이트를 함께 내는 것이 "벡터 검색이 필요 없는 크기"라는 주장을 화면이
 * 스스로 보이게 하는 방법이다.
 */
export function EvidenceBrowser({
  entries,
  systemTextBytes,
  lang,
}: {
  entries: ContextEntry[]
  /** 모델이 실제로 받는 바이트. 아래 목록의 합보다 크다 — 구분 줄이 더해진다. */
  systemTextBytes: number
  lang: Lang
}) {
  const t = dict(lang).evidence
  const [attempt, setAttempt] = useState(0)
  const [selected, setSelected] = useState(entries[0]?.path ?? null)
  const [body, setBody] = useState<Result<string> | null>(null)

  useEffect(() => {
    if (selected === null) return
    let alive = true
    setBody(null)
    fetchContextDocument(selected)
      .then((result) => alive && setBody(result))
      .catch(() => alive && setBody({ kind: 'unavailable', status: 0 }))
    return () => {
      alive = false
    }
  }, [selected, attempt])

  const totalBytes = entries.reduce((sum, entry) => sum + entry.bytes, 0)

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-title-1 font-semibold">{t.title}</h1>
        <p className="text-body text-ink-muted">
          {t.count(entries.length, systemTextBytes.toLocaleString())}
        </p>
        <p className="text-caption text-ink-muted">{t.sumNote(totalBytes.toLocaleString())}</p>
        {/* 개수와 바이트만 있을 때는 이 화면이 왜 있는지가 없었다. 숫자가 무엇을
            뒷받침하는 숫자인지 적어야 세어 볼 이유가 생긴다. */}
        <p className="max-w-prose text-body leading-relaxed text-ink-muted">{t.why}</p>
      </header>

      <div className="grid gap-6 md:grid-cols-[minmax(0,16rem)_1fr]">
        <ul className="space-y-1 text-body">
          {entries.map((entry) => (
            <li key={entry.path}>
              <button
                type="button"
                onClick={() => setSelected(entry.path)}
                aria-current={entry.path === selected}
                className={`w-full rounded-control px-2 py-1.5 text-left font-mono text-caption hover:bg-surface-subtle ${
                  entry.path === selected ? 'bg-surface-subtle' : ''
                }`}
              >
                <span className="block truncate">{entry.path}</span>
                <span className="text-ink-muted">{entry.bytes.toLocaleString()}B</span>
              </button>
            </li>
          ))}
        </ul>

        <div className="min-w-0">
          {selected === null && <p role="status" className="text-body text-ink-muted">{lang === 'ko' ? '아직 공개된 근거 문서가 없어요.' : 'No source documents have been published yet.'}</p>}
          {body === null && selected !== null && <div aria-busy="true"><LoadingPanel compact title={lang === 'ko' ? '근거 문서를 불러오고 있어요' : 'Loading the source document'} /></div>}
          {body?.kind === 'unavailable' && (
            <div className="space-y-3"><p className="text-body text-ink-muted">{t.loadFailBody(body.status)}</p><Button variant="secondary" size="sm" onClick={() => setAttempt(value => value + 1)}>{lang === 'ko' ? '문서 다시 불러오기' : 'Reload document'}</Button></div>
          )}
          {body?.kind === 'loaded' && (
            <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-caption leading-relaxed">
              {body.value}
            </pre>
          )}
        </div>
      </div>
    </div>
  )
}
