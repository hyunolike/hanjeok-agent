import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { AgentFlow, STEP_MS } from './AgentFlow'

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })

it('설명은 정지 상태로 시작하고 재생·일시정지·마지막 단계·다시 시작을 제어한다', () => {
  vi.useFakeTimers()
  render(<AgentFlow lang="ko" />)
  expect(screen.getByRole('button', { name: '이전 단계' })).toBeDisabled()
  act(() => vi.advanceTimersByTime(STEP_MS * 2))
  expect(screen.getByRole('button', { name: /01 질문 보내기/ })).toHaveAttribute('aria-current', 'step')
  fireEvent.click(screen.getByRole('button', { name: '재생' }))
  act(() => vi.advanceTimersByTime(STEP_MS))
  expect(screen.getByRole('button', { name: /02 조회 고르기/ })).toHaveAttribute('aria-current', 'step')
  fireEvent.click(screen.getByRole('button', { name: '일시정지' }))
  act(() => vi.advanceTimersByTime(STEP_MS * 2))
  expect(screen.getByRole('button', { name: /02 조회 고르기/ })).toHaveAttribute('aria-current', 'step')
  fireEvent.click(screen.getByRole('button', { name: /06 검사하고 보내기/ }))
  expect(screen.getByRole('button', { name: '다음 단계' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: '처음으로' }))
  expect(screen.getByRole('button', { name: /01 질문 보내기/ })).toHaveAttribute('aria-current', 'step')
})

it('움직임 줄이기 설정에서는 자동 재생 없이 키보드로 단계 설명을 읽는다', () => {
  vi.stubGlobal('matchMedia', () => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
  render(<AgentFlow lang="en" />)
  expect(screen.getByRole('button', { name: 'Play' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Next' }))
  expect(screen.getByRole('button', { name: /02 Choose a lookup/ })).toHaveAttribute('aria-current', 'step')
  expect(screen.getByText(/Reduced motion is enabled/)).toBeInTheDocument()
})

it('구조도는 단계마다 실제로 거치는 곳을 밝힌다', () => {
  // 그림만 움직이고 어디를 지나는지 말하지 않으면, 화면 읽기 도구에는 아무것도 전해지지 않는다.
  const { container } = render(<AgentFlow lang="ko" />)
  const active = () => [...container.querySelectorAll('svg.sm\\:block [data-active="true"]')].map(node => node.getAttribute('data-node'))
  expect(active()).toEqual(['browser', 'api', 'agent'])
  fireEvent.click(screen.getByRole('button', { name: /04 한적에 묻기/ }))
  expect(active()).toEqual(['browser', 'agent', 'hanjeok'])
  // 조회는 질문 하나에 최대 3번. 조회 단계에서만 그 표시가 뜬다.
  expect(screen.getAllByText('최대 3번').length).toBeGreaterThan(0)
  fireEvent.click(screen.getByRole('button', { name: /06 검사하고 보내기/ }))
  expect(screen.queryByText('최대 3번')).not.toBeInTheDocument()
})

it('기술 로고는 공식 이름을 함께 단다', () => {
  const { container } = render(<AgentFlow lang="en" />)
  const titles = [...container.querySelectorAll('svg.sm\\:block title')].map(node => node.textContent)
  for (const name of ['Next.js', 'Vercel', 'FastAPI', 'LangGraph', 'Neo4j', 'NVIDIA']) expect(titles).toContain(name)
})
