import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as agent from '@/lib/agent'
import { factsFixture } from '@/lib/fixtures'
import { ExplanationBlock } from './ExplanationBlock'

const answered = {
  kind: 'loaded' as const,
  value: {
    explanation: '경복궁은 이 날 매우 붐빕니다.',
    citations: ['concepts/congestion-diagnosis.md', 'concepts/alternative-scoring.md'],
    facts: factsFixture,
    generatedAt: '2026-09-02T00:00:00Z',
    model: 'gpt-4o',
  },
}

afterEach(() => vi.restoreAllMocks())

describe('설명 블록', () => {
  it('설명이 503 이면 블록 자체가 없다', async () => {
    // 코스는 이미 그려져 있다. 여기서 사과문이나 빈 카드를 띄우면, 없는 것을
    // 굳이 알리느라 읽을 수 있는 화면을 어지럽힌다.
    vi.spyOn(agent, 'fetchExplanation').mockResolvedValue({ kind: 'unavailable', status: 503 })

    const { container } = render(<ExplanationBlock courseUuid="abc" lang="ko" />)

    await waitFor(() => expect(container).toBeEmptyDOMElement())
  })

  it('인용 칩은 citations 배열에서만 나온다', async () => {
    // 번들 전체를 칩으로 깔면 모델이 실제로 무엇을 봤는지가 흐려진다.
    vi.spyOn(agent, 'fetchExplanation').mockResolvedValue(answered)

    render(<ExplanationBlock courseUuid="abc" lang="ko" />)

    await screen.findByText('경복궁은 이 날 매우 붐빕니다.')
    expect(screen.getAllByRole('button')).toHaveLength(2)
    expect(screen.getByRole('button', { name: 'concepts/congestion-diagnosis.md' })).toBeInTheDocument()
  })

  it('칩을 누르면 그 경로의 문서를 연다', async () => {
    vi.spyOn(agent, 'fetchExplanation').mockResolvedValue(answered)
    const document = vi
      .spyOn(agent, 'fetchContextDocument')
      .mockResolvedValue({ kind: 'loaded', value: '# 혼잡 진단' })

    render(<ExplanationBlock courseUuid="abc" lang="ko" />)
    await userEvent.click(await screen.findByRole('button', { name: 'concepts/congestion-diagnosis.md' }))

    await waitFor(() => expect(document).toHaveBeenCalledWith('concepts/congestion-diagnosis.md'))
    expect(await screen.findByText('# 혼잡 진단')).toBeInTheDocument()
  })

  it('파싱이 실패해도 화면을 무너뜨리지 않는다', async () => {
    // 서버가 응답 모양을 바꾼 경우다. 예외가 페이지까지 올라가면 코스까지 사라진다.
    vi.spyOn(agent, 'fetchExplanation').mockRejectedValue(new Error('zod'))

    const { container } = render(<ExplanationBlock courseUuid="abc" lang="ko" />)

    await waitFor(() => expect(container).toBeEmptyDOMElement())
  })
})
