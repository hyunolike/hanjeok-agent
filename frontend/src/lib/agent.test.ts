import { describe, expect, it, vi } from 'vitest'
import { fetchContextDocument, fetchContextList, fetchExplanation, fetchFacts } from './agent'
import { factsFixture } from './fixtures'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('에이전트 클라이언트', () => {
  it('사실을 파싱해 돌려준다', async () => {
    const stub = vi.fn().mockResolvedValue(
      jsonResponse({ courseUuid: 'abc', facts: factsFixture }),
    )

    const result = await fetchFacts('abc', stub)

    expect(result).toEqual({ kind: 'loaded', value: factsFixture })
    expect(stub.mock.calls[0][0]).toContain('/agent/facts/abc')
  })

  it('503 을 예외가 아니라 값으로 돌려준다', async () => {
    // 설명이 없는 것은 안전한 실패다. 예외로 던지면 화면 전체가 무너지는데,
    // 이 프로젝트의 계약은 "설명 블록만 사라진다"이다.
    const stub = vi.fn().mockResolvedValue(
      jsonResponse({ code: 'EXPLANATION_UNAVAILABLE' }, 503),
    )

    expect(await fetchExplanation('abc', stub)).toEqual({ kind: 'unavailable', status: 503 })
  })

  it('모르는 등급이 오면 파싱이 실패한다', async () => {
    // 조용히 통과시키면 색도 라벨도 없는 항목이 그려지고, 그 화면은 등급 체계가
    // 어긋난 것을 감춘다.
    const broken = { ...factsFixture, items: [{ ...factsFixture.items[0], grade: 'CHILL' }] }
    const stub = vi.fn().mockResolvedValue(jsonResponse({ courseUuid: 'abc', facts: broken }))

    await expect(fetchFacts('abc', stub)).rejects.toThrow()
  })

  it('필드가 사라지면 파싱이 실패한다', async () => {
    const { congestionReductionRate: _removed, ...broken } = factsFixture
    const stub = vi.fn().mockResolvedValue(jsonResponse({ courseUuid: 'abc', facts: broken }))

    await expect(fetchFacts('abc', stub)).rejects.toThrow()
  })

  it('근거 문서는 텍스트 그대로 받는다', async () => {
    // 모델이 본 바로 그 바이트를 보여 주는 것이 이 화면의 존재 이유라, JSON 으로
    // 한 번 감싸 풀면 그 주장이 약해진다.
    const stub = vi.fn().mockResolvedValue(new Response('# 혼잡 진단\n', { status: 200 }))

    const result = await fetchContextDocument('concepts/congestion-diagnosis.md', stub)

    expect(result).toEqual({ kind: 'loaded', value: '# 혼잡 진단\n' })
  })

  it('없는 문서는 404 를 값으로 돌려준다', async () => {
    const stub = vi.fn().mockResolvedValue(new Response('', { status: 404 }))

    expect(await fetchContextDocument('nope.md', stub)).toEqual({
      kind: 'unavailable',
      status: 404,
    })
  })

  it('번들 목록은 문서별 크기와 프롬프트 크기를 함께 받는다', async () => {
    // 화면이 "모델이 매 요청 보는 전부"라고 적는 숫자는 문서 본문 합계가 아니라
    // systemTextBytes 다. 서버가 이 필드를 빼면 화면은 그 말을 할 수 없다.
    const listing = {
      documents: [{ path: 'concepts/alternative-scoring.md', bytes: 2276 }],
      systemTextBytes: 23079,
    }
    const stub = vi.fn().mockResolvedValue(jsonResponse(listing))

    expect(await fetchContextList(stub)).toEqual({ kind: 'loaded', value: listing })
    expect(stub.mock.calls[0][0]).toContain('/agent/context')
  })

  it('예전 배열 모양이 오면 파싱이 실패한다', async () => {
    // 서버가 목록만 돌려주던 때의 모양이다. 조용히 통과시키면 프롬프트 크기가
    // undefined 가 되고, 화면은 "모델이 보는 전부"라는 자리에 빈 칸을 그린다.
    const stub = vi.fn().mockResolvedValue(
      jsonResponse([{ path: 'concepts/alternative-scoring.md', bytes: 2276 }]),
    )

    await expect(fetchContextList(stub)).rejects.toThrow()
  })
})

describe('예보 커버리지가 없는 코스', () => {
  it('진단 없는 사실을 받아들인다', async () => {
    // 이 분기를 거부하면 멀쩡한 코스가 화면에서 통째로 사라진다. 실제로 서버가
    // 이 분기를 다루기 전에는 그 코스가 503 이었다.
    const noCoverage = {
      ...factsFixture,
      items: [{ ...factsFixture.items[0], grade: null }],
      congestion: {
        hasCongestionData: false as const,
        message: '이 장소는 집중률 예측 데이터가 제공되지 않아요.',
        betterDates: [],
      },
    }
    const stub = vi.fn().mockResolvedValue(jsonResponse({ courseUuid: 'x', facts: noCoverage }))

    const result = await fetchFacts('x', stub)

    expect(result.kind).toBe('loaded')
  })

  it('진단이 있다면서 등급이 없으면 거부한다', async () => {
    // 플래그와 내용이 어긋난 응답이다. 통과시키면 화면이 없는 등급을 읽는다.
    const broken = {
      ...factsFixture,
      congestion: { hasCongestionData: true, message: 'x', betterDates: [] },
    }
    const stub = vi.fn().mockResolvedValue(jsonResponse({ courseUuid: 'x', facts: broken }))

    await expect(fetchFacts('x', stub)).rejects.toThrow()
  })
})

describe('서버가 아예 안 뜬 경우', () => {
  it('연결 거부를 예외가 아니라 값으로 돌려준다', async () => {
    // 첫 프로덕션 빌드가 여기서 죽었다 — 예외가 페이지까지 올라가면 백엔드가
    // 내려간 것이 화면 전체를 무너뜨리고, 빌드까지 실패시킨다.
    const stub = vi.fn().mockRejectedValue(new TypeError('fetch failed'))

    expect(await fetchFacts('abc', stub)).toEqual({ kind: 'unavailable', status: 0 })
    expect(await fetchContextDocument('a.md', stub)).toEqual({ kind: 'unavailable', status: 0 })
  })
})
