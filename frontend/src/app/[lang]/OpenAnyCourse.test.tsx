import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { OpenAnyCourse } from './OpenAnyCourse'

const push = vi.fn()
vi.mock('next/navigation', () => ({ useRouter: () => ({ push }) }))

describe('코스 uuid로 열기', () => {
  it('입력한 uuid의 코스로 이동한다', async () => {
    render(<OpenAnyCourse lang="ko" />)

    await userEvent.type(screen.getByLabelText('코스 uuid로 열기'), 'abc-123')
    await userEvent.click(screen.getByRole('button', { name: '열기' }))

    expect(push).toHaveBeenCalledWith('/ko/course/abc-123')
  })

  it('빈 값으로는 이동하지 않는다', async () => {
    push.mockClear()
    render(<OpenAnyCourse lang="ko" />)

    // 공백만 넣어도 마찬가지다 — /course/%20 은 아무것도 아닌 주소다.
    await userEvent.type(screen.getByLabelText('코스 uuid로 열기'), '   ')

    expect(screen.getByRole('button', { name: '열기' })).toBeDisabled()
    expect(push).not.toHaveBeenCalled()
  })

  it('빈 폼이 제출돼도 이동하지 않는다', () => {
    // 비활성 버튼은 클릭을 막을 뿐이다. 브라우저마다 입력칸의 Enter 가 폼을 제출할
    // 수 있고(jsdom 은 그러지 않는다), 그 경로로 빠지면 /course/ 라는 아무것도 아닌
    // 주소로 이동한다. 그래서 제출 처리기 자체를 직접 검증한다.
    push.mockClear()
    const { container } = render(<OpenAnyCourse lang="ko" />)

    fireEvent.submit(container.querySelector('form')!)

    expect(push).not.toHaveBeenCalled()
  })
})
