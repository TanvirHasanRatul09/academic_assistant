import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  ApiError,
  getCurrentUser,
  getDashboard,
  getSyncStatus,
  synchronize,
  updateTaskState,
  type DashboardData,
  type DashboardEventType,
  type DashboardItem,
  type DashboardView,
  type SyncRun,
} from '../api'
import { DashboardTaskCard } from '../components/DashboardTaskCard'
import { PersonalTasksPanel } from '../components/PersonalTasksPanel'
import { Badge, Button, Dialog, EmptyState, Field, FilterBar, PageHeader, Select, Skeleton, StatCard } from '../components/ui'
import {
  applyTaskStateToSnapshot,
  cacheDashboardSnapshot,
  getCachedSessionUser,
  getOfflineStorageStatus,
  getOfflineConflicts,
  getQueuedTaskUpdates,
  queryOfflineDashboard,
  queueTaskUpdate,
  removeOfflineConflict,
  removeQueuedTaskUpdate,
  saveOfflineConflict,
  type OfflineConflict,
  type TaskStatePatch,
} from '../offline'

const views: Array<{ value: DashboardView; label: string }> = [
  { value: 'today', label: 'Today' },
  { value: 'tomorrow', label: 'Tomorrow' },
  { value: 'week', label: 'This week' },
  { value: 'upcoming', label: 'Upcoming' },
  { value: 'deadlines', label: 'Upcoming deadlines' },
  { value: 'exams', label: 'Exams' },
  { value: 'notices', label: 'Notices' },
  { value: 'recent', label: 'Recently changed' },
  { value: 'all', label: 'All' },
]

type DateWindow = '' | 'overdue' | '7days' | '30days' | 'undated'
type DisplayMode = 'list' | 'timeline'
const PREFERENCE_KEY = 'academic-assistant-dashboard-preferences'

function savedPreference(name: string): string {
  try { return (JSON.parse(sessionStorage.getItem(PREFERENCE_KEY) ?? '{}') as Record<string, string>)[name] ?? '' } catch { return '' }
}

function initialParameter(name: string, fallback = ''): string {
  return new URLSearchParams(window.location.search).get(name) ?? savedPreference(name) ?? fallback
}

function initialView(): DashboardView {
  const value = initialParameter('view', 'today')
  return views.some((candidate) => candidate.value === value) ? value as DashboardView : 'today'
}

function initialSource(): 'all' | 'classroom' | 'manual' {
  const value = initialParameter('source', 'all')
  return value === 'classroom' || value === 'manual' ? value : 'all'
}

