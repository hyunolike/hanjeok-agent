import Link from 'next/link'
import type { Lang } from '@/lib/i18n'
import { DEMO_COURSES, DEMO_PROVES } from '@/lib/demo-courses'
import { GRADE_LABEL, GRADE_STYLE } from '@/lib/grades'
import { placeDescription, tourismPhotos, type RecordedCourse } from '@/lib/recorded-courses'
import { PlacePhoto } from './PlacePhoto'

export function DemoCourseView({ snapshot, lang }: { snapshot: RecordedCourse; lang: Lang }) {
  const { course, capturedAt } = snapshot
  const demo = DEMO_COURSES.find(value => value.uuid === course.uuid)!
  const ko = lang === 'ko'
  const items = [...course.items].sort((a, b) => a.visitOrder - b.visitOrder)
  return <div className="space-y-7">
    <Link href={`/${lang}#demo-courses`} className="inline-flex min-h-control-sm items-center text-body text-brand-primary underline underline-offset-4">{ko ? '모든 예시 코스' : 'All example courses'}</Link>
    <header className="space-y-3">
      <span className="inline-block rounded-chip bg-brand-soft px-3 py-1 text-caption text-brand-primary">{ko ? '예시 코스' : 'Example course'}</span>
      <h1 className="text-title-1 sm:text-display">{demo.label}</h1>
      <p className="text-body text-ink-body">{DEMO_PROVES[lang][demo.kind]}</p>
      <p className="text-caption text-ink-muted">{ko ? `서울 · ${items.length}곳 · 저장된 방문일 ${course.targetDate}` : `Seoul · ${items.length} stops · Saved visit date ${course.targetDate}`}</p>
    </header>
    <aside className="rounded-control border border-line-normal bg-surface-panel p-4 text-caption leading-relaxed text-ink-body">
      <p>{ko ? '한적에서 저장한 코스를 보여 드려요. 혼잡도와 이동 시간은 저장 당시 값이며 현재 예보가 아니에요.' : 'This is a saved Hanjeok course. Grades and travel times are historical values, not current forecasts.'}</p>
      <p className="mt-2 text-ink-muted">{ko ? `자료 확인 ${capturedAt.slice(0, 10)} · 오늘 여행은 한적에서 날짜를 골라 확인해 주세요.` : `Captured ${capturedAt.slice(0, 10)}. Choose your date on Hanjeok for a current forecast.`}</p>
      <a className="mt-2 inline-flex min-h-control-sm items-center text-brand-primary underline underline-offset-4" href="https://hanjeok.com">{ko ? '한적에서 현재 예보 보기' : 'Current forecasts on Hanjeok'} ↗</a>
    </aside>
    {items.length === 0 ? <p role="status">{ko ? '저장된 방문지가 없어요. 다른 예시 코스를 골라 주세요.' : 'No saved stops. Choose another example course.'}</p> : <ol className="space-y-5">
      {items.map((item, index) => {
        const photos = tourismPhotos(item.imageUrls)
        const description = placeDescription(item.overview)
        return <li key={item.attractionId} className="overflow-hidden rounded-card border border-line-normal bg-surface-panel">
          <PlacePhoto urls={photos} name={item.name} lang={lang} eager={index === 0} />
          <div className="space-y-3 p-5">
            <div className="flex flex-wrap items-center gap-2 text-caption text-ink-muted">
              <span className="rounded-chip bg-brand-soft px-2.5 py-1 font-semibold text-brand-primary">{item.visitOrder}</span>
              <span>{item.timeLabel}</span>
              {item.travelMinutesFromPrev !== null && <span>{ko ? `이전 장소에서 이동 ${item.travelMinutesFromPrev}분` : `${item.travelMinutesFromPrev} min from previous stop`}</span>}
              <span className={`rounded-chip px-2 py-1 ${item.grade ? GRADE_STYLE[item.grade] : 'bg-grade-unknown-soft text-grade-unknown-text'}`}>{ko ? '저장 당시 ' : 'Saved: '}{item.grade ? GRADE_LABEL[item.grade] : ko ? '예보 없음' : 'No forecast'}</span>
            </div>
            <h2 className="text-title-2">{item.name}</h2>
            <p className="text-caption text-ink-muted">{item.areaLabel} · {item.latitude.toFixed(5)}, {item.longitude.toFixed(5)}</p>
            <a href={item.detailUrl} aria-label={`${item.name} ${ko ? '공식 상세 보기' : 'official place details'}`} className="inline-flex min-h-control-sm items-center text-caption text-brand-primary underline underline-offset-4">{ko ? '한적에서 장소 상세 보기' : 'Place details on Hanjeok'} ↗</a>
            {description ? <details className="place-description text-body leading-relaxed text-ink-body">
              <summary aria-label={`${item.name}: ${ko ? '장소 소개' : 'Place description'}`} className="cursor-pointer list-none [&::-webkit-details-marker]:hidden"><span aria-hidden="true" className="place-preview line-clamp-3">{description}</span><span className="mt-2 inline-flex min-h-control-sm items-center text-caption text-brand-primary underline underline-offset-4">{ko ? '장소 소개 펼치기 / 접기' : 'Expand / collapse place description'}</span></summary>
              <p className="mt-2 whitespace-pre-line">{description}</p>
            </details> : <p className="text-body text-ink-muted">{ko ? '아직 등록된 장소 소개가 없어요.' : 'No place description is available yet.'}</p>}
            <p className="border-t border-line-normal pt-3 text-caption leading-relaxed text-ink-body">{item.reason}</p>
            <p className="text-caption text-ink-muted">{ko ? '장소 정보와 사진: ⓒ한국관광공사 TourAPI' : 'Place information and photos: © Korea Tourism Organization, TourAPI'}</p>
          </div>
        </li>
      })}
    </ol>}
    {course.recommendedDate && <p className="rounded-control bg-brand-soft p-4 text-body text-brand-primary">{ko ? `저장 당시 다른 날짜 제안: ${course.recommendedDate.date}. 현재 방문 가능한 날짜인지 다시 확인해 주세요.` : `Historical date suggestion: ${course.recommendedDate.date}. Check current availability before visiting.`}</p>}
    <p className="text-caption leading-relaxed text-ink-muted">{ko ? '이 예시는 저장된 코스의 방문 순서와 문구를 그대로 사용해요. 현재 혼잡도나 AI 설명을 새로 만들지 않아요.' : 'The example preserves saved stop order and reasons. It does not generate a current forecast or a new AI explanation.'}</p>
    <Link href={`/${lang}#demo-courses`} className="inline-flex min-h-control-md items-center rounded-control bg-brand-primary px-5 text-body text-brand-on-primary">{ko ? '다른 예시 코스 보기' : 'Explore more examples'}</Link>
  </div>
}
