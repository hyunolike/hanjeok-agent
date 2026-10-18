import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { AgentFlow } from './AgentFlow'

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })
it('설명은 정지 상태로 시작하고 재생·일시정지·마지막 단계·다시 시작을 제어한다', () => {
  vi.useFakeTimers()
  render(<AgentFlow lang="ko" />)
  expect(screen.getByRole('button', { name: '이전 단계' })).toBeDisabled()
  act(() => vi.advanceTimersByTime(5000))
  expect(screen.getByRole('button', { name: /01 질문 읽기/ })).toHaveAttribute('aria-current', 'step')
  fireEvent.click(screen.getByRole('button', { name: '재생' }))
  act(() => vi.advanceTimersByTime(2400))
  expect(screen.getByRole('button', { name: /02 조회 선택하기/ })).toHaveAttribute('aria-current', 'step')
  fireEvent.click(screen.getByRole('button', { name: '일시정지' }))
  act(() => vi.advanceTimersByTime(5000))
  expect(screen.getByRole('button', { name: /02 조회 선택하기/ })).toHaveAttribute('aria-current', 'step')
  fireEvent.click(screen.getByRole('button', { name: /06 인용 검증하기/ }))
  expect(screen.getByRole('button', { name: '다음 단계' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: '처음으로' }))
  expect(screen.getByRole('button', { name: /01 질문 읽기/ })).toHaveAttribute('aria-current', 'step')
})
it('움직임 줄이기 설정에서는 자동 재생 없이 키보드로 단계 설명을 읽는다', () => {
  vi.stubGlobal('matchMedia', () => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
  render(<AgentFlow lang="en" />)
  expect(screen.getByRole('button', { name: 'Play' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Next' }))
  expect(screen.getByRole('button', { name: /02 Choose a lookup/ })).toHaveAttribute('aria-current', 'step')
  expect(screen.getByText(/Reduced motion is enabled/)).toBeInTheDocument()
})
