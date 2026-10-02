import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigationType } from 'react-router-dom'

import { getOfflineStorageStatus } from '../offline'
import { ApiError, getShell, logout, prefetchProfile, synchronize, type SessionUser, type SyncRun } from '../api'
import { ErrorBoundary } from './ErrorBoundary'
import { InstallExperience } from './InstallExperience'
import { MotionController } from './MotionController'
import { Badge, Button, Spinner, ToastRegion, type ToastMessage } from './ui'

let shellCache: { user: SessionUser; unread: number; latest: SyncRun | null } | null = null
let shellRequest: Promise<{ user: SessionUser; unread: number; latest: SyncRun | null }> | null = null
async function fetchShell(){ if (shellRequest) return shellRequest; shellRequest = getShell().then((value) => { shellCache = { user: value.user, unread: value.unread_notification_count, latest: value.latest_sync }; return shellCache }).finally(() => { shellRequest = null }); return shellRequest }

type ShellSyncState = 'idle' | 'running' | 'succeeded' | 'stale' | 'partial' | 'failed'

const routes = [
  { to: '/dashboard', label: 'Dashboard', icon: '⌂' },
  { to: '/assistant', label: 'Assistant', icon: '✦' },
  { to: '/notifications', label: 'Notifications', icon: '◉' },
  { to: '/profile', label: 'Profile', icon: '●' },
]

function prefetchProfileRoute() {
  void import('../pages/ProfilePage')
  void prefetchProfile().catch(() => undefined)
}

const routeTitles: Record<string, string> = {
  '/': 'Welcome', '/onboarding': 'Set up your workspace', '/dashboard': 'Dashboard',
  '/assistant': 'Assistant', '/notifications': 'Notifications',
  '/settings': 'Settings', '/profile': 'Profile', '/dev/design-system': 'Design system', '/dev/relevance': 'Relevance debug',
}

function syncState(latest: SyncRun | null, online: boolean, currentTime = Date.now()): ShellSyncState {
  if (latest?.status === 'running') return 'running'
  if (latest?.status === 'partial') return 'partial'
  if (latest?.status === 'failed') return 'failed'
  if (!latest) return 'idle'
  const completed = latest.finished_at ? new Date(latest.finished_at).getTime() : 0
  if (!online || currentTime - completed > 24 * 60 * 60 * 1000) return 'stale'
  return 'succeeded'
}

function syncCopy(state: ShellSyncState, latest: SyncRun | null, currentTime: number): string {
  if (state === 'idle') return 'Not synchronized yet'
  if (state === 'running') {
    const progress = latest?.courses_total ? `${latest.courses_processed ?? 0} of ${latest.courses_total} courses` : 'Preparing courses'
    const phase = latest?.current_phase?.replaceAll('_', ' ') ?? 'starting'
    const elapsed = latest?.started_at ? Math.max(0, Math.floor((currentTime - new Date(latest.started_at).getTime()) / 1000)) : 0
    return `${progress} · ${phase} · ${elapsed}s`
  }
  if (state === 'stale') return 'Saved data may be out of date'
  if (state === 'partial') return latest?.failed_courses?.length ? `Synced; ${latest.failed_courses.length} course${latest.failed_courses.length === 1 ? '' : 's'} unavailable` : 'Synced with some items unavailable'
  if (state === 'failed') return 'Last synchronization failed'
  return latest?.finished_at ? `Synced ${new Date(latest.finished_at).toLocaleString()}` : 'Classroom is synchronized'
}

