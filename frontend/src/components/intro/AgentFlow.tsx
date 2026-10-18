'use client'

import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/Button'
import type { Lang } from '@/lib/i18n'
import { HANJEOK_GREEN, LOGO_BLACK, LOGO_CHIP, TECH_LOGOS, type TechLogoKey } from './tech-logos'

/**
 * 질문 하나가 답이 되기까지를 구조도 위에서 보여 주는 설명용 재생기.
 *
 * 실제 요청을 보내거나 서버 상태를 읽지 않는다. 단계와 경로는 `bench/src/guide/agent.py` 의
 * 그래프(scope → act ⟲ → answer → verify)를 따른다. 그 순서가 바뀌면 여기도 바꾼다.
 */

/** 한 단계가 머무는 시간. 캐릭터는 이 시간의 85% 동안 경로를 지나고 나머지는 도착한 채로 쉰다. */
export const STEP_MS = 3200
const TRAVEL = 0.85

type NodeKey = 'browser' | 'api' | 'gate' | 'agent' | 'graph' | 'nim' | 'hanjeok'
type EdgeKey = 'browserApi' | 'apiAgent' | 'agentGate' | 'gateApi' | 'agentNim' | 'agentHanjeok' | 'agentGraph'
type Point = readonly [number, number]
/** question: 질문을 들고 감, answer: 가져온 것을 들고 옴, event: 끝난 단계가 화면으로 감 */
type Carry = 'question' | 'answer' | 'event'
type Leg = { edge: EdgeKey; reverse?: boolean; carry: Carry }

const STEPS: { ko: [string, string]; en: [string, string]; legs: Leg[]; active: NodeKey[] }[] = [
  {
    ko: ['질문 보내기', '화면이 질문과 보고 있는 장소, 날짜를 보내요. 서버는 모델을 부르기 전에 규칙으로 장소와 날짜, 답할 수 있는 질문인지부터 읽어요. 모호한 장소는 여기서 되묻고, 답할 수 없는 요청은 여기서 멈춰요.'],
    en: ['Send the question', 'The screen sends the question with the place and day it shows. Before any model is called, rules read the place, the date and whether the question can be answered. An unclear place is asked back here; an unsupported request stops here.'],
    legs: [{ edge: 'browserApi', carry: 'question' }, { edge: 'apiAgent', carry: 'question' }],
    active: ['browser', 'api', 'agent'],
  },
  {
    ko: ['조회 고르기', 'NVIDIA NIM의 모델이 정해 둔 조회 일곱 가지 중 하나를 고르거나, 이제 답하겠다고 말해요. 데이터베이스 쿼리를 직접 쓰지는 않아요.'],
    en: ['Choose a lookup', 'The model on NVIDIA NIM picks one of seven fixed lookups, or says it is ready to answer. It never writes a database query.'],
    legs: [{ edge: 'agentNim', carry: 'question' }, { edge: 'agentNim', reverse: true, carry: 'answer' }],
    active: ['agent', 'nim'],
  },
  {
    ko: ['그래프에서 찾기', '코드가 입력을 검사한 뒤 Neo4j에서 장소와 연관 링크를, 위키에서 정책 문서를 읽어요. 끝난 단계는 바로 화면으로 보내 하나씩 보여 줘요.'],
    en: ['Search the graph', 'Code checks the input, then reads places and related links from Neo4j and policy documents from the wiki. Each finished step goes straight to the screen.'],
    legs: [
      { edge: 'agentGraph', carry: 'question' },
      { edge: 'agentGraph', reverse: true, carry: 'answer' },
      { edge: 'apiAgent', reverse: true, carry: 'event' },
      { edge: 'browserApi', reverse: true, carry: 'event' },
    ],
    active: ['agent', 'graph', 'browser'],
  },
  {
    ko: ['한적에 묻기', '날짜가 걸린 혼잡 예보와 대안은 한적의 읽기 전용 API에 물어요. 조회 고르기부터 여기까지는 질문 하나에 최대 3번 되풀이해요.'],
    en: ['Ask Hanjeok', 'Dated congestion forecasts and alternatives come from Hanjeok’s read-only API. Choosing and running lookups repeats up to three times per question.'],
    legs: [
      { edge: 'agentHanjeok', carry: 'question' },
      { edge: 'agentHanjeok', reverse: true, carry: 'answer' },
      { edge: 'apiAgent', reverse: true, carry: 'event' },
      { edge: 'browserApi', reverse: true, carry: 'event' },
    ],
    active: ['agent', 'hanjeok', 'browser'],
  },
  {
    ko: ['답 쓰기', '모델이 이번 질문에서 가져온 레코드와 문서만 근거로 답을 써요. 대안의 순서는 한적이 준 그대로예요.'],
    en: ['Write the answer', 'The model writes from the records and documents fetched for this question only. Alternatives keep the order Hanjeok gave.'],
    legs: [{ edge: 'agentNim', carry: 'question' }, { edge: 'agentNim', reverse: true, carry: 'answer' }],
    active: ['agent', 'nim'],
  },
  {
    ko: ['검사하고 보내기', '인용한 것이 실제로 가져온 것인지, 레코드보다 더 나간 주장은 없는지 검사해요. 통과한 답만 한 번에 보내요. 실패하면 한 번 다시 쓰게 하고, 그래도 안 되면 보내지 않아요.'],
    en: ['Check, then send', 'The gate checks that every citation was fetched and that no claim goes beyond its record. Only a passing answer is sent, in one piece. A failure gets one rewrite; a second failure sends nothing.'],
    legs: [
      { edge: 'agentGate', carry: 'answer' },
      { edge: 'gateApi', carry: 'answer' },
      { edge: 'browserApi', reverse: true, carry: 'answer' },
    ],
    active: ['agent', 'gate', 'api', 'browser'],
  },
]

