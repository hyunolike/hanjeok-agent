'use client'

import { useState } from 'react'
import { askCourseStream, type AskTurn } from '@/lib/agent'
import { dict, type Dict, type Lang } from '@/lib/i18n'
import { CitationSheet } from './CitationSheet'

type Exchange =
  | { question: string; status: 'streaming'; citations: string[]; text: string; looking: string | null }
  | { question: string; status: 'answered'; answer: string; citations: string[] }
  | { question: string; status: 'failed' }

// 모르는 이름이 와도 화면이 비지 않게 한다 — 서버가 도구를 늘려도 프론트가 먼저
// 깨지지 않는다.
const labelFor = (looking: Dict['ask']['looking'], what: string) =>
  what === 'congestion' || what === 'alternatives' ? looking[what] : looking.fallback

/**
 * 코스에 대해 이어 묻는다.
 *
 * **대화는 여기에만 있다.** 서버는 저장하지 않으므로 이전 turn 을 매 요청 함께
 * 보낸다 — 탭을 닫으면 사라지는 것이 "DB 없음"을 지킨 대가다.
 *
 * 실패한 질문도 목록에 남긴다. 사라지면 사용자는 자기가 뭘 물었는지 잃고, 답이
 * 없었다는 사실도 잃는다.
 */
export function AskBox({ courseUuid, lang }: { courseUuid: string; lang: Lang }) {
  const t = dict(lang).ask
  const [exchanges, setExchanges] = useState<Exchange[]>([])
  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const [openPath, setOpenPath] = useState<string | null>(null)

  async function ask(text: string) {
    const trimmed = text.trim()
    if (!trimmed || asking) return

    setAsking(true)
    setQuestion('')
    // 끝까지 답한 turn 만 이전 대화로 보낸다. 실패하거나 중단된 turn 은 답이 없다.
    const history: AskTurn[] = exchanges.flatMap((e) =>
      e.status === 'answered' ? [{ question: e.question, answer: e.answer }] : [],
    )

    // asking 이 동시 질문을 막으므로 이 자리는 끝날 때까지 이 질문의 것이다.
    const index = exchanges.length
    const put = (next: Exchange) => setExchanges((prev) => prev.map((e, i) => (i === index ? next : e)))
    setExchanges((prev) => [
      ...prev,
      { question: trimmed, status: 'streaming', citations: [], text: '', looking: null },
    ])

    let citations: string[] = []
    let body = ''
    await askCourseStream(courseUuid, trimmed, history, (event) => {
      switch (event.kind) {
        case 'citations':
          citations = event.citations
          put({ question: trimmed, status: 'streaming', citations, text: body, looking: null })
          break
        case 'delta':
          body += event.text
          put({ question: trimmed, status: 'streaming', citations, text: body, looking: null })
          break
        case 'looking':
          // delta 가 아니다 — "답이 시작됐다"는 상태를 만들지 않고, 이미 흐르고
          // 있는 본문(citations/text) 은 그대로 둔 채 안내만 얹는다.
          put({ question: trimmed, status: 'streaming', citations, text: body, looking: event.what })
          break
        case 'done':
          // 본문을 확정하는 조건은 이것 하나뿐이다.
          put({ question: trimmed, status: 'answered', answer: body, citations })
          break
        case 'unavailable':
        case 'aborted':
          // 받은 본문이 있어도 버린다 — 인용은 검증됐지만 문장이 미완이다.
          put({ question: trimmed, status: 'failed' })
          break
      }
    })
    setAsking(false)
  }

  return (
    <section className="space-y-4">
      <h2 className="text-sm font-semibold opacity-70">{t.heading}</h2>

      {exchanges.map((exchange, index) => (
        <div key={index} className="space-y-2 rounded-lg border border-black/10 p-4 dark:border-white/10">
          <p className="text-sm font-medium">{exchange.question}</p>
          {exchange.status === 'failed' ? (
            <p className="text-sm opacity-70">{t.failed}</p>
          ) : (
            <>
              {exchange.status === 'streaming' && exchange.looking && (
                <p className="text-sm opacity-70">{labelFor(t.looking, exchange.looking)}</p>
              )}
              <p className="whitespace-pre-wrap text-sm leading-relaxed opacity-90">
                {exchange.status === 'answered' ? exchange.answer : exchange.text}
              </p>
              <div className="flex flex-wrap gap-2">
                {exchange.citations.map((path) => (
                  <button
                    key={path}
                    type="button"
                    onClick={() => setOpenPath(path)}
                    className="rounded-full border border-black/15 px-2.5 py-0.5 text-xs hover:bg-black/5 dark:border-white/20 dark:hover:bg-white/10"
                  >
                    {path}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      ))}

      {exchanges.length === 0 && (
        <div className="flex flex-wrap gap-2">
          {t.suggestions.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => ask(suggestion)}
              className="rounded-full border border-black/15 px-3 py-1 text-xs hover:bg-black/5 dark:border-white/20 dark:hover:bg-white/10"
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}

      <form
        onSubmit={(event) => {
          event.preventDefault()
          ask(question)
        }}
        className="flex gap-2"
      >
        <label htmlFor="question" className="sr-only">
          {t.heading}
        </label>
        <input
          id="question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder={t.placeholder}
          className="min-w-0 flex-1 rounded border border-black/15 bg-transparent px-3 py-1.5 text-sm dark:border-white/20"
        />
        <button
          type="submit"
          disabled={asking || question.trim().length === 0}
          className="rounded border border-black/15 px-3 py-1.5 text-sm disabled:opacity-40 dark:border-white/20"
        >
          {asking ? t.submitting : t.submit}
        </button>
      </form>

      {openPath && (
        <CitationSheet path={openPath} lang={lang} onClose={() => setOpenPath(null)} />
      )}
    </section>
  )
}
