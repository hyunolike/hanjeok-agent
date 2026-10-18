export const dynamic = 'force-dynamic'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { fetchContextList } from '@/lib/agent'
import { DEMO_COURSES, DEMO_PROVES, missingKinds } from '@/lib/demo-courses'
import { recordedCourse, tourismPhotos } from '@/lib/recorded-courses'
import { PlacePhoto } from '@/components/course/PlacePhoto'
import { dict, isLang } from '@/lib/i18n'
import { AgentFlow } from '@/components/intro/AgentFlow'
import { PendingLink } from '@/components/ui/PendingLink'
import { OpenAnyCourse } from './OpenAnyCourse'

export default async function Home({ params }: { params: Promise<{ lang: string }> }) {
  const { lang } = await params
  if (!isLang(lang)) notFound()
  const t = dict(lang)
  const ko = lang === 'ko'
  // A context service failure must not hide the home or its saved examples.
  const bundle = await fetchContextList().catch(() => ({ kind: 'unavailable' as const, status: 0 }))
  const missing = missingKinds()
  return <div className="space-y-10">
    <section className="home-banner relative isolate overflow-hidden rounded-card bg-surface-inverse text-ink-inverse" aria-label={ko ? '한적 여행 안내' : 'Hanjeok travel guide'}>
      <img src="/brand/home/city.webp" alt="" width={864} height={544} fetchPriority="high" className="home-banner-city pointer-events-none absolute inset-0 h-full w-full object-cover" />
      <div className="relative z-10 max-w-sm space-y-3 px-6 pt-7 sm:px-8 sm:pt-9">
        <h1 className="font-display text-display">한적</h1>
        <p className="text-title-1">{ko ? <>덜 붐비는 곳으로,<br />나만의 하루를 이어 보세요.</> : <>A quieter place.<br />A day of your own.</>}</p>
        <p className="max-w-64 text-body">{ko ? '장소를 둘러보고, 저장된 예시 코스로 한적한 여행을 만나 보세요.' : 'Explore real places and discover quieter travel through saved example routes.'}</p>
        <a href="#demo-courses" className="inline-flex min-h-control-sm items-center rounded-control bg-brand-primary px-4 text-body text-brand-on-primary">{ko ? '예시 코스 둘러보기' : 'Explore example courses'}</a>
      </div>
      <img src="/brand/guide/found.webp" alt="" width={112} height={112} className="home-banner-character pointer-events-none absolute right-6 top-5" />
    </section>

    <PendingLink href={`/${lang}/ask`} pendingLabel={ko ? '질문 화면을 열고 있어요' : 'Opening the question screen'} className="flex items-center justify-between gap-4 rounded-card border border-line-normal bg-surface-panel px-5 py-4 hover:border-brand-primary">
      <span className="flex flex-col gap-1"><span className="text-title-2 text-ink-title">{t.guide.title}</span><span className="text-caption text-ink-muted">{t.guide.lead}</span></span>
      <span aria-hidden="true" className="text-title-2 text-brand-primary">→</span>
    </PendingLink>

    <section className="space-y-3" aria-label={ko ? '한적 에이전트 소개' : 'About the Hanjeok agent'}>
      <h2 className="text-title-1">{ko ? '여행 질문에, 출처가 있는 답을' : 'Travel answers with sources'}</h2>
      <p className="text-body leading-relaxed text-ink-body">{ko ? '한적 에이전트는 장소와 정책을 찾고, 필요한 날짜의 혼잡 예보와 대안을 조회해 여행 질문에 답해요. 답을 뒷받침한 근거와 장소 사이의 관계도 함께 확인할 수 있어요.' : 'The Hanjeok agent finds places and policies, checks dated forecasts and alternatives when needed, and answers travel questions with sources and place relationships you can inspect.'}</p>
    </section>
    <AgentFlow lang={lang} />

    <section id="demo-courses" className="scroll-mt-6 space-y-4" aria-labelledby="demo-heading">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="demo-heading" className="text-title-1">{ko ? '어떤 하루를 보내고 싶나요?' : 'What kind of day would you like?'}</h2>
        <span className="text-caption text-ink-muted">{ko ? '예시 코스' : 'Example courses'}</span>
      </div>
      <p className="text-body leading-relaxed text-ink-body">{ko ? '서울의 고궁과 전시 공간, 한강을 잇는 네 가지 예시 코스를 만나 보세요.' : 'Four example routes connecting Seoul’s palaces, exhibition spaces and the Han River.'}</p>
      <p className="text-caption leading-relaxed text-ink-muted">{ko ? '2026년 9월 12일에 저장된 예시예요. 혼잡도는 저장 당시 값이며 현재 예보가 아니에요.' : 'Saved examples for September 12, 2026. Grades are historical values, not current forecasts.'}</p>
      {DEMO_COURSES.length === 0 ? <div role="status" className="rounded-card border border-dashed border-line-strong p-6 text-body"><p className="font-medium">{t.home.emptyTitle}</p><p className="mt-2 text-ink-muted">{t.home.emptyBody(missing.join(', '))}</p></div> :
        <ul className="grid gap-5 sm:grid-cols-2">
          {DEMO_COURSES.map(course => {
            const snapshot = recordedCourse(course.uuid)
            const items = snapshot?.course.items ?? []
            const first = items[0]
            return <li key={course.uuid} className="min-w-0">
              <PendingLink href={`/${lang}/course/${course.uuid}`} pendingLabel={ko ? '코스를 열고 있어요' : 'Opening the course'} className="block h-full overflow-hidden rounded-card border border-line-normal bg-surface-panel hover:border-brand-primary">
                <PlacePhoto urls={tourismPhotos(first?.imageUrls ?? [])} name={first?.name ?? course.label} lang={lang} />
                <div className="space-y-2 p-5">
                  <p className="text-caption text-brand-primary">{ko ? `예시 코스 · 서울 · ${items.length}곳` : `Example course · Seoul · ${items.length} stops`}</p>
                  <h3 className="text-title-2">{course.label}</h3>
                  <p className="text-caption leading-relaxed text-ink-body">{DEMO_PROVES[lang][course.kind]}</p>
                  <p className="text-caption leading-relaxed text-ink-muted">{items.map(item => item.name).join(' → ')}</p>
                  <span className="inline-flex min-h-control-sm items-center text-caption font-semibold text-brand-primary">{ko ? '코스 자세히 보기' : 'View course'} <span aria-hidden="true" className="ml-2">→</span></span>
                </div>
              </PendingLink>
            </li>
          })}
        </ul>}
      <p className="text-caption text-ink-muted">{ko ? '장소 정보와 사진: ⓒ한국관광공사 TourAPI' : 'Place information and photos: © Korea Tourism Organization, TourAPI'}</p>
    </section>

    <details className="space-y-4 border-t border-line-normal pt-6">
      <summary className="cursor-pointer py-3 text-body text-ink-muted">{ko ? '기존 코스 설명기의 규칙과 검증 기록' : 'Rules and verification of the original course explainer'}</summary>
      <p className="text-caption text-ink-muted">{ko ? '아래는 저장된 코스를 설명하던 기존 기능의 기록이에요. 위 질문 에이전트의 검색 범위나 성능 수치를 뜻하지 않아요.' : 'These records describe the original saved-course explainer, rather than the scope or performance of the question agent above.'}</p>
    <section className="space-y-4">
      <h2 className="text-title-2">{t.home.ruleTitle}</h2>
      <p className="text-body leading-relaxed text-ink-body">{t.home.ruleBody}</p>
      <p className="border-l-2 border-line-strong pl-4 text-body leading-relaxed">{t.home.ruleConsequence}</p>
      <p className="text-body leading-relaxed text-ink-muted">{t.home.silentFailure}</p>
      {t.home.generatedLanguageNote && <p className="text-caption text-ink-muted">{t.home.generatedLanguageNote}</p>}
    </section>
    <section className="space-y-4">
      <h2 className="text-body font-semibold text-ink-muted">{t.home.metricsTitle}</h2>
      <ul className="grid gap-3 sm:grid-cols-3">
        <Metric value={bundle.kind === 'loaded' ? t.home.bundle.value(bundle.value.documents.length, bundle.value.systemTextBytes.toLocaleString()) : t.home.bundle.unavailable} label={t.home.bundle.label} cta={t.home.bundle.cta} href={`/${lang}/evidence`} />
        <Metric value={t.home.forbidden.value} label={t.home.forbidden.label} cta={t.home.forbidden.cta} href={t.home.forbidden.href} external />
        <Metric value={t.home.citationGuard.value} label={t.home.citationGuard.label} cta={t.home.citationGuard.cta} href={t.home.citationGuard.href} external />
      </ul>
    </section>
    </details>
    <section className="border-t border-line-normal pt-6">
      <details><summary className="cursor-pointer py-3 text-body text-ink-muted">{t.home.openAnySummary}</summary><div className="mt-3 space-y-3"><OpenAnyCourse lang={lang} /><p className="text-caption leading-relaxed text-ink-muted">{t.home.openAnyNote}</p></div></details>
    </section>
  </div>
}

function Metric({
  value,
  label,
  cta,
  href,
  external = false,
}: {
  value: string
  label: string
  cta: string
  href: string
  external?: boolean
}) {
  // 숫자마다 그것을 확인할 수 있는 곳으로 가는 링크가 붙는다. 확인할 데가 없는
  // 숫자는 화면에 적지 않는다 — 그건 주장이지 측정값이 아니다.
  const link = external ? (
    <a href={href} target="_blank" rel="noreferrer" className="underline underline-offset-4">
      {cta} ↗
    </a>
  ) : (
    <Link href={href} className="underline underline-offset-4">
      {cta} →
    </Link>
  )

  return (
    <li className="flex flex-col gap-2 rounded-card border border-line-normal p-4">
      <span className="text-body font-semibold">{value}</span>
      <span className="flex-1 text-caption leading-relaxed text-ink-muted">{label}</span>
      <span className="text-caption">{link}</span>
    </li>
  )
}
