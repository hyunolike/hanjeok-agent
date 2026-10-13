import { describe, expect, it, vi } from 'vitest'
import { askGuide, fetchEvalReport, fetchEvalSample, fetchPlace, fetchPlaces, fetchStatus, parseSseFrame } from './guide'
import { DEMO_KEYS, RECORDED_STREAMS, type Frame } from './guide-fixtures'
import {
  EVAL_KINDS,
  EVAL_METRICS,
  EVAL_STRATEGIES,
  isTerminal,
  parseGuideFrame,
  type GuideEvent,
} from './guide-schema'

const BASE = 'http://guide.test'

function sse(frames: Frame[], chunkSize = 0): Response {
  const text = frames.map((f) => `event: ${f.event}\ndata: ${JSON.stringify(f.data)}\n\n`).join('')
  const bytes = new TextEncoder().encode(text)
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      if (chunkSize <= 0) controller.enqueue(bytes)
      else for (let i = 0; i < bytes.length; i += chunkSize) controller.enqueue(bytes.slice(i, i + chunkSize))
      controller.close()
    },
  })
  return new Response(stream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
}

async function collect(options: Parameters<typeof askGuide>[2], choice?: number): Promise<GuideEvent[]> {
  const events: GuideEvent[] = []
  await askGuide({ question: '질문', visitId: null, choice }, (e) => events.push(e), { stepDelayMs: 0, ...options })
  return events
}

describe('녹화본', () => {
  it.each(DEMO_KEYS.filter((key) => key !== 'limit'))('%s 의 모든 프레임이 계약에 맞는다', (key) => {
    for (const frame of RECORDED_STREAMS[key as keyof typeof RECORDED_STREAMS]) {
      expect(() => parseGuideFrame(frame.event, frame.data)).not.toThrow()
    }
  })

  it('답에 붙은 인용은 전부 그 질문의 단계가 가져온 것이다', () => {
    // 서버의 인용 관문이 지키는 규칙이다. 녹화본이 이것을 어기면 화면이 불가능한 답을 보여 준다.
    for (const key of ['answered', 'partial'] as const) {
      const events = RECORDED_STREAMS[key].map((f) => parseGuideFrame(f.event, f.data))
      const fetched = new Set(events.flatMap((e) => (e.type === 'step' ? e.step.produced : [])))
      const answer = events.find((e) => e.type === 'answer')
      expect(answer?.type).toBe('answer')
      if (answer?.type === 'answer') for (const c of answer.citations) expect(fetched).toContain(c.id)
    }
  })
})

describe('askGuide', () => {
  it.each(DEMO_KEYS)('%s 는 종결 사건 정확히 하나로 끝난다', async (demo) => {
    const events = await collect({ baseUrl: '', demo })
    expect(events.filter(isTerminal)).toHaveLength(1)
    expect(isTerminal(events[events.length - 1])).toBe(true)
  })

  it('주소가 없으면 녹화본을 재생하고 네트워크를 건드리지 않는다', async () => {
    const fetchImpl = vi.fn()
    const events = await collect({ baseUrl: '', demo: 'answered', fetchImpl })
    expect(fetchImpl).not.toHaveBeenCalled()
    expect(events.map((e) => e.type)).toEqual(['visit', 'step', 'step', 'step', 'step', 'answer', 'path', 'done'])
  })

  it('답 글자는 answer 사건 안에서만 온다', async () => {
    const events = await collect({ baseUrl: '', demo: 'answered' })
    const firstAnswer = events.findIndex((e) => e.type === 'answer')
    expect(events.slice(0, firstAnswer).every((e) => e.type === 'visit' || e.type === 'step')).toBe(true)
  })

  it('후보를 고르면 그 장소로 이어진 스트림을 재생한다', async () => {
    const events = await collect({ baseUrl: '', demo: 'ambiguous' }, 140)
    expect(events[events.length - 1].type).toBe('done')
  })

  it('서버 스트림을 읽는다 — 프레임이 청크 경계에서 잘려도', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(sse(RECORDED_STREAMS.answered, 17))
    const events = await collect({ baseUrl: BASE, fetchImpl })
    expect(events.map((e) => e.type)).toEqual(['visit', 'step', 'step', 'step', 'step', 'answer', 'path', 'done'])
    expect(fetchImpl).toHaveBeenCalledWith(`${BASE}/guide/ask`, expect.objectContaining({ method: 'POST' }))
  })

  it('종결 없이 끊긴 스트림은 cut 으로 끝나고 답을 지어내지 않는다', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(sse(RECORDED_STREAMS.cut))
    const events = await collect({ baseUrl: BASE, fetchImpl })
    expect(events[events.length - 1]).toEqual({ type: 'cut' })
    expect(events.some((e) => e.type === 'answer')).toBe(false)
  })

  it('429 는 limited 로 끝난다', async () => {
    const body = JSON.stringify({ cause: 'usage_limit', scope: 'day', retry_after_s: 3600 })
    const fetchImpl = vi.fn().mockResolvedValue(new Response(body, { status: 429 }))
    expect(await collect({ baseUrl: BASE, fetchImpl })).toEqual([{ type: 'limited', scope: 'day', retry_after_s: 3600 }])
  })

  it('네트워크 오류와 계약 위반은 던지지 않고 cut 으로 끝난다', async () => {
    const offline = vi.fn().mockRejectedValue(new TypeError('offline'))
    expect(await collect({ baseUrl: BASE, fetchImpl: offline })).toEqual([{ type: 'cut' }])

    const bogus = vi.fn().mockResolvedValue(sse([{ event: 'thinking', data: {} }]))
    expect(await collect({ baseUrl: BASE, fetchImpl: bogus })).toEqual([{ type: 'cut' }])
  })

  it('종결 뒤에 온 사건은 버린다', async () => {
    const frames = [...RECORDED_STREAMS.declined, RECORDED_STREAMS.answered[5]]
    const fetchImpl = vi.fn().mockResolvedValue(sse(frames))
    const events = await collect({ baseUrl: BASE, fetchImpl })
    expect(events[events.length - 1].type).toBe('stopped')
    expect(events.some((e) => e.type === 'answer')).toBe(false)
  })
})

