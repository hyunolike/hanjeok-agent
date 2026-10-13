import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { fetchEvalReport, fetchEvalSample } from '@/lib/guide'
import { EvalReportView } from './EvalReportView'
import { SampleList } from './SampleList'

const report = await fetchEvalReport({ baseUrl: '' })
if (!report.ok) throw new Error('녹화한 보고서가 계약에 맞지 않는다')

const loadRecorded: typeof fetchEvalSample = (reportId, questionId) =>
  fetchEvalSample(reportId, questionId, { baseUrl: '' })

describe('EvalReportView', () => {
  it('무엇으로 잰 것인지 한 곳에 적는다', () => {
    render(<EvalReportView lang="ko" result={report} />)
    expect(screen.getByText(/gen-replay-0001 · 000000000000$/)).toBeInTheDocument()
    expect(screen.getByText('hanjeok-replay r1 · 12문항')).toBeInTheDocument()
    expect(screen.getByText('답한 모델')).toBeInTheDocument()
    expect(screen.getByText('혼잡 예보를 녹화한 시각')).toBeInTheDocument()
  })

  it('모든 점수 옆에 몇 문항으로 계산했는지 있다', () => {
    render(<EvalReportView lang="ko" result={report} />)
    for (const cell of screen.getAllByTestId(/^metric-/)) {
      expect(cell).toHaveTextContent(/\d\.\d\d\d+문항 중 \d+문항/)
    }
    expect(screen.getByTestId('metric-context_recall-graph')).toHaveTextContent('10문항 중 10문항')
    // 채점하지 못한 문항은 분모에 남고 분자에서 빠진다.
    expect(screen.getByTestId('metric-faithfulness-graph')).toHaveTextContent('10문항 중 8문항')
    expect(screen.getByTestId('metric-faithfulness-vector')).toHaveTextContent('10문항 중 9문항')
  })

  it('매기지 못한 점수는 0 이 아니라 "채점 못 함"과 그 이유다', () => {
    render(<EvalReportView lang="ko" result={report} />)
    const cell = screen.getByTestId('kind-policy-faithfulness-graph')
    expect(cell).toHaveTextContent('채점 못 함')
    expect(cell).toHaveTextContent('판정 모델 호출이 실패해')
    expect(cell).not.toHaveTextContent(/0\.00|^0$/)

    const unsupported = screen.getByTestId('kind-unsupported-all-vector')
    expect(unsupported).toHaveTextContent('해당 없음')
    expect(unsupported).not.toHaveTextContent(/\d\.\d\d/)
  })

  it('금지 행동은 검사한 수와 함께 센다', () => {
    render(<EvalReportView lang="ko" result={report} />)
    expect(screen.getByTestId('forbidden-UNCITED_CLAIM-vector')).toHaveTextContent('1건 · 12문항 검사')
    expect(screen.getByTestId('forbidden-INVENTED_PLACE-graph')).toHaveTextContent('0건 · 12문항 검사')
    expect(screen.getByTestId('abstention-graph')).toHaveTextContent('2문항 중 2문항을 거절')
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
    expect(screen.getByTestId('metric-faithfulness-graph')).toHaveTextContent('8 of 10 questions')
    expect(screen.getByTestId('kind-policy-faithfulness-graph')).toHaveTextContent('Not scored')
  })
})

describe('SampleList', () => {
  const renderList = (load = loadRecorded) =>
    render(<SampleList lang="ko" reportId={report.data.report_id} questions={report.data.questions} load={load} />)

  it('문항을 열면 두 방식의 답, 건넨 근거, 점수가 나란히 있다', async () => {
    renderList()
    await userEvent.click(screen.getByRole('button', { name: /가람궁과 이어진 곳 중 솔내구에 있는 곳은/ }))

    const sheet = await screen.findByRole('dialog')
    const vector = await within(sheet).findByRole('region', { name: '글 유사도만' })
    const graph = within(sheet).getByRole('region', { name: '연관 링크까지' })
    expect(vector).toHaveTextContent('솔내구에 있는 곳을 찾지 못했습니다')
    expect(vector).toHaveTextContent('건넨 근거 2건')
    expect(graph).toHaveTextContent('물빛 서원과 달맞이 숲길이 솔내구에 있습니다')
    expect(graph).toHaveTextContent('hanjeok:related/101')
    expect(graph).toHaveTextContent('0.82')
  })

  it('답하지 않은 문항은 이유를 적고 점수를 0 으로 쓰지 않는다', async () => {
    renderList()
    await userEvent.click(screen.getByRole('button', { name: /가람궁 입장료는 얼마야/ }))
    const sheet = await screen.findByRole('dialog')
    const vector = await within(sheet).findByRole('region', { name: '글 유사도만' })
    expect(vector).toHaveTextContent('답하지 않음 (unsupported_topic)')
    expect(vector).toHaveTextContent('건넨 근거가 없습니다.')
    expect(vector).not.toHaveTextContent(/0\.00/)
  })

  it('문항을 못 받으면 그렇게 말한다', async () => {
    renderList(async () => ({ ok: false, cause: 'unavailable' }))
    await userEvent.click(screen.getAllByRole('button')[0])
    expect(await screen.findByText('이 문항을 불러오지 못했습니다.')).toBeInTheDocument()
  })
})
