import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'

import { ApiError, getCurrentUser, type SessionUser } from '../api'
import { clearOfflineData, getCachedSessionUser, setActiveOfflineUser } from '../offline'
import { Button, LinkButton, Spinner } from './ui'

export function ProtectedRoute({ children, requireOnboarding = true }: { children: React.ReactNode; requireOnboarding?: boolean }) {
  const [user, setUser] = useState<SessionUser | null | undefined>(undefined)
  const [failure, setFailure] = useState<'network' | 'unknown' | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let active = true
    async function loadSession() {
      setUser(undefined)
      setFailure(null)
      try {
        const current = await getCurrentUser()
        await setActiveOfflineUser(current)
        if (active) setUser(current)
      } catch (caught) {
        const networkUnavailable = !navigator.onLine || (caught instanceof ApiError && caught.status === 0)
        if (!networkUnavailable && caught instanceof ApiError && caught.status === 401) {
          await clearOfflineData().catch(() => undefined)
          if (active) setUser(null)
          return
        }
        const cached = networkUnavailable ? await getCachedSessionUser().catch(() => null) : null
        if (!active) return
        setUser(cached)
        if (!cached) setFailure(networkUnavailable ? 'network' : 'unknown')
      }
    }
    void loadSession()
    return () => { active = false }
  }, [attempt])

  if (user === undefined) return <section className="auth-progress" role="status" aria-live="polite"><Spinner size="lg" /><div><h1>Opening your workspace</h1><p>Confirming your secure session and loading your profile. No Google password is shared with this app.</p></div></section>
  if (user === null && failure) return <section className="auth-recovery" role="alert"><p className="eyebrow">Connection interrupted</p><h1>{failure === 'network' ? 'We could not reach your account' : 'Your session could not be confirmed'}</h1><p>{failure === 'network' ? 'Check your internet connection, then retry. If you previously synchronized this device, reconnecting will preserve that local snapshot.' : 'Retry once. If the problem continues, return to sign in and contact the person running this Academic Assistant instance.'}</p><div className="button-row"><Button onClick={() => setAttempt((value) => value + 1)}>Retry</Button><LinkButton variant="secondary" href="/?reason=session_expired">Return to sign in</LinkButton></div></section>
  if (user === null) return <Navigate to="/?reason=session_expired" replace />
  if (requireOnboarding && !user.onboarding_complete) return <Navigate to="/onboarding" replace />
  return <>{children}</>
}
