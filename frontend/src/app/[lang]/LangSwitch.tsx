'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { OTHER_LANG, type Lang } from '@/lib/i18n'

/**
 * 반대편 언어의 **같은 화면**으로 간다.
 *
 * 홈으로 보내면 코스를 보다가 언어를 바꾼 사람이 자기 자리를 잃는다. 그래서 첫
 * 세그먼트만 갈아 끼운다 — 모든 경로가 `/{lang}/...` 이므로 갈아 끼울 자리는 늘 거기다.
 *
 * 클라이언트 컴포넌트인 이유는 현재 경로가 필요해서다. `next/root-params` 는 서버
 * 컴포넌트에서만 쓸 수 있어서 여기서는 쓸 수 없다.
 */
export function LangSwitch({ lang, label }: { lang: Lang; label: string }) {
  const pathname = usePathname() ?? `/${lang}`
  const other = OTHER_LANG[lang]
  const rest = pathname.split('/').slice(2).join('/')

  return (
    <Link
      href={`/${other}${rest ? `/${rest}` : ''}`}
      // 언어 이름은 화면 언어를 따라가지 않는다. 읽을 수 있는 언어를 찾는 사람에게
      // 보여야 하므로 그 언어로 적혀 있어야 한다 — hreflang 이 그 사실을 기계에도 알린다.
      hrefLang={other}
      className="ml-auto opacity-70 hover:opacity-100"
    >
      {label}
    </Link>
  )
}
