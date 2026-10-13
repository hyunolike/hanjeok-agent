import type { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost'
type Size = 'sm' | 'md'

const VARIANT: Record<Variant, string> = {
  primary: 'bg-brand-primary text-brand-on-primary hover:bg-brand-pressed',
  secondary: 'border border-line-strong bg-surface-panel text-ink-title hover:bg-surface-subtle',
  ghost: 'text-brand-primary hover:bg-brand-soft',
}

const SIZE: Record<Size, string> = {
  sm: 'min-h-control-sm px-4',
  md: 'min-h-control-md px-5',
}

/**
 * `type` 의 기본값을 `button` 으로 둔다. HTML 기본값은 `submit` 이라, 폼 안에 놓인
 * "예시 질문" 같은 버튼이 눌릴 때마다 폼을 제출해 버린다.
 */
export function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  type = 'button',
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }) {
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center gap-2 rounded-control text-body-strong transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-primary disabled:cursor-not-allowed disabled:bg-surface-subtle disabled:text-ink-disabled ${VARIANT[variant]} ${SIZE[size]} ${className}`}
      {...rest}
    />
  )
}
