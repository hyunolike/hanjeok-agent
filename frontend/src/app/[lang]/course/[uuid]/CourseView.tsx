import { GRADE_LABEL, GRADE_STYLE } from '@/lib/grades'
import { dict, type Lang } from '@/lib/i18n'
import type { Facts } from '@/lib/schema'

/**
 * 코스 자체. **설명 없이도 완전하다** — 각 항목의 `reason`은 한적이 규칙으로 붙인
 * 문구이고, LLM이 죽어도 그 문구는 그대로 있다. 이 컴포넌트가 설명을 인자로 받지
 * 않는 것이 스펙 §6.1의 "설명 블록만 사라진다"를 구조로 지키는 방법이다.
 */
export function CourseView({ facts, lang }: { facts: Facts; lang: Lang }) {
  const items = [...facts.items].sort((a, b) => a.visitOrder - b.visitOrder)
  const t = dict(lang).course

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">{facts.title}</h1>
        <p className="text-sm opacity-70">
          {facts.targetDate} · {t.reductionRate(facts.congestionReductionRate)}
        </p>
        <p className="text-sm opacity-80">{facts.summary}</p>
      </header>

      <ol className="space-y-3">
        {items.map((item) => (
          <li
            key={item.attractionId}
            className="rounded-lg border border-black/10 p-4 dark:border-white/10"
          >
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="text-xs opacity-50">{item.visitOrder}</span>
              <span className="font-medium">{item.name}</span>
              {/* 예보가 없는 장소는 등급이 없다. 자리를 비우면 "등급이 뭐였더라"가
                  되고, 아무 색이나 넣으면 없는 진단을 있는 것처럼 만든다. */}
              {item.grade === null ? (
                <span className="rounded-full px-2 py-0.5 text-xs opacity-60 ring-1 ring-current">
                  {t.noForecast}
                </span>
              ) : (
                <span
                  className={`rounded-full px-2 py-0.5 text-xs ring-1 ${GRADE_STYLE[item.grade]}`}
                >
                  {/* 등급 라벨은 번역하지 않는다 — 위키의 grade-policy 가 정한 이름이고,
                      모델도 번들에서 같은 이름을 본다(i18n.ts 참고). */}
                  {GRADE_LABEL[item.grade]}
                </span>
              )}
              <span className="text-xs opacity-60">{item.timeLabel}</span>
              {item.travelMinutesFromPrev !== null && (
                <span className="text-xs opacity-60">
                  {t.travelMinutes(item.travelMinutesFromPrev)}
                </span>
              )}
            </div>
            <p className="mt-2 text-sm opacity-80">{item.reason}</p>
          </li>
        ))}
      </ol>

      {facts.alternatives.length === 0 && (
        // "점수가 후보를 떨어뜨렸다"와 "후보가 애초에 없었다"는 다른 말이다
        // (concepts/alternative-scoring.md). 한 문구로 덮으면 화면이 그 오해를 만든다.
        <p className="text-sm opacity-70">{t.noAlternatives}</p>
      )}

      {/* 이 화면의 요점은 위쪽과 아래쪽이 다른 곳에서 왔다는 것인데, 둘 다 똑같이 생긴
          회색 상자라 경계가 보이지 않았다. 설명이 실패하면 아래는 비지만 이 줄은 남는다 —
          "백엔드가 여기까지 정했다"는 설명이 있든 없든 참이기 때문이다. */}
      <p className="border-t border-black/10 pt-4 text-xs leading-relaxed opacity-55 dark:border-white/10">
        {t.backendBoundary}
      </p>
    </div>
  )
}
