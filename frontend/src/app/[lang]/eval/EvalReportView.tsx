import type { ReactNode } from 'react'
import { Card } from '@/components/ui/Card'
import { Notice } from '@/components/ui/Notice'
import { formatSeoul } from '@/lib/format'
import { isReplay, type Loaded } from '@/lib/guide'
import {
  EVAL_KINDS,
  EVAL_METRICS,
  EVAL_STRATEGIES,
  FORBIDDEN_BEHAVIOURS,
  type Aggregate,
  type EvalReport,
} from '@/lib/guide-schema'
import { dict, type Lang } from '@/lib/i18n'
import { SampleList } from './SampleList'

const TH = 'px-3 py-2 text-left text-caption font-medium text-ink-muted'
const TD = 'px-3 py-2 align-top text-body text-ink-title'

/** 좁은 화면에서는 표가 화면 밖으로 나가지 않고 그 안에서 옆으로 밀린다. */
function Table({ caption, children }: { caption: string; children: ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-card border border-line-normal bg-surface-panel">
      <table className="w-full border-collapse [&_tbody_tr]:border-t [&_tbody_tr]:border-line-normal">
        <caption className="sr-only">{caption}</caption>
        {children}
      </table>
    </div>
  )
}

/**
 * 점수 한 칸. **숫자만 놓이는 칸은 없다** — 몇 문항으로 계산했는지가 늘 같이 있다.
 *
 * 매기지 못한 점수는 "채점 못 함"과 그 이유를 쓴다. 0 을 쓰면 "전부 틀렸다"로 읽힌다.
 */
export function ScoreCell({ cell, lang }: { cell: Aggregate; lang: Lang }) {
  const t = dict(lang).evalPage
  if (cell.value === null) {
    return (
      <>
        <span className="text-body-strong text-ink-muted">
          {cell.status === 'not_applicable' ? t.notApplicable : t.notScored}
        </span>
        {cell.reason && <span className="block text-caption text-ink-muted">{cell.reason}</span>}
      </>
    )
  }
  return (
    <>
      <span className="font-mono text-body-strong">{cell.value.toFixed(2)}</span>
      <span className="block text-caption whitespace-nowrap text-ink-muted">{t.scored(cell.n, cell.total)}</span>
    </>
  )
}

