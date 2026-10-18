import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { recordedCourse } from '@/lib/recorded-courses'
import { DEMO_COURSES } from '@/lib/demo-courses'
import { DemoCourseView } from './DemoCourseView'
it('빈 방문지와 없는 장소 소개를 구분해 안내한다', () => {
  const snapshot = recordedCourse(DEMO_COURSES[0].uuid)!
  const view = render(<DemoCourseView snapshot={{ ...snapshot, course: { ...snapshot.course, items: [] } }} lang="ko" />)
  expect(screen.getByRole('status')).toHaveTextContent('저장된 방문지가 없어요')
  view.rerender(<DemoCourseView snapshot={{ ...snapshot, course: { ...snapshot.course, items: [{ ...snapshot.course.items[0], overview: null, imageUrls: [] }] } }} lang="en" />)
  expect(screen.getByText('No place description is available yet.')).toBeInTheDocument()
  expect(screen.getByRole('img', { name: '덕수궁: Photo unavailable' })).toBeInTheDocument()
})
it('각 방문지의 지역과 좌표를 보여 주고 같은 ID의 공식 상세로 연결한다', () => {
  const snapshot = recordedCourse(DEMO_COURSES[0].uuid)!
  render(<DemoCourseView snapshot={snapshot} lang="ko" />)
  for (const item of snapshot.course.items) {
    expect(screen.getByRole('link', { name: `${item.name} 공식 상세 보기` })).toHaveAttribute('href', `https://hanjeok.com/attractions/${item.attractionId}`)
    expect(screen.getByText(`${item.areaLabel} · ${item.latitude.toFixed(5)}, ${item.longitude.toFixed(5)}`)).toBeInTheDocument()
  }
})
