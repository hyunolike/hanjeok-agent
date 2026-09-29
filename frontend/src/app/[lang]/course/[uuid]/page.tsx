/**
 * 요청 시점에 그린다. 빌드 때 그리면 Next 가 백엔드를 부르고, 그러면 프론트 배포가
 * 백엔드가 떠 있어야만 성공한다 — 실제로 첫 빌드가 ECONNREFUSED 로 죽었다.
 * 게다가 사실은 매 요청 백엔드에서 와야 한다(스펙 §7).
 */
export const dynamic = 'force-dynamic'

import { notFound } from 'next/navigation'
import { fetchFacts } from '@/lib/agent'
import { dict, isLang } from '@/lib/i18n'
import { CourseView } from './CourseView'
import { AskBox } from './AskBox'
import { ExplanationBlock } from './ExplanationBlock'

/**
 * 사실과 설명을 **따로** 받는다.
 *
 * 하나로 받으면 LLM 왕복(3~5초)이 끝나야 코스가 그려지고, LLM이 죽으면 코스도 함께
 * 사라진다. 스펙 §6.1이 약속한 "설명 블록만 사라진다"는 이 분리 없이는 지킬 수 없다.
 */
export default async function CoursePage({
  params,
}: {
  params: Promise<{ lang: string; uuid: string }>
}) {
  const { lang, uuid } = await params
  if (!isLang(lang)) notFound()
  const t = dict(lang)

  const facts = await fetchFacts(uuid)

  if (facts.kind === 'unavailable') {
    return (
      <div className="space-y-2">
        <h1 className="text-xl font-semibold">{t.course.loadFailTitle}</h1>
        <p className="text-sm opacity-70">{t.course.loadFailBody(facts.status)}</p>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* 코스와 설명은 한국어로 생성된다. 홈에서 이미 밝히지만, 링크를 받아 이 화면으로
          바로 들어온 사람은 그 문장을 본 적이 없다. */}
      {t.home.generatedLanguageNote && (
        <p className="text-xs opacity-55">{t.home.generatedLanguageNote}</p>
      )}

      {/* 경계 문구는 이 페이지가 아니라 각 블록 안에 있다. 여기 두면 설명이 실패해
          블록이 사라졌을 때 "아래 문단은 LLM이 썼습니다"가 아무것도 가리키지 않은 채
          남는다 — 없는 것을 가리키는 라벨은 화면이 거짓말하는 흔한 방식이다. */}
      <CourseView facts={facts.value} lang={lang} />
      <ExplanationBlock courseUuid={uuid} lang={lang} />
      <AskBox courseUuid={uuid} lang={lang} />
    </div>
  )
}
