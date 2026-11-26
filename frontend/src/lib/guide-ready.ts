import { GUIDE_BASE_URL, type ReadOptions } from './guide'

const READY_BUDGET_MS = 90_000
const REQUEST_TIMEOUT_MS = 12_000
const RETRY_DELAY_MS = 5_000

/** 연결 준비만 확인한다. NVIDIA 모델의 응답 가능 여부는 이 경로가 보장하지 않는다. */
export async function waitForGuideReady(options: ReadOptions = {}): Promise<boolean> {
  if (options.signal?.aborted) return false
  const baseUrl = options.baseUrl ?? GUIDE_BASE_URL
  if (baseUrl === '') return true

  const budget = new AbortController()
  const stop = () => budget.abort()
  options.signal?.addEventListener('abort', stop, { once: true })
  const deadline = setTimeout(stop, READY_BUDGET_MS)
  try {
    while (!budget.signal.aborted) {
      const request = new AbortController()
      const abortRequest = () => request.abort()
      budget.signal.addEventListener('abort', abortRequest, { once: true })
      const timeout = setTimeout(abortRequest, REQUEST_TIMEOUT_MS)
      try {
        const response = await (options.fetchImpl ?? fetch)(`${baseUrl}/guide/ready`, {
          method: 'GET', headers: { Accept: 'application/json' },
          cache: 'no-store', signal: request.signal,
        })
        if (response.ok) {
          const data: unknown = await response.json()
          if (!budget.signal.aborted && !request.signal.aborted && typeof data === 'object' && data !== null &&
              'ready' in data && data.ready === true) return true
        } else {
          // Render의 HTML 오류 페이지도 연결 재사용 전에 읽기를 끝낸다.
          await response.body?.cancel()
        }
      } catch {
        // 기동 중 503, 잘못된 JSON, 네트워크 오류와 요청 제한 시간은 모두 재확인한다.
      } finally {
        clearTimeout(timeout)
        budget.signal.removeEventListener('abort', abortRequest)
      }
      if (!budget.signal.aborted) await pause(RETRY_DELAY_MS, budget.signal)
    }
    return false
  } finally {
    clearTimeout(deadline)
    options.signal?.removeEventListener('abort', stop)
  }
}

function pause(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise(resolve => {
    const finish = () => {
      clearTimeout(timer)
      signal.removeEventListener('abort', finish)
      resolve()
    }
    const timer = setTimeout(finish, ms)
    signal.addEventListener('abort', finish, { once: true })
    if (signal.aborted) finish()
  })
}
