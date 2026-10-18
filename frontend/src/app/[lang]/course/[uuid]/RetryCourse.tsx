'use client'
import { useRouter } from 'next/navigation'
import { useTransition } from 'react'
import type { Lang } from '@/lib/i18n'
export function RetryCourse({ lang }: { lang: Lang }) {
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  return <button type="button" disabled={pending} onClick={() => startTransition(() => router.refresh())} className="min-h-control-sm rounded-control bg-brand-primary px-4 text-body text-brand-on-primary disabled:cursor-wait">{lang === 'ko' ? pending ? '다시 불러오는 중' : '다시 시도' : pending ? 'Loading again' : 'Try again'}</button>
}
