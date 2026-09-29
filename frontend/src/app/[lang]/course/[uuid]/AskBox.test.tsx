import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as agent from '@/lib/agent'
import type { AskStreamEvent, AskTurn } from '@/lib/agent'
import { AskBox } from './AskBox'

type OnEvent = (event: AskStreamEvent) => void
type StreamImpl = (courseUuid: string, question: string, history: AskTurn[], onEvent: OnEvent) => Promise<void>

const DONE = { kind: 'done' as const, generatedAt: '2026-09-05T00:00:00Z', model: 'gpt-4o' }

/** 주어진 이벤트를 순서대로, 즉시 내보내는 흉내. 중간 화면을 볼 필요가 없는 테스트용. */
const eagerStream = (...events: AskStreamEvent[]): StreamImpl =>
  async (_courseUuid, _question, _history, onEvent) => {
    for (const event of events) onEvent(event)
  }

/**
 * 이벤트 사이에 멈춰 서서, 테스트가 각 이벤트 뒤 화면을 확인한 다음 `advance(i)` 로
 * 다음 이벤트를 내보내게 하는 흉내. 실제 스트림처럼 델타가 한 번에 다 오지 않고
 * 하나씩 도착하는 상황을 재현한다.
 */
function stepStream(events: AskStreamEvent[]) {
  const gates = events.map(() => {
    let resolve!: () => void
    const promise = new Promise<void>((r) => {
      resolve = r
    })
    return { promise, resolve }
  })
  const impl: StreamImpl = async (_courseUuid, _question, _history, onEvent) => {
    for (let i = 0; i < events.length; i++) {
      onEvent(events[i])
      if (i < events.length - 1) await gates[i].promise
    }
  }
  const advance = (i: number) => gates[i]?.resolve()
  return { impl, advance }
}

afterEach(() => vi.restoreAllMocks())