type Box = { x: number; y: number; w: number }
type Layout = {
  viewBox: string
  nodeH: number
  sprite: number
  nodes: Record<NodeKey, Box>
  container: { x: number; y: number; w: number; h: number; labelX: number; labelY: number; anchor: 'start' | 'end' }
  external: { x: number; y: number; anchor: 'start' | 'middle' }
  loopBadge: Point
  edges: Record<EdgeKey, Point[]>
}

const WIDE: Layout = {
  viewBox: '0 0 760 420',
  nodeH: 78,
  sprite: 56,
  nodes: {
    browser: { x: 16, y: 171, w: 150 },
    api: { x: 216, y: 52, w: 150 },
    gate: { x: 380, y: 52, w: 146 },
    agent: { x: 216, y: 171, w: 310 },
    graph: { x: 216, y: 300, w: 310 },
    nim: { x: 576, y: 90, w: 168 },
    hanjeok: { x: 576, y: 252, w: 168 },
  },
  container: { x: 196, y: 14, w: 350, h: 392, labelX: 236, labelY: 37, anchor: 'start' },
  external: { x: 576, y: 74, anchor: 'start' },
  loopBadge: [526, 262],
  edges: {
    browserApi: [[166, 210], [181, 210], [181, 91], [216, 91]],
    apiAgent: [[291, 130], [291, 171]],
    agentGate: [[453, 171], [453, 130]],
    gateApi: [[380, 91], [366, 91]],
    agentNim: [[526, 195], [551, 195], [551, 129], [576, 129]],
    agentHanjeok: [[526, 225], [551, 225], [551, 291], [576, 291]],
    agentGraph: [[371, 249], [371, 300]],
  },
}

