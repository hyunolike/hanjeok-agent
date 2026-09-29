import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as agent from '@/lib/agent'
import { DEMO_COURSES, DEMO_PROVES } from '@/lib/demo-courses'
import { dict } from '@/lib/i18n'
import Home from './page'

// 홈은 접힌 uuid 폼(OpenAnyCourse)을 함께 그린다 — 그쪽이 useRouter 를 쓴다.
vi.mock('next/navigation', () => ({
  notFound: () => {
    throw new Error('notFound')
  },
  useRouter: () => ({ push: vi.fn() }),
}))

// 본문 합계(3,500)와 모델이 받는 바이트(3,600)를 일부러 다르게 둔다 — 화면이 어느
// 쪽을 쓰는지가 이 차이에서만 드러난다.
const listing = {
  documents: [
    { path: 'concepts/congestion-diagnosis.md', bytes: 2000 },
    { path: 'concepts/alternative-scoring.md', bytes: 1500 },
  ],
  systemTextBytes: 3600,
}

/** 서버 컴포넌트다. 기다린 결과를 그린다. */
const renderHome = async (lang: 'ko' | 'en') =>
  render(await Home({ params: Promise.resolve({ lang }) }))

afterEach(() => vi.restoreAllMocks())

describe('홈 브리핑', () => {
  it('코스 목록보다 규칙이 먼저 온다', async () => {
    // 규칙을 모르면 코스 화면의 인용 칩이 왜 거기 있는지 알 수 없고, 누를 이유도 없다.
    vi.spyOn(agent, 'fetchContextList').mockResolvedValue({ kind: 'loaded', value: listing })

    await renderHome('ko')

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      dict('ko').home.ruleTitle,
    )
  })

  it('번들 숫자를 백엔드에서 받아 적는다', async () => {
    // README 에서 베껴 오면 번들이 자라는 순간 화면이 조용히 거짓말을 한다.
    vi.spyOn(agent, 'fetchContextList').mockResolvedValue({ kind: 'loaded', value: listing })

    await renderHome('ko')

    // 문서 본문 합계(3,500)가 아니다. 이 칸의 라벨이 "모델이 매 요청 보는 전부"라고
    // 말하므로, 프롬프트에 실리는 크기여야 한다.
    expect(screen.getByText('문서 2개 · 3,600바이트')).toBeInTheDocument()
    expect(screen.queryByText('문서 2개 · 3,500바이트')).not.toBeInTheDocument()
  })

  it('번들을 못 받아도 브리핑은 읽을 수 있다', async () => {
    // 백엔드가 내려가 있어도 "이것이 무엇인가"는 여전히 대답할 수 있어야 한다.
    // 숫자를 지어내지 않고, 못 받았다고 적는다.
    vi.spyOn(agent, 'fetchContextList').mockResolvedValue({ kind: 'unavailable', status: 503 })

    await renderHome('ko')

    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    expect(screen.getByText(dict('ko').home.bundle.unavailable)).toBeInTheDocument()
  })

  it('설명이 비어 있을 수 있다는 것을 미리 말한다', async () => {
    // 설명 실패는 블록이 조용히 사라지는 것으로 나타난다(스펙 §6.1). 그 빈자리를
    // 만나기 전에 말해 두지 않으면 아무 일도 없었던 것으로 보인다.
    vi.spyOn(agent, 'fetchContextList').mockResolvedValue({ kind: 'loaded', value: listing })

    await renderHome('ko')

    expect(screen.getByText(dict('ko').home.silentFailure)).toBeInTheDocument()
  })

  it('코스마다 무엇을 볼지 적는다', async () => {
    // 여기에는 `kind` 원문이 있었다. 고른 사람에게만 뜻이 있는 내부 식별자다.
    vi.spyOn(agent, 'fetchContextList').mockResolvedValue({ kind: 'loaded', value: listing })

    await renderHome('ko')

    for (const course of DEMO_COURSES) {
      expect(screen.getByText(DEMO_PROVES.ko[course.kind])).toBeInTheDocument()
    }
    expect(screen.queryByText(DEMO_COURSES[0].kind)).not.toBeInTheDocument()
  })

  it('코스 링크가 보고 있는 언어 안에 머문다', async () => {
    // `/course/...` 로 보내면 리다이렉트를 타고 한국어로 되돌아간다.
    vi.spyOn(agent, 'fetchContextList').mockResolvedValue({ kind: 'loaded', value: listing })

    await renderHome('en')

    expect(
      screen.getByRole('link', { name: new RegExp(DEMO_COURSES[0].label) }),
    ).toHaveAttribute('href', `/en/course/${DEMO_COURSES[0].uuid}`)
  })

  it('영어 화면은 코스와 설명이 한국어로 생성된다고 밝힌다', async () => {
    vi.spyOn(agent, 'fetchContextList').mockResolvedValue({ kind: 'loaded', value: listing })

    await renderHome('en')

    expect(screen.getByText(dict('en').home.generatedLanguageNote!)).toBeInTheDocument()
  })
})
