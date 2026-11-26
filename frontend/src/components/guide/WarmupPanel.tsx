'use client'

import { useId, useState } from 'react'
import { Character } from './Character'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { dict, type Lang } from '@/lib/i18n'
import type { ConnectionState } from '@/lib/use-guide-connection'

export function WarmupPanel({ lang, state, queued, onRetry, onCancel }: {
  lang: Lang
  state: ConnectionState
  queued: boolean
  onRetry: () => void
  onCancel: () => void
}) {
  const t = dict(lang).guide.warmup
  const [revealed, setRevealed] = useState(false)
  const [index, setIndex] = useState(0)
  const tipId = useId()
  const unavailable = state === 'unavailable'

  return <Card className="space-y-5">
    {state === 'ready' ? <p role="status" className="text-caption text-ink-muted">{t.ready}</p> : (
    <Character state={unavailable ? 'waiting' : 'looking'} title={unavailable ? t.unavailableTitle : t.title}>
      <p role="status" className="text-body text-ink-body">
        {unavailable ? t.unavailableBody : queued ? t.queuedBody : t.body}
      </p>
    </Character>
    )}
    <div className="rounded-card border border-line-normal bg-brand-soft p-4 space-y-3">
      <p className="text-caption text-ink-muted">{t.cardLabel}</p>
      <Button variant="secondary" size="sm" aria-expanded={revealed} aria-controls={tipId}
        onClick={() => setRevealed(value => !value)}>
        <span aria-hidden="true">♧</span>{t.flip}
      </Button>
      <div id={tipId} hidden={!revealed} className="space-y-2">
        <p className="text-body-strong text-ink-title">{t.tips[index].title}</p>
        <p className="text-body text-ink-body">{t.tips[index].body}</p>
        <Button variant="ghost" size="sm" onClick={() => setIndex(value => (value + 1) % t.tips.length)}>{t.next}</Button>
      </div>
    </div>
    {(unavailable || queued) && <div className="flex flex-wrap gap-2">
      {unavailable && <Button variant="secondary" size="sm" onClick={onRetry}>{t.retry}</Button>}
      {queued && <Button variant="ghost" size="sm" onClick={onCancel}>{t.cancel}</Button>}
    </div>}
  </Card>
}
