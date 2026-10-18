'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/Button'
import type { Lang } from '@/lib/i18n'

const STEPS = [
  ['질문 읽기', '장소와 날짜, 질문의 범위를 확인해요. 모호한 장소는 되묻고, 지원하지 않는 요청은 여기서 멈춰요.', 'Read the question', 'Check the place, date and scope. Ask for clarification when needed; stop unsupported requests.'],
  ['조회 선택하기', '모델은 허용된 조회 7가지 중 필요한 것을 골라요. 코드가 장소 ID와 날짜, 거리 범위를 검사해 실행해요.', 'Choose a lookup', 'The model chooses from seven allowed lookups. Code validates place IDs, dates and distance before execution.'],
  ['장소와 정책 찾기', '필요한 경우 Neo4j의 글 유사도·연관 링크로 장소를 찾고, 위키에서 질문에 맞는 정책 문서를 읽어요.', 'Find places and policies', 'When needed, search place text and related links in Neo4j, or look up a relevant policy in the wiki.'],
  ['날짜별 정보 조회', '혼잡 예보와 대안이 필요한 질문은 읽기 전용 한적 API를 조회해요. 모든 질문이 이 단계를 거치지는 않아요.', 'Look up dated information', 'Questions about forecasts and alternatives use the read-only Hanjeok API. This step is only used when needed.'],
  ['근거로 답 쓰기', 'NVIDIA NIM 모델이 찾은 근거로 답을 만들어요. 대안 순위는 한적이 정한 순서 그대로 유지해요.', 'Write from evidence', 'The NVIDIA NIM model writes from retrieved evidence. Alternative places keep the order supplied by Hanjeok.'],
  ['인용 검증하기', '인용 검사를 통과한 답과 근거·경로를 보여 줘요. 실패하면 한 번 고쳐 쓰고, 다시 실패하면 답을 내보내지 않아요.', 'Check citations', 'Show the answer, sources and path after citation checks. Repair once on failure; withhold an answer that still fails.'],
] as const

