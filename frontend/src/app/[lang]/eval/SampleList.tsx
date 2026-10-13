'use client'

import { useRef, useState } from 'react'
import { Badge } from '@/components/ui/Badge'
import { Notice } from '@/components/ui/Notice'
import { Sheet } from '@/components/ui/Sheet'
import { StepList } from '@/components/ui/StepList'
import { fetchEvalSample, type Loaded } from '@/lib/guide'
import { EVAL_METRICS, EVAL_STRATEGIES, type EvalReport, type EvalSample } from '@/lib/guide-schema'
import { dict, type Lang } from '@/lib/i18n'

type Opened = { question: string; result: Loaded<EvalSample> | null }

/** 문항 하나를 열어 두 방식의 답, 건넨 근거, 점수를 나란히 본다. */
export function SampleList({
  lang,
  reportId,
  questions,
  load = fetchEvalSample,
}: {
  lang: Lang
  reportId: string
  questions: EvalReport['questions']
  load?: typeof fetchEvalSample
}) {
  const t = dict(lang).evalPage
  const [opened, setOpened] = useState<Opened | null>(null)
  const latest = useRef(0)

  const open = (questionId: string, question: string) => {
    const ticket = ++latest.current
    setOpened({ question, result: null })
    void load(reportId, questionId).then((result) => {
      if (latest.current === ticket) setOpened({ question, result })
    })
  }

  const close = () => {
    latest.current++
    setOpened(null)
  }

  return (
    <>
      <ul className="flex flex-col gap-2">
        {questions.map((item) => (
          <li key={item.question_id}>
            <button
              type="button"
              onClick={() => open(item.question_id, item.question)}
              className="flex min-h-control-md w-full flex-wrap items-center gap-x-3 gap-y-1 rounded-control border border-line-normal bg-surface-panel px-4 py-2 text-left text-body text-ink-title transition-colors hover:border-brand-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-primary"
            >
              <span className="flex-1">{item.question}</span>
              <Badge>{t.kind[item.kind]}</Badge>
            </button>
          </li>
        ))}
      </ul>

      {opened && (
        <Sheet title={opened.question} closeLabel={dict(lang).guide.close} onClose={close}>
          {opened.result === null && (
            <p role="status" className="text-body text-ink-muted">
              {dict(lang).graph.loading}
            </p>
          )}
          {opened.result && !opened.result.ok && <Notice tone="danger">{t.sampleFailed}</Notice>}
          {opened.result?.ok && <SampleDetail lang={lang} sample={opened.result.data} />}
        </Sheet>
      )}
    </>
  )
}

function SampleDetail({ lang, sample }: { lang: Lang; sample: EvalSample }) {
  const t = dict(lang).evalPage
  return (
    <div className="grid gap-6 sm:grid-cols-2">
      {EVAL_STRATEGIES.map((strategy) => {
        const arm = sample.strategies[strategy]
        return (
          <section key={strategy} className="flex min-w-0 flex-col gap-4" aria-label={t.strategy[strategy]}>
            <h3 className="text-title-2 text-ink-title">{t.strategy[strategy]}</h3>

            {arm.answer !== null ? (
              <p className="text-body whitespace-pre-wrap text-ink-title">{arm.answer}</p>
            ) : (
              <p className="text-body text-ink-muted">{t.sampleDeclined(arm.cause ?? arm.outcome)}</p>
            )}

            {arm.forbidden.length > 0 && (
              <div className="flex flex-col gap-1">
                <p className="text-caption text-ink-muted">{t.sampleForbidden}</p>
                <ul className="flex flex-wrap gap-2">
                  {arm.forbidden.map((behaviour) => (
                    <li key={behaviour}>
                      <Badge tone="danger">{t.behaviour[behaviour]}</Badge>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex flex-col gap-2">
              <p className="text-caption text-ink-muted">
                {arm.passages.length > 0 ? t.samplePassages(arm.passages.length) : t.sampleNoPassages}
              </p>
              <ul className="flex flex-col gap-2">
                {arm.passages.map((passage) => (
                  <li key={passage.id} className="rounded-control border border-line-normal px-3 py-2">
                    <p className="font-mono text-caption break-all text-ink-muted">{passage.id}</p>
                    <p className="text-body text-ink-body">{passage.text}</p>
                  </li>
                ))}
              </ul>
            </div>

            <div className="flex flex-col gap-2">
              <p className="text-caption text-ink-muted">{t.sampleScores}</p>
              <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-body">
                {EVAL_METRICS.map((metric) => {
                  const score = arm.scores[metric]
                  return (
                    <div key={metric} className="contents">
                      <dt className="text-ink-body">{t.metric[metric]}</dt>
                      <dd className={score.value === null ? 'text-ink-muted' : 'font-mono text-ink-title'}>
                        {score.value !== null
                          ? score.value.toFixed(2)
                          : score.status === 'not_applicable'
                            ? t.notApplicable
                            : t.notScored}
                      </dd>
                    </div>
                  )
                })}
              </dl>
            </div>

            <details>
              <summary className="cursor-pointer text-caption text-ink-muted">{t.sampleSteps}</summary>
              <div className="mt-2">
                <StepList steps={arm.steps} lang={lang} />
              </div>
            </details>
          </section>
        )
      })}
    </div>
  )
}
