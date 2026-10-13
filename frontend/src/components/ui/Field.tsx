import type { InputHTMLAttributes } from 'react'

/**
 * 한 줄 입력. 라벨은 항상 있다 — 눈에 안 보이게 할 수는 있어도(`hideLabel`) 없앨
 * 수는 없다. placeholder 만 있는 입력은 글자를 치는 순간 무엇을 묻는 칸이었는지
 * 사라진다.
 */
export function Field({
  label,
  hideLabel = false,
  id,
  className = '',
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & { label: string; hideLabel?: boolean; id: string }) {
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      <label htmlFor={id} className={hideLabel ? 'sr-only' : 'text-caption text-ink-muted'}>
        {label}
      </label>
      <input
        id={id}
        className="min-h-control-md w-full rounded-control border border-line-strong bg-surface-panel px-4 text-body text-ink-title placeholder:text-ink-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-primary disabled:bg-surface-subtle disabled:text-ink-disabled"
        {...rest}
      />
    </div>
  )
}
