'use client'

import Link from 'next/link'
import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Character } from '@/components/guide/Character'
import { PathDrawing } from '@/components/guide/PathView'
import { layoutPath } from '@/components/guide/path-layout'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Chip } from '@/components/ui/Chip'
import { Field } from '@/components/ui/Field'
import { Notice } from '@/components/ui/Notice'
import { formatSeoul } from '@/lib/format'
import { fetchPlace, fetchPlaces, fetchStatus, isReplay, type Loaded } from '@/lib/guide'
import type { GuidePath, GuideStatus, PlaceDetail, PlaceHit } from '@/lib/guide-schema'
import { dict, type Lang } from '@/lib/i18n'

const defaultApi = { fetchPlaces, fetchPlace, fetchStatus }

type Search = { query: string; result: Loaded<{ places: PlaceHit[] }> }
type Selection = { placeId: number; result: Loaded<PlaceDetail> | null }

/**
 * 장소 하나와 그 이웃을 `path` 사건과 같은 모양으로 바꾼다. 그림이 답의 경로와 같은
 * 규칙(가운데 장소, 순위 순서, 오른쪽 지역)으로 그려지게 하기 위해서다.
 *
 * 받은 것만 옮긴다. 이웃끼리의 관계처럼 받지 않은 선은 긋지 않는다.
 */
export function neighbourhoodPath(detail: PlaceDetail): GuidePath {
  const placeNode = (id: number) => `hanjeok:place/${id}`
  const regions = [...new Set([detail.place.region, ...detail.related.map((r) => r.region)].filter(Boolean))]
  const start = placeNode(detail.place.place_id)
  return {
    nodes: [
      { id: start, kind: 'place', label: detail.place.name, region: detail.place.region },
      ...detail.related.map((r) => ({ id: placeNode(r.place_id), kind: 'place' as const, label: r.name, region: r.region })),
      ...detail.events.map((e) => ({ id: e.id, kind: 'event' as const, label: e.name, region: null })),
      ...regions.map((region) => ({ id: `region:${region}`, kind: 'region' as const, label: region, region: null })),
    ],
    edges: [
      ...detail.related.map((r) => ({ from: start, to: placeNode(r.place_id), kind: 'related' as const, rank: r.rank })),
      ...detail.events.map((e) => ({ from: e.id, to: start, kind: 'held_at' as const, rank: null })),
      ...[detail.place, ...detail.related]
        .filter((p) => p.region)
        .map((p) => ({ from: placeNode(p.place_id), to: `region:${p.region}`, kind: 'in_region' as const, rank: null })),
    ],
  }
}