/** Educational player only. It never opens a connection or submits an agent request. */
export function AgentFlow({ lang }: { lang: Lang }) {
  const ko = lang === 'ko'
  const [step, setStep] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [reduced, setReduced] = useState(false)
  useEffect(() => {
    const query = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    if (!query) return
    const update = () => { setReduced(query.matches); if (query.matches) setPlaying(false) }
    update()
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])
  useEffect(() => {
    if (!playing || reduced) return
    const timer = setInterval(() => setStep(current => Math.min(current + 1, STEPS.length - 1)), 2400)
    return () => clearInterval(timer)
  }, [playing, reduced])
  useEffect(() => { if (step === STEPS.length - 1) setPlaying(false) }, [step])
  const move = (next: number) => { setPlaying(false); setStep(next) }
  const selected = STEPS[step]
  const nodes = [
    { x: 16, y: 86, w: 142, name: ko ? '브라우저' : 'Browser', sub: 'Next.js · Vercel', active: step === 0 },
    { x: 208, y: 86, w: 190, name: 'FastAPI + LangGraph', sub: ko ? '조회 선택 · 입력 검사' : 'Lookups · validation', active: step === 1 },
    { x: 448, y: 14, w: 220, name: 'Neo4j + Wiki', sub: ko ? '장소 · 관계 · 정책 문서' : 'Places · links · policies', active: step === 2 },
    { x: 448, y: 102, w: 220, name: ko ? '한적 API' : 'Hanjeok API', sub: ko ? '실시간 조회: 예보 · 대안' : 'Dated forecasts · alternatives', active: step === 3 },
    { x: 448, y: 190, w: 220, name: 'NVIDIA NIM', sub: ko ? '근거로 답 작성' : 'Answer from evidence', active: step === 4 },
    { x: 208, y: 278, w: 190, name: ko ? '인용 검증 → 답·근거·경로' : 'Citations → answer & path', sub: ko ? '실패 시 한 번 수정 또는 중단' : 'Repair once or stop', active: step === 5 },
  ]
  return <section className="space-y-5 rounded-card border border-line-normal bg-surface-panel p-5 sm:p-7" aria-labelledby="agent-flow-heading">
    <div className="space-y-2">
      <p className="text-caption font-semibold text-brand-primary">{ko ? '한적 에이전트가 일하는 방식' : 'How the Hanjeok agent works'}</p>
      <h2 id="agent-flow-heading" className="text-title-1">{ko ? '질문 한 번이 답이 되기까지' : 'From a question to an answer'}</h2>
      <p className="text-caption leading-relaxed text-ink-muted">{ko ? '설명용 시뮬레이션이에요. 실제 요청이나 서버 상태를 표시하지 않아요. 질문에 따라 필요한 출처만 조회해요.' : 'An educational simulation, not a live request or server status. Each question uses only the sources it needs.'}</p>
    </div>
    <svg viewBox="0 0 690 358" role="img" aria-label={ko ? '브라우저에서 FastAPI와 LangGraph로 질문을 전달하고, 필요한 데이터와 모델을 사용한 뒤 인용을 검증하는 구조' : 'The browser calls FastAPI and LangGraph, which use sources and a model before validating citations'} className="hidden w-full rounded-card bg-surface-subtle sm:block">
      <g fill="none" stroke="var(--line-strong)" strokeWidth="2">
        <path d="M158 121H208 M398 121H422V49H448 M422 121H448 M422 121V225H448 M558 260V313H398 M208 313H87V156" />
      </g>
      <g fill="none" stroke="var(--brand-primary)" strokeWidth="2" strokeDasharray="5 6" className={playing ? 'motion-safe:animate-[flow-dash_1s_linear_infinite]' : ''} opacity={playing ? 1 : 0.35}>
        <path d={step === 0 ? 'M158 121H208' : step === 1 || step === 2 ? 'M398 121H422V49H448' : step === 3 ? 'M398 121H448' : step === 4 ? 'M398 121H422V225H448' : 'M558 260V313H398 M208 313H87V156'} />
      </g>
      {nodes.map(node => <g key={node.name}>
        <rect x={node.x} y={node.y} width={node.w} height={70} rx={12} fill={node.active ? 'var(--brand-soft)' : 'var(--surface-panel)'} stroke={node.active ? 'var(--brand-primary)' : 'var(--line-normal)'} strokeWidth={node.active ? 2 : 1} />
        <text x={node.x + node.w / 2} y={node.y + 29} textAnchor="middle" fill="var(--ink-title)" className="text-caption font-semibold">{node.name}</text>
        <text x={node.x + node.w / 2} y={node.y + 50} textAnchor="middle" fill="var(--ink-muted)" className="text-caption">{node.sub}</text>
      </g>)}
    </svg>
    <ol className="grid grid-cols-2 gap-2 sm:grid-cols-3" aria-label={ko ? '설명 단계' : 'Explanation steps'}>
      {STEPS.map((item, index) => <li key={item[0]}><button type="button" aria-current={index === step ? 'step' : undefined} onClick={() => move(index)} className={`flex min-h-control-md w-full items-center gap-2 rounded-control border px-3 py-2 text-left text-caption focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-primary ${index === step ? 'border-brand-primary bg-brand-soft text-ink-title' : 'border-line-normal text-ink-muted'}`}><span className="font-semibold text-brand-primary">0{index + 1}</span>{item[ko ? 0 : 2]}</button></li>)}
    </ol>
    <div className="min-h-32 space-y-2 rounded-card bg-brand-soft p-4" aria-live={playing ? 'off' : 'polite'} aria-atomic="true">
      <p className="text-title-2">{step + 1}. {selected[ko ? 0 : 2]}</p>
      <p className="text-body leading-relaxed text-ink-body">{selected[ko ? 1 : 3]}</p>
    </div>
    <div className="flex flex-wrap gap-2" role="group" aria-label={ko ? '흐름 재생' : 'Flow playback'}>
      <Button size="sm" disabled={reduced} onClick={() => { if (step === STEPS.length - 1) setStep(0); setPlaying(value => !value) }}>{playing ? (ko ? '일시정지' : 'Pause') : (ko ? '재생' : 'Play')}</Button>
      <Button size="sm" variant="secondary" disabled={step === 0} onClick={() => move(step - 1)}>{ko ? '이전 단계' : 'Previous'}</Button>
      <Button size="sm" variant="secondary" disabled={step === STEPS.length - 1} onClick={() => move(step + 1)}>{ko ? '다음 단계' : 'Next'}</Button>
      <Button size="sm" variant="ghost" onClick={() => move(0)}>{ko ? '처음으로' : 'Restart'}</Button>
    </div>
    {reduced && <p className="text-caption text-ink-muted">{ko ? '움직임 줄이기 설정에 따라 자동 재생을 끄고, 단계 버튼으로 설명을 읽을 수 있어요.' : 'Reduced motion is enabled. Use the step buttons to read the explanation.'}</p>}
    <details className="border-t border-line-normal pt-4 text-caption text-ink-muted"><summary className="cursor-pointer py-2">{ko ? '실제 구성과 한계 더 보기' : 'Architecture and limits'}</summary><div className="mt-3 space-y-3 leading-relaxed">
      <p>{ko ? '화면은 Vercel의 Next.js, 질문 처리는 Cloud Run의 FastAPI와 LangGraph가 맡아요. Neo4j·임베딩 모델·위키도 이 컨테이너에 있고, NVIDIA NIM과 한적 API는 외부 서비스예요.' : 'Next.js runs on Vercel. FastAPI, LangGraph, Neo4j, the embedding model and wiki run in Cloud Run. NVIDIA NIM and the Hanjeok API are external services.'}</p>
      <p>{ko ? '장소 데이터는 한적에서 내보낸 파일을 검증해 빌드할 때 적재해요. 위키 정책은 키워드에 맞춰 찾아요. 한적 DB에 직접 접속하지 않으며, 예보와 대안만 요청 시 읽기 전용 API로 받아요.' : 'Verified Hanjeok exports populate place data at build time; wiki policies use keyword lookup. There is no direct connection to the Hanjeok database. Forecasts and alternatives use read-only APIs at request time.'}</p>
      <p>{ko ? '조회는 최대 3번, 답 작성과 수정은 각각 1번, 서버 처리 예산은 60초예요. 예약·결제나 확인할 수 없는 정보를 대신 만들어 주지는 않아요.' : 'The server budget is 60 seconds: up to three lookups, one answer and one repair. The agent does not book, take payments or invent unavailable information.'}</p>
      <p>{ko ? '조회 7가지: 장소 검색·상세·연관 장소·혼잡 예보·대안·행사·정책. 모델: nvidia/nemotron-3-super-120b-a12b.' : 'Seven lookups: search, place detail, related places, congestion, alternatives, events and policies. Model: nvidia/nemotron-3-super-120b-a12b.'}</p>
    </div></details>
  </section>
}
