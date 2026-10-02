import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, getDashboard, updateTaskState, type DashboardData, type DashboardItem } from '../api'
import { getOfflineConflicts, getOfflineStorageStatus, removeOfflineConflict, removeQueuedTaskUpdate } from '../offline'
import { DashboardPage } from './DashboardPage'

vi.mock('../api', async (importOriginal) => {
  const original = await importOriginal<typeof import('../api')>()
  return { ...original, getCurrentUser: vi.fn(), getDashboard: vi.fn(), getSyncStatus: vi.fn().mockResolvedValue({ latest: null }), synchronize: vi.fn(), updateTaskState: vi.fn(), getPersonalTasks: vi.fn().mockResolvedValue([]), createPersonalTask: vi.fn(), updatePersonalTask: vi.fn(), deletePersonalTask: vi.fn() }
})
vi.mock('../offline', () => ({
  applyTaskStateToSnapshot: vi.fn(), cacheDashboardSnapshot: vi.fn(), getCachedSessionUser: vi.fn().mockResolvedValue({ id: 'u1' }), getOfflineStorageStatus: vi.fn().mockResolvedValue({ userId: 'u1', cachedAt: null, lastSuccessfulSyncAt: null, queuedChanges: 0, conflicts: 0 }), getOfflineConflicts: vi.fn().mockResolvedValue([]), getQueuedTaskUpdates: vi.fn().mockResolvedValue([]), queryOfflineDashboard: vi.fn(), queueTaskUpdate: vi.fn(), removeOfflineConflict: vi.fn(), removeQueuedTaskUpdate: vi.fn(), saveOfflineConflict: vi.fn(),
}))

function task(overrides: Partial<DashboardItem> = {}): DashboardItem {
  return { task_id: 't1', event_id: 'e1', course_id: 'c1', course_name: 'Physics', title: 'Lab report', body: null, source_type: 'coursework', source_url: 'https://classroom.google.com/example', source_created_at: new Date().toISOString(), source_updated_at: new Date().toISOString(), event_type: 'exam', starts_at: null, due_at: new Date(Date.now() + 2 * 86400000).toISOString(), priority: 3, action_required: true, confidence: .9, review_required: false, manually_corrected: false, relevant: true, completed: false, acknowledged: false, read: true, task_updated_at: new Date().toISOString(), targets: [{ section: null, lab_group: null, course_wide: true }], source_kind: 'classroom', ...overrides }
}
const data: DashboardData = { generated_at: new Date().toISOString(), timezone: 'Asia/Dhaka', courses: [{ id: 'c1', name: 'Physics' }], items: [task()] }

describe('F5 dashboard experience', () => {
  beforeEach(() => {
    sessionStorage.clear(); window.history.replaceState(null, '', '/dashboard')
    vi.mocked(getDashboard).mockResolvedValue(data)
    vi.mocked(updateTaskState).mockResolvedValue({ completed: true, acknowledged: false, read: true, updated_at: new Date().toISOString() })
    vi.mocked(getOfflineConflicts).mockResolvedValue([])
    vi.mocked(getOfflineStorageStatus).mockResolvedValue({ userId: 'u1', cachedAt: null, lastSuccessfulSyncAt: null, queuedChanges: 0, conflicts: 0 })
  })
  afterEach(() => { cleanup(); vi.clearAllMocks(); sessionStorage.clear(); window.history.replaceState(null, '', '/') })

  it('syncs non-sensitive filter and layout preferences with the URL', async () => {
    window.history.replaceState(null, '', '/dashboard?view=all&type=exam&date=7days&layout=timeline')
    render(<DashboardPage />)
    expect(await screen.findByRole('heading', { name: 'Lab report' })).toBeInTheDocument()
    expect(screen.getByLabelText('Event type')).toHaveValue('exam')
    expect(screen.getByLabelText('Date')).toHaveValue('7days')
    expect(screen.getByRole('button', { name: /timeline/i })).toHaveAttribute('aria-pressed', 'true')
    expect(window.location.search).toContain('layout=timeline')
    expect(window.location.search).not.toContain('user')
  })

  it('filters the unified dashboard by source', async () => {
    render(<DashboardPage />)
    await screen.findByRole('heading', { name: 'Lab report' })
    fireEvent.change(screen.getByLabelText('Source'), { target: { value: 'manual' } })
    await waitFor(() => expect(getDashboard).toHaveBeenLastCalledWith(expect.objectContaining({ source: 'manual' })))
    expect(window.location.search).toContain('source=manual')
  })

  it('repairs an empty source parameter instead of sending an invalid filter', async () => {
    window.history.replaceState(null, '', '/dashboard?source=')
    render(<DashboardPage />)
    await screen.findByRole('heading', { name: 'Lab report' })
    expect(screen.getByLabelText('Source')).toHaveValue('all')
    await waitFor(() => expect(getDashboard).toHaveBeenLastCalledWith(expect.objectContaining({ source: 'all' })))
    expect(window.location.search).not.toContain('source=')
  })

  it('requires a plain user choice when an offline change conflicts with newer server data', async () => {
    vi.mocked(getOfflineStorageStatus).mockResolvedValue({ userId: 'u1', cachedAt: new Date().toISOString(), lastSuccessfulSyncAt: new Date().toISOString(), queuedChanges: 1, conflicts: 1 })
    vi.mocked(getOfflineConflicts).mockResolvedValue([{
      key: 'u1:t1',
      userId: 'u1',
      taskId: 't1',
      title: 'Lab report',
      courseName: 'Physics',
      patch: { completed: true },
      serverState: { completed: false, acknowledged: false, read: true, updated_at: new Date().toISOString() },
      detectedAt: new Date().toISOString(),
    }])
    render(<DashboardPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'Resolve conflicts' }))
    expect(screen.getByRole('heading', { name: 'Resolve offline change' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Keep server version' }))
    await waitFor(() => expect(removeOfflineConflict).toHaveBeenCalledWith('u1:t1'))
    expect(removeQueuedTaskUpdate).toHaveBeenCalledWith('u1:t1')
  })

  it('shows optimistic completion and rolls back safely after failure', async () => {
    vi.mocked(updateTaskState).mockRejectedValue(new ApiError('Could not save', 500))
    render(<DashboardPage />)
    const complete = await screen.findByRole('button', { name: 'Mark complete' })
    fireEvent.click(complete)
    expect(screen.getByText('✓ Completed')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Could not save'))
    expect(screen.getByRole('button', { name: 'Mark complete' })).toBeInTheDocument()
  })
})



