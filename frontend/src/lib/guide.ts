import {
  RECORDED_AFTER_CHOICE,
  RECORDED_LIMIT,
  RECORDED_STREAMS,
  type DemoKey,
  type Frame,
} from './guide-fixtures'
import {
  RECORDED_EVAL_REPORT,
  RECORDED_STATUS,
  recordedEvalSample,
  recordedPlace,
  searchRecordedPlaces,
} from './guide-data-fixtures'
import {
  evalReportSchema,
  evalSampleSchema,
  isTerminal,
  parseGuideFrame,
  placeDetailSchema,
  placesResponseSchema,
  statusSchema,
  usageLimitSchema,
  type EvalReport,
  type EvalSample,
  type GuideEvent,
  type GuideStatus,
  type PlaceDetail,
  type PlacesResponse,
} from './guide-schema'

/**
 * 안내 에이전트 서버 주소. **비어 있으면 녹화본을 재생한다.**
 *
 * 기본값을 localhost 로 두지 않는 이유가 그것이다 — 주소가 없다는 사실 자체가
 * "서버 없이 화면만 본다"는 뜻이어야, 백엔드 없이 올라간 미리보기 배포가 죽은
 * 주소를 두드리다 실패 화면을 보여 주는 대신 데모를 재생한다.
 */
export const GUIDE_BASE_URL = process.env.NEXT_PUBLIC_GUIDE_BASE_URL ?? ''

export const isReplay = GUIDE_BASE_URL === ''

export type AskRequest = {
  question: string
  visitId: string | null
  /** `ask_user` 에 대한 답. 서버가 내놓은 후보 중 하나여야 한다. */
  choice?: number | null
}

export type AskOptions = {
  baseUrl?: string
  fetchImpl?: typeof fetch
  /** 재생할 녹화본. 주소가 없을 때만 쓰인다. */
  demo?: DemoKey
  /** 녹화본의 단계 사이 간격. 테스트는 0 을 준다. */
  stepDelayMs?: number
  signal?: AbortSignal
}

const sleep = (ms: number) => (ms > 0 ? new Promise<void>((resolve) => setTimeout(resolve, ms)) : Promise.resolve())

/**
 * 질문 하나를 보내고 사건을 차례로 넘긴다.
 *
 * **던지지 않고, 언제나 종결 사건 정확히 하나로 끝난다.** 화면은 "이 질문이
 * 끝났는가"를 그 하나로 판단하므로, 종결이 없거나 둘이면 입력창이 영영 잠기거나
 * 두 번 풀린다. 서버가 종결 없이 끊으면 `cut` 을 대신 낸다 — 답을 지어내지 않는다.
 */
export async function askGuide(
  request: AskRequest,
  onEvent: (event: GuideEvent) => void,
  options: AskOptions = {},
): Promise<void> {
  const baseUrl = options.baseUrl ?? GUIDE_BASE_URL
  let ended = false
  const emit = (event: GuideEvent) => {
    if (ended) return
    if (isTerminal(event)) ended = true
    onEvent(event)
  }

  try {
    if (baseUrl === '') {
      await replay(request, emit, options)
    } else {
      await stream(baseUrl, request, emit, options)
    }
  } catch {
    // 계약에 어긋난 프레임, 끊긴 연결, 취소. 어느 쪽이든 화면이 할 일은 같다.
  }
  emit({ type: 'cut' })
}

async function replay(request: AskRequest, emit: (event: GuideEvent) => void, options: AskOptions) {
  const demo = options.demo ?? 'answered'
  const delay = options.stepDelayMs ?? 700
  if (demo === 'limit') {
    emit({ type: 'limited', scope: RECORDED_LIMIT.scope, retry_after_s: RECORDED_LIMIT.retry_after_s })
    return
  }
  const frames: Frame[] = request.choice != null ? RECORDED_AFTER_CHOICE : RECORDED_STREAMS[demo]
  for (const frame of frames) {
    if (options.signal?.aborted) return
    emit(parseGuideFrame(frame.event, frame.data))
    await sleep(delay)
  }
}

