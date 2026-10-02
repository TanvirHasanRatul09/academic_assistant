import type { ReactNode } from 'react'
import { Button } from './primitives'

type StatePanelProps = {
  title: string
  description: string
  icon?: ReactNode
  actionLabel?: string
  onAction?: () => void
  tone?: 'neutral' | 'danger' | 'warning' | 'info'
  role?: 'status' | 'alert'
}

function StatePanel({ title, description, icon, actionLabel, onAction, tone = 'neutral', role = 'status' }: StatePanelProps) {
  return <section className={`ui-state ui-state-${tone}`} role={role}>
    <span className="ui-state-icon" aria-hidden="true">{icon ?? '◇'}</span>
    <div><h3>{title}</h3><p>{description}</p></div>
    {actionLabel && onAction && <Button variant="secondary" onClick={onAction}>{actionLabel}</Button>}
  </section>
}

export function EmptyState(props: Omit<StatePanelProps, 'tone' | 'role'>) { return <StatePanel {...props} /> }
export function ErrorState(props: Omit<StatePanelProps, 'tone' | 'role'>) { return <StatePanel {...props} tone="danger" role="alert" /> }
export function PermissionState(props: Omit<StatePanelProps, 'tone' | 'role'>) { return <StatePanel {...props} tone="warning" /> }
export function OfflineState(props: Omit<StatePanelProps, 'tone' | 'role'>) { return <StatePanel {...props} tone="warning" /> }
export function PartialDataState(props: Omit<StatePanelProps, 'tone' | 'role'>) { return <StatePanel {...props} tone="info" /> }