export function EvalReportView({ lang, result }: { lang: Lang; result: Loaded<EvalReport> }) {
  const t = dict(lang).evalPage

  const header = (
    <header className="flex flex-col gap-3">
      <h1 className="font-display text-display text-ink-title">{t.title}</h1>
      <p className="text-body text-ink-body">{t.lead}</p>
    </header>
  )

  // 보고서가 없으면 표를 그리지 않는다. 빈 표나 0 으로 찬 표는 "측정했더니 0 이었다"로 읽힌다.
  if (!result.ok) {
    const missing = result.cause === 'not_found'
    return (
      <div className="flex flex-col gap-8">
        {header}
        <Notice tone={missing ? 'info' : 'danger'} title={missing ? t.noReportTitle : t.unavailableTitle}>
          {missing ? t.noReportBody : t.unavailableBody}
        </Notice>
      </div>
    )
  }

  const report = result.data
  const provenance: [string, string][] = [
    [
      t.provExport,
      t.provExportValue(formatSeoul(report.export_as_of, lang), report.generation, report.export_sha256.slice(0, 12)),
    ],
    [t.provQuestions, t.provQuestionsValue(report.question_set, report.question_set_revision, report.question_count)],
    [t.provAnswerModel, report.answer_model],
    [t.provJudgeModel, report.judge_model],
    [t.provLive, formatSeoul(report.live_recorded_at, lang)],
    [t.provRun, formatSeoul(report.timestamp, lang)],
  ]

  return (
    <div className="flex flex-col gap-10">
      {header}
      {isReplay && (
        <Notice tone="info" title={dict(lang).guide.replayTitle}>
          {t.replayBody}
        </Notice>
      )}

      <section className="flex flex-col gap-3" aria-labelledby="eval-provenance">
        <h2 id="eval-provenance" className="text-title-1 text-ink-title">
          {t.provenance}
        </h2>
        <Card>
          <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-[auto_1fr]">
            {provenance.map(([name, value]) => (
              <div key={name} className="contents">
                <dt className="text-caption text-ink-muted">{name}</dt>
                <dd className="text-body break-words text-ink-title">{value}</dd>
              </div>
            ))}
          </dl>
        </Card>
      </section>

      <section className="flex flex-col gap-3" aria-labelledby="eval-metrics">
        <h2 id="eval-metrics" className="text-title-1 text-ink-title">
          {t.metricsTitle}
        </h2>
        <p className="text-caption text-ink-muted">{t.strategyNote}</p>
        <Table caption={t.metricsTitle}>
          <thead>
            <tr>
              <th scope="col" className={TH}>
                {t.metricColumn}
              </th>
              {EVAL_STRATEGIES.map((strategy) => (
                <th key={strategy} scope="col" className={TH}>
                  {t.strategy[strategy]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {EVAL_METRICS.map((metric) => (
              <tr key={metric}>
                <th scope="row" className={`${TD} text-left font-normal`}>
                  <span className="text-body-strong">{t.metric[metric]}</span>
                  <span className="block text-caption text-ink-muted">{t.metricNote[metric]}</span>
                </th>
                {EVAL_STRATEGIES.map((strategy) => (
                  <td key={strategy} className={TD} data-testid={`metric-${metric}-${strategy}`}>
                    <ScoreCell cell={report.strategies[strategy].metrics[metric]} lang={lang} />
                  </td>
                ))}
              </tr>
            ))}
            <tr>
              <th scope="row" className={`${TD} text-left text-body-strong`}>
                {t.abstentionTitle}
              </th>
              {EVAL_STRATEGIES.map((strategy) => {
                const { unanswerable_correct, unanswerable_total } = report.strategies[strategy].abstention
                return (
                  <td key={strategy} className={TD} data-testid={`abstention-${strategy}`}>
                    {t.abstention(unanswerable_correct, unanswerable_total)}
                  </td>
                )
              })}
            </tr>
          </tbody>
        </Table>
      </section>

      <section className="flex flex-col gap-3" aria-labelledby="eval-identical">
        <h2 id="eval-identical" className="text-title-1 text-ink-title">
          {t.identicalTitle}
        </h2>
        <p className="text-body text-ink-body">{t.identicalBody}</p>
      </section>

      <section className="flex flex-col gap-3" aria-labelledby="eval-forbidden">
        <h2 id="eval-forbidden" className="text-title-1 text-ink-title">
          {t.forbiddenTitle}
        </h2>
        <p className="text-caption text-ink-muted">{t.forbiddenLead}</p>
        <Table caption={t.forbiddenTitle}>
          <thead>
            <tr>
              <th scope="col" className={TH}>
                {t.behaviourColumn}
              </th>
              {EVAL_STRATEGIES.map((strategy) => (
                <th key={strategy} scope="col" className={TH}>
                  {t.strategy[strategy]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {FORBIDDEN_BEHAVIOURS.map((behaviour) => (
              <tr key={behaviour}>
                <th scope="row" className={`${TD} text-left font-normal`}>
                  {t.behaviour[behaviour]}
                  <span className="block font-mono text-caption text-ink-muted">{behaviour}</span>
                </th>
                {EVAL_STRATEGIES.map((strategy) => {
                  const counted = report.strategies[strategy].forbidden[behaviour]
                  return (
                    <td
                      key={strategy}
                      className={`${TD} ${counted && counted.occurrences > 0 ? 'text-status-danger-text' : ''} ${counted ? '' : 'text-ink-muted'}`}
                      data-testid={`forbidden-${behaviour}-${strategy}`}
                    >
                      {counted ? t.occurrences(counted.occurrences, counted.runs) : t.notCounted}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </Table>
      </section>

      <section className="flex flex-col gap-3" aria-labelledby="eval-by-kind">
        <h2 id="eval-by-kind" className="text-title-1 text-ink-title">
          {t.byKindTitle}
        </h2>
        <Table caption={t.byKindTitle}>
          <thead>
            <tr>
              <th scope="col" className={TH}>
                {t.kindColumn}
              </th>
              <th scope="col" className={TH}>
                {t.strategyColumn}
              </th>
              {EVAL_METRICS.map((metric) => (
                <th key={metric} scope="col" className={TH}>
                  {t.metric[metric]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {EVAL_KINDS.flatMap((kind) =>
              EVAL_STRATEGIES.map((strategy, index) => {
                const cells = EVAL_METRICS.map((metric) => report.strategies[strategy].by_kind[kind][metric])
                // 줄 전체가 같은 이유로 비어 있으면 한 칸으로 합친다. 같은 문장을 여섯 번 읽게 하지 않는다.
                const blank =
                  cells.every((cell) => cell.value === null && cell.reason === cells[0].reason) && cells[0]
                return (
                  <tr key={`${kind}-${strategy}`}>
                    {index === 0 && (
                      <th
                        scope="rowgroup"
                        rowSpan={EVAL_STRATEGIES.length}
                        className={`${TD} text-left text-body-strong whitespace-nowrap`}
                      >
                        {t.kind[kind]}
                      </th>
                    )}
                    <th scope="row" className={`${TD} text-left font-normal whitespace-nowrap`}>
                      {t.strategy[strategy]}
                    </th>
                    {blank ? (
                      <td colSpan={EVAL_METRICS.length} className={TD} data-testid={`kind-${kind}-all-${strategy}`}>
                        <ScoreCell cell={blank} lang={lang} />
                      </td>
                    ) : (
                      EVAL_METRICS.map((metric, column) => (
                        <td
                          key={metric}
                          className={`${TD} ${cells[column].value === null ? 'min-w-40' : ''}`}
                          data-testid={`kind-${kind}-${metric}-${strategy}`}
                        >
                          <ScoreCell cell={cells[column]} lang={lang} />
                        </td>
                      ))
                    )}
                  </tr>
                )
              }),
            )}
          </tbody>
        </Table>
      </section>

      <section className="flex flex-col gap-3" aria-labelledby="eval-limitations">
        <h2 id="eval-limitations" className="text-title-1 text-ink-title">
          {t.limitationsTitle}
        </h2>
        <ul className="flex list-disc flex-col gap-1 pl-5 text-body text-ink-body">
          {report.limitations.map((limitation) => (
            <li key={limitation}>{limitation}</li>
          ))}
        </ul>
      </section>

      <section className="flex flex-col gap-3" aria-labelledby="eval-samples">
        <h2 id="eval-samples" className="text-title-1 text-ink-title">
          {t.samplesTitle}
        </h2>
        <p className="text-caption text-ink-muted">{t.samplesLead}</p>
        <SampleList lang={lang} reportId={report.report_id} questions={report.questions} />
      </section>
    </div>
  )
}
