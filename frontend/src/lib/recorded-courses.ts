import { z } from 'zod'
import { courseItemSchema } from './schema'
import deoksu from './recorded-courses/129efdef-41ec-4044-ac87-303abe4ccdde.json'
import gyeongbok from './recorded-courses/e66302c6-b413-4a07-88a5-3bd55e61fc2a.json'
import museum from './recorded-courses/5a2eb601-1f2b-499b-83eb-8a0093f4817e.json'
import placeRecords from './recorded-places.json'
import fourStops from './recorded-courses/dfdb93f6-bfc3-478d-8a14-f9fde88e9c2a.json'

const places = new Map(placeRecords.map(place => [place.id, place]))

// A saved course is not Facts: it contains no live diagnosis or ranked alternatives.
// Keep a distinct type so archived grades cannot silently become current forecasts.
const snapshotSchema = z.object({
  sourceUrl: z.string().url(),
  capturedAt: z.string().datetime(),
  course: z.object({
    uuid: z.string().uuid(),
    targetDate: z.string(),
    congestionReductionRate: z.number(),
    recommendedDate: z.object({ date: z.string(), congestionReductionRate: z.number() }).nullable(),
    items: z.array(courseItemSchema.extend({
      overview: z.string().nullable(),
      imageUrls: z.array(z.string().url()),
      latitude: z.number().min(37.4).max(37.7),
      longitude: z.number().min(126.8).max(127.2),
    }).transform(item => {
      const place = places.get(item.attractionId)
      if (!place || place.name !== item.name || !place.areaLabel.startsWith('서울 ') || !item.imageUrls.includes(place.imageUrl)) {
        throw new Error(`Saved course place does not match official registry: ${item.attractionId}`)
      }
      return { ...item, areaLabel: place.areaLabel, detailUrl: `https://hanjeok.com/attractions/${item.attractionId}` }
    })),
  }),
})
export type RecordedCourse = z.infer<typeof snapshotSchema>
const snapshots: RecordedCourse[] = [deoksu, gyeongbok, museum, fourStops].map(value => snapshotSchema.parse(value))
export function recordedCourse(uuid: string): RecordedCourse | undefined {
  return snapshots.find(snapshot => snapshot.course.uuid === uuid)
}

/** TourAPI text is displayed as text, never injected as HTML. */
export function placeDescription(overview: string | null): string {
  return (overview ?? '').replace(/<br\s*\/?\s*>/gi, '\n').replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').trim()
}

/** Only the official tourism image host supplied by the saved course is accepted. */
export function tourismPhotos(urls: readonly string[]): string[] {
  return urls.filter(value => {
    try {
      const url = new URL(value)
      return url.protocol === 'https:' && url.hostname === 'tong.visitkorea.or.kr' && /^\/cms\/resource(?:_photo)?\//.test(url.pathname)
    } catch { return false }
  })
}
