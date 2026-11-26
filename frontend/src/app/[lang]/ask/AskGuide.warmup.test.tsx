import { StrictMode } from 'react'
import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { askGuide } from '@/lib/guide'
import { waitForGuideReady } from '@/lib/guide-ready'
import { AskGuide } from './AskGuide'

function deferred() {
  let resolve!: (value: boolean) => void
  const promise = new Promise<boolean>(done => { resolve = done })
  return { promise, resolve }
}
const answered: typeof askGuide = (request, onEvent, options) =>
  askGuide(request, onEvent, { ...options, baseUrl: '', stepDelayMs: 0 })
const fillAndSubmit = () => {
  fireEvent.change(screen.getByLabelText('질문'), { target: { value: '경복궁 토요일에 붐벼?' } })
  fireEvent.click(screen.getByRole('button', { name: '물어보기' }))
}

describe('서버 준비와 질문 대기', () => {
  it('진입 시 깨우고, 미제출 초안은 연결 뒤에도 보내지 않는다', async () => {
    const job = deferred()
    const prepare = vi.fn<typeof waitForGuideReady>(() => job.promise)
    const ask = vi.fn<typeof askGuide>(answered)
    render(<AskGuide lang="ko" prepare={prepare} ask={ask} />)
    expect(prepare).toHaveBeenCalledTimes(1)
    expect(screen.getByLabelText('질문')).toBeEnabled()
    fireEvent.change(screen.getByLabelText('질문'), { target: { value: '작성 중인 질문' } })
    await act(async () => job.resolve(true))
    expect(ask).not.toHaveBeenCalled()
    expect(screen.getByLabelText('질문')).toHaveValue('작성 중인 질문')
  })

  it('준비 전 보낸 질문을 보존하고 연타해도 준비 뒤 한 번만 실행한다', async () => {
    const job = deferred()
    const prepare = vi.fn<typeof waitForGuideReady>(() => job.promise)
    const ask = vi.fn<typeof askGuide>(answered)
    render(<AskGuide lang="ko" prepare={prepare} ask={ask} place={{ place_id: 653, name: '경복궁', region: '서울' }} />)
    fillAndSubmit()
    fireEvent.submit(screen.getByRole('button', { name: '연결 기다리는 중' }).closest('form')!)
    expect(ask).not.toHaveBeenCalled()
    expect(prepare).toHaveBeenCalledTimes(1)
    expect(screen.getByLabelText('질문')).toHaveValue('경복궁 토요일에 붐벼?')
    expect(screen.queryByText('찾아보는 중입니다')).not.toBeInTheDocument()
    await act(async () => job.resolve(true))
    expect(await screen.findByTestId('answer-text')).toBeInTheDocument()
    expect(ask).toHaveBeenCalledTimes(1)
    expect(ask.mock.calls[0][0]).toMatchObject({ question: '경복궁 토요일에 붐벼?', context: { place_id: 653 } })
  })

  it('연결 실패 후에는 질문을 남기고 명시적 재연결로 한 번만 실행한다', async () => {
    const first = deferred()
    const prepare = vi.fn<typeof waitForGuideReady>().mockImplementationOnce(() => first.promise).mockResolvedValue(true)
    const ask = vi.fn<typeof askGuide>(answered)
    render(<AskGuide lang="ko" prepare={prepare} ask={ask} />)
    fillAndSubmit()
    await act(async () => first.resolve(false))
    expect(screen.getByText('연결이 예상보다 오래 걸리고 있어요')).toBeInTheDocument()
    expect(screen.getByLabelText('질문')).toHaveValue('경복궁 토요일에 붐벼?')
    expect(ask).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: '다시 연결하기' }))
    expect(await screen.findByTestId('answer-text')).toBeInTheDocument()
    expect(ask).toHaveBeenCalledTimes(1)
  })

  it('대기 취소 후 늦게 준비되어도 보내지 않고 초안을 보존한다', async () => {
    const job = deferred()
    const ask = vi.fn<typeof askGuide>(answered)
    render(<AskGuide lang="ko" prepare={() => job.promise} ask={ask} />)
    fillAndSubmit()
    await userEvent.click(screen.getByRole('button', { name: '대기 취소' }))
    await act(async () => job.resolve(true))
    expect(ask).not.toHaveBeenCalled()
    expect(screen.getByLabelText('질문')).toBeEnabled()
    expect(screen.getByLabelText('질문')).toHaveValue('경복궁 토요일에 붐벼?')
  })

  it('언마운트 시 확인을 취소하고 늦은 완료를 무시한다', async () => {
    const job = deferred()
    let signal: AbortSignal | undefined
    const prepare: typeof waitForGuideReady = options => { signal = options?.signal; return job.promise }
    const ask = vi.fn<typeof askGuide>(answered)
    const view = render(<AskGuide lang="ko" prepare={prepare} ask={ask} />)
    fillAndSubmit()
    view.unmount()
    expect(signal?.aborted).toBe(true)
    await act(async () => job.resolve(true))
    expect(ask).not.toHaveBeenCalled()
  })

  it('준비된 채 오래 열린 화면도 제출할 때 재확인한다', async () => {
    const second = deferred()
    const prepare = vi.fn<typeof waitForGuideReady>().mockResolvedValueOnce(true).mockImplementationOnce(() => second.promise)
    const ask = vi.fn<typeof askGuide>(answered)
    render(<AskGuide lang="ko" prepare={prepare} ask={ask} />)
    await act(async () => {})
    fillAndSubmit()
    expect(prepare).toHaveBeenCalledTimes(2)
    expect(ask).not.toHaveBeenCalled()
    await act(async () => second.resolve(true))
    expect(await screen.findByTestId('answer-text')).toBeInTheDocument()
  })

  it('StrictMode의 취소된 첫 확인은 두 번째 확인이나 제출을 완료하지 못한다', async () => {
    const first = deferred(), second = deferred()
    const prepare = vi.fn<typeof waitForGuideReady>().mockImplementationOnce(() => first.promise).mockImplementationOnce(() => second.promise)
    const ask = vi.fn<typeof askGuide>(answered)
    render(<StrictMode><AskGuide lang="ko" prepare={prepare} ask={ask} /></StrictMode>)
    fillAndSubmit()
    await act(async () => first.resolve(true))
    expect(ask).not.toHaveBeenCalled()
    await act(async () => second.resolve(true))
    expect(await screen.findByTestId('answer-text')).toBeInTheDocument()
    expect(ask).toHaveBeenCalledTimes(1)
  })

  it('잎새 카드는 키보드로 뒤집고 넘길 수 있으며 질문을 보내지 않는다', async () => {
    const ask = vi.fn<typeof askGuide>(answered)
    render(<AskGuide lang="ko" prepare={() => new Promise(() => {})} ask={ask} />)
    const flip = screen.getByRole('button', { name: '잎새 카드 뒤집기' })
    flip.focus()
    await userEvent.keyboard('{Enter}')
    expect(flip).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('장소와 날짜를 함께 적어보세요.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '다음 카드' }))
    expect(screen.getByText('혼잡 데이터가 없다고 한적한 것은 아니에요.')).toBeInTheDocument()
    expect(ask).not.toHaveBeenCalled()
  })

  it('영어 연결 문구와 조작을 제공한다', () => {
    render(<AskGuide lang="en" prepare={() => new Promise(() => {})} />)
    expect(screen.getByText('Hanjeok is waking up')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Turn over an Ipsae card' })).toBeInTheDocument()
  })
  it('예시를 누르면 초안만 채우고 준비 완료 뒤에도 자동 전송하지 않는다', async () => {
    const job = deferred()
    const ask = vi.fn<typeof askGuide>(answered)
    render(<AskGuide lang="ko" prepare={() => job.promise} ask={ask} />)
    await userEvent.click(screen.getByRole('button', { name: '이번 토요일 가람궁 대신 조용한 곳 있어?' }))
    expect(screen.getByLabelText('질문')).toHaveValue('이번 토요일 가람궁 대신 조용한 곳 있어?')
    await act(async () => job.resolve(true))
    expect(ask).not.toHaveBeenCalled()
  })

  it('취소한 질문의 늦은 완료가 새 질문을 보내지 않는다', async () => {
    const first = deferred(), second = deferred()
    const prepare = vi.fn<typeof waitForGuideReady>().mockImplementationOnce(() => first.promise).mockImplementationOnce(() => second.promise)
    const ask = vi.fn<typeof askGuide>(answered)
    render(<AskGuide lang="ko" prepare={prepare} ask={ask} />)
    fillAndSubmit()
    await userEvent.click(screen.getByRole('button', { name: '대기 취소' }))
    fireEvent.change(screen.getByLabelText('질문'), { target: { value: '명동은 어때?' } })
    fireEvent.click(screen.getByRole('button', { name: '물어보기' }))
    await act(async () => first.resolve(true))
    expect(ask).not.toHaveBeenCalled()
    await act(async () => second.resolve(true))
    expect(await screen.findByTestId('answer-text')).toBeInTheDocument()
    expect(ask).toHaveBeenCalledTimes(1)
    expect(ask.mock.calls[0][0].question).toBe('명동은 어때?')
  })

  it('준비 확인을 거친 후보 선택에도 방문 번호와 선택값을 유지한다', async () => {
    const prepare = vi.fn<typeof waitForGuideReady>().mockResolvedValue(true)
    const ask = vi.fn<typeof askGuide>((request, onEvent, options) =>
      askGuide(request, onEvent, { ...options, demo: 'ambiguous', baseUrl: '', stepDelayMs: 0 }))
    render(<AskGuide lang="ko" prepare={prepare} ask={ask} />)
    await act(async () => {})
    fillAndSubmit()
    await userEvent.click(await screen.findByRole('button', { name: '은행나무길 · 한빛시 가람구' }))
    expect(await screen.findByTestId('answer-text')).toBeInTheDocument()
    expect(ask).toHaveBeenCalledTimes(2)
    expect(ask.mock.calls[1][0]).toMatchObject({ visitId: 'replay-visit', choice: expect.any(Number) })
    expect(prepare).toHaveBeenCalledTimes(3)
  })

  it('연결이 완료되어도 조작 중인 카드의 키보드 포커스를 유지한다', async () => {
    const job = deferred()
    render(<AskGuide lang="ko" prepare={() => job.promise} />)
    const flip = screen.getByRole('button', { name: '잎새 카드 뒤집기' })
    flip.focus()
    await userEvent.keyboard('{Enter}')
    const next = screen.getByRole('button', { name: '다음 카드' })
    next.focus()
    await act(async () => job.resolve(true))
    expect(next).toHaveFocus()
    expect(screen.getByText('서버에 연결됐어요')).toBeInTheDocument()
  })

  it('보관한 질문이 SSE로 넘어가도 사용 중인 카드 포커스를 유지한다', async () => {
    const job = deferred()
    const ask = vi.fn<typeof askGuide>(() => new Promise(() => {}))
    render(<AskGuide lang="ko" prepare={() => job.promise} ask={ask} />)
    fillAndSubmit()
    const flip = screen.getByRole('button', { name: '잎새 카드 뒤집기' })
    flip.focus()
    await userEvent.keyboard('{Enter}')
    const next = screen.getByRole('button', { name: '다음 카드' })
    next.focus()
    await act(async () => job.resolve(true))
    expect(next).toHaveFocus()
    expect(screen.getByText('찾아보는 중입니다')).toBeInTheDocument()
    expect(ask).toHaveBeenCalledTimes(1)
  })

})
