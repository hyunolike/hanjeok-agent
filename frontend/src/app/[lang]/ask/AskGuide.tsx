'use client'

import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Character } from '@/components/guide/Character'
import { CitationChip } from '@/components/guide/CitationChip'
import { PathView } from '@/components/guide/PathView'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Chip } from '@/components/ui/Chip'
import { Field } from '@/components/ui/Field'
import { Notice } from '@/components/ui/Notice'
import { Sheet } from '@/components/ui/Sheet'
import { StepList } from '@/components/ui/StepList'
import { formatSeoul } from '@/lib/format'
import { askGuide, isReplay, type AskOptions } from '@/lib/guide'
import type { DemoKey } from '@/lib/guide-fixtures'
import type { Citation, GuideEvent, GuidePath, Step } from '@/lib/guide-schema'
import { dict, type Lang } from '@/lib/i18n'

type Ending = Extract<GuideEvent, { type: 'done' | 'ask_user' | 'stopped' | 'limited' | 'cut' }>

type Turn = {
  id: number
  question: string
  steps: Step[]
  answer: { text: string; citations: Citation[]; partial: boolean } | null
  path: GuidePath | null
  ending: Ending | null
}

/** 같은 index 로 다시 온 단계는 "진행 중"이 결과로 바뀐 것이다. 덧붙이지 않고 갈아 끼운다. */
function upsertStep(steps: Step[], step: Step): Step[] {
  return steps.some((s) => s.index === step.index)
    ? steps.map((s) => (s.index === step.index ? step : s))
    : [...steps, step]
}

function applyEvent(turn: Turn, event: GuideEvent): Turn {
  switch (event.type) {
    case 'visit':
      return turn
    case 'step':
      return { ...turn, steps: upsertStep(turn.steps, event.step) }
    case 'answer':
      return { ...turn, answer: { text: event.text, citations: event.citations, partial: event.partial } }
    case 'path':
      return { ...turn, path: { nodes: event.nodes, edges: event.edges } }
    default:
      return { ...turn, ending: event }
  }
}

/**
 * 질문을 받고, 단계를 보여 주고, 검증을 통과한 답을 보여 준다.
 *
 * 한 질문은 종결 사건 하나로 끝나고, 입력창은 그때까지 잠긴다. 답 글자는 `answer`
 * 사건으로만 들어온다 — 이 화면에는 검증 전의 글자가 놓일 자리가 없다.
 */
