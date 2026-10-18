import { notFound } from 'next/navigation'
import Link from 'next/link'
import { fetchPlace } from '@/lib/guide'
import type { PlaceHit } from '@/lib/guide-schema'
import { isDemoKey } from '@/lib/guide-fixtures'
import { isLang } from '@/lib/i18n'
import { AskGuide } from './AskGuide'
import { RetryPlace } from './RetryPlace'

/**
 * The screen verifies an optional place selection, but never submits a question itself.
 *
 * `?demo=` 는 녹화본을 고른다. 안내 서버 주소가 있으면 무시된다. 주소가 없을 때
 * 이 값으로 화면의 모든 상태를 하나씩 열어 볼 수 있다.
 */
export default async function AskPage({
  params,
  searchParams,
}: {
  params: Promise<{ lang: string }>
  searchParams: Promise<{ demo?: string | string[]; place?: string | string[] }>
}) {
  const { lang } = await params
  if (!isLang(lang)) notFound()
  const { demo, place } = await searchParams
  const key = Array.isArray(demo) ? demo[0] : demo
  const ko = lang === 'ko'
  let selected: Pick<PlaceHit, 'place_id' | 'name' | 'region'> | undefined
  if (place !== undefined) {
    const valid = typeof place === 'string' && /^[1-9]\d{0,8}$/.test(place)
    const result = valid ? await fetchPlace(Number(place)) : null
    if (!result?.ok) {
      const unavailable = result && !result.ok && result.cause === 'unavailable'
      return <div className="space-y-4">
        <div role="alert" className="space-y-2"><h1 className="text-title-1">{ko ? unavailable ? '선택한 장소를 불러오지 못했어요' : '장소 주소를 확인해 주세요' : unavailable ? 'Could not load the selected place' : 'Check the selected place address'}</h1><p className="text-body text-ink-body">{ko ? '선택한 장소를 확인하기 전에는 질문을 보내지 않아요. 다시 불러오거나 다른 장소를 골라 주세요.' : 'No question is sent without checking the selected place. Try loading again or choose another place.'}</p></div>
        {unavailable && <RetryPlace lang={lang} />}
        <Link href={`/${lang}/graph`} className="inline-flex min-h-control-sm items-center text-body text-brand-primary underline">{ko ? '장소 다시 고르기' : 'Choose another place'}</Link>
        <Link href={`/${lang}/ask`} className="block py-3 text-body text-brand-primary underline">{ko ? '장소 선택 없이 질문하기' : 'Ask without a selected place'}</Link>
      </div>
    }
    const { place_id, name, region } = result.data.place
    selected = { place_id, name, region }
  }

  return <AskGuide key={`${lang}-${selected?.place_id ?? 'general'}`} lang={lang} demo={isDemoKey(key) ? key : undefined} place={selected} />
}
