import { expect, it } from 'vitest'
import { DEMO_COURSES } from './demo-courses'
import { placeDescription, recordedCourse, tourismPhotos } from './recorded-courses'
it('공식 응답의 네 예시가 모두 있고 원본 URL, 날짜와 실제 사진을 갖는다', () => {
  for (const demo of DEMO_COURSES) {
    const snapshot = recordedCourse(demo.uuid)!
    expect(snapshot.sourceUrl).toBe(`https://api.hanjeok.com/api/v1/courses/${demo.uuid}`)
    expect(snapshot.course.targetDate).toBe('2026-09-12')
    expect(snapshot.course.items.length).toBeGreaterThan(0)
    for (const item of snapshot.course.items) {
      expect(tourismPhotos(item.imageUrls).length).toBeGreaterThan(0)
      expect(item.overview === null || placeDescription(item.overview).length > 0).toBe(true)
    }
  }
  expect(recordedCourse('unknown')).toBeUndefined()
})
it('제외한 혼동 코스는 반환하지 않고 네 방문지 순서를 보존한다', () => {
  expect(recordedCourse('b0719488-c2c7-4256-bc83-e8b2cf5734cd')).toBeUndefined()
  expect(recordedCourse(DEMO_COURSES[3].uuid)!.course.items.map(item => item.visitOrder)).toEqual([1, 2, 3, 4])
})
it('사진, 설명, 좌표, 지역과 공식 상세 링크가 같은 장소 ID에 묶인다', () => {
  for (const demo of DEMO_COURSES) {
    for (const item of recordedCourse(demo.uuid)!.course.items) {
      expect(item.attractionId).not.toBe(19983)
      expect(item.areaLabel).toMatch(/^서울 /)
      expect(item.detailUrl).toBe(`https://hanjeok.com/attractions/${item.attractionId}`)
      expect(item.latitude).toBeGreaterThan(37.4)
      expect(item.latitude).toBeLessThan(37.7)
      expect(item.longitude).toBeGreaterThan(126.8)
      expect(item.longitude).toBeLessThan(127.2)
      expect(placeDescription(item.overview).length).toBeGreaterThan(0)
      expect(tourismPhotos(item.imageUrls).length).toBeGreaterThan(0)
    }
  }
})
it('본문을 HTML로 실행하지 않고 공식 사진 호스트만 허용한다', () => {
  expect(placeDescription('소개<br />두 줄<script>alert(1)</script>')).toBe('소개\n두 줄alert(1)')
  expect(tourismPhotos(['javascript:alert(1)', 'http://tong.visitkorea.or.kr/cms/resource/test.jpg', 'https://tong.visitkorea.or.kr.evil.test/cms/resource/x.jpg', 'https://tong.visitkorea.or.kr/cms/resource/x.jpg'])).toEqual(['https://tong.visitkorea.or.kr/cms/resource/x.jpg'])
})
