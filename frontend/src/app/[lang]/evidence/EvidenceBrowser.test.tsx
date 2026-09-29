import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as agent from '@/lib/agent'
import { EvidenceBrowser } from './EvidenceBrowser'

const entries = [
  { path: 'concepts/congestion-diagnosis.md', bytes: 2000 },
  { path: 'concepts/alternative-scoring.md', bytes: 1500 },
]

afterEach(() => vi.restoreAllMocks())

describe('근거 열람', () => {
  it('전체 바이트가 각 문서의 합이다', async () => {
    // "벡터 검색이 필요 없는 크기"라는 주장을 화면이 스스로 보이게 하는 숫자다.
    // 합이 아니라 어림수를 적으면 그 주장이 검증 불가능한 문구가 된다.
    vi.spyOn(agent, 'fetchContextDocument').mockResolvedValue({ kind: 'loaded', value: '본문' })

    render(<EvidenceBrowser entries={entries} systemTextBytes={3600} lang="ko" />)

    // 머리글의 숫자는 프롬프트에 실리는 크기이고, 아래 목록의 합은 그보다 작다.
    // 둘을 같은 수로 적으면 화면이 자기 목록과 어긋난다.
    expect(screen.getByText(/문서 2개 · 3,600바이트/)).toBeInTheDocument()
    expect(screen.getByText(/3,500바이트입니다/)).toBeInTheDocument()
  })

  it('문서를 고르면 본문이 바뀐다', async () => {
    const document = vi
      .spyOn(agent, 'fetchContextDocument')
      .mockResolvedValue({ kind: 'loaded', value: '본문' })

    render(<EvidenceBrowser entries={entries} systemTextBytes={3600} lang="ko" />)
    await waitFor(() => expect(document).toHaveBeenCalledWith(entries[0].path))

    await userEvent.click(screen.getByRole('button', { name: /alternative-scoring/ }))

    await waitFor(() => expect(document).toHaveBeenCalledWith(entries[1].path))
  })

  it('목록이 비어도 무너지지 않는다', () => {
    render(<EvidenceBrowser entries={[]} systemTextBytes={0} lang="ko" />)

    expect(screen.getByText(/문서 0개 · 0바이트/)).toBeInTheDocument()
  })
})
