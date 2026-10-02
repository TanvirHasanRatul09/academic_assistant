import type { ReactNode } from 'react'
import { Card } from './primitives'

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description?: string; actions?: ReactNode }) {
  return <header className="ui-page-header"><div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h1>{title}</h1>{description && <p>{description}</p>}</div>{actions && <div className="ui-header-actions">{actions}</div>}</header>
}

export function SectionHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return <header className="ui-section-header"><div><h2>{title}</h2>{description && <p>{description}</p>}</div>{actions && <div className="ui-header-actions">{actions}</div>}</header>
}

export function FilterBar({ children, actions, activeCount }: { children: ReactNode; actions?: ReactNode; activeCount?: number }) {
  return <section className="ui-filter-bar" aria-label="Filters"><div className="ui-filter-fields">{children}</div>{activeCount !== undefined && <span className="ui-filter-count" aria-live="polite">{activeCount} active</span>}{actions && <div className="ui-filter-actions">{actions}</div>}</section>
}

export function StatCard({ label, value, detail, tone = 'neutral' }: { label: string; value: ReactNode; detail?: string; tone?: 'neutral' | 'accent' | 'success' | 'warning' }) {
  return <Card className={`ui-stat-card ui-stat-${tone}`}><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</Card>
}

export function ResponsiveDataList<T>({ items, keyOf, renderItem, empty }: { items: T[]; keyOf: (item: T) => string; renderItem: (item: T) => ReactNode; empty?: ReactNode }) {
  if (!items.length) return <>{empty ?? null}</>
  return <div className="ui-data-list" role="list">{items.map((item) => <article className="ui-data-list-item" role="listitem" key={keyOf(item)}>{renderItem(item)}</article>)}</div>
}
