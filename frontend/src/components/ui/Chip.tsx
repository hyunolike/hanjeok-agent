import type { ButtonHTMLAttributes } from 'react'

/** 누를 수 있는 알약. 예시 질문과 후보 장소가 이것이다. 상태를 보여 주기만 하는 것은 `Badge` 다. */
export function Chip({ className = '', type = 'button', ...rest }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type={type}
      className={`inline-flex min-h-control-sm items-center rounded-chip border border-line-strong bg-surface-panel px-4 text-left text-body text-ink-body transition-colors hover:border-brand-primary hover:text-brand-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-primary disabled:cursor-not-allowed disabled:text-ink-disabled ${className}`}
      {...rest}
    />
  )
}