async function stream(
  baseUrl: string,
  request: AskRequest,
  emit: (event: GuideEvent) => void,
  options: AskOptions,
) {
  const fetchImpl = options.fetchImpl ?? fetch
  const response = await fetchImpl(`${baseUrl}/guide/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({
      question: request.question,
      visit_id: request.visitId,
      choice: request.choice ?? null,
    }),
    cache: 'no-store',
    signal: options.signal,
  })

  if (response.status === 429) {
    const limit = usageLimitSchema.parse(await response.json())
    emit({ type: 'limited', scope: limit.scope, retry_after_s: limit.retry_after_s })
    return
  }
  if (!response.ok || !response.body) return

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    // 프록시가 CRLF 로 바꿔 보내는 경우가 있다. 한 가지로 맞춘 뒤 자른다.
    buffer = (buffer + decoder.decode(value, { stream: true })).replace(/\r\n/g, '\n')
    let boundary = buffer.indexOf('\n\n')
    while (boundary >= 0) {
      const frame = parseSseFrame(buffer.slice(0, boundary))
      buffer = buffer.slice(boundary + 2)
      if (frame) emit(parseGuideFrame(frame.event, JSON.parse(frame.data)))
      boundary = buffer.indexOf('\n\n')
    }
  }
}

/** `event:` 한 줄과 `data:` 여러 줄. 주석(`:`)만 있는 프레임은 keep-alive 라 버린다. */
export function parseSseFrame(raw: string): { event: string; data: string } | null {
  let event = ''
  const data: string[] = []
  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) data.push(line.slice(5).replace(/^ /, ''))
  }
  return event && data.length > 0 ? { event, data: data.join('\n') } : null
}

/**
 * 한 번 읽어 오는 것들의 결과. **던지지 않는다** — 화면이 다룰 경우는 셋뿐이다:
 * 받았다, 그런 것이 없다(404), 지금은 못 받는다(그 밖의 전부).
 *
 * 계약에 어긋난 응답도 "못 받는다"로 간다. 모양이 틀린 보고서를 반쯤 그리는 것보다
 * 없다고 말하는 편이 낫다.
 */
export type Loaded<T> = { ok: true; data: T } | { ok: false; cause: 'not_found' | 'unavailable' }

export type ReadOptions = { baseUrl?: string; fetchImpl?: typeof fetch; signal?: AbortSignal }

const found = <T>(data: T | null): Loaded<T> => (data === null ? { ok: false, cause: 'not_found' } : { ok: true, data })

async function read<T>(
  path: string,
  schema: { parse: (data: unknown) => T },
  // 녹화본은 어디서 왔든 스키마를 지나야 한다. 그래서 타입을 믿지 않고 받는다.
  recorded: () => unknown,
  options: ReadOptions,
): Promise<Loaded<T>> {
  const baseUrl = options.baseUrl ?? GUIDE_BASE_URL
  try {
    // 녹화본도 같은 스키마를 지나게 한다. 녹화본이 계약에서 벗어나면 여기서 드러난다.
    if (baseUrl === '') {
      const data = recorded()
      return found(data === null ? null : schema.parse(data))
    }
    const response = await (options.fetchImpl ?? fetch)(`${baseUrl}${path}`, {
      headers: { Accept: 'application/json' },
      cache: 'no-store',
      signal: options.signal,
    })
    if (response.status === 404) return { ok: false, cause: 'not_found' }
    if (!response.ok) return { ok: false, cause: 'unavailable' }
    return { ok: true, data: schema.parse(await response.json()) }
  } catch {
    return { ok: false, cause: 'unavailable' }
  }
}

/** 이름으로 장소 찾기. 순서는 서버가 정한 그대로다. */
export function fetchPlaces(query: string, options: ReadOptions = {}): Promise<Loaded<PlacesResponse>> {
  return read(
    `/guide/places?query=${encodeURIComponent(query.trim())}`,
    placesResponseSchema,
    () => searchRecordedPlaces(query),
    options,
  )
}

export function fetchPlace(placeId: number, options: ReadOptions = {}): Promise<Loaded<PlaceDetail>> {
  return read(`/guide/places/${placeId}`, placeDetailSchema, () => recordedPlace(placeId), options)
}

export function fetchStatus(options: ReadOptions = {}): Promise<Loaded<GuideStatus>> {
  return read('/guide/status', statusSchema, () => RECORDED_STATUS, options)
}

/** 가장 최근에 공개한 평가. `empty` 는 "공개한 평가가 없다"를 녹화본으로 보여 줄 때만 쓴다. */
export function fetchEvalReport(options: ReadOptions & { empty?: boolean } = {}): Promise<Loaded<EvalReport>> {
  return read('/guide/eval/latest', evalReportSchema, () => (options.empty ? null : RECORDED_EVAL_REPORT), options)
}

export function fetchEvalSample(
  reportId: string,
  questionId: string,
  options: ReadOptions = {},
): Promise<Loaded<EvalSample>> {
  return read(
    `/guide/eval/${encodeURIComponent(reportId)}/samples/${encodeURIComponent(questionId)}`,
    evalSampleSchema,
    () => recordedEvalSample(questionId),
    options,
  )
}