function ScrollAndFocusManager() {
  const location = useLocation()
  const navigationType = useNavigationType()
  const previousKey = useRef(location.key)
  const positions = useRef(new Map<string, number>())
  const firstRender = useRef(true)

  useEffect(() => {
    const oldKey = previousKey.current
    if (!firstRender.current) positions.current.set(oldKey, window.scrollY)
    previousKey.current = location.key
    document.title = `${routeTitles[location.pathname] ?? 'Academic Assistant'} · Academic Assistant`
    if (firstRender.current) { firstRender.current = false; return }
    const restore = navigationType === 'POP' ? positions.current.get(location.key) ?? 0 : 0
    window.requestAnimationFrame(() => {
      window.scrollTo({ top: restore, behavior: 'auto' })
      if (navigationType !== 'POP') {
        document.getElementById('main-content')?.focus({ preventScroll: true })
      }
    })
  }, [location.key, location.pathname, navigationType])
  return null
}

function RouteContent() {
  const location = useLocation()
  return <div className="route-content" key={location.pathname}><ErrorBoundary><Suspense fallback={<div className="route-loading" role="status"><Spinner /><span>Loading page…</span></div>}><Outlet /></Suspense></ErrorBoundary></div>
}

export function AppLayout() {
  const location = useLocation()
  const [user, setUser] = useState<SessionUser | null>(null)
  const [unreadCount, setUnreadCount] = useState(0)
  const [latest, setLatest] = useState<SyncRun | null>(null)
  const [online, setOnline] = useState(navigator.onLine)
  const [syncBusy, setSyncBusy] = useState(false)
  const [cooldownUntil, setCooldownUntil] = useState(0)
  const [now, setNow] = useState(Date.now())
  const [toasts, setToasts] = useState<ToastMessage[]>([])
  const [offlineSummary, setOfflineSummary] = useState({ queuedChanges: 0, conflicts: 0, lastSuccessfulSyncAt: null as string | null })
  const accountMenuRef = useRef<HTMLDetailsElement>(null)
  const lastSyncStatus = useRef<SyncRun['status'] | null>(null)

  const addToast = useCallback((message: Omit<ToastMessage, 'id'>) => {
    const id = crypto.randomUUID()
    setToasts((current) => [...current, { ...message, id }].slice(-3))
    window.setTimeout(() => setToasts((current) => current.filter((toast) => toast.id !== id)), 5000)
  }, [])

  const refreshShell = useCallback(async () => {
    if (!navigator.onLine) return
    if (shellCache) { setUser(shellCache.user); setUnreadCount(shellCache.unread); setLatest(shellCache.latest) }
    try {
      const current = await fetchShell()
      if (current) {
        setUser(current.user); setUnreadCount(current.unread); setLatest(current.latest)
        const nextStatus = current.latest?.status ?? null
        if (nextStatus !== lastSyncStatus.current) {
          lastSyncStatus.current = nextStatus
          if (nextStatus) window.dispatchEvent(new CustomEvent("academic-sync-state", { detail: { status: nextStatus } }))
          if (nextStatus && nextStatus !== "running") window.dispatchEvent(new Event("academic-sync-updated"))
        }
      }
      const local = await getOfflineStorageStatus().catch(() => null)
      if (local) setOfflineSummary({ queuedChanges: local.queuedChanges, conflicts: local.conflicts, lastSuccessfulSyncAt: local.lastSuccessfulSyncAt })
    } catch (caught) { if (caught instanceof ApiError && caught.status === 401) { shellCache = null; setUser(null) } }
  }, [])
  useEffect(() => { void refreshShell() }, [refreshShell])
  useEffect(() => {
    function dismissAccountMenu(event: MouseEvent) {
      if (accountMenuRef.current?.open && !accountMenuRef.current.contains(event.target as Node)) accountMenuRef.current.open = false
    }
    function escapeAccountMenu(event: KeyboardEvent) {
      if (event.key !== 'Escape' || !accountMenuRef.current?.open) return
      accountMenuRef.current.open = false
      accountMenuRef.current.querySelector<HTMLElement>('summary')?.focus()
    }
    document.addEventListener('pointerdown', dismissAccountMenu)
    document.addEventListener('keydown', escapeAccountMenu)
    return () => { document.removeEventListener('pointerdown', dismissAccountMenu); document.removeEventListener('keydown', escapeAccountMenu) }
  }, [])
  useEffect(() => {
    const interval = window.setInterval(() => { setNow(Date.now()); void refreshShell() }, latest?.status === 'running' || syncBusy ? 3000 : 60_000)
    const notifications = () => void refreshShell()
    const handleOnline = () => { setOnline(true); void refreshShell() }
    const handleOffline = () => setOnline(false)
    window.addEventListener('notifications-updated', notifications)
    const syncEvent = (event: Event) => {
      const status = (event as CustomEvent<{ status?: SyncRun['status'] }>).detail?.status
      setSyncBusy(status === 'running')
      void refreshShell()
    }
    window.addEventListener('academic-sync-updated', notifications)
    window.addEventListener('academic-sync-state', syncEvent)
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    return () => {
      window.clearInterval(interval)
      window.removeEventListener('notifications-updated', notifications)
      window.removeEventListener('academic-sync-updated', notifications)
      window.removeEventListener('academic-sync-state', syncEvent)
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [latest?.status, refreshShell, syncBusy])

  useEffect(() => {
    if (cooldownUntil <= now) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [cooldownUntil, now])

  const state = useMemo(() => syncState(latest, online, now), [latest, online, now])
  const cooldownSeconds = Math.max(0, Math.ceil((cooldownUntil - now) / 1000))
  const syncDisabled = !online || syncBusy || state === 'running' || cooldownSeconds > 0
  const disabledReason = !online ? 'Connect to the internet to synchronize.' : state === 'running' || syncBusy ? 'Synchronization is already running.' : cooldownSeconds > 0 ? `You can synchronize again in ${cooldownSeconds} seconds.` : ''

  async function syncNow() {
    if (syncDisabled) return
    setSyncBusy(true)
    window.dispatchEvent(new CustomEvent('academic-sync-state', { detail: { status: 'running' } }))
    try {
      const result = await synchronize()
      setLatest(result)
      setCooldownUntil(Date.now() + 30_000)
      setNow(Date.now())
      lastSyncStatus.current = result.status
      window.dispatchEvent(new CustomEvent('academic-sync-state', { detail: { status: result.status } }))
      addToast({ tone: 'success', title: 'Synchronization started', description: 'You can keep using the app while Classroom updates in the background.' })
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409 && caught.message === 'sync_already_running') {
        addToast({ tone: 'info', title: 'Synchronization in progress', description: 'The existing Classroom update is still running.' })
        await refreshShell()
        return
      }
      window.dispatchEvent(new CustomEvent('academic-sync-state', { detail: { status: 'failed' } }))
      addToast({ tone: 'danger', title: 'Could not synchronize', description: caught instanceof Error ? caught.message : 'Try again in a moment.' })
      await refreshShell()
    } finally {
      setSyncBusy(false)
    }
  }

  async function signOut() {
    try { await logout() } catch (caught) { addToast({ tone: 'danger', title: 'Could not sign out', description: caught instanceof Error ? caught.message : 'Try again.' }) }
  }

  const pageTitle = routeTitles[location.pathname] ?? 'Academic Assistant'
  const privateShell = Boolean(user)

  return <div className={`app-shell${privateShell ? ' app-shell-authenticated' : ''}`}>
    <ScrollAndFocusManager />
    <MotionController />
    <a className="skip-link" href="#main-content">Skip to content</a>
    {user ? <>
      <aside className="app-sidebar" aria-label="Application navigation">
        <NavLink className="shell-brand" to="/dashboard" aria-label="Academic Assistant dashboard"><span aria-hidden="true">◆</span><span>Academic<br />Assistant</span></NavLink>
        <nav className="desktop-navigation" aria-label="Primary navigation">{routes.map((route) => <NavLink key={route.to} to={route.to} onPointerEnter={route.to === '/profile' ? prefetchProfileRoute : undefined} onFocus={route.to === '/profile' ? prefetchProfileRoute : undefined} onPointerDown={route.to === '/profile' ? prefetchProfileRoute : undefined}><span className="nav-icon" aria-hidden="true">{route.icon}</span><span>{route.label}</span>{route.to === '/notifications' && unreadCount > 0 && <Badge tone="accent" aria-label={`${unreadCount} unread notifications`}>{unreadCount > 99 ? '99+' : unreadCount}</Badge>}</NavLink>)}</nav>
        <div className="sidebar-footer"><div className={`global-sync sync-state-${state}`} role="status" aria-live="polite"><span className="sync-dot" aria-hidden="true" /><div><strong>{state === 'stale' ? 'Data is stale' : state === 'running' ? 'Synchronizing' : 'Classroom'}</strong><small>{syncCopy(state, latest, now)}</small>{offlineSummary.lastSuccessfulSyncAt && (state === 'stale' || !online) && <small>Last success {new Date(offlineSummary.lastSuccessfulSyncAt).toLocaleString()}</small>}{offlineSummary.queuedChanges > 0 && <small>{offlineSummary.queuedChanges} queued</small>}{offlineSummary.conflicts > 0 && <small className="conflict-copy">{offlineSummary.conflicts} conflict{offlineSummary.conflicts === 1 ? '' : 's'}</small>}</div></div><Button variant="secondary" loading={syncBusy || state === 'running'} disabled={syncDisabled} title={disabledReason || 'Synchronize Classroom'} onClick={() => void syncNow()}>{cooldownSeconds > 0 ? `Wait ${cooldownSeconds}s` : 'Sync now'}</Button>{disabledReason && <p className="sync-disabled-reason">{disabledReason}</p>}</div>
      </aside>
      <header className="app-topbar"><div><p className="topbar-context">Workspace</p><strong>{pageTitle}</strong></div><details className="account-menu" ref={accountMenuRef}><summary aria-label="Open account menu"><span className="account-avatar" aria-hidden="true">{user.display_name?.[0]?.toUpperCase() || 'A'}</span><span className="account-copy"><strong>{user.display_name}</strong><small>{online ? 'Online' : 'Offline'}</small></span><span aria-hidden="true">⌄</span></summary><div className="account-panel"><div className="account-identity"><strong>{user.display_name}</strong><small>{user.email}</small></div><div className={`connection-row ${online ? 'online' : 'offline'}`}><span aria-hidden="true" />{online ? 'Connected' : 'Working offline'}</div><NavLink to="/profile" onPointerEnter={prefetchProfileRoute} onFocus={prefetchProfileRoute} onPointerDown={prefetchProfileRoute}>Profile</NavLink><NavLink to="/settings">Settings</NavLink><button type="button" onClick={() => void signOut()}>Sign out</button></div></details></header>
    </> : <header className="public-header"><NavLink className="shell-brand" to="/"><span aria-hidden="true">◆</span><span>Academic Assistant</span></NavLink></header>}
    <main id="main-content" className="main-content" tabIndex={-1}><RouteContent /></main>
    {privateShell && <nav className="mobile-navigation" aria-label="Mobile navigation">{routes.map((route) => <NavLink key={route.to} to={route.to} onPointerDown={route.to === '/profile' ? prefetchProfileRoute : undefined}><span aria-hidden="true">{route.icon}</span><small>{route.label}</small>{route.to === '/notifications' && unreadCount > 0 && <i aria-label={`${unreadCount} unread notifications`}>{unreadCount > 9 ? '9+' : unreadCount}</i>}</NavLink>)}<NavLink to="/settings"><span aria-hidden="true">⚙</span><small>Settings</small></NavLink></nav>}
    <InstallExperience />
    <ToastRegion messages={toasts} onDismiss={(id) => setToasts((current) => current.filter((toast) => toast.id !== id))} />
  </div>
}