describe('parseSseFrame', () => {
  it('keep-alive 주석은 프레임이 아니다', () => {
    expect(parseSseFrame(': ping')).toBeNull()
  })

  it('여러 줄 data 를 잇는다', () => {
    expect(parseSseFrame('event: step\ndata: {"a":\ndata: 1}')).toEqual({ event: 'step', data: '{"a":\n1}' })
  })
})

describe('한 번 읽어 오는 것들', () => {
  const json = (body: unknown, status = 200) =>
    vi.fn(async () => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }))

  it('이름 찾기는 똑같은 이름을 앞세우고, 공백을 무시한다', async () => {
    const exact = await fetchPlaces('은행나무길', { baseUrl: '' })
    expect(exact.ok && exact.data.places.map((p) => p.place_id)).toEqual([140, 141])

    const spaced = await fetchPlaces('솔내한옥', { baseUrl: '' })
    expect(spaced.ok && spaced.data.places.map((p) => p.name)).toEqual(['솔내 한옥마을'])

    const none = await fetchPlaces('없는곳', { baseUrl: '' })
    expect(none.ok && none.data.places).toEqual([])
  })

  it('장소의 이웃은 순위 순서이고 혼잡도 값을 싣지 않는다', async () => {
    const result = await fetchPlace(101, { baseUrl: '' })
    expect(result.ok && result.data.related.map((r) => [r.rank, r.name])).toEqual([
      [1, '솔내 한옥마을'],
      [2, '물빛 서원'],
      [3, '달맞이 숲길'],
    ])
    expect(JSON.stringify(result)).not.toMatch(/grade|concentration|혼잡도/)
  })

  it('없는 장소는 not_found 다', async () => {
    expect(await fetchPlace(999, { baseUrl: '' })).toEqual({ ok: false, cause: 'not_found' })
    expect(await fetchPlace(999, { baseUrl: BASE, fetchImpl: json({ cause: 'unknown_place' }, 404) })).toEqual({
      ok: false,
      cause: 'not_found',
    })
  })

  it('서버 오류, 끊긴 연결, 계약에 어긋난 응답은 전부 unavailable 이고 던지지 않는다', async () => {
    const unavailable = { ok: false, cause: 'unavailable' }
    expect(await fetchStatus({ baseUrl: BASE, fetchImpl: json({}, 503) })).toEqual(unavailable)
    expect(await fetchStatus({ baseUrl: BASE, fetchImpl: json({ ready: 'yes' }) })).toEqual(unavailable)
    const broken = vi.fn(async () => {
      throw new TypeError('network')
    })
    expect(await fetchEvalReport({ baseUrl: BASE, fetchImpl: broken })).toEqual(unavailable)
  })

  it('주소가 있으면 계약의 경로를 부른다', async () => {
    const fetchImpl = json({ places: [], as_of: '2026-10-13T02:00:00Z' })
    await fetchPlaces(' 가람 궁 ', { baseUrl: BASE, fetchImpl })
    expect((fetchImpl.mock.calls[0] as unknown[])[0]).toBe(`${BASE}/guide/places?query=${encodeURIComponent('가람 궁')}`)
  })

  it('공개한 평가가 없으면 not_found 다', async () => {
    expect(await fetchEvalReport({ baseUrl: '', empty: true })).toEqual({ ok: false, cause: 'not_found' })
  })
})

describe('녹화한 평가 보고서', () => {
  it('전체 점수의 문항 수는 종류별 문항 수의 합이다', async () => {
    const result = await fetchEvalReport({ baseUrl: '' })
    if (!result.ok) throw new Error('녹화본이 계약에 맞지 않는다')
    for (const strategy of EVAL_STRATEGIES) {
      const { metrics, by_kind, forbidden } = result.data.strategies[strategy]
      for (const metric of EVAL_METRICS) {
        const scored = EVAL_KINDS.reduce((sum, kind) => sum + by_kind[kind][metric].n, 0)
        expect(metrics[metric].n, `${strategy} ${metric}`).toBe(scored)
      }
      for (const { runs } of Object.values(forbidden)) expect(runs).toBe(result.data.question_count)
    }
    expect(result.data.questions).toHaveLength(result.data.question_count)
  })

  it('목록에 있는 문항은 전부 열린다', async () => {
    const report = await fetchEvalReport({ baseUrl: '' })
    if (!report.ok) throw new Error('녹화본이 계약에 맞지 않는다')
    for (const { question_id } of report.data.questions) {
      const sample = await fetchEvalSample(report.data.report_id, question_id, { baseUrl: '' })
      expect(sample.ok, question_id).toBe(true)
    }
    expect(await fetchEvalSample(report.data.report_id, 'q99', { baseUrl: '' })).toEqual({ ok: false, cause: 'not_found' })
  })
})
