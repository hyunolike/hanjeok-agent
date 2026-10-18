import type { Metadata } from 'next'
import { Suspense } from 'react'
import { PendingLink } from '@/components/ui/PendingLink'
import { notFound } from 'next/navigation'
import { dict, isLang, LANGS } from '@/lib/i18n'
import { LangSwitch } from './LangSwitch'
import '../globals.css'

/**
 * 탭 제목은 화면 위의 이름과 같은 사전에서 온다. 따로 적어 두면 한쪽만 바뀐다 —
 * 이름을 "Hermes Agent" 에서 바꿀 때 실제로 두 곳이었다.
 */
export async function generateMetadata({ params }: { params: Promise<{ lang: string }> }): Promise<Metadata> {
  const { lang } = await params
  return {
    title: dict(isLang(lang) ? lang : 'ko').nav.brand,
    description: '한적의 장소와 혼잡 예보를 묻고, 답이 어디에서 왔는지 단계마다 확인하는 안내 에이전트',
  }
}

/**
 * 두 언어를 미리 알려 둔다. 없어도 라우트는 동작하지만, 있으면 `/ko` 와 `/en` 이
 * 빌드 시점에 알려진 값이 되어 오타 난 경로를 배포 전에 드러낸다.
 */
export function generateStaticParams() {
  return LANGS.map((lang) => ({ lang }))
}

export default async function RootLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ lang: string }>
}) {
  const { lang } = await params
  // 아무 문자열이나 받아 기본 언어로 그리면 `/de` 가 한국어 화면으로 200 을 준다.
  // 없는 언어는 없다고 말하는 편이 맞다.
  if (!isLang(lang)) notFound()

  const t = dict(lang)

  return (
    <html lang={lang}>
      <body className="min-h-screen antialiased">
        <header className="border-b border-line-normal">
          <nav className="mx-auto flex max-w-3xl flex-wrap items-baseline gap-x-6 gap-y-2 px-6 py-4 text-body">
            <PendingLink pendingLabel={lang === 'ko' ? '화면을 열고 있어요' : 'Opening this page'} href={`/${lang}`} className="font-semibold">
              {t.nav.brand}
            </PendingLink>
            <PendingLink pendingLabel={lang === 'ko' ? '화면을 열고 있어요' : 'Opening this page'} href={`/${lang}/ask`} className="text-ink-muted hover:text-ink-title">
              {t.guide.navLabel}
            </PendingLink>
            <PendingLink pendingLabel={lang === 'ko' ? '화면을 열고 있어요' : 'Opening this page'} href={`/${lang}/graph`} className="text-ink-muted hover:text-ink-title">
              {t.graph.navLabel}
            </PendingLink>
            <PendingLink pendingLabel={lang === 'ko' ? '화면을 열고 있어요' : 'Opening this page'} href={`/${lang}/eval`} className="text-ink-muted hover:text-ink-title">
              {t.evalPage.navLabel}
            </PendingLink>
            <PendingLink pendingLabel={lang === 'ko' ? '화면을 열고 있어요' : 'Opening this page'} href={`/${lang}/evidence`} className="text-ink-muted hover:text-ink-title">
              {t.nav.evidence}
            </PendingLink>
            <Suspense fallback={<span className="ml-auto text-ink-muted" aria-busy="true">{t.nav.switchTo}</span>}><LangSwitch lang={lang} label={t.nav.switchTo} /></Suspense>
          </nav>
        </header>
        <main className="mx-auto max-w-3xl px-6 py-10">{children}</main>
      </body>
    </html>
  )
}
