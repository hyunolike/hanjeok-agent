/**
 * 홈은 번들 크기를 백엔드에서 받아 적는다. 빌드 때 그리면 그 숫자가 굳고, 배포도
 * 백엔드가 떠 있어야만 성공한다 — 코스 화면과 같은 이유다.
 */
export const dynamic = 'force-dynamic'

import Link from 'next/link'
import { notFound } from 'next/navigation'
import { fetchContextList } from '@/lib/agent'
import { DEMO_COURSES, DEMO_PROVES, missingKinds } from '@/lib/demo-courses'
import { dict, isLang } from '@/lib/i18n'
import { OpenAnyCourse } from './OpenAnyCourse'

/**
 * 처음 온 사람이 읽는 화면.
 *
 * 여기 오는 사람 다수는 코스를 짜러 온 것이 아니라 **이것이 무엇을 하는 물건인지**
 * 보러 온다. 그래서 코스 목록보다 규칙이 먼저 온다 — 규칙을 모르면 아래 인용 칩이
 * 왜 거기 있는지 알 수 없고, 칩을 누를 이유도 없다.
 */
export default async function Home({ params }: { params: Promise<{ lang: string }> }) {
  const { lang } = await params
  if (!isLang(lang)) notFound()
  const t = dict(lang)

  // 번들 숫자는 README 에서 베껴 오지 않는다. 베끼면 번들이 자라는 순간 화면이
  // 조용히 거짓말을 하게 된다. 받아 오되, 못 받는 것이 이 화면을 무너뜨리면 안 된다 —
  // 브리핑은 백엔드가 내려가 있어도 읽을 수 있어야 한다.
  const bundle = await fetchContextList()
  const missing = missingKinds()

  return (
    <div className="space-y-12">
      <section className="space-y-4">
        <h1 className="text-2xl font-semibold leading-snug sm:text-3xl">{t.home.ruleTitle}</h1>
        <p className="text-sm leading-relaxed opacity-80">{t.home.ruleBody}</p>
        <p className="border-l-2 border-black/20 pl-4 text-sm leading-relaxed dark:border-white/25">
          {t.home.ruleConsequence}
        </p>
        <p className="text-sm leading-relaxed opacity-70">{t.home.silentFailure}</p>
        {t.home.generatedLanguageNote && (
          <p className="text-xs opacity-60">{t.home.generatedLanguageNote}</p>
        )}
      </section>

      <section className="space-y-4">
        <h2 className="text-sm font-semibold opacity-70">{t.home.metricsTitle}</h2>
        <ul className="grid gap-3 sm:grid-cols-3">
          <Metric
            value={
              // 문서 본문 합계가 아니라 프롬프트에 실리는 원문 크기다. 라벨이
              // "모델이 매 요청 보는 전부"라고 말하므로, 그 말대로인 숫자여야 한다.
              bundle.kind === 'loaded'
                ? t.home.bundle.value(
                    bundle.value.documents.length,
                    bundle.value.systemTextBytes.toLocaleString(),
                  )
                : t.home.bundle.unavailable
            }
            label={t.home.bundle.label}
            cta={t.home.bundle.cta}
            href={`/${lang}/evidence`}
          />
          <Metric
            value={t.home.forbidden.value}
            label={t.home.forbidden.label}
            cta={t.home.forbidden.cta}
            href={t.home.forbidden.href}
            external
          />
          <Metric
            value={t.home.citationGuard.value}
            label={t.home.citationGuard.label}
            cta={t.home.citationGuard.cta}
            href={t.home.citationGuard.href}
            external
          />
        </ul>
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">{t.home.demoTitle}</h2>
        <p className="text-sm leading-relaxed opacity-80">{t.home.demoIntro}</p>

        {DEMO_COURSES.length === 0 ? (
          <div className="rounded-lg border border-dashed border-black/20 p-6 text-sm dark:border-white/20">
            <p className="font-medium">{t.home.emptyTitle}</p>
            <p className="mt-2 opacity-70">{t.home.emptyBody(missing.join(', '))}</p>
          </div>
        ) : (
          <ul className="space-y-3">
            {DEMO_COURSES.map((course) => (
              <li key={course.uuid}>
                <Link
                  href={`/${lang}/course/${course.uuid}`}
                  className="block rounded-lg border border-black/10 p-4 hover:bg-black/5 dark:border-white/10 dark:hover:bg-white/5"
                >
                  <span className="font-medium">{course.label}</span>
                  {/* 여기에 `kind` 원문이 있었다. 고른 사람에게만 뜻이 있는 식별자라
                      처음 보는 사람에게는 읽을 것이 없었다. */}
                  <span className="mt-1.5 block text-xs leading-relaxed opacity-65">
                    <span className="opacity-70">{t.home.provesLabel}</span>{' '}
                    {DEMO_PROVES[lang][course.kind]}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* 담당자에게는 노이즈이고 개발자에게만 필요하다. 접어 두되 없애지는 않는다. */}
      <section className="border-t border-black/10 pt-6 dark:border-white/10">
        <details className="space-y-3">
          <summary className="cursor-pointer text-sm opacity-70 hover:opacity-100">
            {t.home.openAnySummary}
          </summary>
          <div className="mt-3 space-y-3">
            <OpenAnyCourse lang={lang} />
            <p className="text-xs leading-relaxed opacity-60">{t.home.openAnyNote}</p>
          </div>
        </details>
      </section>
    </div>
  )
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
    <li className="flex flex-col gap-2 rounded-lg border border-black/10 p-4 dark:border-white/10">
      <span className="text-sm font-semibold">{value}</span>
      <span className="flex-1 text-xs leading-relaxed opacity-70">{label}</span>
      <span className="text-xs">{link}</span>
    </li>
  )
}
