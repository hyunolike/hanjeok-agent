'use client'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { isLang } from '@/lib/i18n'
export default function CourseError({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  const params = useParams<{ lang: string }>()
  const lang = isLang(params.lang) ? params.lang : 'ko'
  const ko = lang === 'ko'
  return <div role="alert" className="space-y-4">
    <h1 className="text-title-1">{ko ? '코스를 표시하지 못했어요' : 'Could not display this course'}</h1>
    <p className="text-body text-ink-body">{ko ? '받은 코스 정보를 확인하지 못했어요. 잠시 후 다시 시도하거나 다른 예시를 골라 주세요.' : 'The course information could not be verified. Try again or choose another example.'}</p>
    <div className="flex flex-wrap items-center gap-4">
      <button type="button" onClick={retry} className="min-h-control-sm rounded-control bg-brand-primary px-4 text-body text-brand-on-primary">{ko ? '다시 시도' : 'Try again'}</button>
      <Link href={`/${lang}`} className="inline-flex min-h-control-sm items-center text-brand-primary underline underline-offset-4">{ko ? '홈으로 돌아가기' : 'Back to home'}</Link>
    </div>
  </div>
}
