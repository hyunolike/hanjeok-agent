import {
  contextListSchema,
  explainResponseSchema,
  factsResponseSchema,
  type ContextEntry,
  type ExplainResponse,
  type Facts,
} from './schema'

/**
 * 에이전트 서버 클라이언트.
 *
 * 프론트가 아는 백엔드는 이것 하나다. 한적 주소는 여기 없고, 앞으로도 없어야
 * 한다 — 사실의 출처가 두 곳이 되면 "설명이 근거로 삼은 것"과 "화면이 그린 것"이
 * 갈라질 수 있고, 그 순간 인용 화면은 아무것도 증명하지 못한다.
 */
export const AGENT_BASE_URL =
  process.env.NEXT_PUBLIC_AGENT_BASE_URL ?? 'http://localhost:8080'

/** 설명이 없는 것은 다뤄야 할 정상 상태다 — 예외로 던지지 않고 값으로 돌려준다. */
export type Unavailable = { kind: 'unavailable'; status: number }
export type Loaded<T> = { kind: 'loaded'; value: T }
export type Result<T> = Loaded<T> | Unavailable

type Fetch = typeof fetch

async function get<T>(
  path: string,
  parse: (raw: unknown) => T,
  init: RequestInit & { fetchImpl?: Fetch } = {},
): Promise<Result<T>> {
  const { fetchImpl = fetch, ...rest } = init

  // 서버가 아예 안 뜬 경우(ECONNREFUSED)는 예외로 온다. 503 과 같은 상태이므로
  // 같은 값으로 만든다 — 여기서 던지면 백엔드가 내려간 것이 화면 전체를 무너뜨린다.
  let response: Response
  try {
    response = await fetchImpl(`${AGENT_BASE_URL}${path}`, rest)
  } catch {
    return { kind: 'unavailable', status: 0 }
  }

  if (!response.ok) return { kind: 'unavailable', status: response.status }

  // 파싱 실패는 삼키지 않는다. 서버가 모양을 바꾼 것을 "설명 없음"으로 덮으면,
  // 고장난 배포가 조용한 화면으로 보인다.
  return { kind: 'loaded', value: parse(await response.json()) }
}

export function fetchFacts(courseUuid: string, fetchImpl?: Fetch): Promise<Result<Facts>> {
  return get(
    `/agent/facts/${encodeURIComponent(courseUuid)}`,
    (raw) => factsResponseSchema.parse(raw).facts,
    { cache: 'no-store', fetchImpl },
  )
}

export function fetchExplanation(
  courseUuid: string,
  fetchImpl?: Fetch,
): Promise<Result<ExplainResponse>> {
  return get('/agent/explain', (raw) => explainResponseSchema.parse(raw), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ courseUuid }),
    cache: 'no-store',
    fetchImpl,
  })
}

/** 서버는 대화를 저장하지 않는다 — 이전 turn 을 매 요청 함께 보낸다. */
export type AskTurn = { question: string; answer: string }

export function fetchContextList(fetchImpl?: Fetch): Promise<Result<ContextEntry[]>> {
  return get('/agent/context', (raw) => contextListSchema.parse(raw), { fetchImpl })
}

export type AskStreamEvent =
  | { kind: 'citations'; citations: string[] }
  | { kind: 'delta'; text: string }
  | { kind: 'looking'; what: string }
  | { kind: 'done'; generatedAt: string; model: string }
  | { kind: 'unavailable' }
  | { kind: 'aborted' }

/**
 * 이어 묻기를 스트림으로 받는다.
 *
 * **던지지 않고, 반드시 종결 이벤트 하나(done·unavailable·aborted)로 끝난다.** 연결 실패를
 * 예외로 올리면 백엔드가 내려간 것이 화면 전체를 무너뜨린다 — `get()` 과 같은 이유다.
 *
 * `done` 없이 연결이 끊기면, 본문을 받았으면 aborted 를, 못 받았으면 unavailable 을 낸다.
 * 받은 본문은 인용 검증을 통과했지만 문장이 미완이므로 호출자는 그것을 설명으로 남기면
 * 안 된다.
 */
