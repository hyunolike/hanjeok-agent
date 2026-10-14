import { notFound } from 'next/navigation'
import { isLang } from '@/lib/i18n'
import { GraphBrowser } from './GraphBrowser'

/**
 * 질문 없이 장소를 둘러보는 화면. 답 하나의 경로는 그 답 아래(`/ask`)에 열린다 —
 * 여기는 답과 상관없이 장소 하나의 이웃을 본다.
 *
 * `?place=` 는 장소 하나를 연 채로 시작한다. 숫자가 아니면 없는 것으로 친다.
 */
export default async function GraphPage({
  params,
  searchParams,
}: {
  params: Promise<{ lang: string }>
  searchParams: Promise<{ place?: string | string[] }>
}) {
  const { lang } = await params
  if (!isLang(lang)) notFound()
  const { place } = await searchParams
  const raw = Array.isArray(place) ? place[0] : place
  const placeId = raw && /^\d{1,9}$/.test(raw) ? Number(raw) : undefined

  return <GraphBrowser lang={lang} initialPlaceId={placeId} />
}
