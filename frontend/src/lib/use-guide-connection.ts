'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { waitForGuideReady } from './guide-ready'

export type ConnectionState = 'connecting' | 'ready' | 'unavailable'

/** 한 화면 안의 진입/제출/재시도가 같은 활성 확인을 기다린다. */
export function useGuideConnection(prepare: typeof waitForGuideReady, enabled: boolean) {
  const [state, setState] = useState<ConnectionState>(enabled ? 'connecting' : 'ready')
  const active = useRef<{ controller: AbortController; promise: Promise<boolean> } | null>(null)

  const cancel = useCallback(() => {
    const job = active.current
    active.current = null
    job?.controller.abort()
  }, [])

  const ensureReady = useCallback((): Promise<boolean> => {
    if (!enabled) return Promise.resolve(true)
    if (active.current) return active.current.promise
    setState('connecting')
    const job = { controller: new AbortController(), promise: Promise.resolve(false) }
    active.current = job
    const check = async () => prepare({ signal: job.controller.signal })
    job.promise = check().catch(() => false).then(ready => {
      if (active.current !== job || job.controller.signal.aborted) return false
      active.current = null
      setState(ready ? 'ready' : 'unavailable')
      return ready
    })
    return job.promise
  }, [enabled, prepare])

  useEffect(() => {
    void ensureReady()
    return cancel
  }, [ensureReady, cancel])

  const cancelWait = useCallback(() => {
    cancel()
    setState('unavailable')
  }, [cancel])

  return { state, ensureReady, cancel: cancelWait, enabled }
}
