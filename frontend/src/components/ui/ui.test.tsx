import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Character, CHARACTER_STATES } from '@/components/guide/Character'
import { Badge } from './Badge'
import { Button } from './Button'
import { Field } from './Field'
import { Notice } from './Notice'
import { Sheet } from './Sheet'

describe('Button', () => {
  it('폼 안에서도 제출하지 않는다 — 기본 type 이 button 이다', async () => {
    const onSubmit = vi.fn((event: React.FormEvent) => event.preventDefault())
    render(
      <form onSubmit={onSubmit}>
        <Button>예시</Button>
      </form>,
    )
    await userEvent.click(screen.getByRole('button', { name: '예시' }))
    expect(onSubmit).not.toHaveBeenCalled()
  })
})

describe('Field', () => {
  it('라벨을 눈에서 숨겨도 이름은 남는다', () => {
    render(<Field id="q" label="질문" hideLabel />)
    expect(screen.getByLabelText('질문')).toBeInTheDocument()
  })
})

describe('Badge', () => {
  it('"데이터 없음"은 어떤 등급의 색도 쓰지 않는다', () => {
    render(<Badge tone="unknown">데이터 없음</Badge>)
    const badge = screen.getByText('데이터 없음')
    expect(badge.className).toContain('grade-unknown')
    expect(badge.className).not.toMatch(/grade-(relaxed|normal|crowded|very-crowded)/)
  })
})

describe('Notice', () => {
  it('위험만 하던 말을 끊고 읽힌다', () => {
    render(<Notice tone="danger">실패</Notice>)
    render(<Notice tone="info">안내</Notice>)
    expect(screen.getByRole('alert')).toHaveTextContent('실패')
    expect(screen.getByRole('status')).toHaveTextContent('안내')
  })
})

describe('Sheet', () => {
  it('열리면 초점이 닫기 버튼으로 가고, Esc 와 배경으로 닫힌다', async () => {
    const onClose = vi.fn()
    render(
      <Sheet title="근거" closeLabel="닫기" onClose={onClose}>
        <p>본문</p>
      </Sheet>,
    )
    expect(screen.getByRole('button', { name: '닫기' })).toHaveFocus()

    await userEvent.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledTimes(1)

    // 시트 안을 눌러서는 닫히지 않는다.
    await userEvent.click(screen.getByText('본문'))
    expect(onClose).toHaveBeenCalledTimes(1)

    await userEvent.click(screen.getByRole('dialog').parentElement!)
    expect(onClose).toHaveBeenCalledTimes(2)
  })
})

describe('Character', () => {
  it.each(CHARACTER_STATES)('%s 포즈는 그림 옆에 글로도 상태를 말한다', (state) => {
    const { container } = render(<Character state={state} title="상태 제목" />)
    expect(screen.getByText('상태 제목')).toBeInTheDocument()
    const image = container.querySelector('img')!
    // 같은 말을 글이 하고 있으므로 그림은 장식이다.
    expect(image).toHaveAttribute('alt', '')
    expect(image).toHaveAttribute('src', `/brand/guide/${state}.webp`)
  })

  it('캐릭터 자체는 누를 수 없다', () => {
    render(<Character state="waiting" title="제목" />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
