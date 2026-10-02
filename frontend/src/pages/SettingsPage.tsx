import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { ApiError, beginGoogleAuth, deleteAccount, disconnectAccount, logout, reconnectGoogle } from '../api'
import { clearOfflineData, getOfflineStorageStatus } from '../offline'

export function SettingsPage() {
  const [parameters] = useSearchParams()
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [offlineStatus, setOfflineStatus] = useState<Awaited<ReturnType<typeof getOfflineStorageStatus>> | null>(null)
  const run = (action: () => Promise<void>) => {
    setError('')
    void action().catch((caught) => {
      if (caught instanceof ApiError && caught.status === 0) setError('The server is unreachable. Check your connection and retry this action.')
      else if (caught instanceof ApiError && caught.status === 401) setError('Your session expired. Sign in again before changing account access.')
      else if (caught instanceof ApiError && caught.status === 403) setError('Google permission or recent identity confirmation is required. Reauthenticate, then retry.')
      else setError(caught instanceof Error ? caught.message : 'Action failed. Retry, or contact the person running this app.')
    })
  }

  useEffect(() => {
    if (parameters.get('reauthenticated') === 'true') setMessage('Your identity was confirmed. You can now continue the protected account action.')
    void getOfflineStorageStatus().then(setOfflineStatus).catch(() => setOfflineStatus(null))
  }, [parameters])

  async function clearDeviceData() {
    if (!window.confirm('Clear all Academic Assistant offline data and queued changes from this device?')) return
    setError('')
    await clearOfflineData()
    setOfflineStatus(null)
    setMessage('Offline academic data was cleared from this browser.')
  }

  return <section className="settings-layout" aria-labelledby="settings-title">
    <div className="form-card"><p className="eyebrow">Account</p><h1 id="settings-title">Settings</h1><p>Reauthenticate immediately before disconnecting or permanently deleting your account. If Classroom access was revoked, use Reconnect and approve the requested read-only permissions on Google’s website.</p>{error && <p className="error-message" role="alert">{error}</p>}{message && <p role="status">{message}</p>}<div className="button-row"><button type="button" onClick={() => run(() => beginGoogleAuth(true))}>Reauthenticate with Google</button><button type="button" onClick={() => run(reconnectGoogle)}>Reconnect Classroom access</button><button type="button" className="secondary" onClick={() => run(logout)}>Sign out</button><button type="button" className="secondary" onClick={() => run(disconnectAccount)}>Disconnect Google</button><button type="button" className="danger" onClick={() => window.confirm('Permanently delete your account and all saved data?') && run(deleteAccount)}>Delete account</button></div><p className="support-copy">If reauthentication or reconnect repeatedly fails, sign out and try once more. Then contact the person running this app to verify its OAuth configuration. Never send anyone your Google password.</p></div>

    <div className="form-card" aria-labelledby="offline-data-title"><p className="eyebrow">This device</p><h2 id="offline-data-title">Offline academic data</h2><p>Saved courses and tasks make the installed app useful without internet. Anyone who can unlock this device and browser profile may be able to view that saved academic data.</p>{offlineStatus?.cachedAt ? <dl className="settings-details"><div><dt>Data saved</dt><dd>{new Date(offlineStatus.cachedAt).toLocaleString()}</dd></div><div><dt>Last successful sync</dt><dd>{offlineStatus.lastSuccessfulSyncAt ? new Date(offlineStatus.lastSuccessfulSyncAt).toLocaleString() : 'Not recorded'}</dd></div><div><dt>Queued changes</dt><dd>{offlineStatus.queuedChanges}</dd></div><div><dt>Conflicts needing a choice</dt><dd>{offlineStatus.conflicts}</dd></div></dl> : <p>No offline academic snapshot is stored in this browser.</p>}<button type="button" className="danger" onClick={() => run(clearDeviceData)}>Clear offline data</button></div>
  </section>
}

