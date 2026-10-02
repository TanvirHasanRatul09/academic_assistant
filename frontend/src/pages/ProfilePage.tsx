import { FormEvent, useEffect, useState } from 'react'
import { ApiError, getProfile, saveProfile, type Profile } from '../api'

function messageFor(error: unknown): string {
  if (error instanceof ApiError && error.status === 0) return 'You are offline. Reconnect and try again.'
  if (error instanceof ApiError && error.status === 401) return 'Your session expired. Sign in again.'
  if (error instanceof ApiError && error.status === 422) return 'Check the highlighted profile values and try again.'
  return error instanceof Error ? error.message : 'Could not save your profile.'
}

export function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'saving' | 'saved' | 'error'>('loading')
  const [error, setError] = useState('')

  useEffect(() => {
    getProfile().then((value) => { setProfile(value); setState('ready') }).catch((caught) => { setError(messageFor(caught)); setState('error') })
  }, [])

  function update<K extends keyof Profile>(key: K, value: Profile[K]) {
    setProfile((current) => current ? { ...current, [key]: value } : current)
    if (state === 'saved') setState('ready')
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!profile) return
    setState('saving'); setError('')
    try {
      const saved = await saveProfile({
        academic_level: profile.academic_level?.trim() || null,
        program: profile.program?.trim() || null,
        section: profile.section?.trim() || null,
        lab_group: profile.lab_group?.trim() || null,
        timezone: profile.timezone.trim(),
        selected_course_ids: profile.selected_course_ids,
        notification_preferences: profile.notification_preferences,
      })
      setProfile(saved); setState('saved')
      window.dispatchEvent(new Event('academic-profile-updated'))
    } catch (caught) { setError(messageFor(caught)); setState('error') }
  }

  if (state === 'loading') return <section className="form-card" role="status"><h1>Profile</h1><p>Loading your profile…</p></section>
  if (!profile) return <section className="form-card" role="alert"><h1>Profile</h1><p>{error}</p><button type="button" onClick={() => window.location.reload()}>Try again</button></section>

  const courses = profile.courses ?? []
  const preferences = profile.notification_preferences
  return <section className="settings-layout profile-layout" aria-labelledby="profile-title">
    <form className="form-card profile-form" onSubmit={submit}>
      <p className="eyebrow">Personal workspace</p><h1 id="profile-title">Profile</h1>
      <p>Your academic context controls which dashboard items and notifications are relevant to you.</p>
      {error && <p className="error-message" role="alert">{error}</p>}
      {state === 'saved' && <p className="success-message" role="status">Profile saved successfully.</p>}
      <div className="profile-grid">
        <label>Name<input value={profile.display_name} readOnly /></label>
        <label>Email<input value={profile.email} readOnly /></label>
        <label>Academic year or level<input maxLength={128} value={profile.academic_level ?? ''} onChange={(event) => update('academic_level', event.target.value)} placeholder="Third year" /></label>
        <label>Department or program<input maxLength={200} value={profile.program ?? ''} onChange={(event) => update('program', event.target.value)} placeholder="Computer Science and Engineering" /></label>
        <label>Section<input maxLength={64} value={profile.section ?? ''} onChange={(event) => update('section', event.target.value)} placeholder="A" /></label>
        <label>Lab group<input maxLength={64} value={profile.lab_group ?? ''} onChange={(event) => update('lab_group', event.target.value)} placeholder="A1" /></label>
        <label>Time zone<input required maxLength={64} value={profile.timezone} onChange={(event) => update('timezone', event.target.value)} placeholder="Asia/Dhaka" /></label>
      </div>
      <fieldset className="course-picker"><legend>Enrolled Classroom courses</legend>{courses.length === 0 ? <p>No Classroom courses are available.</p> : courses.map((course) => <label key={course.id}><input type="checkbox" disabled={course.eligible === false} checked={profile.selected_course_ids.includes(course.id)} onChange={(event) => update('selected_course_ids', event.target.checked ? [...profile.selected_course_ids, course.id] : profile.selected_course_ids.filter((id) => id !== course.id))} /> {course.name}{course.eligible === false ? ' (Historical — no longer active)' : ''}</label>)}</fieldset>
      <fieldset className="profile-preferences"><legend>Notification preferences</legend>{(['assignments', 'exams', 'notices'] as const).map((key) => <label key={key}><input type="checkbox" checked={preferences[key] !== false} onChange={(event) => update('notification_preferences', { ...preferences, [key]: event.target.checked })} /> {key.charAt(0).toUpperCase() + key.slice(1)}</label>)}</fieldset>
      <button type="submit" disabled={state === 'saving'}>{state === 'saving' ? 'Saving…' : 'Save profile'}</button>
    </form>
    <aside className="form-card"><h2>Connection status</h2><dl className="settings-details"><div><dt>Google Classroom</dt><dd>{profile.classroom_connected ? 'Connected' : 'Not connected'}</dd></div><div><dt>Last successful sync</dt><dd>{profile.last_successful_sync_at ? new Date(profile.last_successful_sync_at).toLocaleString() : 'Not synchronized yet'}</dd></div><div><dt>Selected courses</dt><dd>{profile.selected_course_ids.length}</dd></div></dl></aside>
  </section>
}