export async function askCourseStream(
  courseUuid: string,
  question: string,
  history: AskTurn[],
  onEvent: (event: AskStreamEvent) => void,
  fetchImpl: Fetch = fetch,
): Promise<void> {
  let response: Response
  try {
    response = await fetchImpl(`${AGENT_BASE_URL}/agent/ask/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ courseUuid, question, history }),
      cache: 'no-store',
    })
  } catch {
    onEvent({ kind: 'unavailable' })
    return
  }
  if (!response.ok || !response.body) {
    onEvent({ kind: 'unavailable' })
    return
  }

  let terminated = false
  let deltas = 0

  const dispatch = (frame: string) => {
    let name = ''
    let data = ''
    for (const line of frame.split('\n')) {
      if (line.startsWith('event:')) name = line.slice(6).trim()
      else if (line.startsWith('data:')) data += line.slice(5).replace(/^ /, '')
    }
    if (terminated || !name) return
    const payload = data ? JSON.parse(data) : {}
    switch (name) {
      case 'citations':
        onEvent({ kind: 'citations', citations: payload.citations })
        break
      case 'delta':
        deltas++
        onEvent({ kind: 'delta', text: payload.text })
        break
      case 'looking':
        // 도구 이름만 온다 — 인자는 실려 오지 않는다. delta 가 아니므로 deltas 는
        // 건드리지 않는다: done 없이 끊겼을 때 aborted/unavailable 을 가르는 신호가
        // "본문을 받았는가"이지 "뭔가 왔는가"가 아니기 때문이다.
        onEvent({ kind: 'looking', what: String(payload.what ?? '') })
        break
      case 'done':
        terminated = true
        onEvent({ kind: 'done', generatedAt: payload.generatedAt, model: payload.model })
        break
      case 'unavailable':
        terminated = true
        onEvent({ kind: 'unavailable' })
        break
      case 'aborted':
        terminated = true
        onEvent({ kind: 'aborted' })
        break
    }
  }

  const reader = response.body.getReader()
  // stream: true — 한글 UTF-8 바이트가 read 경계에서 잘려도 다음 read 와 이어 푼다.
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
      let cut: number
      while ((cut = buffer.indexOf('\n\n')) >= 0) {
        dispatch(buffer.slice(0, cut))
        buffer = buffer.slice(cut + 2)
      }
    }
  } catch {
    // 연결이 도중에 끊겼다. 여기엔 이름 있는 프레임의 JSON.parse 실패도 포함된다 —
    // 의도적이다. 깨진 프레임을 건너뛰고 계속 읽으면, 그게 delta 라면 답의 한 조각이
    // 조용히 사라진 채로 done 이 뒤따라와 "완결된 답"으로 확정돼 버린다. done 은
    // 완결을 뜻한다는 계약을 지키려면 여기서 멈추고 실패로 닫아야 한다 — "설명 없음은
    // 안전한 실패"라는 이 서비스 전체의 원칙과 같다. 아래에서 종결 이벤트를 채운다.
  }

  if (!terminated) onEvent(deltas > 0 ? { kind: 'aborted' } : { kind: 'unavailable' })
}

/** 근거 문서 본문. 모델이 본 바로 그 바이트라 JSON 이 아니라 text 다. */
export async function fetchContextDocument(
  path: string,
  fetchImpl: Fetch = fetch,
): Promise<Result<string>> {
  let response: Response
  try {
    response = await fetchImpl(`${AGENT_BASE_URL}/agent/context/${path}`)
  } catch {
    return { kind: 'unavailable', status: 0 }
  }
  if (!response.ok) return { kind: 'unavailable', status: response.status }
  return { kind: 'loaded', value: await response.text() }
}
