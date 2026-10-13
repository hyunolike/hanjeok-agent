import { describe, expect, it, vi } from 'vitest'
import { askGuide, parseSseFrame } from './guide'
import { DEMO_KEYS, RECORDED_STREAMS, type Frame } from './guide-fixtures'
import { isTerminal, parseGuideFrame, type GuideEvent } from './guide-schema'

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