const NARROW: Layout = {
  viewBox: '0 0 360 642',
  nodeH: 78,
  sprite: 50,
  nodes: {
    browser: { x: 100, y: 8, w: 160 },
    api: { x: 24, y: 156, w: 150 },
    gate: { x: 186, y: 156, w: 150 },
    agent: { x: 24, y: 274, w: 312 },
    graph: { x: 24, y: 392, w: 312 },
    nim: { x: 8, y: 556, w: 166 },
    hanjeok: { x: 186, y: 556, w: 166 },
  },
  container: { x: 8, y: 116, w: 344, h: 392, labelX: 336, labelY: 139, anchor: 'end' },
  external: { x: 180, y: 546, anchor: 'middle' },
  loopBadge: [330, 366],
  edges: {
    browserApi: [[180, 86], [180, 106], [99, 106], [99, 156]],
    apiAgent: [[99, 234], [99, 274]],
    agentGate: [[261, 274], [261, 234]],
    gateApi: [[186, 195], [174, 195]],
    agentNim: [[24, 313], [16, 313], [16, 530], [91, 530], [91, 556]],
    agentHanjeok: [[336, 313], [344, 313], [344, 530], [269, 530], [269, 556]],
    agentGraph: [[180, 352], [180, 392]],
  },
}

const NODE_TEXT: Record<NodeKey, { ko: [string, string]; en: [string, string]; logos: (TechLogoKey | 'hanjeok' | 'gate')[] }> = {
  browser: { ko: ['방문자 화면', 'Next.js, Vercel'], en: ['Visitor screen', 'Next.js, Vercel'], logos: ['nextjs', 'vercel'] },
  api: { ko: ['FastAPI', '질문 받기, 단계 보내기'], en: ['FastAPI', 'Takes questions, streams'], logos: ['fastapi'] },
  gate: { ko: ['인용 검사', '통과한 답만 내보내요'], en: ['Citation gate', 'Only passing answers'], logos: ['gate'] },
  agent: { ko: ['LangGraph 에이전트', '규칙으로 읽기 → 조회 → 답 쓰기'], en: ['LangGraph agent', 'Rules → lookups → answer'], logos: ['langgraph', 'python'] },
  graph: { ko: ['Neo4j 그래프와 위키', '장소, 연관 링크, 정책 문서'], en: ['Neo4j graph and wiki', 'Places, links, policy documents'], logos: ['neo4j', 'obsidian'] },
  nim: { ko: ['NVIDIA NIM', '조회 고르기, 답 쓰기'], en: ['NVIDIA NIM', 'Picks lookups, writes'], logos: ['nvidia'] },
  hanjeok: { ko: ['한적 API', '읽기 전용: 예보, 대안'], en: ['Hanjeok API', 'Read-only: forecasts'], logos: ['hanjeok'] },
}

const SPRITES: Record<Exclude<Carry, 'event'>, string> = {
  question: '/brand/guide/flow/carry-question.webp',
  answer: '/brand/guide/flow/carry-answer.webp',
}

const segmentLength = (a: Point, b: Point) => Math.hypot(b[0] - a[0], b[1] - a[1])
const polylineLength = (points: Point[]) => points.slice(1).reduce((sum, p, i) => sum + segmentLength(points[i], p), 0)

/** 꺾은선 위 `distance` 지점과 그 지점에서 가는 방향. DOM 없이 계산해 서버 렌더와 테스트에서도 같다. */
function pointAt(points: Point[], distance: number): { at: Point; dx: number } {
  let left = distance
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1], b = points[i]
    const length = segmentLength(a, b)
    if (left <= length || i === points.length - 1) {
      const t = length === 0 ? 1 : Math.min(1, Math.max(0, left / length))
      return { at: [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t], dx: b[0] - a[0] }
    }
    left -= length
  }
  return { at: points[0], dx: 1 }
}