function dateGroup(item: DashboardItem): string {
  const value = item.due_at ?? item.starts_at
  if (!value) return 'No scheduled date'
  const date = new Date(value)
  const today = new Date(); today.setHours(0, 0, 0, 0)
  const tomorrow = new Date(today); tomorrow.setDate(today.getDate() + 1)
  const itemDay = new Date(date); itemDay.setHours(0, 0, 0, 0)
  if (itemDay.getTime() === today.getTime()) return 'Today'
  if (itemDay.getTime() === tomorrow.getTime()) return 'Tomorrow'
  return new Intl.DateTimeFormat(undefined, { weekday: 'long', month: 'long', day: 'numeric' }).format(date)
}
export function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [latest, setLatest] = useState<SyncRun | null>(null)
  const [userId, setUserId] = useState('')
  const [view, setView] = useState<DashboardView>(initialView)
  const [courseId, setCourseId] = useState(initialParameter('course'))
  const [eventType, setEventType] = useState<DashboardEventType | ''>(initialParameter('type') as DashboardEventType | '')
  const [completion, setCompletion] = useState(initialParameter('state'))
  const [priority, setPriority] = useState(initialParameter('priority'))
  const [source, setSource] = useState<'all'|'classroom'|'manual'>(initialSource)
  const [dateWindow, setDateWindow] = useState<DateWindow>(initialParameter('date') as DateWindow)
  const [displayMode, setDisplayMode] = useState<DisplayMode>(initialParameter('layout', 'list') === 'timeline' ? 'timeline' : 'list')
  const [online, setOnline] = useState(navigator.onLine)
  const [usingCache, setUsingCache] = useState(false)
  const [cachedAt, setCachedAt] = useState<string | null>(null)
  const [lastSuccessfulSyncAt, setLastSuccessfulSyncAt] = useState<string | null>(null)
  const [pendingChanges, setPendingChanges] = useState(0)
  const [conflicts, setConflicts] = useState<OfflineConflict[]>([])
  const [conflictOpen, setConflictOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [syncBusy, setSyncBusy] = useState(false)
  const [flushBusy, setFlushBusy] = useState(false)
  const [updatingTask, setUpdatingTask] = useState('')
  const [error, setError] = useState('')

  const filters = useMemo(() => ({
    view,
    courseId: courseId || undefined,
    eventType: eventType || undefined,
    completed: completion === '' ? undefined : completion === 'complete',
    priority: priority === '' ? undefined : Number(priority),
    source,
  }), [view, courseId, eventType, completion, priority, source])

  const refreshOfflineStatus = useCallback(async () => {
    const status = await getOfflineStorageStatus().catch(() => null)
    if (!status) return
    setCachedAt(status.cachedAt)
    setLastSuccessfulSyncAt(status.lastSuccessfulSyncAt)
    setPendingChanges(status.queuedChanges)
    if (status.userId) setConflicts(await getOfflineConflicts(status.userId))
    else setConflicts([])
  }, [])

  const loadCachedDashboard = useCallback(async (activeUserId: string) => {
    const cached = await queryOfflineDashboard(activeUserId, filters)
    if (!cached) {
      setData(null)
      setError('No offline dashboard has been saved on this device yet. Connect once and synchronize Classroom first.')
      return false
    }
    setData(cached.data)
    setUsingCache(true)
    setCachedAt(cached.cachedAt)
    setLastSuccessfulSyncAt(cached.lastSuccessfulSyncAt)
    return true
  }, [filters])

  const loadDashboard = useCallback(async () => {
    const activeUserId = userId || (await getCachedSessionUser())?.id || ''
    if (!activeUserId) {
      setLoading(false)
      return
    }
    if (!userId) setUserId(activeUserId)
    setLoading(true)
    setError('')
    try {
      if (!navigator.onLine) {
        await loadCachedDashboard(activeUserId)
      } else {
        setData(await getDashboard(filters))
        setUsingCache(false)
      }
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 0) {
        setOnline(false)
        await loadCachedDashboard(activeUserId)
      } else {
        setError(caught instanceof Error ? caught.message : 'Could not load your academic dashboard.')
      }
    } finally {
      setLoading(false)
    }
  }, [filters, loadCachedDashboard, userId])

  const refreshOfflineSnapshot = useCallback(async (
    activeUserId: string,
    successfulSyncAt: string | null,
  ) => {
    const snapshot = await getDashboard({ view: 'all', limit: 1000 })
    await cacheDashboardSnapshot(activeUserId, snapshot, successfulSyncAt)
    await refreshOfflineStatus()
  }, [refreshOfflineStatus])

  const flushQueuedChanges = useCallback(async () => {
    if (!navigator.onLine || flushBusy) return
    const cachedUser = await getCachedSessionUser()
    if (!cachedUser) return
    setFlushBusy(true)
    try {
      const authenticatedUser = await getCurrentUser()
      if (authenticatedUser.id !== cachedUser.id) {
        setError('Account changed. Local queued changes were not uploaded.')
        return
      }
      const queued = await getQueuedTaskUpdates(authenticatedUser.id)
      for (const change of queued) {
        try {
          let saved
          try {
            saved = await updateTaskState(change.taskId, change.patch, change.expectedUpdatedAt)
          } catch (caught) {
            if (!(caught instanceof ApiError) || caught.status !== 409) throw caught
            const newest = await getDashboard({ view: 'all', limit: 1000 })
            const current = newest.items.find((item) => item.task_id === change.taskId)
            if (!current) {
              await removeQueuedTaskUpdate(change.key)
              continue
            }
            await saveOfflineConflict(authenticatedUser.id, change, current)
            setConflictOpen(true)
            continue
          }
          await applyTaskStateToSnapshot(
            authenticatedUser.id,
            change.taskId,
            change.patch,
            saved.updated_at,
          )
          await removeQueuedTaskUpdate(change.key)
        } catch (caught) {
          if (caught instanceof ApiError && [401, 403].includes(caught.status)) {
            setError('Your session expired. Queued changes remain on this device and were not uploaded.')
            break
          }
          throw caught
        }
      }
      await refreshOfflineStatus()
      await loadDashboard()
    } catch (caught) {
      if (!(caught instanceof ApiError && caught.status === 0)) {
        setError(caught instanceof Error ? caught.message : 'Could not upload queued changes.')
      }
    } finally {
      setFlushBusy(false)
    }
  }, [flushBusy, loadDashboard, refreshOfflineStatus])

  useEffect(() => {
    let active = true
    async function initialize() {
      const cachedUser = await getCachedSessionUser().catch(() => null)
      if (!active) return
      if (cachedUser) setUserId(cachedUser.id)
      await refreshOfflineStatus()
      if (!navigator.onLine) return
      try {
        const { latest: value } = await getSyncStatus()
        if (!active) return
        setLatest(value)
        const successfulAt = value?.status === 'succeeded' || value?.status === 'partial'
          ? value.finished_at
          : null
        if (cachedUser && successfulAt) await refreshOfflineSnapshot(cachedUser.id, successfulAt)
      } catch {
        // The filtered dashboard load provides the visible error/fallback state.
      }
    }
    void initialize()
    return () => { active = false }
  }, [refreshOfflineSnapshot, refreshOfflineStatus])

  useEffect(() => {
    const handleShellSync = (event: Event) => {
      const status = (event as CustomEvent<{ status?: SyncRun['status'] }>).detail?.status
      setSyncBusy(status === 'running')
      if (status && status !== 'running') {
        void getSyncStatus().then(({ latest: value }) => { setLatest(value); void loadDashboard() }).catch(() => undefined)
      }
    }
    window.addEventListener('academic-sync-state', handleShellSync)
    return () => window.removeEventListener('academic-sync-state', handleShellSync)
  }, [loadDashboard])

  useEffect(() => {
    const handleOnline = () => {
      setOnline(true)
      void flushQueuedChanges()
    }
    const handleOffline = () => setOnline(false)
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [flushQueuedChanges])

  useEffect(() => {
    if (userId && online && pendingChanges > 0) {
      void flushQueuedChanges()
    }
  }, [flushQueuedChanges, online, pendingChanges, userId])

  useEffect(() => {
    const taskId = new URLSearchParams(window.location.search).get('task')
    if (!taskId || !data) return
    window.requestAnimationFrame(() => {
      document.getElementById('task-' + taskId)?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      })
    })
  }, [data])

  useEffect(() => {
    const parameters = new URLSearchParams()
    const selectedTask = new URLSearchParams(window.location.search).get('task')
    if (selectedTask) parameters.set('task', selectedTask)
    if (view !== 'today') parameters.set('view', view)
    if (courseId) parameters.set('course', courseId)
    if (eventType) parameters.set('type', eventType)
    if (completion) parameters.set('state', completion)
    if (priority) parameters.set('priority', priority)
    if (source !== 'all') parameters.set('source', source)
    if (dateWindow) parameters.set('date', dateWindow)
    if (displayMode !== 'list') parameters.set('layout', displayMode)
    const query = parameters.toString()
    window.history.replaceState(null, '', `${window.location.pathname}${query ? `?${query}` : ''}`)
    sessionStorage.setItem(PREFERENCE_KEY, JSON.stringify({ view, course: courseId, type: eventType, state: completion, priority, source, date: dateWindow, layout: displayMode }))
    void loadDashboard()
  }, [view, courseId, eventType, completion, priority, source, dateWindow, displayMode, loadDashboard])

  async function syncNow() {
    if (!navigator.onLine) {
      setError('Classroom synchronization requires an internet connection.')
      return
    }
    setSyncBusy(true)
    window.dispatchEvent(new CustomEvent('academic-sync-state', { detail: { status: 'running' } }))
    setError('')
    try {
      const started = await synchronize()
      setLatest(started)
      window.dispatchEvent(new CustomEvent('academic-sync-state', { detail: { status: started.status } }))
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409 && caught.message === 'sync_already_running') {
        const { latest: running } = await getSyncStatus().catch(() => ({ latest: null }))
        setLatest(running)
        window.dispatchEvent(new CustomEvent('academic-sync-state', { detail: { status: running?.status ?? 'running' } }))
        return
      }
      window.dispatchEvent(new CustomEvent('academic-sync-state', { detail: { status: 'failed' } }))
      setError(caught instanceof Error ? caught.message : 'Synchronization failed.')
    } finally {
      setSyncBusy(false)
    }
  }

  async function changeTask(item: DashboardItem, patch: TaskStatePatch) {
    if (!data || !userId) return
    const previous = data
    setUpdatingTask(item.task_id)
    setError('')
    setData({ ...data, items: data.items.map((current) => current.task_id === item.task_id ? { ...current, ...patch } : current) })
    try {
      if (!navigator.onLine) {
        await queueTaskUpdate(userId, item, patch)
        setUsingCache(true)
      } else {
        try {
          const saved = await updateTaskState(item.task_id, patch, item.task_updated_at)
          await applyTaskStateToSnapshot(userId, item.task_id, patch, saved.updated_at)
          setData((current) => current ? {
            ...current,
            items: current.items.map((entry) =>
              entry.task_id === item.task_id
                ? { ...entry, ...saved, task_updated_at: saved.updated_at }
                : entry
            ),
          } : current)
        } catch (caught) {
          if (!(caught instanceof ApiError) || caught.status !== 0) throw caught
          await queueTaskUpdate(userId, item, patch)
          setOnline(false)
          setUsingCache(true)
        }
      }
      await refreshOfflineStatus()
    } catch (caught) {
      setData(previous)
      setError(caught instanceof Error ? caught.message : 'Could not update this task.')
    } finally {
      setUpdatingTask('')
    }
  }

  async function resolveConflict(conflict: OfflineConflict, choice: 'server' | 'device') {
    setError('')
    try {
      if (choice === 'server') {
        await applyTaskStateToSnapshot(conflict.userId, conflict.taskId, { completed: conflict.serverState.completed, acknowledged: conflict.serverState.acknowledged, read: conflict.serverState.read }, conflict.serverState.updated_at)
      } else {
        const saved = await updateTaskState(conflict.taskId, conflict.patch, conflict.serverState.updated_at)
        await applyTaskStateToSnapshot(conflict.userId, conflict.taskId, conflict.patch, saved.updated_at)
      }
      await removeQueuedTaskUpdate(conflict.key)
      await removeOfflineConflict(conflict.key)
      const remaining = conflicts.filter((item) => item.key !== conflict.key)
      setConflicts(remaining)
      setConflictOpen(remaining.length > 0)
      await refreshOfflineStatus()
      await loadDashboard()
    } catch (caught) {
      setError(caught instanceof ApiError && caught.status === 409 ? 'The server changed again. Refresh the conflict details before choosing.' : caught instanceof Error ? caught.message : 'Could not resolve this conflict.')
      await refreshOfflineStatus()
    }
  }
  function clearFilters() {
    setCourseId(''); setEventType(''); setCompletion(''); setPriority(''); setSource('all'); setDateWindow('')
  }

  const visibleItems = useMemo(() => {
    const items = data?.items ?? []
    if (!dateWindow) return items
    const now = Date.now(); const sevenDays = now + 7 * 86400000; const thirtyDays = now + 30 * 86400000
    return items.filter((item) => {
      const value = item.due_at ?? item.starts_at
      if (dateWindow === 'undated') return !value
      if (!value) return false
      const timestamp = new Date(value).getTime()
      if (dateWindow === 'overdue') return timestamp < now && !item.completed
      return timestamp >= now && timestamp <= (dateWindow === '7days' ? sevenDays : thirtyDays)
    })
  }, [data?.items, dateWindow])

  const timelineGroups = useMemo(() => {
    const groups = new Map<string, DashboardItem[]>()
    for (const item of visibleItems) { const label = dateGroup(item); groups.set(label, [...(groups.get(label) ?? []), item]) }
    return [...groups.entries()]
  }, [visibleItems])
  const activeFilterCount = [courseId, eventType, completion, priority, dateWindow, source !== 'all' ? source : ''].filter(Boolean).length
  const hasFilters = activeFilterCount > 0
  const successfulSyncAt = latest && ['succeeded', 'partial'].includes(latest.status) ? latest.finished_at : lastSuccessfulSyncAt
  const stale = usingCache || !successfulSyncAt || Date.now() - new Date(successfulSyncAt).getTime() > 24 * 60 * 60 * 1000
  const freshness = latest?.status === 'partial' ? 'Partial' : latest?.status === 'failed' ? 'Last attempt failed' : stale ? 'Stale' : 'Current'
  const urgentCount = visibleItems.filter((item) => { const time = item.due_at ?? item.starts_at; return !item.completed && (item.priority === 3 || Boolean(time && new Date(time).getTime() >= Date.now() && new Date(time).getTime() - Date.now() <= 86400000)) }).length
  const openCount = visibleItems.filter((item) => !item.completed).length

  const cards = (items: DashboardItem[]) => items.map((item) => <DashboardTaskCard key={item.task_id} item={item} updating={updatingTask === item.task_id} onChange={(patch) => void changeTask(item, patch)} />)

  return <section aria-labelledby="dashboard-title" className="dashboard premium-dashboard">
    <PageHeader eyebrow="Your workspace" title="Academic dashboard" description="See what matters now, act locally, and verify every item at its Classroom source." actions={<Button loading={syncBusy || latest?.status === 'running'} disabled={!online || syncBusy || latest?.status === 'running'} onClick={() => void syncNow()}>{online ? 'Sync Classroom' : 'Offline'}</Button>} />

    <PersonalTasksPanel courses={data?.courses ?? []} onChanged={loadDashboard} />

    <section className="dashboard-status-grid" aria-label="Workspace summary"><StatCard label="Open in this view" value={openCount} detail={`${visibleItems.length} total items`} tone="accent" /><StatCard label="Urgent" value={urgentCount} detail="High priority or due within 24 hours" tone="warning" /><article className={`freshness-card freshness-${freshness.toLowerCase().replaceAll(' ', '-')}`} role="status" aria-live="polite"><div><span className="freshness-icon" aria-hidden="true">{freshness === 'Current' ? '✓' : freshness === 'Partial' ? '△' : '!'}</span><div><small>Data freshness</small><strong>{freshness}</strong></div></div><p>{successfulSyncAt ? `Last successful sync: ${new Date(successfulSyncAt).toLocaleString()}.` : 'No successful sync has been recorded.'}</p>{latest?.status === 'partial' && <p>{latest.items_seen} checked; some Classroom data could not be refreshed.</p>}{latest?.status === 'failed' && <p>The last attempt failed; previously successful data remains visible.</p>}{usingCache && cachedAt && <p>Showing the device snapshot saved {new Date(cachedAt).toLocaleString()}.</p>}{pendingChanges > 0 && <p>{pendingChanges} local change{pendingChanges === 1 ? '' : 's'} waiting to upload.</p>}{flushBusy && <p>Uploading queued changes…</p>}{conflicts.length > 0 && <p>{conflicts.length} change conflict{conflicts.length === 1 ? '' : 's'} need your choice.</p>}</article></section>

    {conflicts.length > 0 && <section className="offline-conflict-banner" role="alert"><div><strong>Choose which changes to keep</strong><p>{conflicts.length} queued change{conflicts.length === 1 ? ' conflicts' : 's conflict'} with newer server data.</p></div><Button variant="secondary" onClick={() => setConflictOpen(true)}>Resolve conflicts</Button></section>}

    {error && <div className="error-panel" role="alert"><p>{error}</p><Button variant="secondary" onClick={() => void loadDashboard()}>Try again</Button></div>}

    <nav className="overview-nav" aria-label="Dashboard overview sections">{views.map((option) => <button className={view === option.value ? 'active' : ''} type="button" aria-current={view === option.value ? 'page' : undefined} onClick={() => setView(option.value)} key={option.value}>{option.label}</button>)}</nav>

    <FilterBar activeCount={activeFilterCount} actions={hasFilters ? <Button variant="ghost" onClick={clearFilters}>Clear all</Button> : undefined}>
      <Field label="Course">{({ id }) => <Select id={id} value={courseId} onChange={(event) => setCourseId(event.target.value)}><option value="">All courses</option>{data?.courses.map((course) => <option value={course.id} key={course.id}>{course.name}</option>)}</Select>}</Field>
      <Field label="Event type">{({ id }) => <Select id={id} value={eventType} onChange={(event) => setEventType(event.target.value as DashboardEventType | '')}><option value="">All types</option><option value="assignment">Assignments</option><option value="exam">Exams</option><option value="notice">Notices</option><option value="material">Materials</option><option value="other">Other</option></Select>}</Field>
      <Field label="Date">{({ id }) => <Select id={id} value={dateWindow} onChange={(event) => setDateWindow(event.target.value as DateWindow)}><option value="">Any date</option><option value="overdue">Overdue</option><option value="7days">Next 7 days</option><option value="30days">Next 30 days</option><option value="undated">No date</option></Select>}</Field>
      <Field label="Completion">{({ id }) => <Select id={id} value={completion} onChange={(event) => setCompletion(event.target.value)}><option value="">Any state</option><option value="open">Open</option><option value="complete">Completed</option></Select>}</Field>
      <Field label="Priority">{({ id }) => <Select id={id} value={priority} onChange={(event) => setPriority(event.target.value)}><option value="">Any priority</option><option value="3">High</option><option value="2">Medium</option><option value="1">Low</option><option value="0">None</option></Select>}</Field>
      <Field label="Source">{({ id }) => <Select id={id} value={source} onChange={(event) => setSource(event.target.value as 'all'|'classroom'|'manual')}><option value="all">All</option><option value="classroom">Classroom</option><option value="manual">Added by me</option></Select>}</Field>
    </FilterBar>

    <header className="dashboard-results-header"><div><h2>{views.find((option) => option.value === view)?.label}</h2>{!loading && <p>{visibleItems.length} item{visibleItems.length === 1 ? '' : 's'}{hasFilters ? ` · ${activeFilterCount} active filter${activeFilterCount === 1 ? '' : 's'}` : ''}</p>}</div><div className="layout-switch" role="group" aria-label="Information layout"><button type="button" aria-pressed={displayMode === 'list'} onClick={() => setDisplayMode('list')}>☷ List</button><button type="button" aria-pressed={displayMode === 'timeline'} onClick={() => setDisplayMode('timeline')}>⌁ Timeline</button></div></header>

    {loading ? <div className="premium-task-list" aria-label="Loading dashboard">{[0,1,2].map((key) => <article className="premium-task-card dashboard-skeleton" key={key}><Skeleton lines={1} /><Skeleton lines={2} /><div className="skeleton-actions"><Skeleton lines={1} /><Skeleton lines={1} /></div></article>)}</div>
      : visibleItems.length > 0 ? displayMode === 'list' ? <div className="premium-task-list">{cards(visibleItems)}</div>
        : <div className="dashboard-timeline">{timelineGroups.map(([label, items]) => <section key={label} aria-labelledby={`timeline-${label.replace(/\W+/g, '-').toLowerCase()}`}><header><span aria-hidden="true" /><h3 id={`timeline-${label.replace(/\W+/g, '-').toLowerCase()}`}>{label}</h3><Badge>{items.length}</Badge></header><div>{cards(items)}</div></section>)}</div>
      : <EmptyState title={hasFilters ? 'No items match these filters' : 'Nothing here right now'} description={hasFilters ? 'Clear the filters or choose another overview to widen the results.' : 'Synchronize Classroom or choose another overview to find academic items.'} actionLabel={hasFilters ? 'Clear all filters' : online ? 'Sync Classroom' : undefined} onAction={hasFilters ? clearFilters : online ? () => void syncNow() : undefined} />}
    <Dialog open={conflictOpen && conflicts.length > 0} onOpenChange={setConflictOpen} title="Resolve offline change" description="The same task changed on this device and on the server. Choose one version; the other task-state change will be discarded." footer={<Button variant="ghost" onClick={() => setConflictOpen(false)}>Decide later</Button>}>
      {conflicts[0] && <div className="conflict-comparison"><p className="course-name">{conflicts[0].courseName}</p><h3>{conflicts[0].title}</h3><section><h4>Server version</h4><p>{conflicts[0].serverState.completed ? 'Completed' : 'Open'} · {conflicts[0].serverState.read ? 'Read' : 'Unread'} · {conflicts[0].serverState.acknowledged ? 'Acknowledged' : 'Not acknowledged'}</p><Button variant="secondary" onClick={() => void resolveConflict(conflicts[0]!, 'server')}>Keep server version</Button></section><section><h4>My device change</h4><p>{Object.entries(conflicts[0].patch).map(([key, value]) => `${key}: ${value ? 'yes' : 'no'}`).join(' · ')}</p><Button onClick={() => void resolveConflict(conflicts[0]!, 'device')}>Apply my device change</Button></section><p className="muted-copy">This choice only affects your local task status. It never edits the original Classroom item.</p></div>}
    </Dialog>  </section>
}