export function AskGuide({
  lang,
  demo,
  ask = askGuide,
}: {
  lang: Lang
  demo?: DemoKey
  /** 테스트가 스트림을 한 사건씩 밀어 넣을 수 있게 한다. */
  ask?: typeof askGuide
}) {
  const t = dict(lang).guide
  const [turns, setTurns] = useState<Turn[]>([])
  const [draft, setDraft] = useState('')
  const [visitId, setVisitId] = useState<string | null>(null)
  const [exportAsOf, setExportAsOf] = useState<string | null>(null)
  const [opened, setOpened] = useState<{ citation: Citation; turn: Turn } | null>(null)
  const [pathOpen, setPathOpen] = useState<number | null>(null)
  const nextId = useRef(0)
  const abort = useRef<AbortController | null>(null)

  const last = turns[turns.length - 1]
  const busy = last !== undefined && last.ending === null

  useEffect(() => () => abort.current?.abort(), [])

  const submit = useCallback(
    (question: string, choice?: number) => {
      const text = question.trim()
      if (text === '' || busy) return
      const id = nextId.current++
      setTurns((prev) => [...prev, { id, question: text, steps: [], answer: null, path: null, ending: null }])
      setDraft('')

      const controller = new AbortController()
      abort.current = controller
      const options: AskOptions = { demo, signal: controller.signal }
      void ask(
        { question: text, visitId, choice },
        (event) => {
          if (event.type === 'visit') {
            setVisitId(event.visit_id)
            setExportAsOf(event.as_of.export)
          }
          setTurns((prev) => prev.map((turn) => (turn.id === id ? applyEvent(turn, event) : turn)))
        },
        options,
      )
    },
    [ask, busy, demo, visitId],
  )

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    submit(draft)
  }

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-3">
        <h1 className="font-display text-display text-ink-title">{t.title}</h1>
        <p className="text-body text-ink-body">{t.lead}</p>
        {exportAsOf && <p className="text-caption text-ink-muted">{t.asOf(formatSeoul(exportAsOf, lang))}</p>}
      </header>

      {isReplay && (
        <Notice tone="info" title={t.replayTitle}>
          {t.replayBody}
        </Notice>
      )}

      {turns.length === 0 && (
        <Card>
          <Character state="waiting" title={t.waitingTitle}>
            <p className="text-body text-ink-body">{t.waitingBody}</p>
          </Character>
          <p className="mt-5 mb-2 text-caption text-ink-muted">{t.examplesLabel}</p>
          <ul className="flex flex-col gap-2">
            {t.examples.map((example) => (
              <li key={example}>
                <Chip onClick={() => submit(example)}>{example}</Chip>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {turns.map((turn) => (
        <article key={turn.id} className="flex flex-col gap-4" aria-busy={turn.ending === null}>
          <p className="self-end rounded-card bg-surface-inverse px-4 py-3 text-body text-ink-inverse">
            {turn.question}
          </p>

          {turn.ending === null && <Character state="looking" title={t.lookingTitle} size="sm" />}

          {turn.steps.length > 0 &&
            (turn.ending?.type === 'done' ? (
              <details className="group">
                <summary className="cursor-pointer text-caption text-ink-muted">
                  {t.stepsSummary(turn.steps.length)}
                </summary>
                <div className="mt-2">
                  <StepList steps={turn.steps} lang={lang} />
                </div>
              </details>
            ) : (
              <StepList steps={turn.steps} lang={lang} />
            ))}

          {turn.answer && turn.ending?.type === 'done' && (
            <Card className="flex flex-col gap-4">
              <Character state="found" title={turn.answer.partial ? t.partialTitle : t.foundTitle} size="sm">
                {turn.answer.partial && <p className="text-caption text-ink-muted">{t.partialBody}</p>}
              </Character>
              <p className="text-body whitespace-pre-wrap text-ink-title" data-testid="answer-text">
                {turn.answer.text}
              </p>
              <div className="flex flex-col gap-2">
                <p className="text-caption text-ink-muted">{t.citationsLabel}</p>
                <ul className="flex flex-wrap gap-2">
                  {turn.answer.citations.map((citation) => (
                    <li key={citation.id}>
                      <CitationChip
                        citation={citation}
                        kindLabel={t.citationKind[citation.kind]}
                        onOpen={(c) => setOpened({ citation: c, turn })}
                      />
                    </li>
                  ))}
                </ul>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-3">
                {turn.path && (
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-expanded={pathOpen === turn.id}
                    onClick={() => setPathOpen(pathOpen === turn.id ? null : turn.id)}
                  >
                    {pathOpen === turn.id ? t.hidePath : t.showPath}
                  </Button>
                )}
                <p className="text-caption text-ink-muted">
                  {t.model(turn.ending.model, (turn.ending.elapsed_ms / 1000).toFixed(1))}
                </p>
              </div>
              {turn.path && pathOpen === turn.id && <PathView path={turn.path} lang={lang} />}
            </Card>
          )}

          {turn.ending?.type === 'ask_user' && (
            <Card>
              <Character state="choose" title={t.chooseTitle}>
                <p className="text-body text-ink-body">{turn.ending.prompt}</p>
                <ul className="flex flex-col gap-2">
                  {turn.ending.candidates.map((candidate) => (
                    <li key={candidate.place_id}>
                      <Chip disabled={busy || turn !== last} onClick={() => submit(turn.question, candidate.place_id)}>
                        {candidate.name} · {candidate.region}
                      </Chip>
                    </li>
                  ))}
                </ul>
              </Character>
            </Card>
          )}

          {turn.ending?.type === 'stopped' && (
            <Card>
              <Character
                state={turn.ending.outcome === 'failed' ? 'failed' : 'no-data'}
                title={
                  turn.ending.outcome === 'failed'
                    ? t.failedTitle
                    : turn.ending.outcome === 'declined'
                      ? t.declinedTitle
                      : t.noDataTitle
                }
              >
                <p className="text-body text-ink-body">{turn.ending.message}</p>
                {turn.ending.outcome === 'failed' && turn === last && (
                  <div>
                    <Button variant="secondary" size="sm" onClick={() => submit(turn.question)}>
                      {t.retry}
                    </Button>
                  </div>
                )}
              </Character>
            </Card>
          )}

          {turn.ending?.type === 'limited' && (
            <Notice tone="warning" title={t.limitTitle}>
              {turn.ending.scope === 'day' ? t.limitDayBody : t.limitBody(Math.ceil(turn.ending.retry_after_s / 60))}
            </Notice>
          )}

          {turn.ending?.type === 'cut' && (
            <Card>
              <Character state="failed" title={t.cutTitle}>
                <p className="text-body text-ink-body">{t.cutBody}</p>
                {turn === last && (
                  <div>
                    <Button variant="secondary" size="sm" onClick={() => submit(turn.question)}>
                      {t.retry}
                    </Button>
                  </div>
                )}
              </Character>
            </Card>
          )}
        </article>
      ))}

      <form onSubmit={onSubmit} className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <Field
          id="guide-question"
          label={t.fieldLabel}
          hideLabel
          className="flex-1"
          value={draft}
          maxLength={500}
          disabled={busy}
          placeholder={turns.length === 0 ? t.fieldPlaceholder : t.followUpPlaceholder}
          onChange={(event) => setDraft(event.target.value)}
        />
        <Button type="submit" disabled={busy || draft.trim() === ''}>
          {t.submit}
        </Button>
      </form>

      {opened && (
        <Sheet title={opened.citation.label} closeLabel={t.close} onClose={() => setOpened(null)}>
          <CitationDetail citation={opened.citation} turn={opened.turn} lang={lang} />
        </Sheet>
      )}
    </div>
  )
}

/** 인용 하나가 어디에서 왔는지. 어느 단계가, 언제 가져왔는지를 그 질문의 기록에서 찾는다. */
function CitationDetail({ citation, turn, lang }: { citation: Citation; turn: Turn; lang: Lang }) {
  const t = dict(lang).guide
  const source = turn.steps.find((step) => step.produced.includes(citation.id))
  return (
    <div className="flex flex-col gap-3 text-body">
      <p className="text-ink-body">{citation.kind === 'record' ? t.citationRecordNote : t.citationPolicyNote}</p>
      <dl className="flex flex-col gap-3">
      <div>
        <dt className="text-caption text-ink-muted">{t.citationId}</dt>
        <dd className="font-mono text-caption break-all text-ink-title">{citation.id}</dd>
      </div>
      {source && (
        <div>
          <dt className="text-caption text-ink-muted">{t.citationFetchedBy}</dt>
          <dd className="text-ink-title">
            {t.stepKind(source.kind)} — {source.summary}
          </dd>
        </div>
      )}
      {source?.as_of && (
        <div>
          <dt className="text-caption text-ink-muted">{t.citationFetchedAt}</dt>
          <dd className="text-ink-title">{formatSeoul(source.as_of, lang)}</dd>
        </div>
      )}
      </dl>
    </div>
  )
}
