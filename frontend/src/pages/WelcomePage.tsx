import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { ApiError, beginGoogleAuth } from '../api'
import { AmbientBackground } from '../components/AmbientBackground'
import { Button, Card } from '../components/ui'

function initialNotice(reason: string | null): string {
  if (reason === 'session_expired') return 'Your session ended safely. Continue with Google to open your workspace again.'
  if (reason === 'permission_revoked') return 'Google access was removed. Continue with Google and approve the requested read-only access to reconnect.'
  if (reason === 'oauth_failed') return 'Google sign-in did not finish. You can safely try again.'
  return ''
}

export function WelcomePage() {
  const [parameters] = useSearchParams()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const notice = useMemo(() => initialNotice(parameters.get('reason')), [parameters])

  async function signIn() {
    if (busy) return
    setBusy(true)
    setError('')
    try { await beginGoogleAuth() } catch (caught) {
      setBusy(false)
      setError(caught instanceof ApiError && caught.status === 0 ? 'Google sign-in could not start because the server is unreachable. Check your connection and try again.' : 'Google sign-in could not start. Try again; if it continues, ask the person running this app to verify its Google OAuth configuration.')
    }
  }

  return <section className="welcome-page ambient-surface" aria-labelledby="welcome-title">
    <AmbientBackground variant="hero" />
    <div className="welcome-hero"><p className="eyebrow">Private academic clarity</p><h1 id="welcome-title">Your academic day, without the noise.</h1><p>Bring permitted Classroom assignments, deadlines, exams, and notices into one calm workspace built for a single student.</p>{notice && <p className="auth-notice" role="status">{notice}</p>}{error && <div className="auth-error" role="alert"><strong>Sign-in needs attention</strong><p>{error}</p></div>}<Button size="lg" loading={busy} onClick={() => void signIn()}>Continue with Google</Button><p className="auth-fine-print">You will continue on Google’s website. This app never asks for or stores your Google password.</p></div>
    <div className="welcome-details"><Card elevated><span className="welcome-detail-icon" aria-hidden="true">◌</span><h2>Read-only by purpose</h2><p>The app requests your basic identity and read-only Classroom access so it can organize work. It cannot submit, edit, or delete Classroom content.</p></Card><Card><span className="welcome-detail-icon" aria-hidden="true">◇</span><h2>Your choices stay yours</h2><p>You choose which courses are relevant. Disconnecting Google or deleting the account remains available in Settings.</p></Card><Card><span className="welcome-detail-icon" aria-hidden="true">⌁</span><h2>Useful when offline</h2><p>After a successful sync, this browser can keep a private local snapshot. Clear it from Settings whenever you want.</p></Card></div>
  </section>
}
