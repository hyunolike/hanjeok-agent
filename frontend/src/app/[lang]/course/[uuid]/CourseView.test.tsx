import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { factsFixture } from '@/lib/fixtures'
import { CourseView } from './CourseView'

describe('코스 화면', () => {
  it('설명이 없어도 방문 순서가 전부 그려진다', () => {
    // 스펙 §6.1 의 약속이다. 이 컴포넌트가 설명을 인자로 받지 않는 것이 그 약속을
    // 구조로 지키는 방법이라, 여기서 렌더되는 것이 곧 LLM 이 죽었을 때의 화면이다.
    render(<CourseView facts={factsFixture} lang="ko" />)

    expect(screen.getByText('경복궁')).toBeInTheDocument()
    expect(screen.getByText('북촌 한옥마을')).toBeInTheDocument()
    // 한적이 규칙으로 붙인 문구는 LLM 과 무관하게 남는다.
    expect(screen.getByText(/첫 방문지로 두었어요/)).toBeInTheDocument()
  })

  it('등급을 한국어 라벨로 그린다', () => {
    render(<CourseView facts={factsFixture} lang="ko" />)

    expect(screen.getByText('매우혼잡')).toBeInTheDocument()
    expect(screen.getByText('보통')).toBeInTheDocument()
  })

  it('visitOrder 순서대로 그린다', () => {
    // 서버가 순서를 섞어 보내도 화면은 방문 순서를 지켜야 한다 — 순서가 곧
    // 이 코스의 내용이고, 뒤집어 그리면 REORDERED_COURSE 를 화면이 저지른다.
    const shuffled = { ...factsFixture, items: [...factsFixture.items].reverse() }
    render(<CourseView facts={shuffled} lang="ko" />)

    // 항목 자체를 세로로 읽는다 — 제목과 reason 문장에도 같은 이름이 들어 있어
    // 텍스트 전체를 훑으면 순서가 아니라 등장 횟수를 세게 된다.
    const order = screen.getAllByRole('listitem').map((item) => item.textContent ?? '')
    expect(order[0]).toContain('경복궁')
    expect(order[1]).toContain('북촌 한옥마을')
  })

  it('예보가 없는 장소는 등급 대신 그렇게 말한다', () => {
    // 자리를 비우면 "등급이 뭐였더라"가 되고, 아무 색이나 넣으면 없는 진단을
    // 있는 것처럼 만든다. 코스는 등급 없는 장소가 있어도 여전히 코스다.
    const noForecast = {
      ...factsFixture,
      items: [{ ...factsFixture.items[0], grade: null }, factsFixture.items[1]],
    }
    render(<CourseView facts={noForecast} lang="ko" />)

    expect(screen.getByText('예보 없음')).toBeInTheDocument()
    expect(screen.getByText('경복궁')).toBeInTheDocument()
  })

  it('대안이 비면 후보가 없었다고 말한다', () => {
    // "점수가 낮아 밀렸다"와 "후보가 애초에 없었다"는 다른 말이다.
    render(<CourseView facts={{ ...factsFixture, alternatives: [] }} lang="ko" />)

    expect(screen.getByText(/후보 자체가 없었습니다/)).toBeInTheDocument()
  })

  it('대안이 있으면 그 문구를 띄우지 않는다', () => {
    render(<CourseView facts={factsFixture} lang="ko" />)

    expect(screen.queryByText(/후보 자체가 없었습니다/)).not.toBeInTheDocument()
  })

  it('첫 방문지에는 이동 시간을 붙이지 않는다', () => {
    render(<CourseView facts={factsFixture} lang="ko" />)

    expect(screen.getByText('이동 8분')).toBeInTheDocument()
    expect(screen.queryByText(/이동 null분/)).not.toBeInTheDocument()
  })
})
