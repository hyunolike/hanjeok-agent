import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { PlacePhoto } from './PlacePhoto'
it('첫 사진 실패 시 같은 장소의 다음 사진을 시도하고 모두 실패하면 안내한다', () => {
  render(<PlacePhoto urls={['https://example.test/first.jpg', 'https://example.test/second.jpg']} name="덕수궁" lang="ko" />)
  expect(screen.getByRole('status')).toHaveTextContent('사진 불러오는 중')
  fireEvent.error(screen.getByAltText('덕수궁'))
  expect(screen.getByAltText('덕수궁')).toHaveAttribute('src', 'https://example.test/second.jpg')
  fireEvent.error(screen.getByAltText('덕수궁'))
  expect(screen.getByRole('img', { name: '덕수궁: 사진을 준비 중이에요' })).toBeInTheDocument()
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
})
it('사진이 도착하면 로딩 안내가 사라진다', () => {
  render(<PlacePhoto urls={['https://example.test/photo.jpg']} name="서울" lang="en" />)
  fireEvent.load(screen.getByAltText('서울'))
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
  expect(screen.getByAltText('서울')).not.toHaveClass('invisible')
})
it('사진이 없고 장소가 바뀌는 경우에도 다른 장소 사진을 남기지 않는다', () => {
  const view = render(<PlacePhoto urls={[]} name="서울" lang="en" />)
  expect(screen.getByRole('img', { name: '서울: Photo unavailable' })).toBeInTheDocument()
  view.rerender(<PlacePhoto urls={['https://example.test/new.jpg']} name="부산" lang="en" />)
  expect(screen.getByAltText('부산')).toHaveAttribute('src', 'https://example.test/new.jpg')
})
