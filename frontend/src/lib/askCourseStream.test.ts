import { describe, expect, it } from 'vitest'
import { askCourseStream, type AskStreamEvent } from './agent'

/** 주어진 바이트 조각을 차례로 흘리는 fetch. */
function fetchStreaming(chunks: Uint8Array[], status = 200): typeof fetch {
  return async () =>
    new Response(
      new ReadableStream({
        start(controller) {
          for (const chunk of chunks) controller.enqueue(chunk)
          controller.close()
        },
      }),
      { status, headers: { 'Content-Type': 'text/event-stream' } },
    )
}

const encode = (text: string) => new TextEncoder().encode(text)

async function collect(fetchImpl: typeof fetch): Promise<AskStreamEvent[]> {
  const events: AskStreamEvent[] = []
  await askCourseStream('c', 'q', [], (e) => events.push(e), fetchImpl)
  return events
}

const frames =
  'event:citations\ndata:{"citations":["a.md"]}\n\n' +
  'event:delta\ndata:{"text":"가나"}\n\n' +
  'event:delta\ndata:{"text":"다"}\n\n' +
  'event:done\ndata:{"generatedAt":"t","model":"gpt-4o"}\n\n'

describe('askCourseStream', () => {
  it('이벤트를 순서대로 낸다', async () => {
    const events = await collect(fetchStreaming([encode(frames)]))

    expect(events).toEqual([
      { kind: 'citations', citations: ['a.md'] },
      { kind: 'delta', text: '가나' },
      { kind: 'delta', text: '다' },
      { kind: 'done', generatedAt: 't', model: 'gpt-4o' },
    ])
  })

  it('프레임이 read 경계에 걸려도 같다', async () => {
    const bytes = encode(frames)
    for (let cut = 1; cut < bytes.length; cut++) {
      const events = await collect(fetchStreaming([bytes.slice(0, cut), bytes.slice(cut)]))
      expect(events.map((e) => e.kind), `cut=${cut}`).toEqual(['citations', 'delta', 'delta', 'done'])
      expect(
        events.flatMap((e) => (e.kind === 'delta' ? [e.text] : [])).join(''),
        `cut=${cut}`,
      ).toBe('가나다')
    }
  })

  it('done 없이 끝나면 본문을 받았으면 aborted', async () => {
    const events = await collect(
      fetchStreaming([encode('event:citations\ndata:{"citations":["a.md"]}\n\nevent:delta\ndata:{"text":"미"}\n\n')]),
    )

    expect(events.at(-1)).toEqual({ kind: 'aborted' })
  })

  it('done 없이 끝나면 본문을 못 받았으면 unavailable', async () => {
    const events = await collect(fetchStreaming([encode('event:citations\ndata:{"citations":["a.md"]}\n\n')]))

    expect(events.at(-1)).toEqual({ kind: 'unavailable' })
  })

  it('서버가 aborted 를 보내면 그 이름 그대로 종결 이벤트가 된다', async () => {
    // AskStreamController.kt 가 내는 이벤트 이름("aborted")과 여기 case 라벨이
    // 어긋나면, 서버가 본문 도중 실패를 알려도 클라이언트는 이름 없는 프레임으로
    // 여기고 무시한 뒤 스트림이 끊길 때의 fallback(aborted/unavailable)에 기댄다 —
    // 우연히 같은 결과가 나올 뿐 이 case 문은 죽은 코드가 된다.
    const events = await collect(
      fetchStreaming([
        encode(
          'event:delta\ndata:{"text":"본문"}\n\n' +
            'event:aborted\ndata:{"code":"EXPLANATION_ABORTED"}\n\n',
        ),
      ]),
    )

    expect(events).toEqual([{ kind: 'delta', text: '본문' }, { kind: 'aborted' }])
  })

  it('서버가 unavailable 을 보내면 그것으로 끝나고 덧붙이지 않는다', async () => {
    const events = await collect(
      fetchStreaming([encode('event:unavailable\ndata:{"code":"EXPLANATION_UNAVAILABLE"}\n\n')]),
    )

    expect(events).toEqual([{ kind: 'unavailable' }])
  })

  it('연결이 아예 안 되면 던지지 않고 unavailable', async () => {
    const events = await collect(async () => {
      throw new TypeError('fetch failed')
    })

    expect(events).toEqual([{ kind: 'unavailable' }])
  })

  it('4xx/5xx 면 unavailable', async () => {
    const events = await collect(fetchStreaming([], 503))

    expect(events).toEqual([{ kind: 'unavailable' }])
  })

  it('event: 없는 프레임(프레이밍 없이 붙은 에러 바디)은 무시하고 종결 이벤트로 끝난다', async () => {
    const events = await collect(
      fetchStreaming([
        encode(
          'event:citations\ndata:{"citations":["a.md"]}\n\n' +
            'event:delta\ndata:{"text":"본문"}\n\n' +
            '{"code":"EXPLANATION_UNAVAILABLE"}\n\n',
        ),
      ]),
    )

    expect(events).toEqual([
      { kind: 'citations', citations: ['a.md'] },
      { kind: 'delta', text: '본문' },
      { kind: 'aborted' },
    ])
  })

  it('깨진 프레임은 건너뛰지 않고 스트림을 끝낸다 — 빈 조각이 난 답을 done 으로 확정하지 않는다', async () => {
    const events = await collect(
      fetchStreaming([
        encode(
          'event:citations\ndata:{"citations":["a.md"]}\n\n' +
            'event:delta\ndata:{"text":"본문"}\n\n' +
            'event:delta\ndata:not-json-at-all\n\n' +
            'event:done\ndata:{"generatedAt":"t","model":"gpt-4o"}\n\n',
        ),
      ]),
    )

    expect(events).toEqual([
      { kind: 'citations', citations: ['a.md'] },
      { kind: 'delta', text: '본문' },
      { kind: 'aborted' },
    ])
  })

  it('looking 이벤트를 kind looking 으로 넘긴다', async () => {
    const events = await collect(
      fetchStreaming([
        encode(
          'event:looking\ndata:{"what":"congestion"}\n\n' +
            'event:citations\ndata:{"citations":["concepts/a.md"]}\n\n' +
            'event:delta\ndata:{"text":"답"}\n\n' +
            'event:done\ndata:{"generatedAt":"t","model":"m"}\n\n',
        ),
      ]),
    )

    expect(events[0]).toEqual({ kind: 'looking', what: 'congestion' })
    expect(events.at(-1)).toEqual({ kind: 'done', generatedAt: 't', model: 'm' })
  })

  it('모르는 what 이 와도 터지지 않고 그대로 넘긴다', async () => {
    const events = await collect(
      fetchStreaming([
        encode(
          'event:looking\ndata:{"what":"weather"}\n\nevent:done\ndata:{"generatedAt":"t","model":"m"}\n\n',
        ),
      ]),
    )

    expect(events[0]).toEqual({ kind: 'looking', what: 'weather' })
  })

  it('looking 은 delta 가 아니다 — done 없이 끊기면 본문 없음으로 취급된다', async () => {
    // looking 만 오고 delta 는 한 번도 오지 않은 채 연결이 끊기면, "본문을 받았는가"
    // 기준(aborted/unavailable 을 가르는 그 기준)은 여전히 아니오여야 한다.
    const events = await collect(fetchStreaming([encode('event:looking\ndata:{"what":"congestion"}\n\n')]))

    expect(events).toEqual([{ kind: 'looking', what: 'congestion' }, { kind: 'unavailable' }])
  })

  it('data: 가 깨진 이름 없는 프레임은 JSON.parse 에 닿지 않고 무시된다', async () => {
    const events = await collect(
      fetchStreaming([
        encode(
          'event:citations\ndata:{"citations":["a.md"]}\n\n' +
            'data:not-json-at-all\n\n' +
            'event:delta\ndata:{"text":"본문"}\n\n' +
            'event:done\ndata:{"generatedAt":"t","model":"gpt-4o"}\n\n',
        ),
      ]),
    )

    expect(events).toEqual([
      { kind: 'citations', citations: ['a.md'] },
      { kind: 'delta', text: '본문' },
      { kind: 'done', generatedAt: 't', model: 'gpt-4o' },
    ])
  })
})
