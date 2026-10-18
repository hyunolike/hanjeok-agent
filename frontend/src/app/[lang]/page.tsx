export const dynamic = 'force-dynamic'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { fetchContextList } from '@/lib/agent'
import { fetchEvalReport, type Loaded } from '@/lib/guide'
import type { EvalReport } from '@/lib/guide-schema'
import { DEMO_COURSES, DEMO_PROVES, missingKinds } from '@/lib/demo-courses'
import { recordedCourse, tourismPhotos } from '@/lib/recorded-courses'
import { PlacePhoto } from '@/components/course/PlacePhoto'
import { dict, isLang, type Dict, type Lang } from '@/lib/i18n'
import { AgentFlow } from '@/components/intro/AgentFlow'
import { PendingLink } from '@/components/ui/PendingLink'
import { OpenAnyCourse } from './OpenAnyCourse'

export default async function Home({ params }: { params: Promise<{ lang: string }> }) {
  const { lang } = await params
  if (!isLang(lang)) notFound()
  const t = dict(lang)
  const ko = lang === 'ko'
  // 숫자는 평가 화면과 같은 보고서에서 읽는다. 여기 따로 적어 두면 다음 평가에서 두 화면이 어긋난다.
  const report = await fetchEvalReport().catch((): Loaded<EvalReport> => ({ ok: false, cause: 'unavailable' }))
  // 코스 설명기 기록용. 실패해도 홈은 그대로 읽힌다.
  const bundle = await fetchContextList().catch(() => ({ kind: 'unavailable' as const, status: 0 }))
  const missing = missingKinds()
  return <div className="space-y-12">
    <section className="home-banner relative isolate overflow-hidden rounded-card bg-surface-inverse text-ink-inverse" aria-labelledby="home-title">
      <img src="/brand/home/city.webp" alt="" width={864} height={544} fetchPriority="high" className="home-banner-city pointer-events-none absolute inset-0 h-full w-full object-cover" />
      <div className="relative z-10 max-w-sm space-y-3 px-6 pt-7 sm:px-8 sm:pt-9">
        <p className="text-caption font-semibold">{t.home.bannerEyebrow}</p>
        <h1 id="home-title" className="text-title-1">{t.home.bannerTitle[0]}<br />{t.home.bannerTitle[1]}</h1>
        <p className="max-w-64 text-body">{t.home.bannerBody}</p>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <PendingLink href={`/${lang}/ask`} pendingLabel={ko ? '질문 화면을 열고 있어요' : 'Opening the question screen'} className="inline-flex min-h-control-sm items-center rounded-control bg-brand-primary px-4 text-body text-brand-on-primary">{t.home.bannerCta}</PendingLink>
          <a href="#demo-courses" className="inline-flex min-h-control-sm items-center text-body underline underline-offset-4">{t.home.bannerSecondary}</a>
        </div>
      </div>
      <img src="/brand/guide/found.webp" alt="" width={112} height={112} className="home-banner-character pointer-events-none absolute right-6 top-5" />
    </section>

    <section className="space-y-5" aria-labelledby="role-heading">
      <h2 id="role-heading" className="text-title-1">{t.home.roleTitle}</h2>
      <p className="text-body leading-relaxed text-ink-body">{t.home.roleLead}</p>
      <img src="/brand/home/guide-in-hanjeok.webp" alt="" width={960} height={434} loading="lazy" className="mx-auto w-full max-w-xl" />
      <ol className="grid gap-3 sm:grid-cols-3">
        {t.home.roles.map((role, index) => <li key={role.title} className="flex flex-col gap-2 rounded-card border border-line-normal bg-surface-panel p-4">
          <span className="text-caption font-semibold text-brand-primary">{index + 1}</span>
          <h3 className="text-body font-semibold text-ink-title">{role.title}</h3>
          <p className="text-caption leading-relaxed text-ink-body">{role.body}</p>
        </li>)}
      </ol>
      <dl className="grid gap-3 rounded-card bg-surface-panel p-4 text-caption leading-relaxed sm:grid-cols-2">
        <div><dt className="font-semibold text-ink-title">{t.home.scopeYesLabel}</dt><dd className="mt-1 text-ink-body">{t.home.scopeYes}</dd></div>
        <div><dt className="font-semibold text-ink-title">{t.home.scopeNoLabel}</dt><dd className="mt-1 text-ink-body">{t.home.scopeNo}</dd></div>
      </dl>
      <p className="text-caption leading-relaxed text-ink-muted">{t.home.stageNote}</p>
    </section>

    <AgentFlow lang={lang} />

    <Metrics lang={lang} t={t} report={report} />

    <section id="demo-courses" className="scroll-mt-6 space-y-4 border-t border-line-normal pt-6" aria-labelledby="demo-heading">
      <h2 id="demo-heading" className="text-title-1">{t.home.demoHeading}</h2>
      <p className="text-body leading-relaxed text-ink-body">{t.home.demoLead}</p>
      <p className="text-caption leading-relaxed text-ink-muted">{t.home.demoSavedNote}</p>
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
      <p className="text-caption leading-relaxed text-ink-muted">{t.home.silentFailure}</p>
      {t.home.generatedLanguageNote && <p className="text-caption text-ink-muted">{t.home.generatedLanguageNote}</p>}
      <p className="text-caption text-ink-muted">{ko ? '장소 정보와 사진: ⓒ한국관광공사 TourAPI' : 'Place information and photos: © Korea Tourism Organization, TourAPI'}</p>
    </section>

    <details className="space-y-4 border-t border-line-normal pt-6">
      <summary className="cursor-pointer py-3 text-body text-ink-muted">{ko ? '기존 코스 설명기의 규칙과 검증 기록' : 'Rules and verification of the original course explainer'}</summary>
      <p className="text-caption text-ink-muted">{ko ? '아래는 저장된 코스를 설명하던 기존 기능의 기록이에요. 위 질문 에이전트의 검색 범위나 성능 수치를 뜻하지 않아요.' : 'These records describe the original saved-course explainer, rather than the scope or performance of the question agent above.'}</p>
      <section className="space-y-4">
        <h2 className="text-title-2">{t.explainer.ruleTitle}</h2>
        <p className="text-body leading-relaxed text-ink-body">{t.explainer.ruleBody}</p>
        <p className="border-l-2 border-line-strong pl-4 text-body leading-relaxed">{t.explainer.ruleConsequence}</p>
      </section>
      <section className="space-y-4">
        <h2 className="text-body font-semibold text-ink-muted">{t.explainer.metricsTitle}</h2>
        <ul className="grid gap-3 sm:grid-cols-3">
          <Metric value={bundle.kind === 'loaded' ? t.explainer.bundle.value(bundle.value.documents.length, bundle.value.systemTextBytes.toLocaleString()) : t.explainer.bundle.unavailable} label={t.explainer.bundle.label} cta={t.explainer.bundle.cta} href={`/${lang}/evidence`} />
          <Metric value={t.explainer.forbidden.value} label={t.explainer.forbidden.label} cta={t.explainer.forbidden.cta} href={t.explainer.forbidden.href} external />
          <Metric value={t.explainer.citationGuard.value} label={t.explainer.citationGuard.label} cta={t.explainer.citationGuard.cta} href={t.explainer.citationGuard.href} external />
        </ul>
      </section>
    </details>

    <section className="border-t border-line-normal pt-6">
      <details><summary className="cursor-pointer py-3 text-body text-ink-muted">{t.home.openAnySummary}</summary><div className="mt-3 space-y-3"><OpenAnyCourse lang={lang} /><p className="text-caption leading-relaxed text-ink-muted">{t.home.openAnyNote}</p></div></details>
    </section>
  </div>
}

