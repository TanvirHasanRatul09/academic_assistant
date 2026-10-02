import { type FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { ApiError, getCourses, getProfile, reconnectGoogle, saveProfile } from '../api'
import { AmbientBackground } from '../components/AmbientBackground'
import { Button, Checkbox, Field, Input, Spinner, Switch } from '../components/ui'

const DRAFT_KEY = 'academic-assistant-onboarding-draft'
type Course = { id: string; name: string; selected: boolean }
type Draft = { section: string; labGroup: string; timezone: string; notifications: boolean; selectedCourseIds: string[]; step: 1 | 2 }

function readDraft(): Draft | null {
  try { return JSON.parse(sessionStorage.getItem(DRAFT_KEY) ?? 'null') as Draft | null } catch { return null }
}

function validTimezone(value: string): boolean {
  if (!value.trim() || value.length > 64) return false
  try { new Intl.DateTimeFormat(undefined, { timeZone: value }); return true } catch { return false }
}

function loadError(caught: unknown): { message: string; permission: boolean } {
  if (caught instanceof ApiError && caught.status === 0) return { message: 'We could not reach the server. Check your connection and retry; your entries on this page are preserved.', permission: false }
  if (caught instanceof ApiError && [401, 403].includes(caught.status)) return { message: 'Your Google session or Classroom permission needs attention. Reconnect access, then retry this step.', permission: true }
  return { message: caught instanceof Error ? caught.message : 'Setup could not be loaded. Retry, or contact the person running this app if it continues.', permission: false }
}

export function OnboardingPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState<1 | 2>(readDraft()?.step ?? 1)
  const [section, setSection] = useState(readDraft()?.section ?? '')
  const [labGroup, setLabGroup] = useState(readDraft()?.labGroup ?? '')
  const [timezone, setTimezone] = useState(readDraft()?.timezone ?? (Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'))
  const [notifications, setNotifications] = useState(readDraft()?.notifications ?? true)
  const [courses, setCourses] = useState<Course[]>([])
  const [ready, setReady] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [permissionError, setPermissionError] = useState(false)
  const [timezoneError, setTimezoneError] = useState('')

  const load = useCallback(async () => {
    setBusy(true); setError(''); setPermissionError(false)
    try {
      const [profile, availableCourses] = await Promise.all([getProfile(), getCourses()])
      if (profile.onboarding_complete) { navigate('/dashboard', { replace: true }); return }
      const draft = readDraft()
      setSection(draft?.section ?? profile.section ?? '')
      setLabGroup(draft?.labGroup ?? profile.lab_group ?? '')
      setTimezone(draft?.timezone ?? profile.timezone)
      setNotifications(draft?.notifications ?? profile.notification_preferences.assignments !== false)
      setStep(draft?.step ?? 1)
      const selected = draft?.selectedCourseIds
      setCourses(availableCourses.map((course) => selected ? { ...course, selected: selected.includes(course.id) } : course))
      setReady(true)
    } catch (caught) {
      const result = loadError(caught); setError(result.message); setPermissionError(result.permission)
    } finally { setBusy(false) }
  }, [navigate])

  useEffect(() => { void load() }, [load])
  useEffect(() => {
    if (!ready) return
    const draft: Draft = { section, labGroup, timezone, notifications, selectedCourseIds: courses.filter((course) => course.selected).map((course) => course.id), step }
    sessionStorage.setItem(DRAFT_KEY, JSON.stringify(draft))
  }, [courses, labGroup, notifications, ready, section, step, timezone])

  const selectedCount = useMemo(() => courses.filter((course) => course.selected).length, [courses])

  function continueSetup() {
    if (!validTimezone(timezone)) { setTimezoneError('Enter a valid IANA timezone, such as Asia/Dhaka or UTC.'); return }
    setTimezoneError(''); setStep(2)
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!validTimezone(timezone)) { setStep(1); setTimezoneError('Enter a valid IANA timezone, such as Asia/Dhaka or UTC.'); return }
    setBusy(true); setError(''); setPermissionError(false)
    try {
      await saveProfile({ section: section.trim() || null, lab_group: labGroup.trim() || null, timezone: timezone.trim(), selected_course_ids: courses.filter((course) => course.selected).map((course) => course.id), notification_preferences: { assignments: notifications, exams: notifications, notices: notifications } })
      sessionStorage.removeItem(DRAFT_KEY)
      navigate('/dashboard', { replace: true })
    } catch (caught) {
      const result = loadError(caught); setError(result.message); setPermissionError(result.permission)
    } finally { setBusy(false) }
  }

  if (!ready && busy) return <section className="auth-progress" role="status"><Spinner size="lg" /><div><h1>Preparing your setup</h1><p>Loading your profile and available Classroom courses.</p></div></section>
  if (!ready && error) return <section className="auth-recovery" role="alert"><p className="eyebrow">Setup paused</p><h1>We could not load your setup</h1><p>{error}</p><div className="button-row"><Button onClick={() => void load()}>Retry</Button>{permissionError && <Button variant="secondary" onClick={() => void reconnectGoogle()}>Reconnect Google</Button>}</div><p className="support-copy">If retry and reconnect do not work, contact the person running this app and mention that onboarding could not load. Do not send them your Google password.</p></section>

  return <section className="onboarding-page ambient-surface" aria-labelledby="onboarding-title"><AmbientBackground variant="onboarding" /><header><p className="eyebrow">A two-minute setup</p><h1 id="onboarding-title">Make your workspace relevant</h1><p>Step {step} of 2 · Your progress is kept in this browser tab if you refresh.</p><div className="onboarding-progress" aria-hidden="true"><span className={step >= 1 ? 'complete' : ''} /><span className={step >= 2 ? 'complete' : ''} /></div></header>
    <form onSubmit={submit} noValidate>
      {step === 1 ? <section className="onboarding-step" aria-labelledby="context-title"><div><h2 id="context-title">Academic context</h2><p>Section and lab group help hide notices meant for other students. Leave either blank if your course does not use it.</p></div><div className="onboarding-fields"><Field label="Section" hint="Optional · for example, A">{({ id, describedBy }) => <Input id={id} aria-describedby={describedBy} maxLength={64} value={section} onChange={(event) => setSection(event.target.value)} autoComplete="off" />}</Field><Field label="Lab group" hint="Optional · for example, 2">{({ id, describedBy }) => <Input id={id} aria-describedby={describedBy} maxLength={64} value={labGroup} onChange={(event) => setLabGroup(event.target.value)} autoComplete="off" />}</Field><Field label="Timezone" hint="Used to place deadlines on the correct day" error={timezoneError} required>{({ id, describedBy }) => <Input id={id} aria-describedby={describedBy} aria-invalid={Boolean(timezoneError)} required maxLength={64} value={timezone} onChange={(event) => { setTimezone(event.target.value); if (timezoneError) setTimezoneError('') }} placeholder="Asia/Dhaka" />}</Field></div><div className="onboarding-actions"><Button type="button" onClick={continueSetup}>Continue to courses</Button></div></section>
      : <section className="onboarding-step" aria-labelledby="courses-title"><div><h2 id="courses-title">Courses and reminders</h2><p>Select only the courses you want in your workspace. You can change notification preferences later.</p></div><fieldset className="course-picker"><legend>Classroom courses <span>{selectedCount} selected</span></legend>{courses.length === 0 ? <p>No Classroom courses are available. You can still finish setup and reconnect later.</p> : courses.map((course) => <Checkbox key={course.id} label={course.name} checked={course.selected} onChange={(event) => setCourses((current) => current.map((item) => item.id === course.id ? { ...item, selected: event.target.checked } : item))} />)}</fieldset><Switch label="Academic reminders" description="Receive relevant assignment, exam, and notice reminders." checked={notifications} onChange={setNotifications} /><div className="onboarding-actions"><Button type="button" variant="ghost" onClick={() => setStep(1)}>Back</Button><Button type="submit" loading={busy}>Save and open dashboard</Button></div></section>}
      {error && <div className="auth-error" role="alert"><strong>Setup was not saved</strong><p>{error}</p>{permissionError && <Button type="button" variant="secondary" onClick={() => void reconnectGoogle()}>Reconnect Google access</Button>}<p className="support-copy">Your entries are still here. Retry when ready; if the error continues, contact the person running this app.</p></div>}
    </form>
  </section>
}

