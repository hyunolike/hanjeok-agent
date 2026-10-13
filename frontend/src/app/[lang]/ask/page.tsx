import { notFound } from 'next/navigation'
import { isDemoKey } from '@/lib/guide-fixtures'
import { isLang } from '@/lib/i18n'
import { AskGuide } from './AskGuide'

/**
 * 질문 화면. 서버에서 받아 올 것이 없다 — 질문은 방문자가 쳐야 생긴다.
 *
 * `?demo=` 는 녹화본을 고른다. 안내 서버 주소가 있으면 무시된다. 주소가 없을 때
 * 이 값으로 화면의 모든 상태를 하나씩 열어 볼 수 있다.
 */
export default async function AskPage({
  params,
  searchParams,
}: {
  params: Promise<{ lang: string }>
  searchParams: Promise<{ demo?: string | string[] }>
}) {
  const { lang } = await params
  if (!isLang(lang)) notFound()
  const { demo } = await searchParams
  const key = Array.isArray(demo) ? demo[0] : demo

  return <AskGuide lang={lang} demo={isDemoKey(key) ? key : undefined} />
}