/** 한 단계의 경로를 0~1 진행도로 읽는다. 다리마다 길이에 비례해 시간을 나눈다. */
function placeOnLegs(layout: Layout, legs: Leg[], progress: number) {
  const paths = legs.map(leg => (leg.reverse ? [...layout.edges[leg.edge]].reverse() : layout.edges[leg.edge]))
  const lengths = paths.map(polylineLength)
  const total = lengths.reduce((a, b) => a + b, 0)
  let left = Math.min(1, Math.max(0, progress)) * total
  for (let i = 0; i < legs.length; i++) {
    if (left <= lengths[i] || i === legs.length - 1) {
      const { at, dx } = pointAt(paths[i], Math.min(left, lengths[i]))
      return { at, dx, carry: legs[i].carry }
    }
    left -= lengths[i]
  }
  return { at: paths[0][0], dx: 1, carry: legs[0].carry }
}

const pathOf = (points: Point[]) => points.map((p, i) => `${i ? 'L' : 'M'}${p[0]} ${p[1]}`).join(' ')

function Logo({ name, x, y, size }: { name: TechLogoKey | 'hanjeok' | 'gate'; x: number; y: number; size: number }) {
  const inner = size * 0.64
  const pad = (size - inner) / 2
  return <g transform={`translate(${x} ${y})`}>
    <rect width={size} height={size} rx={6} fill={LOGO_CHIP} stroke="var(--line-normal)" />
    {name === 'hanjeok' ? <>
      <rect x={2} y={2} width={size - 4} height={size - 4} rx={5} fill={HANJEOK_GREEN} />
      <text x={size / 2} y={size / 2 + 4} textAnchor="middle" fontSize={11} fontWeight={700} fill={LOGO_CHIP}>한적</text>
    </> : name === 'gate' ? (
      <path transform={`translate(${pad} ${pad}) scale(${inner / 24})`} fill="var(--accent-quiet)" d="M12 1.5 3.5 4.7v6.1c0 5.3 3.6 10.2 8.5 11.7 4.9-1.5 8.5-6.4 8.5-11.7V4.7L12 1.5Zm-1.3 14.9-4-4 1.5-1.5 2.5 2.5 5.3-5.3 1.5 1.5-6.8 6.8Z" />
    ) : (
      <path transform={`translate(${pad} ${pad}) scale(${inner / 24})`} fill={TECH_LOGOS[name].hex ?? LOGO_BLACK} d={TECH_LOGOS[name].path}>
        <title>{TECH_LOGOS[name].title}</title>
      </path>
    )}
  </g>
}

