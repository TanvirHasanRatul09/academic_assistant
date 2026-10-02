import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'

import { createPersonalTask, deletePersonalTask, getPersonalTasks, updatePersonalTask, type DashboardData, type DashboardEventType, type PersonalTask, type PersonalTaskInput } from '../api'
import { Button, Dialog, Field, Select } from './ui'

const emptyTask: PersonalTaskInput = { title: '', details: null, course_id: null, event_type: 'assignment', starts_at: null, due_at: null, priority: 1, section: null, lab_group: null, completed: false }

function localInput(value: string | null): string {
  if (!value) return ''
  const date = new Date(value)
  const offset = date.getTimezoneOffset() * 60000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}

function iso(value: string): string | null { return value ? new Date(value).toISOString() : null }

export function PersonalTasksPanel({ courses, onChanged }: { courses: DashboardData['courses']; onChanged?: () => void | Promise<void> }) {
  const [tasks, setTasks] = useState<PersonalTask[]>([])
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<PersonalTask | null>(null)
  const [form, setForm] = useState<PersonalTaskInput>(emptyTask)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [dateError, setDateError] = useState('')

  async function load() {
    try { setTasks(await getPersonalTasks()) } catch (caught) { setError(caught instanceof Error ? caught.message : 'Could not load personal tasks.') }
  }
  useEffect(() => { void load() }, [])

  function show(task?: PersonalTask) {
    setEditing(task ?? null)
    setForm(task ? { title: task.title, details: task.details, course_id: task.course_id, event_type: task.event_type, starts_at: task.starts_at, due_at: task.due_at, priority: task.priority, section: task.section, lab_group: task.lab_group, completed: task.completed } : emptyTask)
    setError(''); setDateError(''); setOpen(true)
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    setError('')
    if (form.starts_at && form.due_at && new Date(form.due_at) < new Date(form.starts_at)) {
      setDateError('Due date and time cannot be earlier than the start date and time.')
      return
    }
    setDateError('')
    setBusy(true)
    try {
      const payload = { ...form, title: form.title.trim(), details: form.details?.trim() || null }
      if (editing) await updatePersonalTask(editing.id, payload); else await createPersonalTask(payload)
      setOpen(false); await load(); await onChanged?.()
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Could not save this task.') } finally { setBusy(false) }
  }

  async function toggle(task: PersonalTask) { setBusy(true); try { await updatePersonalTask(task.id, { completed: !task.completed }); await load(); await onChanged?.() } finally { setBusy(false) } }
  async function remove(task: PersonalTask) { if (!window.confirm(`Delete “${task.title}”?`)) return; setBusy(true); try { await deletePersonalTask(task.id); await load(); await onChanged?.() } finally { setBusy(false) } }

  return <section className="personal-tasks-panel" aria-labelledby="personal-tasks-title">
    <header><div><span className="personal-task-icon" aria-hidden="true">＋</span><div><p className="eyebrow">Personal tasks</p><h2 id="personal-tasks-title">Capture work outside Classroom</h2><p>Personal tasks join the dashboard feed and remain clearly labelled.</p></div></div><Button onClick={() => show()}>Add task</Button></header>
    {error && <p role="alert" className="error-panel">{error}</p>}
    {tasks.length === 0 ? <p className="personal-task-empty">No personal tasks yet. Add work announced in class when you need it.</p> : <details className="personal-task-manager"><summary><span>Manage added tasks</span><span>{tasks.length}</span></summary><div className="personal-task-list">{tasks.slice(0, 10).map((task) => <article key={task.id} className={task.completed ? 'is-completed' : ''}><div><span>Added by you</span><h3>{task.title}</h3><p>{task.course_name ?? 'Personal'}{task.due_at ? ` · ${new Date(task.due_at).toLocaleString()}` : ' · No due date'}</p></div><div><Button size="sm" variant="secondary" disabled={busy} onClick={() => void toggle(task)}>{task.completed ? 'Mark incomplete' : 'Complete'}</Button><Button size="sm" variant="ghost" disabled={busy} onClick={() => show(task)}>Edit</Button><Button size="sm" variant="danger" disabled={busy} onClick={() => void remove(task)}>Delete</Button></div></article>)}</div></details>}
    <Dialog open={open} onOpenChange={setOpen} title={editing ? 'Edit personal task' : 'Add personal task'} description="Use this for academic work announced outside Google Classroom.">
      <form id="personal-task-form" onSubmit={(event) => void save(event)}>
        <Field label="Title">{({ id }) => <input id={id} required maxLength={500} value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />}</Field>
        <Field label="Details">{({ id }) => <textarea id={id} maxLength={30000} value={form.details ?? ''} onChange={(event) => setForm({ ...form, details: event.target.value || null })} />}</Field>
        <Field label="Course">{({ id }) => <Select id={id} value={form.course_id ?? ''} onChange={(event) => setForm({ ...form, course_id: event.target.value || null })}><option value="">Personal / Other</option>{courses.map((course) => <option value={course.id} key={course.id}>{course.name}</option>)}</Select>}</Field>
        <Field label="Type">{({ id }) => <Select id={id} value={form.event_type} onChange={(event) => setForm({ ...form, event_type: event.target.value as DashboardEventType })}><option value="assignment">Assignment</option><option value="exam">Exam</option><option value="notice">Notice</option><option value="material">Material</option><option value="other">Other</option></Select>}</Field>
        <Field label="Starts">{({ id }) => <input id={id} type="datetime-local" max={localInput(form.due_at)} value={localInput(form.starts_at)} onChange={(event) => { setForm({ ...form, starts_at: iso(event.target.value) }); setDateError('') }} />}</Field>
        <Field label="Due" error={dateError}>{({ id, describedBy }) => <input id={id} type="datetime-local" min={localInput(form.starts_at)} value={localInput(form.due_at)} aria-invalid={Boolean(dateError)} aria-describedby={describedBy} onChange={(event) => { setForm({ ...form, due_at: iso(event.target.value) }); setDateError('') }} />}</Field>
        <Field label="Priority">{({ id }) => <Select id={id} value={String(form.priority)} onChange={(event) => setForm({ ...form, priority: Number(event.target.value) })}><option value="0">None</option><option value="1">Low</option><option value="2">Medium</option><option value="3">High</option></Select>}</Field>
        <div className="ui-dialog-footer"><Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button><Button type="submit" loading={busy} disabled={!form.title.trim()}>Save task</Button></div>
      </form>
    </Dialog>
  </section>
}
