/**
 * 요청 시점에 그린다. 빌드 때 그리면 Next 가 백엔드를 부르고, 그러면 프론트 배포가
 * 백엔드가 떠 있어야만 성공한다 — 실제로 첫 빌드가 ECONNREFUSED 로 죽었다.
 * 게다가 사실은 매 요청 백엔드에서 와야 한다(스펙 §7).
 */
export const dynamic = 'force-dynamic'

import { notFound } from 'next/navigation'
import { fetchContextList } from '@/lib/agent'
import { dict, isLang } from '@/lib/i18n'
import { EvidenceBrowser } from './EvidenceBrowser'

export default async function EvidencePage({ params }: { params: Promise<{ lang: string }> }) {
  const { lang } = await params
  if (!isLang(lang)) notFound()
  const t = dict(lang).evidence

  const list = await fetchContextList()

  if (list.kind === 'unavailable') {
    return (
      <div className="space-y-2">
        <h1 className="text-xl font-semibold">{t.listFailTitle}</h1>
        <p className="text-sm opacity-70">{t.listFailBody(list.status)}</p>
      </div>
    )
  }

  return (
    <EvidenceBrowser
      entries={list.value.documents}
      systemTextBytes={list.value.systemTextBytes}
      lang={lang}
    />
  )
}
