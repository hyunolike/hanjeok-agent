import type { Metadata } from 'next'
import Link from 'next/link'
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
        <header className="border-b border-black/10 dark:border-white/10">
          <nav className="mx-auto flex max-w-3xl flex-wrap items-baseline gap-x-6 gap-y-2 px-6 py-4 text-sm">
            <Link href={`/${lang}`} className="font-semibold">
              {t.nav.brand}
            </Link>
            <Link href={`/${lang}/ask`} className="opacity-70 hover:opacity-100">
              {t.guide.navLabel}
            </Link>
            <Link href={`/${lang}/graph`} className="opacity-70 hover:opacity-100">
              {t.graph.navLabel}
            </Link>
            <Link href={`/${lang}/eval`} className="opacity-70 hover:opacity-100">
              {t.evalPage.navLabel}
            </Link>
            <Link href={`/${lang}/evidence`} className="opacity-70 hover:opacity-100">
              {t.nav.evidence}
            </Link>
            <LangSwitch lang={lang} label={t.nav.switchTo} />
          </nav>
        </header>
        <main className="mx-auto max-w-3xl px-6 py-10">{children}</main>
      </body>
    </html>
  )
}
