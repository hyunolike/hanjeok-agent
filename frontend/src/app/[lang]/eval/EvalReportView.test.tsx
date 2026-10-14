import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { fetchEvalReport, fetchEvalSample, type Loaded } from '@/lib/guide'
import { evalReportSchema, evalSampleSchema, type EvalReport } from '@/lib/guide-schema'
import { EvalReportView } from './EvalReportView'
import { SampleList } from './SampleList'

/**
 * 화면 테스트는 서버 쪽 테스트가 만든 고정 보고서를 쓴다
 * (`bench/tests/fixtures/guide-report/`). 데모가 보여 주는 보고서는 공개할 때마다
 * 숫자가 바뀌므로, 거기에 단언을 걸면 화면이 멀쩡해도 테스트가 깨진다.
 */
const fixtures = join(process.cwd(), '..', 'bench', 'tests', 'fixtures', 'guide-report')
const fixed = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'))
const report: Loaded<EvalReport> = { ok: true, data: evalReportSchema.parse(fixed('report.json')) }
const sample = evalSampleSchema.parse(fixed('sample.json'))

const loadRecorded: typeof fetchEvalSample = async (_reportId, questionId) =>
  questionId === sample.question_id ? { ok: true, data: sample } : { ok: false, cause: 'not_found' }

