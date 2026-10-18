import { render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import * as agent from '@/lib/agent'
import { DEMO_COURSES } from '@/lib/demo-courses'
import CoursePage from './page'
vi.mock('next/navigation', () => ({ notFound: () => { throw new Error('notFound') }, useRouter: () => ({ refresh: vi.fn() }) }))
afterEach(() => vi.restoreAllMocks())
it.each(DEMO_COURSES)('서버가 없어도 저장된 예시를 연다: $kind', async ({ uuid }) => {
  const fetch = vi.spyOn(agent, 'fetchFacts').mockResolvedValue({ kind: 'unavailable', status: 503 })
  const explain = vi.spyOn(agent, 'fetchExplanation')
  render(await CoursePage({ params: Promise.resolve({ lang: 'ko', uuid }) }))
  expect(screen.getByText('예시 코스')).toBeInTheDocument()
  expect(screen.getByText(/현재 예보가 아니에요/)).toBeInTheDocument()
  expect(screen.getAllByRole('listitem').length).toBeGreaterThan(0)
  expect(fetch).not.toHaveBeenCalled()
  expect(explain).not.toHaveBeenCalled()
})
it('일반 UUID의 실패를 다른 예시로 대체하지 않고 재시도와 홈을 제공한다', async () => {
  vi.spyOn(agent, 'fetchFacts').mockResolvedValue({ kind: 'unavailable', status: 503 })
  render(await CoursePage({ params: Promise.resolve({ lang: 'en', uuid: 'unknown' }) }))
  expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Back to home' })).toHaveAttribute('href', '/en')
  expect(screen.queryByText('예시 코스')).not.toBeInTheDocument()
})

it('제외한 동명 장소 코스의 기존 URL은 라이브 요청 없이 404로 처리한다', async () => {
  const fetch = vi.spyOn(agent, 'fetchFacts')
  await expect(CoursePage({ params: Promise.resolve({ lang: 'ko', uuid: 'b0719488-c2c7-4256-bc83-e8b2cf5734cd' }) })).rejects.toThrow('notFound')
  expect(fetch).not.toHaveBeenCalled()
})
