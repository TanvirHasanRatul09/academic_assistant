import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  ApiError,
  dismissNotification,
  getNotificationPreferences,
  getNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  saveNotificationPreferences,
  type AppNotification,
  type NotificationPreferences,
} from '../api'
import { Badge, Button, Checkbox, EmptyState, Field, PageHeader, Select, Skeleton, Switch } from '../components/ui'
import { safeExternalUrl } from '../security'

const GROUP_PREVIEW = 4

function actionError(caught: unknown, fallback: string): string {
  if (caught instanceof ApiError && caught.status === 0) return 'This action needs internet. Reconnect and retry.'
  return caught instanceof Error ? caught.message : fallback
}

export function NotificationsPage() {
  const [items, setItems] = useState<AppNotification[]>([])
  const [preferences, setPreferences] = useState<NotificationPreferences | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [online, setOnline] = useState(navigator.onLine)
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())
  const [permission, setPermission] = useState<NotificationPermission | 'unsupported'>(() => 'Notification' in window ? Notification.permission : 'unsupported')

  async function load() {
    setLoading(true); setError('')
    try {
      const [notifications, settings] = await Promise.all([getNotifications(), getNotificationPreferences()])
      setItems(notifications.items)
      setPreferences(settings)
    } catch (caught) {
      setError(actionError(caught, 'Could not load notifications.'))
    } finally { setLoading(false) }
  }

  useEffect(() => { void load() }, [])
  useEffect(() => {
    const handleOnline = () => { setOnline(true); void load() }
    const handleOffline = () => setOnline(false)
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    return () => { window.removeEventListener('online', handleOnline); window.removeEventListener('offline', handleOffline) }
  }, [])

  async function runItem(notification: AppNotification, action: 'read' | 'dismiss') {
    if (!online || busy) return
    setBusy(notification.id); setError('')
    try {
      if (action === 'read') {
        if (!notification.read_at) await markNotificationRead(notification.id)
        setItems((current) => current.map((item) => item.id === notification.id ? { ...item, read_at: item.read_at ?? new Date().toISOString() } : item))
      } else {
        await dismissNotification(notification.id)
        setItems((current) => current.filter((item) => item.id !== notification.id))
      }
    } catch (caught) {
      setError(actionError(caught, 'Could not update this notification.'))
    } finally { setBusy('') }
  }

  async function readAll() {
    if (!online || busy) return
    setBusy('all'); setError('')
    try {
      await markAllNotificationsRead()
      const now = new Date().toISOString()
      setItems((current) => current.map((item) => ({ ...item, read_at: item.read_at ?? now })))
    } catch (caught) { setError(actionError(caught, 'Could not mark notifications as read.')) }
    finally { setBusy('') }
  }

  async function savePreferences() {
    if (!preferences || !online || busy) return
    setBusy('preferences'); setError(''); setMessage('')
    try {
      const saved = await saveNotificationPreferences({
        assignments: preferences.assignments,
        exams: preferences.exams,
        notices: preferences.notices,
        minimum_priority: preferences.minimum_priority,
        course_preferences: Object.fromEntries(preferences.courses.map((course) => [course.id, course.enabled])),
      })
      setPreferences(saved)
      setMessage('Notification preferences saved. Future syncs will use these rules.')
    } catch (caught) { setError(actionError(caught, 'Could not save preferences.')) }
    finally { setBusy('') }
  }

  async function requestBrowserPermission() {
    if (!('Notification' in window) || permission !== 'default') return
    const result = await Notification.requestPermission()
    setPermission(result)
  }

  const unread = items.filter((item) => !item.read_at).length
  const grouped = useMemo(() => {
    const groups = new Map<string, AppNotification[]>()
    for (const item of items) {
      const key = item.course_name || 'Other academic updates'
      groups.set(key, [...(groups.get(key) ?? []), item])
    }
    return [...groups.entries()].sort((a, b) => Number(b[1].some((item) => !item.read_at)) - Number(a[1].some((item) => !item.read_at)))
  }, [items])

  return <section className="notifications-page" aria-labelledby="notifications-title">
    <PageHeader eyebrow="Stay informed" title="Notifications" description="Relevant academic changes created from your Classroom sync—not a second noisy inbox." actions={unread > 0 ? <Button variant="secondary" disabled={!online || Boolean(busy)} title={online ? '' : 'Reconnect to update notifications.'} onClick={() => void readAll()}>Mark all read</Button> : undefined} />

    {!online && <div className="offline-action-note" role="status"><strong>Offline notification view</strong><p>Previously loaded alerts remain visible, but read, dismiss, and preference changes require internet.</p></div>}
    {error && <div className="error-panel" role="alert"><p>{error}</p><Button variant="secondary" disabled={!online} onClick={() => void load()}>Retry</Button></div>}
    {message && <p className="success-message" role="status">{message}</p>}

    <section aria-labelledby="notification-list-title">
      <div className="notification-summary"><div><h2 id="notification-list-title">Inbox</h2><p>{unread} unread · {items.length} active</p></div><Badge tone={unread ? 'accent' : 'success'}>{unread ? unread + ' need attention' : 'Caught up'}</Badge></div>
      {loading ? <div className="notification-list" aria-label="Loading notifications">{[0, 1, 2].map((item) => <Skeleton key={item} lines={3} />)}</div>
        : grouped.length === 0 ? <EmptyState title="You are caught up" description="New relevant assignments, exams, and actionable notices appear after a Classroom sync." />
        : <div className="notification-groups">{grouped.map(([course, notifications]) => {
          const expanded = expandedGroups.has(course)
          const visible = expanded ? notifications : notifications.slice(0, GROUP_PREVIEW)
          const groupUnread = notifications.filter((item) => !item.read_at).length
          return <section className="notification-group" key={course} aria-labelledby={'group-' + course.replace(/W/g, '-')}>
            <header><div><h3 id={'group-' + course.replace(/W/g, '-')}>{course}</h3><span>{groupUnread} unread · {notifications.length} total</span></div></header>
            <div className="notification-list">{visible.map((notification) => <article className={'notification-card' + (notification.read_at ? '' : ' unread')} key={notification.id}>
              <div><div className="task-card-topline"><Badge tone={notification.event_type === 'exam' ? 'danger' : notification.priority >= 3 ? 'warning' : 'neutral'}>{notification.event_type}</Badge><Badge>Priority {notification.priority}</Badge>{!notification.read_at && <Badge tone="accent">New</Badge>}</div><h4>{notification.title}</h4><p>{notification.due_at ? 'Due ' + new Date(notification.due_at).toLocaleString() : 'Action may be required.'}<small>Received {new Date(notification.created_at).toLocaleString()}</small></p></div>
              <div className="notification-actions">{!notification.read_at && <Button size="sm" variant="secondary" disabled={!online || busy === notification.id} onClick={() => void runItem(notification, 'read')}>Mark read</Button>}<Link className="ui-button ui-button-primary ui-button-sm" to={'/dashboard?view=all&task=' + notification.task_id} onClick={() => { if (online) void runItem(notification, 'read') }}>View task</Link>{safeExternalUrl(notification.source_url) && <a className="ui-button ui-button-ghost ui-button-sm" href={safeExternalUrl(notification.source_url) ?? undefined} target="_blank" rel="noopener noreferrer">Verify in Classroom ↗</a>}<Button size="sm" variant="ghost" disabled={!online || busy === notification.id} onClick={() => void runItem(notification, 'dismiss')}>Dismiss</Button></div>
            </article>)}</div>
            {notifications.length > GROUP_PREVIEW && <Button variant="ghost" size="sm" onClick={() => setExpandedGroups((current) => { const next = new Set(current); if (expanded) next.delete(course); else next.add(course); return next })}>{expanded ? 'Show fewer' : 'Show ' + (notifications.length - GROUP_PREVIEW) + ' more'}</Button>}
          </section>
        })}</div>}
    </section>

    <section className="notification-settings-grid">
      {preferences && <section className="form-card notification-preferences" aria-labelledby="notification-preferences-title">
        <p className="eyebrow">Alert rules</p><h2 id="notification-preferences-title">In-app preferences</h2><p>Only relevant items at or above your selected priority create alerts.</p>
        <fieldset><legend>Event types</legend>{(['assignments', 'exams', 'notices'] as const).map((key) => <Checkbox key={key} label={key.charAt(0).toUpperCase() + key.slice(1)} checked={preferences[key]} onChange={(event) => setPreferences({ ...preferences, [key]: event.target.checked })} />)}</fieldset>
        <Field label="Minimum priority">{({ id }) => <Select id={id} value={preferences.minimum_priority} onChange={(event) => setPreferences({ ...preferences, minimum_priority: Number(event.target.value) })}><option value="1">Low and above</option><option value="2">Medium and above</option><option value="3">High only</option></Select>}</Field>
        <fieldset><legend>Courses</legend><div className="course-preferences">{preferences.courses.map((course) => <Switch key={course.id} label={course.name} checked={course.enabled} onChange={(enabled) => setPreferences({ ...preferences, courses: preferences.courses.map((item) => item.id === course.id ? { ...item, enabled } : item) })} />)}</div></fieldset>
        <Button disabled={!online || busy === 'preferences'} loading={busy === 'preferences'} onClick={() => void savePreferences()}>Save preferences</Button>
      </section>}

      <section className="form-card browser-notification-card" aria-labelledby="browser-alert-title">
        <p className="eyebrow">Optional device permission</p><h2 id="browser-alert-title">Browser notifications</h2>
        <p>Browser permission can let this device display supported reminders outside the notification page. Notifications may be visible on your lock screen, so enable this only on a private device.</p>
        <p className="muted-copy">Your in-app inbox works without this permission. Permission alone does not promise background delivery when the application is closed.</p>
        {permission === 'unsupported' ? <p>This browser does not support notification permission.</p>
          : permission === 'granted' ? <p className="permission-state success">Allowed on this device. You can revoke access in browser site settings.</p>
          : permission === 'denied' ? <p className="permission-state warning">Blocked by the browser. Change site permissions in your browser if you want to reconsider.</p>
          : <Button variant="secondary" onClick={() => void requestBrowserPermission()}>Allow browser permission</Button>}
      </section>
    </section>
  </section>
}
