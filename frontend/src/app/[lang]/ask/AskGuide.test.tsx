import { act, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { askGuide } from '@/lib/guide'
import type { DemoKey } from '@/lib/guide-fixtures'
import type { GuideEvent } from '@/lib/guide-schema'
import { AskGuide, WAKING_AFTER_MS } from './AskGuide'

/** 녹화본을 지연 없이 재생한다. 화면은 실제 클라이언트와 같은 사건을 받는다. */
const instant: typeof askGuide = (request, onEvent, options) =>
  askGuide(request, onEvent, { ...options, baseUrl: '', stepDelayMs: 0 })

function renderDemo(demo: DemoKey) {
  render(<AskGuide lang="ko" demo={demo} ask={instant} />)
}

async function askFirstExample() {
  await userEvent.click(screen.getByRole('button', { name: '이번 토요일 가람궁 대신 조용한 곳 있어?' }))
}

describe('AskGuide', () => {
  it('질문 전에는 무엇을 물을 수 있는지 글로 말한다', () => {
    renderDemo('answered')
    expect(screen.getByText('무엇이 궁금하세요?')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /가람궁|대안 장소|솔내/ })).toHaveLength(4)
    expect(screen.getByRole('button', { name: '물어보기' })).toBeDisabled()
  })

  it('답과 함께 두 종류의 인용을 구분해 보여 준다', async () => {
    renderDemo('answered')
    await askFirstExample()

    expect(await screen.findByTestId('answer-text')).toHaveTextContent('솔내 한옥마을, 물빛 서원, 달맞이 숲길')
    expect(screen.getAllByRole('button', { name: /한적 레코드/ })).toHaveLength(2)
    expect(screen.getAllByRole('button', { name: /정책 문서/ })).toHaveLength(2)
    expect(screen.getByText('4단계를 거쳤습니다')).toBeInTheDocument()
  })

  it('인용을 누르면 어느 단계가 언제 가져왔는지 연다', async () => {
    renderDemo('answered')
    await askFirstExample()
    await userEvent.click(await screen.findByRole('button', { name: /가람궁 혼잡 예보/ }))

    const sheet = screen.getByRole('dialog')
    expect(within(sheet).getByText('hanjeok:congestion/101@2026-10-17')).toBeInTheDocument()
    expect(within(sheet).getByText(/혼잡 예보 조회 — 10월 17일 예보: 매우혼잡/)).toBeInTheDocument()

    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('경로를 펼치면 한적이 준 순위 그대로 장소가 나온다', async () => {
    renderDemo('answered')
    await askFirstExample()
    await userEvent.click(await screen.findByRole('button', { name: '경로 보기' }))

    const places = within(screen.getByTestId('path-places')).getAllByRole('listitem')
    expect(places.map((li) => li.textContent)).toEqual([
      expect.stringContaining('출발 · 가람궁'),
      expect.stringContaining('1순위 · 솔내 한옥마을'),
      expect.stringContaining('2순위 · 물빛 서원'),
      expect.stringContaining('3순위 · 달맞이 숲길'),
    ])
  })

  it('일부만 확인한 답은 그렇다고 말하고, 거절된 단계를 숨기지 않는다', async () => {
    renderDemo('partial')
    await askFirstExample()

    expect(await screen.findByText('일부만 확인했습니다')).toBeInTheDocument()
    await userEvent.click(screen.getByText('4단계를 거쳤습니다'))
    expect(screen.getByText('radius_km 는 1에서 50 사이여야 합니다')).toBeInTheDocument()
  })

  it('이름이 겹치면 고르게 하고, 고르면 그 장소로 이어 답한다', async () => {
    renderDemo('ambiguous')
    await askFirstExample()

    expect(await screen.findByText('어느 은행나무길을 말씀하시나요?')).toBeInTheDocument()
    expect(screen.queryByTestId('answer-text')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: '은행나무길 · 한빛시 가람구' }))
    expect(await screen.findByTestId('answer-text')).toHaveTextContent('가람구 은행나무길은 보통')
  })

  it('데이터가 없으면 한산하다고 하지 않고 모른다고 한다', async () => {
    renderDemo('no-data')
    await askFirstExample()

    expect(await screen.findByText('알 수 없습니다')).toBeInTheDocument()
    expect(screen.getByText(/한산하다는 뜻이 아닙니다/)).toBeInTheDocument()
    // 단계에 붙는 배지도 등급이 아니라 "데이터 없음"이다.
    expect(screen.getByText('데이터 없음')).toBeInTheDocument()
    expect(screen.queryByTestId('answer-text')).not.toBeInTheDocument()
  })

  it('답할 수 없는 질문은 무엇을 대신 물을 수 있는지 말한다', async () => {
    renderDemo('declined')
    await askFirstExample()
    expect(await screen.findByText('답할 수 없는 질문입니다')).toBeInTheDocument()
    expect(screen.getByText(/대신 갈 만한 곳이 있는지는 물어보실 수 있습니다/)).toBeInTheDocument()
  })

  it('실패하면 이유를 말하고 다시 물을 수 있게 한다', async () => {
    renderDemo('failed')
    await askFirstExample()
    expect(await screen.findByText('답을 가져오지 못했습니다')).toBeInTheDocument()
    expect(screen.getByText(/저장해 둔 값으로 대신 답하지 않습니다/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '다시 물어보기' })).toBeInTheDocument()
  })

  it('한도에 닿으면 언제 다시 올 수 있는지 말한다', async () => {
    renderDemo('limit')
    await askFirstExample()
    expect(await screen.findByText('오늘은 여기까지입니다')).toBeInTheDocument()
    expect(screen.getByText(/약 30분 뒤/)).toBeInTheDocument()
  })

  it('연결이 끊기면 받은 단계만 보여 주고 답을 지어내지 않는다', async () => {
    renderDemo('cut')
    await askFirstExample()
    expect(await screen.findByText('연결이 끊겼습니다')).toBeInTheDocument()
    expect(screen.getByText('가람궁 (한빛시 가람구)')).toBeInTheDocument()
    expect(screen.queryByTestId('answer-text')).not.toBeInTheDocument()
  })

  it('답이 오기 전에는 입력을 잠그고, 단계는 온 순서대로 쌓인다', async () => {
    let push: (event: GuideEvent) => void = () => {}
    const manual = vi.fn<typeof askGuide>((_request, onEvent) => {
      push = onEvent
      return new Promise<void>(() => {})
    })
    render(<AskGuide lang="ko" ask={manual} />)
    await userEvent.type(screen.getByLabelText('질문'), '가람궁 토요일에 붐벼?')
    await userEvent.click(screen.getByRole('button', { name: '물어보기' }))

    expect(screen.getByLabelText('질문')).toBeDisabled()
    expect(screen.getByText('찾아보는 중입니다')).toBeInTheDocument()

    const step = { inputs: {}, produced: [], as_of: null }
    push({ type: 'step', step: { ...step, index: 0, kind: 'congestion', status: 'running', summary: '' } })
    expect(await screen.findByText('진행 중')).toBeInTheDocument()

    // 같은 index 로 다시 오면 갈아 끼운다. 줄이 둘이 되면 안 된다.
    push({ type: 'step', step: { ...step, index: 0, kind: 'congestion', status: 'ok', summary: '예보: 보통' } })
    expect(await screen.findByText('예보: 보통')).toBeInTheDocument()
    expect(screen.queryByText('진행 중')).not.toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(1)
    expect(manual).toHaveBeenCalledWith(
      expect.objectContaining({ question: '가람궁 토요일에 붐벼?', visitId: null }),
      expect.any(Function),
      expect.any(Object),
    )
  })

  it('이어 묻는 질문에는 서버가 준 방문 번호를 싣는다', async () => {
    const spy = vi.fn<typeof askGuide>(instant)
    render(<AskGuide lang="ko" demo="answered" ask={spy} />)
    await askFirstExample()
    await screen.findByTestId('answer-text')

    await userEvent.type(screen.getByLabelText('질문'), '그 중 두 번째는?')
    await userEvent.click(screen.getByRole('button', { name: '물어보기' }))
    expect(spy.mock.calls[1][0]).toMatchObject({ question: '그 중 두 번째는?', visitId: 'replay-visit' })
  })

  describe('서버가 깨어나는 동안', () => {
    const question = { name: '이번 토요일 가람궁 대신 조용한 곳 있어?' }
    const waking = /안내 서버를 깨우고 있습니다/

    /** 사건을 손으로 밀어 넣는 가짜 서버. 아무것도 밀지 않으면 잠든 서버와 같다. */
    function asleep() {
      let push: (event: GuideEvent) => void = () => {}
      const ask: typeof askGuide = (_request, onEvent) => {
        push = onEvent
        return new Promise<void>(() => {})
      }
      return { ask, push: (event: GuideEvent) => act(() => push(event)) }
    }

    it('몇 초 동안 아무것도 오지 않으면 깨우는 중이라고 알린다', () => {
      vi.useFakeTimers()
      try {
        const server = asleep()
        render(<AskGuide lang="ko" ask={server.ask} />)
        fireEvent.click(screen.getByRole('button', question))

        expect(screen.queryByText(waking)).not.toBeInTheDocument()
        act(() => vi.advanceTimersByTime(WAKING_AFTER_MS - 1))
        expect(screen.queryByText(waking)).not.toBeInTheDocument()
        act(() => vi.advanceTimersByTime(1))
        expect(screen.getByText(waking)).toBeInTheDocument()
        expect(screen.getByText('찾아보는 중입니다')).toBeInTheDocument()
      } finally {
        vi.useRealTimers()
      }
    })

    it('서버에서 첫 사건이 오면 안내가 사라진다', () => {
      vi.useFakeTimers()
      try {
        const server = asleep()
        render(<AskGuide lang="ko" ask={server.ask} />)
        fireEvent.click(screen.getByRole('button', question))
        act(() => vi.advanceTimersByTime(WAKING_AFTER_MS))
        expect(screen.getByText(waking)).toBeInTheDocument()

        server.push({ type: 'visit', visit_id: 'v', as_of: { export: '2026-10-14T00:47:32Z', wiki: '' } })

        expect(screen.queryByText(waking)).not.toBeInTheDocument()
        expect(screen.getByText('찾아보는 중입니다')).toBeInTheDocument()
      } finally {
        vi.useRealTimers()
      }
    })

    it('제때 답한 서버에는 안내가 뜨지 않는다', () => {
      vi.useFakeTimers()
      try {
        const server = asleep()
        render(<AskGuide lang="ko" ask={server.ask} />)
        fireEvent.click(screen.getByRole('button', question))
        server.push({ type: 'visit', visit_id: 'v', as_of: { export: '2026-10-14T00:47:32Z', wiki: '' } })

        act(() => vi.advanceTimersByTime(WAKING_AFTER_MS * 3))

        expect(screen.queryByText(waking)).not.toBeInTheDocument()
      } finally {
        vi.useRealTimers()
      }
    })
  })
})