describe('EvalReportView', () => {
  it('무엇으로 잰 것인지 한 곳에 적는다', () => {
    render(<EvalReportView lang="ko" result={report} />)
    expect(screen.getByText(/gen-test · aaaaaaaaaaaa$/)).toBeInTheDocument()
    expect(screen.getByText('hanjeok-synthetic-v1 1cf4ae75a886 · 12문항')).toBeInTheDocument()
    expect(screen.getByText('답한 모델')).toBeInTheDocument()
    expect(screen.getByText('혼잡 예보를 녹화한 시각')).toBeInTheDocument()
  })

  it('모든 점수 옆에 몇 문항으로 계산했는지 있다', () => {
    render(<EvalReportView lang="ko" result={report} />)
    expect(screen.getByTestId('metric-faithfulness-graph')).toHaveTextContent('0.5010문항 중 10문항')
    expect(screen.getByTestId('metric-id_recall-graph')).toHaveTextContent('0.3710문항 중 10문항')
    // 채점하지 못한 문항은 분모에 남고 분자에서 빠진다.
    expect(screen.getByTestId('metric-context_precision-vector')).toHaveTextContent('0.5010문항 중 3문항')
  })

  it('매기지 못한 점수는 0 이 아니라 "채점 못 함"과 그 이유다', () => {
    render(<EvalReportView lang="ko" result={report} />)
    const cell = screen.getByTestId('metric-context_recall-graph')
    expect(cell).toHaveTextContent('채점 못 함')
    expect(cell).toHaveTextContent('기준 글을 만들 수 없습니다')
    expect(cell).not.toHaveTextContent(/\d\.\d\d/)

    const unsupported = screen.getByTestId('kind-unsupported-all-vector')
    expect(unsupported).toHaveTextContent('해당 없음')
    expect(unsupported).not.toHaveTextContent(/\d\.\d\d/)
  })

  it('금지 행동은 검사한 수와 함께 센다', () => {
    render(<EvalReportView lang="ko" result={report} />)
    expect(screen.getByTestId('forbidden-UNCITED_CLAIM-vector')).toHaveTextContent('0건 · 12문항 검사')
    expect(screen.getByTestId('abstention-graph')).toHaveTextContent('2문항 중 2문항을 거절')
  })

  it('한 건이라도 나온 금지 행동은 숫자로 드러난다', () => {
    const flagged = structuredClone(report)
    if (!flagged.ok) throw new Error()
    flagged.data.strategies.vector.forbidden.INVENTED_PLACE.occurrences = 3
    render(<EvalReportView lang="ko" result={flagged} />)
    expect(screen.getByTestId('forbidden-INVENTED_PLACE-vector')).toHaveTextContent('3건 · 12문항 검사')
  })

  it('두 방식에서 무엇을 같게 두었는지와 한계를 적는다', () => {
    render(<EvalReportView lang="ko" result={report} />)
    expect(screen.getByText(/다른 것은 모델에게 건넨 근거뿐입니다/)).toBeInTheDocument()
    expect(screen.getByText(/문항 하나에 크게 흔들립니다/)).toBeInTheDocument()
  })

  it('공개한 평가가 없으면 그렇게 말하고 표를 그리지 않는다', () => {
    render(<EvalReportView lang="ko" result={{ ok: false, cause: 'not_found' }} />)
    expect(screen.getByText('공개한 평가가 아직 없습니다')).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(document.body).not.toHaveTextContent(/0\.00/)
  })

  it('보고서를 못 받으면 없다고 하지 않고 못 받았다고 한다', () => {
    render(<EvalReportView lang="ko" result={{ ok: false, cause: 'unavailable' }} />)
    expect(screen.getByRole('alert')).toHaveTextContent('보고서를 불러오지 못했습니다')
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('영어 화면에서도 같은 표가 나온다', () => {
    render(<EvalReportView lang="en" result={report} />)
    expect(screen.getByTestId('metric-context_precision-vector')).toHaveTextContent('3 of 10 questions')
    expect(screen.getByTestId('metric-context_recall-graph')).toHaveTextContent('Not scored')
  })
})

describe('데모가 보여 주는 보고서', () => {
  it('저장해 둔 보고서가 계약에 맞고, 목록의 문항이 전부 열린다', async () => {
    const stored = await fetchEvalReport({ baseUrl: '' })
    if (!stored.ok) throw new Error('저장한 보고서가 계약에 맞지 않는다')
    render(<EvalReportView lang="ko" result={stored} />)
    expect(screen.getAllByRole('table')).toHaveLength(3)
    for (const { question_id } of stored.data.questions) {
      expect((await fetchEvalSample(stored.data.report_id, question_id, { baseUrl: '' })).ok, question_id).toBe(true)
    }
  })
})

describe('SampleList', () => {
  const renderList = (load = loadRecorded) =>
    render(<SampleList lang="ko" reportId={report.data.report_id} questions={report.data.questions} load={load} />)

  it('문항을 열면 두 방식의 답, 건넨 근거, 점수가 나란히 있다', async () => {
    renderList()
    await userEvent.click(screen.getByRole('button', { name: /가람궁과 이어진 장소 중 솔내구에 있는 곳은/ }))

    const sheet = await screen.findByRole('dialog')
    const vector = await within(sheet).findByRole('region', { name: '글 유사도만' })
    const graph = within(sheet).getByRole('region', { name: '연관 링크까지' })
    expect(vector).toHaveTextContent('건넨 근거 1건')
    expect(graph).toHaveTextContent('건넨 근거 8건')
    expect(graph).toHaveTextContent('hanjeok:related/101')
    expect(vector).not.toHaveTextContent('hanjeok:related/101')
    // 판정이 실패한 지표는 문항 화면에서도 0 이 아니다.
    expect(graph).toHaveTextContent('근거 재현율채점 못 함')
    expect(graph).toHaveTextContent('레코드 재현율1.00')
  })

  it('답하지 않은 문항은 이유를 적고 점수를 0 으로 쓰지 않는다', async () => {
    const declined = structuredClone(sample)
    const none = { value: null, status: 'not_applicable' as const, reason: null }
    declined.strategies.vector = {
      ...declined.strategies.vector,
      outcome: 'declined',
      cause: 'unsupported_topic',
      answer: null,
      passages: [],
      scores: Object.fromEntries(Object.keys(declined.strategies.vector.scores).map((m) => [m, none])) as never,
    }
    renderList(async () => ({ ok: true, data: declined }))
    await userEvent.click(screen.getAllByRole('button')[0])

    const vector = await within(await screen.findByRole('dialog')).findByRole('region', { name: '글 유사도만' })
    expect(vector).toHaveTextContent('답하지 않음 (unsupported_topic)')
    expect(vector).toHaveTextContent('건넨 근거가 없습니다.')
    expect(vector).toHaveTextContent('해당 없음')
    expect(vector).not.toHaveTextContent(/\d\.\d\d/)
  })

  it('문항을 못 받으면 그렇게 말한다', async () => {
    renderList(async () => ({ ok: false, cause: 'unavailable' }))
    await userEvent.click(screen.getAllByRole('button')[0])
    expect(await screen.findByText('이 문항을 불러오지 못했습니다.')).toBeInTheDocument()
  })
})
