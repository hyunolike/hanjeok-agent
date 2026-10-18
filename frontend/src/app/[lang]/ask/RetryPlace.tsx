'use client'
import { useRouter } from 'next/navigation'
import { useTransition } from 'react'
import { Button } from '@/components/ui/Button'
import type { Lang } from '@/lib/i18n'
export function RetryPlace({ lang }: { lang: Lang }) {
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  return <div aria-busy={pending}><Button disabled={pending} onClick={() => startTransition(() => router.refresh())}>{lang === 'ko' ? pending ? '다시 불러오는 중' : '다시 시도' : pending ? 'Loading again' : 'Try again'}</Button>{pending && <span role="status" className="sr-only">{lang === 'ko' ? '장소를 다시 불러오고 있어요' : 'Loading the selected place again'}</span>}</div>
}
