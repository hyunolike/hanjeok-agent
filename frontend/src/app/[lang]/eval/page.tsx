import { notFound } from 'next/navigation'
import { fetchEvalReport } from '@/lib/guide'
import { isLang } from '@/lib/i18n'
import { EvalReportView } from './EvalReportView'

/**
 * 가장 최근에 공개한 평가 보고서.
 *
 * 서버에서 받아 온다. 보고서는 방문자마다 다르지 않고, 받아서 그리면 표가 처음부터
 * HTML 에 들어 있어 스크립트 없이도 읽힌다.
 *
 * `?demo=none` 은 안내 서버 주소가 없을 때 "공개한 평가가 없다" 상태를 열어 본다.
 */
export default async function EvalPage({
  params,
  searchParams,
}: {
  params: Promise<{ lang: string }>
  searchParams: Promise<{ demo?: string | string[] }>
}) {
  const { lang } = await params
  if (!isLang(lang)) notFound()
  const { demo } = await searchParams
  const result = await fetchEvalReport({ empty: (Array.isArray(demo) ? demo[0] : demo) === 'none' })

  return <EvalReportView lang={lang} result={result} />
}
