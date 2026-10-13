import { notFound } from 'next/navigation'
import { Character, CHARACTER_STATES } from '@/components/guide/Character'
import { Badge, BADGE_TONES } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Chip } from '@/components/ui/Chip'
import { Field } from '@/components/ui/Field'
import { Notice } from '@/components/ui/Notice'
import { dict, isLang } from '@/lib/i18n'

/**
 * Tailwind 는 소스에 글자 그대로 적힌 클래스만 만든다. 그래서 이름을 조립하지 않고
 * 전부 적어 둔다 — `bg-${name}` 으로 쓰면 이 화면만 색이 비어 보인다.
 */
const SURFACES = [
  ['surface-canvas', 'bg-surface-canvas'],
  ['surface-panel', 'bg-surface-panel'],
  ['surface-subtle', 'bg-surface-subtle'],
  ['surface-inverse', 'bg-surface-inverse'],
  ['brand-primary', 'bg-brand-primary'],
  ['brand-pressed', 'bg-brand-pressed'],
  ['brand-soft', 'bg-brand-soft'],
  ['accent-route', 'bg-accent-route'],
  ['accent-quiet', 'bg-accent-quiet'],
  ['accent-sky', 'bg-accent-sky'],
  ['accent-gold', 'bg-accent-gold'],
  ['grade-relaxed-fill', 'bg-grade-relaxed-fill'],
  ['grade-normal-fill', 'bg-grade-normal-fill'],
  ['grade-crowded-fill', 'bg-grade-crowded-fill'],
  ['grade-very-crowded-fill', 'bg-grade-very-crowded-fill'],
  ['line-normal', 'bg-line-normal'],
  ['line-strong', 'bg-line-strong'],
] as const

const PAIRS = [
  ['ink-title / surface-panel', 'bg-surface-panel text-ink-title'],
  ['ink-body / surface-panel', 'bg-surface-panel text-ink-body'],
  ['ink-muted / surface-panel', 'bg-surface-panel text-ink-muted'],
  ['ink-title / surface-canvas', 'bg-surface-canvas text-ink-title'],
  ['ink-muted / surface-canvas', 'bg-surface-canvas text-ink-muted'],
  ['ink-body / surface-subtle', 'bg-surface-subtle text-ink-body'],
  ['ink-inverse / surface-inverse', 'bg-surface-inverse text-ink-inverse'],
  ['brand-on-primary / brand-primary', 'bg-brand-primary text-brand-on-primary'],
  ['brand-primary / brand-soft', 'bg-brand-soft text-brand-primary'],
  ['cite-record', 'bg-cite-record-soft text-cite-record-text'],
  ['cite-policy', 'bg-cite-policy-soft text-cite-policy-text'],
] as const

const TYPE = [
  ['display', 'font-display text-display'],
  ['title-1', 'text-title-1'],
  ['title-2', 'text-title-2'],
  ['body', 'text-body'],
  ['body-strong', 'text-body-strong'],
  ['caption', 'text-caption'],
  ['mono', 'font-mono text-caption'],
] as const

export default async function DesignPage({ params }: { params: Promise<{ lang: string }> }) {
  const { lang } = await params
  if (!isLang(lang)) notFound()
  const t = dict(lang).design
  const g = dict(lang).guide

  return (
    <div className="flex flex-col gap-10">
      <header className="flex flex-col gap-3">
        <h1 className="font-display text-display text-ink-title">{t.title}</h1>
        <p className="text-body text-ink-body">{t.lead}</p>
        <p className="text-caption text-ink-muted">{t.appearanceNote}</p>
      </header>

      <section className="flex flex-col gap-3">
        <h2 className="text-title-1 text-ink-title">{t.colours}</h2>
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {SURFACES.map(([name, className]) => (
            <li key={name} className="flex flex-col gap-1.5">
              <span className={`h-14 rounded-control border border-line-normal ${className}`} />
              <span className="font-mono text-caption text-ink-muted">{name}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-title-1 text-ink-title">{t.pairs}</h2>
        <ul className="grid gap-3 sm:grid-cols-2">
          {PAIRS.map(([name, className]) => (
            <li key={name} className={`rounded-control border border-line-normal px-4 py-3 ${className}`}>
              <p className="text-body-strong">{t.sample}</p>
              <p className="font-mono text-caption">{name}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-title-1 text-ink-title">{t.type}</h2>
        <Card className="flex flex-col gap-4">
          {TYPE.map(([name, className]) => (
            <div key={name} className="flex flex-col gap-1">
              <span className="font-mono text-caption text-ink-muted">{name}</span>
              <span className={`text-ink-title ${className}`}>{t.sample}</span>
            </div>
          ))}
        </Card>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-title-1 text-ink-title">{t.components}</h2>
        <Card className="flex flex-col gap-5">
          <div className="flex flex-wrap gap-3">
            <Button>{g.submit}</Button>
            <Button variant="secondary">{g.retry}</Button>
            <Button variant="ghost">{g.showPath}</Button>
            <Button disabled>{g.submit}</Button>
          </div>
          <div className="flex flex-wrap gap-2">
            <Chip>{g.examples[0]}</Chip>
            <Chip disabled>{g.examples[1]}</Chip>
          </div>
          <div className="flex flex-wrap gap-2">
            {BADGE_TONES.map((tone) => (
              <Badge key={tone} tone={tone}>
                {tone}
              </Badge>
            ))}
          </div>
          <Field id="design-field" label={g.fieldLabel} placeholder={g.fieldPlaceholder} />
          <Notice tone="info" title={g.replayTitle}>
            {g.replayBody}
          </Notice>
          <Notice tone="warning" title={g.limitTitle}>
            {g.limitDayBody}
          </Notice>
          <Notice tone="danger" title={g.failedTitle}>
            {g.cutBody}
          </Notice>
        </Card>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-title-1 text-ink-title">{t.character}</h2>
        <p className="text-caption text-ink-muted">{t.characterNote}</p>
        <ul className="grid gap-3 sm:grid-cols-2">
          {CHARACTER_STATES.map((state) => (
            <li key={state}>
              <Card>
                <Character state={state} title={t.states[state]}>
                  <span className="font-mono text-caption text-ink-muted">{state}</span>
                </Character>
              </Card>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
