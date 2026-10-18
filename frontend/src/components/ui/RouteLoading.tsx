'use client'
import { useParams } from 'next/navigation'
import { LoadingPanel } from './LoadingPanel'
export function RouteLoading({ course = false }: { course?: boolean }) {
  const { lang } = useParams<{ lang: string }>()
  const ko = lang !== 'en'
  return <div aria-busy="true"><LoadingPanel title={ko ? course ? '코스를 불러오는 중이에요' : '화면을 불러오는 중이에요' : course ? 'Loading your course' : 'Loading this page'} detail={ko ? '준비되면 바로 보여 드릴게요.' : 'The content will appear as soon as it is ready.'} /></div>
}
