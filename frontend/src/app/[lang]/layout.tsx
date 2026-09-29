import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { dict, isLang, LANGS } from '@/lib/i18n'
import { LangSwitch } from './LangSwitch'
import '../globals.css'

export const metadata: Metadata = {
  title: 'Hermes Agent',
  description: '설명이 어디에서 왔는지 눌러서 확인할 수 있는 여행 컨텍스트 에이전트',
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
          <nav className="mx-auto flex max-w-3xl items-baseline gap-6 px-6 py-4 text-sm">
            <Link href={`/${lang}`} className="font-semibold">
              {t.nav.brand}
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
