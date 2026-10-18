import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as agent from '@/lib/agent'
import * as guide from '@/lib/guide'
import { DEMO_COURSES, DEMO_PROVES } from '@/lib/demo-courses'
import { RECORDED_EVAL_REPORT } from '@/lib/guide-data-fixtures'
import { evalReportSchema } from '@/lib/guide-schema'
import { dict } from '@/lib/i18n'
import Home from './page'

// 홈은 접힌 uuid 폼(OpenAnyCourse)을 함께 그린다 — 그쪽이 useRouter 를 쓴다.
vi.mock('next/navigation', () => ({
  notFound: () => {
    throw new Error('notFound')
  },
  useRouter: () => ({ push: vi.fn() }),
}))

const report = evalReportSchema.parse(RECORDED_EVAL_REPORT)
const loaded = () => {
  // 코스 설명기 기록(접힌 영역)이 번들 목록을 읽는다. 홈 숫자와는 상관없다.
  vi.spyOn(agent, 'fetchContextList').mockResolvedValue({ kind: 'unavailable', status: 0 })
  return vi.spyOn(guide, 'fetchEvalReport').mockResolvedValue({ ok: true, data: report })
}

/** 서버 컴포넌트다. 기다린 결과를 그린다. */
const renderHome = async (lang: 'ko' | 'en') =>
  render(await Home({ params: Promise.resolve({ lang }) }))

afterEach(() => vi.restoreAllMocks())

describe('홈 브리핑', () => {
  it('이 사이트가 한적 안의 안내 에이전트라고 먼저 말한다', async () => {
    // 예전 홈은 앞서 만든 코스 설명기를 소개했다. 처음 온 사람은 이곳이 한적의 무엇인지 몰랐다.
    loaded()

    await renderHome('ko')

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('대신 갈 곳을 들어 보세요')
    expect(screen.getByRole('heading', { name: dict('ko').home.roleTitle })).toBeInTheDocument()
    expect(screen.getByText(dict('ko').home.scopeNo)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: dict('ko').home.bannerCta })).toHaveAttribute('href', '/ko/ask')
    expect(screen.getByRole('link', { name: dict('ko').home.bannerSecondary })).toHaveAttribute('href', '#demo-courses')
  })

  it('숫자를 공개한 평가 보고서에서 읽어 적는다', async () => {
    // 손으로 적어 두면 다음 평가에서 홈과 평가 화면이 다른 말을 한다.
    loaded()

    await renderHome('ko')

    const graph = report.strategies.graph
    expect(screen.getByText(`필요한 레코드 ${Math.round(graph.metrics.id_recall.value! * 1000) / 10}% 확보`)).toBeInTheDocument()
    expect(screen.getByText(`${graph.abstention.unanswerable_total}문항 중 ${graph.abstention.unanswerable_correct}문항 거절`)).toBeInTheDocument()
    const total = Object.values(graph.forbidden).reduce((sum, entry) => sum + (entry?.occurrences ?? 0), 0)
    expect(screen.getByText(`금지 행동 ${total}건`)).toBeInTheDocument()
  })

  it('보고서를 못 받아도 소개는 읽을 수 있다', async () => {
    // 숫자를 지어내지 않고, 못 받았다고 적는다.
    vi.spyOn(agent, 'fetchContextList').mockResolvedValue({ kind: 'unavailable', status: 0 })
    vi.spyOn(guide, 'fetchEvalReport').mockResolvedValue({ ok: false, cause: 'unavailable' })

    await renderHome('ko')

    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    expect(screen.getByText(dict('ko').home.metricsUnavailable, { exact: false })).toBeInTheDocument()
  })

  it('설명이 비어 있을 수 있다는 것을 미리 말한다', async () => {
    // 설명 실패는 블록이 조용히 사라지는 것으로 나타난다(스펙 §6.1). 그 빈자리를
    // 만나기 전에 말해 두지 않으면 아무 일도 없었던 것으로 보인다.
    loaded()

    await renderHome('ko')

    expect(screen.getByText(dict('ko').home.silentFailure)).toBeInTheDocument()
  })

  it('코스마다 무엇을 볼지 적는다', async () => {
    // 여기에는 `kind` 원문이 있었다. 고른 사람에게만 뜻이 있는 내부 식별자다.
    loaded()

    await renderHome('ko')

    for (const course of DEMO_COURSES) {
      expect(screen.getByText(DEMO_PROVES.ko[course.kind])).toBeInTheDocument()
    }
    expect(screen.queryByText(DEMO_COURSES[0].kind)).not.toBeInTheDocument()
  })

  it('코스 링크가 보고 있는 언어 안에 머문다', async () => {
    // `/course/...` 로 보내면 리다이렉트를 타고 한국어로 되돌아간다.
    loaded()

    await renderHome('en')

    expect(
      screen.getByRole('link', { name: new RegExp(DEMO_COURSES[0].label) }),
    ).toHaveAttribute('href', `/en/course/${DEMO_COURSES[0].uuid}`)
  })

  it('영어 화면은 코스와 설명이 한국어로 생성된다고 밝힌다', async () => {
    loaded()

    await renderHome('en')

    expect(screen.getByText(dict('en').home.generatedLanguageNote!)).toBeInTheDocument()
  })

  it('질문이 답이 되는 흐름을 설명용이라고 밝히고 보여 준다', async () => {
    loaded()
    await renderHome('ko')
    expect(screen.getByRole('heading', { name: '질문 한 번이 답이 되기까지' })).toBeInTheDocument()
    expect(screen.getByText(/실제 요청이나 서버 상태를 표시하지 않아요/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '재생' })).toBeInTheDocument()
  })

  it('코스 설명기의 옛 숫자는 접힌 기록 안에만 있다', async () => {
    // 에이전트의 성적으로 읽히면 안 된다. 접힌 영역의 제목이 그것이 무엇인지 말한다.
    loaded()
    await renderHome('ko')
    const summary = screen.getByText('기존 코스 설명기의 규칙과 검증 기록')
    expect(summary.closest('details')).toContainElement(screen.getByText(dict('ko').explainer.forbidden.value))
  })
})
