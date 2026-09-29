import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { LangSwitch } from './LangSwitch'

const pathname = vi.fn()
vi.mock('next/navigation', () => ({ usePathname: () => pathname() }))

const href = () => screen.getByRole('link').getAttribute('href')

describe('언어 전환', () => {
  it('보고 있던 화면을 그대로 두고 언어만 바꾼다', () => {
    // 홈으로 보내면 코스를 보다가 언어를 바꾼 사람이 자기 자리를 잃는다.
    pathname.mockReturnValue('/ko/course/abc-123')

    render(<LangSwitch lang="ko" label="English" />)

    expect(href()).toBe('/en/course/abc-123')
  })

  it('홈에서도 홈으로 간다', () => {
    pathname.mockReturnValue('/en')

    render(<LangSwitch lang="en" label="한국어" />)

    expect(href()).toBe('/ko')
  })

  it('경로를 모를 때도 링크가 깨지지 않는다', () => {
    // usePathname 은 null 을 줄 수 있다. 그때 `/undefined` 로 가면 404 다.
    pathname.mockReturnValue(null)

    render(<LangSwitch lang="ko" label="English" />)

    expect(href()).toBe('/en')
  })

  it('링크 문구는 가려는 언어로 적힌다', () => {
    // 한국어를 못 읽는 사람이 찾아야 하는 링크다. 한국어로 "영어" 라고 적혀 있으면
    // 그 사람에게는 보이지 않는 것과 같다.
    pathname.mockReturnValue('/ko')

    render(<LangSwitch lang="ko" label="English" />)

    expect(screen.getByRole('link')).toHaveAttribute('hreflang', 'en')
    expect(screen.getByRole('link')).toHaveTextContent('English')
  })
})
