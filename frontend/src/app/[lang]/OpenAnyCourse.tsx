'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { dict, type Lang } from '@/lib/i18n'

/**
 * 데모 목록에 없는 코스를 열어 본다.
 *
 * **코스를 만드는 화면이 아니다**(스펙 §7). 만드는 것은 한적의 일이고, 여기서는
 * 이미 있는 코스의 uuid 를 받아 그 설명을 보여 줄 뿐이다. 서버는 데모 uuid 를
 * 특별 취급하지 않으므로, 한적에 있는 코스라면 어느 것이든 그대로 열린다.
 */
export function OpenAnyCourse({ lang }: { lang: Lang }) {
  const router = useRouter()
  const [value, setValue] = useState('')
  const t = dict(lang).openAny

  const uuid = value.trim()

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        if (uuid) router.push(`/${lang}/course/${encodeURIComponent(uuid)}`)
      }}
      className="flex flex-wrap items-center gap-2"
    >
      <label htmlFor="course-uuid" className="text-sm opacity-70">
        {t.label}
      </label>
      <input
        id="course-uuid"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder={t.placeholder}
        spellCheck={false}
        className="min-w-0 flex-1 rounded border border-black/15 bg-transparent px-3 py-1.5 font-mono text-xs dark:border-white/20"
      />
      <button
        type="submit"
        disabled={uuid.length === 0}
        className="rounded border border-black/15 px-3 py-1.5 text-sm disabled:opacity-40 dark:border-white/20"
      >
        {t.submit}
      </button>
    </form>
  )
}
