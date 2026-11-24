import { afterEach, describe, expect, it, vi } from 'vitest'
import { waitForGuideReady } from './guide-ready'

const baseUrl = 'https://guide.test'
const ready = () => Response.json({ ready: true })
const tick = (ms: number) => vi.advanceTimersByTimeAsync(ms)
afterEach(() => vi.useRealTimers())

describe('waitForGuideReady', () => {
  it('녹화 모드는 네트워크를 사용하지 않는다', async () => {
    const fetchImpl = vi.fn<typeof fetch>()
    expect(await waitForGuideReady({ baseUrl: '', fetchImpl })).toBe(true)
    expect(fetchImpl).not.toHaveBeenCalled()
  })

  it('ready:true만 준비 완료로 인정하고 순차 확인으로 복구한다', async () => {
    vi.useFakeTimers()
    const fetchImpl = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response('starting', { status: 503 }))
      .mockResolvedValueOnce(Response.json({ ready: false }))
      .mockResolvedValueOnce(new Response('<html>starting</html>'))
      .mockResolvedValueOnce(ready())
    const result = waitForGuideReady({ baseUrl, fetchImpl })
    await tick(0)
    expect(fetchImpl).toHaveBeenCalledTimes(1)
    await tick(15000)
    expect(await result).toBe(true)
    expect(fetchImpl).toHaveBeenCalledTimes(4)
    expect(fetchImpl).toHaveBeenCalledWith(`${baseUrl}/guide/ready`, expect.objectContaining({
      method: 'GET', cache: 'no-store', signal: expect.any(AbortSignal),
    }))
  })

  it('계속 실패하면 별도 90초 예산에서 종료하고 타이머를 정리한다', async () => {
    vi.useFakeTimers()
    const fetchImpl = vi.fn<typeof fetch>().mockRejectedValue(new TypeError('offline'))
    const result = waitForGuideReady({ baseUrl, fetchImpl })
    await tick(90000)
    expect(await result).toBe(false)
    const attempts = fetchImpl.mock.calls.length
    await tick(60000)
    expect(fetchImpl).toHaveBeenCalledTimes(attempts)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('응답 없는 GET은 12초에 취소한 뒤 다음 확인을 한다', async () => {
    vi.useFakeTimers()
    let signal: AbortSignal | undefined
    const fetchImpl = vi.fn<typeof fetch>().mockImplementationOnce((_url, init) => {
      signal = init?.signal as AbortSignal
      return new Promise((_resolve, reject) => signal!.addEventListener('abort', () => reject(new Error('timeout')), { once: true }))
    }).mockResolvedValue(ready())
    const result = waitForGuideReady({ baseUrl, fetchImpl })
    await tick(11999)
    expect(signal?.aborted).toBe(false)
    expect(fetchImpl).toHaveBeenCalledTimes(1)
    await tick(5001)
    expect(signal?.aborted).toBe(true)
    expect(await result).toBe(true)
    expect(fetchImpl).toHaveBeenCalledTimes(2)
  })

  it('취소는 진행 중 GET과 다음 재시도를 끝낸다', async () => {
    vi.useFakeTimers()
    const controller = new AbortController()
    let requestSignal: AbortSignal | undefined
    const fetchImpl = vi.fn<typeof fetch>((_url, init) => {
      requestSignal = init?.signal as AbortSignal
      return new Promise((_resolve, reject) => requestSignal!.addEventListener('abort', () => reject(new Error('abort')), { once: true }))
    })
    const result = waitForGuideReady({ baseUrl, fetchImpl, signal: controller.signal })
    controller.abort()
    expect(await result).toBe(false)
    expect(requestSignal?.aborted).toBe(true)
    await tick(90000)
    expect(fetchImpl).toHaveBeenCalledTimes(1)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('확인 사이 대기도 즉시 취소된다', async () => {
    vi.useFakeTimers()
    const controller = new AbortController()
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(new Response('', { status: 503 }))
    const result = waitForGuideReady({ baseUrl, fetchImpl, signal: controller.signal })
    await tick(0)
    controller.abort()
    expect(await result).toBe(false)
    expect(vi.getTimerCount()).toBe(0)
  })
})