/** 지금 서비스가 쓰는 방식. 서버의 기본값(`api.py`)과 같아야 한다. */
const SERVED = 'graph' as const
const OTHER = 'vector' as const

function Metrics({ lang, t, report }: { lang: Lang; t: Dict; report: Loaded<EvalReport> }) {
  const href = `/${lang}/eval`
  if (!report.ok) {
    return <section className="space-y-4">
      <h2 className="text-title-2">{t.home.metricsTitle}</h2>
      <p className="text-body text-ink-muted">{t.home.metricsUnavailable} <Link href={href} className="underline underline-offset-4">{t.home.metricsCta} →</Link></p>
    </section>
  }
  const data = report.data
  const served = data.strategies[SERVED]
  const recall = served.metrics.id_recall
  const otherRecall = data.strategies[OTHER].metrics.id_recall
  // 세지 않은 규칙은 0으로 더하지 않는다. 세어진 것만 건수와 가짓수에 들어간다.
  const counted = Object.values(served.forbidden).filter(entry => entry !== undefined)
  const occurrences = counted.reduce((sum, entry) => sum + entry.occurrences, 0)
  const runs = Math.max(0, ...counted.map(entry => entry.runs))
  return <section className="space-y-4">
    <h2 className="text-title-2">{t.home.metricsTitle}</h2>
    <p className="text-body leading-relaxed text-ink-body">{t.home.metricsLead(data.question_count, exportDay(data.export_as_of, lang))}</p>
    <p className="text-caption leading-relaxed text-ink-muted">{t.home.ruleLimit}</p>
    <ul className="grid gap-3 sm:grid-cols-3">
      {recall.value !== null && otherRecall.value !== null &&
        <Metric value={t.home.recall.value(percent(recall.value))} label={t.home.recall.label(recall.n, percent(otherRecall.value))} cta={t.home.metricsCta} href={`${href}#eval-metrics`} />}
      <Metric value={t.home.abstention.value(served.abstention.unanswerable_correct, served.abstention.unanswerable_total)} label={t.home.abstention.label} cta={t.home.metricsCta} href={`${href}#eval-metrics`} />
      <Metric value={t.home.forbidden.value(occurrences)} label={t.home.forbidden.label(runs, counted.length)} cta={t.home.metricsCta} href={`${href}#eval-forbidden`} />
    </ul>
  </section>
}

const percent = (value: number) => `${Math.round(value * 1000) / 10}%`

/** 내보낸 날짜. 한적의 기준인 한국 시간으로 적는다. */
function exportDay(iso: string, lang: Lang) {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return new Intl.DateTimeFormat(lang === 'ko' ? 'ko-KR' : 'en-GB', { timeZone: 'Asia/Seoul', month: 'long', day: 'numeric' }).format(date)
}

function Metric({ value, label, cta, href, external = false }: { value: string; label: string; cta: string; href: string; external?: boolean }) {
  // 숫자마다 그것을 확인할 수 있는 곳으로 가는 링크가 붙는다. 확인할 데가 없는
  // 숫자는 화면에 적지 않는다. 그건 주장이지 측정값이 아니다.
  return (
    <li className="flex flex-col gap-2 rounded-card border border-line-normal p-4">
      <span className="text-body font-semibold">{value}</span>
      <span className="flex-1 text-caption leading-relaxed text-ink-muted">{label}</span>
      <span className="text-caption">{external
        ? <a href={href} target="_blank" rel="noreferrer" className="underline underline-offset-4">{cta} ↗</a>
        : <Link href={href} className="underline underline-offset-4">{cta} →</Link>}</span>
    </li>
  )
}