export function GraphBrowser({
  lang,
  initialPlaceId,
  api = defaultApi,
}: {
  lang: Lang
  initialPlaceId?: number
  /** 테스트가 응답을 바꿔 끼울 수 있게 한다. */
  api?: typeof defaultApi
}) {
  const t = dict(lang).graph
  const [status, setStatus] = useState<Loaded<GuideStatus> | null>(null)
  const [draft, setDraft] = useState('')
  const [search, setSearch] = useState<Search | null>(null)
  const [searching, setSearching] = useState(false)
  const [selection, setSelection] = useState<Selection | null>(null)
  // 늦게 온 응답이 그 뒤에 고른 장소를 덮지 않게, 가장 최근 요청만 받아들인다.
  const latest = useRef(0)

  const open = useCallback(
    (placeId: number) => {
      const ticket = ++latest.current
      setSelection({ placeId, result: null })
      void api.fetchPlace(placeId).then((result) => {
        if (latest.current === ticket) setSelection({ placeId, result })
      })
    },
    [api],
  )

  useEffect(() => {
    let alive = true
    void api.fetchStatus().then((result) => alive && setStatus(result))
    return () => {
      alive = false
    }
  }, [api])

  useEffect(() => {
    if (initialPlaceId !== undefined) open(initialPlaceId)
  }, [initialPlaceId, open])

  const onSearch = async (event: FormEvent) => {
    event.preventDefault()
    const query = draft.trim()
    if (query === '' || searching) return
    setSearching(true)
    const result = await api.fetchPlaces(query)
    setSearch({ query, result })
    setSearching(false)
  }

  const detail = selection?.result?.ok ? selection.result.data : null

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-3">
        <h1 className="font-display text-display text-ink-title">{t.title}</h1>
        <p className="text-body text-ink-body">{t.lead}</p>
        {status?.ok && status.data.ready && status.data.as_of.export && (
          <p className="text-caption text-ink-muted">
            {t.statusLine(formatSeoul(status.data.as_of.export, lang), status.data.counts.places, status.data.counts.related)}
          </p>
        )}
      </header>

      {isReplay && (
        <Notice tone="info" title={dict(lang).guide.replayTitle}>
          {dict(lang).guide.replayBody}
        </Notice>
      )}
      {status?.ok && !status.data.ready && <Notice tone="warning">{t.notReady}</Notice>}

      <form onSubmit={onSearch} className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <Field
          id="place-query"
          label={t.searchLabel}
          className="flex-1"
          value={draft}
          maxLength={50}
          placeholder={isReplay ? t.searchPlaceholder : t.searchPlaceholderLive}
          onChange={(event) => setDraft(event.target.value)}
        />
        <Button type="submit" disabled={searching || draft.trim() === ''}>
          {t.search}
        </Button>
      </form>

      {search && !search.result.ok && <Notice tone="danger">{t.searchFailed}</Notice>}
      {search?.result.ok && search.result.data.places.length === 0 && (
        <Notice tone="warning">{t.noResults(search.query)}</Notice>
      )}
      {search?.result.ok && search.result.data.places.length > 0 && (
        <section className="flex flex-col gap-3" aria-label={t.resultsTitle(search.result.data.places.length)}>
          <h2 className="text-title-2 text-ink-title">{t.resultsTitle(search.result.data.places.length)}</h2>
          <ul className="flex flex-col gap-2">
            {search.result.data.places.map((place) => (
              <li key={place.place_id}>
                <Chip aria-pressed={selection?.placeId === place.place_id} onClick={() => open(place.place_id)}>
                  {place.name} · {place.region}
                </Chip>
              </li>
            ))}
          </ul>
        </section>
      )}

      {selection && selection.result === null && (
        <p role="status" className="text-body text-ink-muted">
          {t.loading}
        </p>
      )}

      {/* 못 찾았거나 못 불러왔을 때는 글만 낸다. 빈 그림을 그리면 "이웃이 없는 장소"로 읽힌다. */}
      {selection?.result && !selection.result.ok && (
        <Card>
          <Character
            state={selection.result.cause === 'not_found' ? 'no-data' : 'failed'}
            title={selection.result.cause === 'not_found' ? t.notFoundTitle : t.unavailableTitle}
          >
            <p className="text-body text-ink-body">
              {selection.result.cause === 'not_found' ? t.notFoundBody : t.unavailableBody}
            </p>
            {selection.result.cause === 'unavailable' && (
              <div>
                <Button variant="secondary" size="sm" onClick={() => open(selection.placeId)}>
                  {dict(lang).guide.retry}
                </Button>
              </div>
            )}
          </Character>
        </Card>
      )}

      {detail && (
        <Card className="flex flex-col gap-6" data-testid="place-panel">
          <div className="flex flex-col gap-2">
            <p className="text-caption text-brand-primary">{t.selected}</p>
            <h2 className="text-title-1 text-ink-title">{detail.place.name}</h2>
            <p className="text-caption text-ink-muted">
              {[detail.place.region, detail.place.category].filter(Boolean).join(' · ')}
            </p>
            {detail.place.overview && <p className="text-body text-ink-body">{detail.place.overview}</p>}
          </div>

          {/* 혼잡도 값은 여기 없다. 날짜에 묶인 값이라 질문으로만 가져온다. */}
          <div className="flex flex-col items-start gap-2">
            <Badge tone={detail.place.has_congestion_data ? 'info' : 'unknown'}>
              {detail.place.has_congestion_data ? t.covered : t.notCovered}
            </Badge>
            <p className="text-caption text-ink-muted">
              {detail.place.has_congestion_data ? t.coveredNote : t.notCoveredNote}
            </p>
            {detail.place.has_congestion_data && (
              <Link href={`/${lang}/ask`} className="text-body-strong text-brand-primary underline-offset-4 hover:underline">
                {t.askAbout}
              </Link>
            )}
          </div>

          <section className="hidden flex-col gap-2 sm:flex" aria-hidden="true">
            <h3 className="text-title-2 text-ink-title">{t.drawingTitle}</h3>
            <PathDrawing layout={layoutPath(neighbourhoodPath(detail))} />
          </section>

          <section className="flex flex-col gap-2">
            <h3 className="text-title-2 text-ink-title">{t.relatedTitle}</h3>
            {detail.related.length === 0 ? (
              <p className="text-body text-ink-muted">{t.relatedNone}</p>
            ) : (
              <>
                <p className="text-caption text-ink-muted">{t.relatedNote}</p>
                <ol className="flex flex-col gap-2" data-testid="related-places">
                  {detail.related.map((related) => (
                    <li key={related.place_id}>
                      <Chip onClick={() => open(related.place_id)}>
                        <span className="mr-2 text-accent-route">{dict(lang).guide.pathRank(related.rank)}</span>
                        {related.name} · {related.region}
                      </Chip>
                    </li>
                  ))}
                </ol>
              </>
            )}
          </section>

          <section className="flex flex-col gap-2">
            <h3 className="text-title-2 text-ink-title">{t.eventsTitle}</h3>
            {detail.events.length === 0 ? (
              <p className="text-body text-ink-muted">{t.eventsNone}</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {detail.events.map((event) => (
                  <li key={event.id} className="rounded-control border border-line-normal px-4 py-3">
                    <p className="text-body-strong text-ink-title">{event.name}</p>
                    <p className="text-caption text-ink-muted">{t.eventDates(event.start_date, event.end_date)}</p>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <p className="text-caption text-ink-muted">{dict(lang).guide.asOf(formatSeoul(detail.as_of, lang))}</p>
        </Card>
      )}
    </div>
  )
}
