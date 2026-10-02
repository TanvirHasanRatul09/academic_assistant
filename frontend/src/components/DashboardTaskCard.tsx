import type { DashboardItem } from '../api'
import type { TaskStatePatch } from '../offline'
import { Badge, Button, Card } from './ui'

function formatDate(value: string | null): string {
  if (!value) return 'No date provided'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

function safeSourceUrl(value: string): string | null {
  try { const url = new URL(value); return url.protocol === 'https:' ? url.toString() : null } catch { return null }
}

function targetLabel(item: DashboardItem): string {
  if (item.source_kind === 'manual' && item.targets.some((target) => target.course_wide)) return 'Personal task'
  if (item.targets.some((target) => target.course_wide)) return 'Entire course'
  const labels = item.targets.flatMap((target) => [target.section ? `Section ${target.section}` : null, target.lab_group ? `Lab group ${target.lab_group}` : null]).filter(Boolean)
  return [...new Set(labels)].join(' · ') || 'Target not specified'
}

function itemSignals(item: DashboardItem, now = Date.now()) {
  const date = item.due_at ?? item.starts_at
  const timestamp = date ? new Date(date).getTime() : null
  return {
    overdue: Boolean(timestamp && timestamp < now && !item.completed),
    urgent: Boolean(timestamp && timestamp >= now && timestamp - now <= 24 * 60 * 60 * 1000 && !item.completed) || item.priority === 3,
    changed: now - new Date(item.source_updated_at).getTime() <= 7 * 24 * 60 * 60 * 1000,
  }
}

export function DashboardTaskCard({ item, updating, onChange }: { item: DashboardItem; updating: boolean; onChange: (patch: TaskStatePatch) => void }) {
  const signals = itemSignals(item)
  const source = item.source_url ? safeSourceUrl(item.source_url) : null
  const personal = item.source_kind === 'manual'
  const classes = ['premium-task-card', personal && 'is-personal', item.completed && 'is-completed', !item.read && !personal && 'is-unread', signals.overdue && 'is-overdue', signals.urgent && 'is-urgent'].filter(Boolean).join(' ')
  return <Card as="article" id={`task-${item.task_id}`} className={classes} aria-busy={updating || undefined}>
    <div className="task-card-topline"><Badge tone={item.event_type === 'exam' ? 'danger' : item.event_type === 'notice' ? 'warning' : 'accent'}>{item.event_type}</Badge>{personal && <Badge tone="info">Personal</Badge>}<Badge>Priority {item.priority}</Badge>{signals.overdue && <Badge tone="danger">! Overdue</Badge>}{signals.urgent && !signals.overdue && <Badge tone="warning">! Due soon</Badge>}{item.completed && <Badge tone="success">✓ Completed</Badge>}{!item.read && !personal && <Badge tone="info">● Unread</Badge>}{signals.changed && !personal && <Badge>↻ Recently changed</Badge>}</div>
    <div className="premium-task-heading"><div><p className="course-name">{item.course_name}</p><h3>{item.title}</h3></div><time dateTime={item.due_at ?? item.starts_at ?? undefined}><small>{item.event_type === 'exam' ? 'Starts or due' : 'Due'}</small><strong>{formatDate(item.due_at ?? item.starts_at)}</strong></time></div>
    {item.body && <p className="task-summary">{item.body}</p>}
    <dl className="task-details"><div><dt>Target</dt><dd>{targetLabel(item)}</dd></div><div><dt>Completion</dt><dd>{item.completed ? 'Complete' : 'Open'}</dd></div><div><dt>{personal ? 'Last edited' : 'Source updated'}</dt><dd>{formatDate(item.source_updated_at)}</dd></div></dl>
    <footer className="premium-task-actions"><Button size="sm" loading={updating} onClick={() => onChange({ completed: !item.completed })}>{item.completed ? 'Mark incomplete' : 'Mark complete'}</Button>{!personal && <><Button size="sm" variant="secondary" disabled={updating} onClick={() => onChange({ read: !item.read })}>{item.read ? 'Mark unread' : 'Mark read'}</Button><Button size="sm" variant="ghost" disabled={updating} onClick={() => onChange({ acknowledged: !item.acknowledged })}>{item.acknowledged ? 'Unacknowledge' : 'Acknowledge'}</Button></>}{source ? <a className="source-link" href={source} target="_blank" rel="noopener noreferrer">Verify in Classroom <span aria-hidden="true">↗</span></a> : personal ? <span className="source-unavailable">Private to you</span> : <span className="source-unavailable">Source unavailable</span>}</footer>
  </Card>
}

