'use client'
import Link, { useLinkStatus } from 'next/link'
import { useEffect, useRef, type ComponentProps, type MutableRefObject, type ReactNode } from 'react'

/** Next's actual navigation state; fast/prefetched links do not get an artificial delay. */
export function PendingLink({ children, pendingLabel, className = '', ...props }: Omit<ComponentProps<typeof Link>, 'children' | 'onClick' | 'onNavigate'> & { children: ReactNode; pendingLabel: string }) {
  const busy = useRef(false)
  return <Link {...props} className={`relative ${className}`} onClick={event => { if (busy.current) event.preventDefault() }} onNavigate={() => { busy.current = true }}>
    {children}
    <PendingHint busy={busy} label={pendingLabel} />
  </Link>
}
function PendingHint({ busy, label }: { busy: MutableRefObject<boolean>; label: string }) {
  const { pending } = useLinkStatus()
  useEffect(() => { busy.current = pending; return () => { busy.current = false } }, [pending, busy])
  return pending ? <span aria-busy="true">
    <span className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-brand-primary motion-safe:animate-pulse" aria-hidden="true" />
    <span role="status" className="sr-only">{label}</span>
  </span> : null
}