describe('코스 후속 질문', () => {
  it('질문을 보내면 답과 인용이 그려진다', async () => {
    vi.spyOn(agent, 'askCourseStream').mockImplementation(
      eagerStream(
        { kind: 'citations', citations: ['concepts/course-generation-policy.md'] },
        { kind: 'delta', text: '이동 시간이 가장 짧아요.' },
        DONE,
      ),
    )

    render(<AskBox courseUuid="abc" lang="ko" />)
    await userEvent.type(screen.getByLabelText('이 코스에 대해 더 묻기'), '왜 이 순서예요?')
    await userEvent.click(screen.getByRole('button', { name: '묻기' }))

    expect(await screen.findByText('이동 시간이 가장 짧아요.')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'concepts/course-generation-policy.md' }),
    ).toBeInTheDocument()
  })

  it('이전 대화를 함께 보낸다', async () => {
    // 서버가 대화를 저장하지 않으므로, 안 보내면 "거기"가 무엇인지 알 수 없다.
    const ask = vi
      .spyOn(agent, 'askCourseStream')
      .mockImplementationOnce(eagerStream({ kind: 'delta', text: '이동 시간 때문이에요.' }, DONE))
      .mockImplementationOnce(eagerStream({ kind: 'delta', text: '네, 붐벼요.' }, DONE))

    render(<AskBox courseUuid="abc" lang="ko" />)
    const input = screen.getByLabelText('이 코스에 대해 더 묻기')

    await userEvent.type(input, '왜 이 순서예요?')
    await userEvent.click(screen.getByRole('button', { name: '묻기' }))
    await screen.findByText('이동 시간 때문이에요.')

    await userEvent.type(input, '거기는 붐비나요?')
    await userEvent.click(screen.getByRole('button', { name: '묻기' }))
    await screen.findByText('네, 붐벼요.')

    expect(ask.mock.calls[1][2]).toEqual([
      { question: '왜 이 순서예요?', answer: '이동 시간 때문이에요.' },
    ])
  })

  it('실패한 질문도 목록에 남는다', async () => {
    // 사라지면 사용자는 자기가 뭘 물었는지도, 답이 없었다는 사실도 잃는다.
    vi.spyOn(agent, 'askCourseStream').mockImplementation(eagerStream({ kind: 'unavailable' }))

    render(<AskBox courseUuid="abc" lang="ko" />)
    await userEvent.type(screen.getByLabelText('이 코스에 대해 더 묻기'), '왜요?')
    await userEvent.click(screen.getByRole('button', { name: '묻기' }))

    expect(await screen.findByText(/답을 만들지 못했어요/)).toBeInTheDocument()
    expect(screen.getByText('왜요?')).toBeInTheDocument()
  })

  it('실패한 답은 다음 질문의 대화 기록에 넣지 않는다', async () => {
    // 없는 답을 맥락으로 보내면 모델이 그것을 이미 한 말로 읽는다.
    const ask = vi
      .spyOn(agent, 'askCourseStream')
      .mockImplementationOnce(eagerStream({ kind: 'unavailable' }))
      .mockImplementationOnce(eagerStream({ kind: 'delta', text: '답' }, DONE))

    render(<AskBox courseUuid="abc" lang="ko" />)
    const input = screen.getByLabelText('이 코스에 대해 더 묻기')

    await userEvent.type(input, '첫 질문')
    await userEvent.click(screen.getByRole('button', { name: '묻기' }))
    await screen.findByText(/답을 만들지 못했어요/)

    await userEvent.type(input, '둘째 질문')
    await userEvent.click(screen.getByRole('button', { name: '묻기' }))
    await screen.findByText('답')

    expect(ask.mock.calls[1][2]).toEqual([])
  })

  it('빈 질문은 보내지 않는다', async () => {
    const ask = vi.spyOn(agent, 'askCourseStream')

    render(<AskBox courseUuid="abc" lang="ko" />)
    await userEvent.type(screen.getByLabelText('이 코스에 대해 더 묻기'), '   ')

    expect(screen.getByRole('button', { name: '묻기' })).toBeDisabled()
    expect(ask).not.toHaveBeenCalled()
  })

  it('추천 질문을 누르면 그대로 묻는다', async () => {
    const ask = vi
      .spyOn(agent, 'askCourseStream')
      .mockImplementation(eagerStream({ kind: 'delta', text: '답' }, DONE))

    render(<AskBox courseUuid="abc" lang="ko" />)
    await userEvent.click(screen.getByRole('button', { name: '왜 이 순서예요?' }))

    await waitFor(() => expect(ask.mock.calls[0][1]).toBe('왜 이 순서예요?'))
  })

  it('delta 가 올 때마다 본문이 이어 붙어 보인다', async () => {
    const { impl, advance } = stepStream([
      { kind: 'delta', text: '이동' },
      { kind: 'delta', text: ' 시간이' },
      DONE,
    ])
    vi.spyOn(agent, 'askCourseStream').mockImplementation(impl)

    render(<AskBox courseUuid="abc" lang="ko" />)
    await userEvent.type(screen.getByLabelText('이 코스에 대해 더 묻기'), '왜요?')
    await userEvent.click(screen.getByRole('button', { name: '묻기' }))

    await screen.findByText('이동')
    advance(0)
    await screen.findByText('이동 시간이')
    advance(1)
    await waitFor(() => expect(screen.queryByRole('button', { name: '묻는 중…' })).not.toBeInTheDocument())
  })

  it('citations 가 오면 본문보다 먼저 인용 칩이 보인다', async () => {
    const { impl, advance } = stepStream([
      { kind: 'citations', citations: ['a.md'] },
      { kind: 'delta', text: '답' },
      DONE,
    ])
    vi.spyOn(agent, 'askCourseStream').mockImplementation(impl)

    render(<AskBox courseUuid="abc" lang="ko" />)
    await userEvent.type(screen.getByLabelText('이 코스에 대해 더 묻기'), '왜요?')
    await userEvent.click(screen.getByRole('button', { name: '묻기' }))

    await screen.findByRole('button', { name: 'a.md' })
    expect(screen.queryByText('답')).not.toBeInTheDocument()

    advance(0)
    await screen.findByText('답')
    advance(1)
    await waitFor(() => expect(screen.queryByRole('button', { name: '묻는 중…' })).not.toBeInTheDocument())
  })

  it('unavailable 이면 "답을 만들지 못했어요" 가 보이고 본문은 없다', async () => {
    vi.spyOn(agent, 'askCourseStream').mockImplementation(eagerStream({ kind: 'unavailable' }))

    render(<AskBox courseUuid="abc" lang="ko" />)
    await userEvent.type(screen.getByLabelText('이 코스에 대해 더 묻기'), '왜요?')
    await userEvent.click(screen.getByRole('button', { name: '묻기' }))

    expect(await screen.findByText(/답을 만들지 못했어요/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /\.md$/ })).not.toBeInTheDocument()
  })

  it('delta 몇 개 뒤 aborted 면 받은 본문이 화면에서 사라지고 실패 문구가 보인다', async () => {
    // 미완 문장을 설명으로 남기지 않는다 — 인용이 검증됐어도 문장은 끝나지 않았다.
    vi.spyOn(agent, 'askCourseStream').mockImplementation(
      eagerStream(
        { kind: 'citations', citations: ['a.md'] },
        { kind: 'delta', text: '이동 시간이' },
        { kind: 'delta', text: ' 가장' },
        { kind: 'aborted' },
      ),
    )

    render(<AskBox courseUuid="abc" lang="ko" />)
    await userEvent.type(screen.getByLabelText('이 코스에 대해 더 묻기'), '왜요?')
    await userEvent.click(screen.getByRole('button', { name: '묻기' }))

    expect(await screen.findByText(/답을 만들지 못했어요/)).toBeInTheDocument()
    expect(screen.queryByText(/이동 시간이/)).not.toBeInTheDocument()
  })

  it('다음 질문의 history 에는 done 으로 끝난 답만 들어가고, 중단된 것은 빠진다', async () => {
    const ask = vi
      .spyOn(agent, 'askCourseStream')
      .mockImplementationOnce(eagerStream({ kind: 'delta', text: '미완' }, { kind: 'aborted' }))
      .mockImplementationOnce(eagerStream({ kind: 'delta', text: '답' }, DONE))

    render(<AskBox courseUuid="abc" lang="ko" />)
    const input = screen.getByLabelText('이 코스에 대해 더 묻기')

    await userEvent.type(input, '첫 질문')
    await userEvent.click(screen.getByRole('button', { name: '묻기' }))
    await screen.findByText(/답을 만들지 못했어요/)

    await userEvent.type(input, '둘째 질문')
    await userEvent.click(screen.getByRole('button', { name: '묻기' }))
    await screen.findByText('답')

    expect(ask.mock.calls[1][2]).toEqual([])
  })

  it('조회 중에는 안내를 보여 주고 citations/delta 가 오면 치운다', async () => {
    const { impl, advance } = stepStream([
      { kind: 'looking', what: 'congestion' },
      { kind: 'citations', citations: ['a.md'] },
      { kind: 'delta', text: '답' },
      DONE,
    ])
    vi.spyOn(agent, 'askCourseStream').mockImplementation(impl)

    render(<AskBox courseUuid="abc" lang="ko" />)
    await userEvent.type(screen.getByLabelText('이 코스에 대해 더 묻기'), '다른 날은 어때요?')
    await userEvent.click(screen.getByRole('button', { name: '묻기' }))

    expect(await screen.findByText(/혼잡도를 다시 확인/)).toBeInTheDocument()

    advance(0)
    await waitFor(() => expect(screen.queryByText(/혼잡도를 다시 확인/)).not.toBeInTheDocument())

    advance(1)
    advance(2)
    await waitFor(() => expect(screen.queryByRole('button', { name: '묻는 중…' })).not.toBeInTheDocument())
    expect(screen.getByText('답')).toBeInTheDocument()
    // done 이후에도 안내가 남아 있지 않아야 한다 — done 은 답을 확정하는 유일한
    // 조건이므로, 여기서 이전 looking 문구가 되살아나면 안 된다.
    expect(screen.queryByText(/혼잡도를 다시 확인/)).not.toBeInTheDocument()
  })

  it('looking 중 unavailable 이 오면 안내가 사라지고 실패 문구만 보인다', async () => {
    const { impl, advance } = stepStream([{ kind: 'looking', what: 'congestion' }, { kind: 'unavailable' }])
    vi.spyOn(agent, 'askCourseStream').mockImplementation(impl)

    render(<AskBox courseUuid="abc" lang="ko" />)
    await userEvent.type(screen.getByLabelText('이 코스에 대해 더 묻기'), '왜요?')
    await userEvent.click(screen.getByRole('button', { name: '묻기' }))

    expect(await screen.findByText(/혼잡도를 다시 확인/)).toBeInTheDocument()

    advance(0)
    expect(await screen.findByText(/답을 만들지 못했어요/)).toBeInTheDocument()
    expect(screen.queryByText(/혼잡도를 다시 확인/)).not.toBeInTheDocument()
  })

  it('looking 중 aborted 가 오면 안내가 사라지고 실패 문구만 보인다', async () => {
    const { impl, advance } = stepStream([{ kind: 'looking', what: 'alternatives' }, { kind: 'aborted' }])
    vi.spyOn(agent, 'askCourseStream').mockImplementation(impl)

    render(<AskBox courseUuid="abc" lang="ko" />)
    await userEvent.type(screen.getByLabelText('이 코스에 대해 더 묻기'), '왜요?')
    await userEvent.click(screen.getByRole('button', { name: '묻기' }))

    expect(await screen.findByText(/주변 대안을 찾아보는 중/)).toBeInTheDocument()

    advance(0)
    expect(await screen.findByText(/답을 만들지 못했어요/)).toBeInTheDocument()
    expect(screen.queryByText(/주변 대안을 찾아보는 중/)).not.toBeInTheDocument()
  })

  it('모르는 what 이 와도 화면이 비지 않는다', async () => {
    const { impl } = stepStream([{ kind: 'looking', what: 'weather' }, DONE])
    vi.spyOn(agent, 'askCourseStream').mockImplementation(impl)

    render(<AskBox courseUuid="abc" lang="ko" />)
    await userEvent.type(screen.getByLabelText('이 코스에 대해 더 묻기'), '왜요?')
    await userEvent.click(screen.getByRole('button', { name: '묻기' }))

    expect(await screen.findByText(/자료를 더 찾아보는 중/)).toBeInTheDocument()
  })

  it('답이 흐르는 동안에는 둘째 질문이 나가지 않는다', async () => {
    // 두 스트림이 겹치면 둘 다 같은 자리(index)를 잡아, 한 질문이 다른 질문의 답과
    // 인용을 달고 있게 된다. 막는 자리는 세 군데 모두여야 한다 — 버튼의 disabled,
    // 입력창의 Enter, 그리고 그 둘을 지나쳐 ask() 에 곧장 닿는 form 제출.
    // 마지막 하나가 ask() 안의 잠금 자체를 건드린다(버튼이 안 막아 주는 경로).
    let release!: () => void
    const held = new Promise<void>((resolve) => {
      release = resolve
    })
    const asked: string[] = []
    const ask = vi
      .spyOn(agent, 'askCourseStream')
      .mockImplementation(async (_courseUuid, question, _history, onEvent) => {
        asked.push(question)
        if (asked.length > 1) {
          // 둘째 스트림이 열렸다면 첫 답 위에 덮어쓰려 들 것이다.
          onEvent({ kind: 'citations', citations: ['b.md'] })
          onEvent({ kind: 'delta', text: '둘째 답' })
          onEvent(DONE)
          return
        }
        onEvent({ kind: 'citations', citations: ['a.md'] })
        await held
        onEvent({ kind: 'delta', text: '첫 답' })
        onEvent(DONE)
      })

    render(<AskBox courseUuid="abc" lang="ko" />)
    const input = screen.getByLabelText('이 코스에 대해 더 묻기')
    await userEvent.type(input, '첫 질문')
    await userEvent.click(screen.getByRole('button', { name: '묻기' }))

    // 첫 스트림은 아직 흐르는 중이다 — 인용은 왔고 done 은 오지 않았다.
    await screen.findByRole('button', { name: 'a.md' })

    await userEvent.type(input, '둘째 질문')
    await userEvent.click(screen.getByRole('button', { name: '묻는 중…' }))
    await userEvent.type(input, '{Enter}')
    fireEvent.submit(input.closest('form') as HTMLFormElement)

    expect(ask).toHaveBeenCalledTimes(1)

    await act(async () => {
      release()
    })

    expect(ask).toHaveBeenCalledTimes(1)
    expect(screen.getAllByText(/질문$/)).toHaveLength(1)
    expect(screen.getByText('첫 질문')).toBeInTheDocument()
    expect(screen.getByText('첫 답')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'a.md' })).toBeInTheDocument()
    expect(screen.queryByText('둘째 답')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '묻기' })).toBeInTheDocument()
  })
})
