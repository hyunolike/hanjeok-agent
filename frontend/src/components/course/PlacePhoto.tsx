'use client'
import { useState } from 'react'
import type { Lang } from '@/lib/i18n'

/** Tries the next official photo, then a labelled placeholder. Never substitutes another place. */
export function PlacePhoto({ urls, name, lang, eager = false }: { urls: string[]; name: string; lang: Lang; eager?: boolean }) {
  // A key on the inner component resets failure state when the place or URLs change.
  return <Photo key={`${name}:${urls.join('|')}`} urls={urls} name={name} lang={lang} eager={eager} />
}
function Photo({ urls, name, lang, eager }: { urls: string[]; name: string; lang: Lang; eager: boolean }) {
  const [index, setIndex] = useState(0)
  const [loaded, setLoaded] = useState(false)
  const ko = lang === 'ko'
  return (
    <div className="relative aspect-[16/10] overflow-hidden bg-surface-subtle">
      {index < urls.length ? <>
        {!loaded && <span className="absolute inset-0 flex items-center justify-center text-caption text-ink-muted" role="status">{ko ? '사진 불러오는 중' : 'Loading photo'}</span>}
        <img src={urls[index]} alt={name} width={800} height={500} loading={eager ? 'eager' : 'lazy'} decoding="async"
          className="relative h-full w-full object-cover"
          onLoad={() => setLoaded(true)} onError={() => { setIndex(value => value + 1); setLoaded(false) }} />
      </> : <div className="flex h-full min-h-36 flex-col items-center justify-center gap-2 px-4 text-center text-caption text-ink-muted" role="img" aria-label={`${name}: ${ko ? '사진을 준비 중이에요' : 'Photo unavailable'}`}>
        <span aria-hidden="true" className="text-title-1">▧</span>
        <span>{ko ? '사진을 준비 중이에요' : 'Photo unavailable'}</span>
      </div>}
    </div>
  )
}