function Diagram({ layout, lang, step, reduced, className }: { layout: Layout; lang: Lang; step: number; reduced: boolean; className: string }) {
  const ko = lang === 'ko'
  const current = STEPS[step]
  const spriteRef = useRef<SVGGElement>(null)
  const questionRef = useRef<SVGImageElement>(null)
  const answerRef = useRef<SVGImageElement>(null)
  const eventRef = useRef<SVGCircleElement>(null)

  // 처음 그릴 때(서버 렌더 포함)와 움직임 줄이기에서는 경로의 끝, 곧 이 단계가 닿는 곳에 둔다.
  const rest = placeOnLegs(layout, current.legs.filter(leg => leg.carry !== 'event'), 1)

  useEffect(() => {
    const draw = (progress: number) => {
      const { at, dx, carry } = placeOnLegs(layout, current.legs, progress)
      const half = layout.sprite / 2
      spriteRef.current?.setAttribute('transform', `translate(${at[0] - half} ${at[1] - half - 4})`)
      for (const [ref, kind] of [[questionRef, 'question'], [answerRef, 'answer']] as const) {
        ref.current?.setAttribute('visibility', carry === kind ? 'visible' : 'hidden')
        ref.current?.setAttribute('transform', dx < 0 ? `translate(${layout.sprite} 0) scale(-1 1)` : '')
      }
      eventRef.current?.setAttribute('visibility', carry === 'event' ? 'visible' : 'hidden')
      eventRef.current?.setAttribute('cx', String(at[0]))
      eventRef.current?.setAttribute('cy', String(at[1]))
      if (carry === 'event') spriteRef.current?.setAttribute('visibility', 'hidden')
      else spriteRef.current?.setAttribute('visibility', 'visible')
    }
    if (reduced || typeof window.requestAnimationFrame !== 'function') {
      const end = placeOnLegs(layout, current.legs.filter(leg => leg.carry !== 'event'), 1)
      const half = layout.sprite / 2
      spriteRef.current?.setAttribute('transform', `translate(${end.at[0] - half} ${end.at[1] - half - 4})`)
      spriteRef.current?.setAttribute('visibility', 'visible')
      eventRef.current?.setAttribute('visibility', 'hidden')
      return
    }
    let frame = 0
    const start = performance.now()
    const tick = (now: number) => {
      const elapsed = (now - start) % STEP_MS
      draw(Math.min(1, elapsed / (STEP_MS * TRAVEL)))
      frame = window.requestAnimationFrame(tick)
    }
    frame = window.requestAnimationFrame(tick)
    return () => window.cancelAnimationFrame(frame)
  }, [layout, current, reduced])

  const activeEdges = new Set(current.legs.map(leg => leg.edge))
  const half = layout.sprite / 2
  const label = ko
    ? '방문자 화면에서 Cloud Run 컨테이너의 FastAPI와 LangGraph 에이전트로 질문이 가고, 에이전트가 NVIDIA NIM, Neo4j 그래프와 위키, 한적 API를 오간 뒤 인용 검사를 통과한 답이 화면으로 돌아오는 구조'
    : 'A question goes from the visitor screen to FastAPI and the LangGraph agent in one Cloud Run container; the agent goes back and forth to NVIDIA NIM, the Neo4j graph and wiki, and the Hanjeok API, and an answer that passes the citation gate returns to the screen'

  return <svg viewBox={layout.viewBox} role="img" aria-label={label} className={className}>
    <rect x={layout.container.x} y={layout.container.y} width={layout.container.w} height={layout.container.h} rx={16} fill="none" stroke="var(--line-strong)" strokeDasharray="6 6" />
    <g>
      {layout.container.anchor === 'start' && <Logo name="googlecloud" x={layout.container.x + 12} y={layout.container.y + 9} size={22} />}
      <text x={layout.container.labelX} y={layout.container.labelY} textAnchor={layout.container.anchor} fontSize={12} fontWeight={600} fill="var(--ink-muted)">
        {ko ? 'Cloud Run 컨테이너 하나' : 'One Cloud Run container'}
      </text>
    </g>
    <text x={layout.external.x} y={layout.external.y} textAnchor={layout.external.anchor} fontSize={12} fontWeight={600} fill="var(--ink-muted)">{ko ? '외부 서비스' : 'External services'}</text>

    <g fill="none" strokeWidth={2} strokeLinejoin="round">
      {(Object.keys(layout.edges) as EdgeKey[]).map(key => <path key={key} d={pathOf(layout.edges[key])} stroke="var(--line-strong)" />)}
      {(Object.keys(layout.edges) as EdgeKey[]).filter(key => activeEdges.has(key)).map(key =>
        <path key={`on-${key}`} d={pathOf(layout.edges[key])} stroke="var(--brand-primary)" strokeDasharray="6 5" className={reduced ? '' : 'motion-safe:animate-[flow-dash_1s_linear_infinite]'} />)}
    </g>

    {(Object.keys(layout.nodes) as NodeKey[]).map(key => {
      const box = layout.nodes[key]
      const text = NODE_TEXT[key][ko ? 'ko' : 'en']
      const on = current.active.includes(key)
      return <g key={key} data-node={key} data-active={on ? 'true' : 'false'}>
        <rect x={box.x} y={box.y} width={box.w} height={layout.nodeH} rx={12} fill={on ? 'var(--brand-soft)' : 'var(--surface-panel)'} stroke={on ? 'var(--brand-primary)' : 'var(--line-normal)'} strokeWidth={on ? 2 : 1} />
        {NODE_TEXT[key].logos.map((logo, i) => <Logo key={logo} name={logo} x={box.x + 12 + i * 28} y={box.y + 10} size={24} />)}
        <text x={box.x + 12} y={box.y + 52} fontSize={13} fontWeight={600} fill="var(--ink-title)">{text[0]}</text>
        <text x={box.x + 12} y={box.y + 68} fontSize={11} fill="var(--ink-muted)">{text[1]}</text>
      </g>
    })}

    {step >= 1 && step <= 3 && <g transform={`translate(${layout.loopBadge[0]} ${layout.loopBadge[1]})`}>
      <rect x={-58} y={-10} width={58} height={20} rx={10} fill="var(--brand-primary)" />
      <text x={-29} y={4} textAnchor="middle" fontSize={11} fontWeight={600} fill="var(--brand-on-primary)">{ko ? '최대 3번' : 'Up to 3×'}</text>
    </g>}

    <circle ref={eventRef} r={6} fill="var(--brand-primary)" stroke="var(--surface-panel)" strokeWidth={2} visibility="hidden" />
    <g ref={spriteRef} transform={`translate(${rest.at[0] - half} ${rest.at[1] - half - 4})`} aria-hidden="true">
      <image ref={questionRef} href={SPRITES.question} width={layout.sprite} height={layout.sprite} visibility={rest.carry === 'question' ? 'visible' : 'hidden'} />
      <image ref={answerRef} href={SPRITES.answer} width={layout.sprite} height={layout.sprite} visibility={rest.carry === 'answer' ? 'visible' : 'hidden'} />
    </g>
  </svg>
}

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
    const timer = setInterval(() => setStep(current => Math.min(current + 1, STEPS.length - 1)), STEP_MS)
    return () => clearInterval(timer)
  }, [playing, reduced])
  useEffect(() => { if (step === STEPS.length - 1) setPlaying(false) }, [step])
  const move = (next: number) => { setPlaying(false); setStep(next) }
  const selected = STEPS[step][ko ? 'ko' : 'en']
  return <section className="space-y-5 rounded-card border border-line-normal bg-surface-panel p-5 sm:p-7" aria-labelledby="agent-flow-heading">
    <div className="space-y-2">
      <p className="text-caption font-semibold text-brand-primary">{ko ? '한적 에이전트가 일하는 방식' : 'How the Hanjeok agent works'}</p>
      <h2 id="agent-flow-heading" className="text-title-1">{ko ? '질문 한 번이 답이 되기까지' : 'From a question to an answer'}</h2>
      <p className="text-caption leading-relaxed text-ink-muted">{ko ? '설명용 시뮬레이션이에요. 실제 요청이나 서버 상태를 표시하지 않아요. 잎새가 질문을 들고 가고, 찾은 것을 카드에 담아 돌아와요.' : 'An educational simulation, not a live request or server status. The leaf carries the question out and brings back what it found on a card.'}</p>
    </div>
    <div className="rounded-card bg-surface-subtle p-2 sm:p-3">
      <Diagram layout={WIDE} lang={lang} step={step} reduced={reduced} className="hidden w-full sm:block" />
      <Diagram layout={NARROW} lang={lang} step={step} reduced={reduced} className="block w-full sm:hidden" />
    </div>
    <ol className="grid grid-cols-2 gap-2 sm:grid-cols-3" aria-label={ko ? '설명 단계' : 'Explanation steps'}>
      {STEPS.map((item, index) => <li key={item.en[0]}><button type="button" aria-current={index === step ? 'step' : undefined} onClick={() => move(index)} className={`flex min-h-control-md w-full items-center gap-2 rounded-control border px-3 py-2 text-left text-caption focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-primary ${index === step ? 'border-brand-primary bg-brand-soft text-ink-title' : 'border-line-normal text-ink-muted'}`}><span className="font-semibold text-brand-primary">0{index + 1}</span>{item[ko ? 'ko' : 'en'][0]}</button></li>)}
    </ol>
    <div className="min-h-32 space-y-2 rounded-card bg-brand-soft p-4" aria-live={playing ? 'off' : 'polite'} aria-atomic="true">
      <p className="text-title-2">{step + 1}. {selected[0]}</p>
      <p className="text-body leading-relaxed text-ink-body">{selected[1]}</p>
    </div>
    <div className="flex flex-wrap gap-2" role="group" aria-label={ko ? '흐름 재생' : 'Flow playback'}>
      <Button size="sm" disabled={reduced} onClick={() => { if (step === STEPS.length - 1) setStep(0); setPlaying(value => !value) }}>{playing ? (ko ? '일시정지' : 'Pause') : (ko ? '재생' : 'Play')}</Button>
      <Button size="sm" variant="secondary" disabled={step === 0} onClick={() => move(step - 1)}>{ko ? '이전 단계' : 'Previous'}</Button>
      <Button size="sm" variant="secondary" disabled={step === STEPS.length - 1} onClick={() => move(step + 1)}>{ko ? '다음 단계' : 'Next'}</Button>
      <Button size="sm" variant="ghost" onClick={() => move(0)}>{ko ? '처음으로' : 'Restart'}</Button>
    </div>
    {reduced && <p className="text-caption text-ink-muted">{ko ? '움직임 줄이기 설정에 따라 자동 재생과 이동하는 그림을 끄고, 단계 버튼으로 설명을 읽을 수 있어요.' : 'Reduced motion is enabled. Playback and moving pictures are off; use the step buttons to read the explanation.'}</p>}
    <details className="border-t border-line-normal pt-4 text-caption text-ink-muted"><summary className="cursor-pointer py-2">{ko ? '실제 구성과 한계 더 보기' : 'Architecture and limits'}</summary><div className="mt-3 space-y-3 leading-relaxed">
      <p>{ko ? '화면은 Vercel의 Next.js, 질문 처리는 Cloud Run의 FastAPI와 LangGraph가 맡아요. Neo4j와 임베딩 모델, 위키도 이 컨테이너에 있고, NVIDIA NIM과 한적 API는 외부 서비스예요.' : 'Next.js runs on Vercel. FastAPI, LangGraph, Neo4j, the embedding model and wiki run in Cloud Run. NVIDIA NIM and the Hanjeok API are external services.'}</p>
      <p>{ko ? '장소 데이터는 한적에서 내보낸 파일을 검증해 빌드할 때 적재해요. 위키 정책은 키워드에 맞춰 찾아요. 한적 DB에 직접 접속하지 않으며, 예보와 대안만 요청 시 읽기 전용 API로 받아요.' : 'Verified Hanjeok exports populate place data at build time; wiki policies use keyword lookup. There is no direct connection to the Hanjeok database. Forecasts and alternatives use read-only APIs at request time.'}</p>
      <p>{ko ? '조회는 최대 3번, 답 작성과 수정은 각각 1번, 서버 처리 예산은 60초예요. 예약, 결제나 확인할 수 없는 정보를 대신 만들어 주지는 않아요.' : 'The server budget is 60 seconds: up to three lookups, one answer and one repair. The agent does not book, take payments or invent unavailable information.'}</p>
      <p>{ko ? '조회 7가지: 장소 검색, 상세, 연관 장소, 혼잡 예보, 대안, 행사, 정책. 모델: nvidia/nemotron-3-super-120b-a12b.' : 'Seven lookups: search, place detail, related places, congestion, alternatives, events and policies. Model: nvidia/nemotron-3-super-120b-a12b.'}</p>
      <p>{ko ? '로고는 각 회사의 상표이고, simple-icons(CC0)의 공식 마크를 바꾸지 않고 썼어요. 잎새 그림은 Codex 이미지 생성으로 만들었어요.' : 'Logos are trademarks of their owners, used unaltered from simple-icons (CC0). The leaf pictures were made with Codex image generation.'}</p>
    </div></details>
  </section>
}
