import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as agent from '@/lib/agent'
import { CitationSheet } from './CitationSheet'

afterEach(() => vi.restoreAllMocks())

describe('인용 시트', () => {
  it('번들에 없는 문서면 그렇게 말한다', async () => {
    // 빈 시트는 "문서에 내용이 없다"로 읽힌다. 번들에 없다는 것은 인용이
    // 잘못되었다는 뜻이라 그 자체가 알려야 할 정보다.
    vi.spyOn(agent, 'fetchContextDocument').mockResolvedValue({ kind: 'unavailable', status: 404 })

    render(<CitationSheet path="nope.md" lang="ko" onClose={() => {}} />)

    expect(await screen.findByText(/번들에 없습니다/)).toBeInTheDocument()
  })

  it('Esc 로 닫힌다', async () => {
    vi.spyOn(agent, 'fetchContextDocument').mockResolvedValue({ kind: 'loaded', value: '본문' })
    const onClose = vi.fn()

    render(<CitationSheet path="a.md" lang="ko" onClose={onClose} />)
    await userEvent.keyboard('{Escape}')

    expect(onClose).toHaveBeenCalled()
  })

  it('바깥을 누르면 닫히고 본문을 누르면 닫히지 않는다', async () => {
    vi.spyOn(agent, 'fetchContextDocument').mockResolvedValue({ kind: 'loaded', value: '본문' })
    const onClose = vi.fn()

    render(<CitationSheet path="a.md" lang="ko" onClose={onClose} />)
    await userEvent.click(await screen.findByRole('dialog'))
    expect(onClose).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('dialog').parentElement!)
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1))
  })
})

describe('키보드 접근', () => {
  it('열리면 초점이 시트 안으로 들어온다', async () => {
    // 초점이 뒤에 남으면, 화면에는 시트가 떠 있는데 Tab 은 그 아래를 돌아다닌다.
    vi.spyOn(agent, 'fetchContextDocument').mockResolvedValue({ kind: 'loaded', value: '본문' })

    render(<CitationSheet path="a.md" lang="ko" onClose={() => {}} />)

    await waitFor(() =>
      expect(screen.getByRole('button', { name: '닫기' })).toHaveFocus(),
    )
  })

  it('대화상자임을 알린다', async () => {
    vi.spyOn(agent, 'fetchContextDocument').mockResolvedValue({ kind: 'loaded', value: '본문' })

    render(<CitationSheet path="concepts/x.md" lang="ko" onClose={() => {}} />)

    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog).toHaveAccessibleName('concepts/x.md')
  })
})
