import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { dismissNotification, getNotificationPreferences, getNotifications, markNotificationRead } from '../api'
import { NotificationsPage } from './NotificationsPage'

vi.mock('../api', async (importOriginal) => {
  const original = await importOriginal<typeof import('../api')>()
  return { ...original, dismissNotification: vi.fn(), getNotificationPreferences: vi.fn(), getNotifications: vi.fn(), markAllNotificationsRead: vi.fn(), markNotificationRead: vi.fn(), saveNotificationPreferences: vi.fn() }
})

const items = Array.from({ length: 6 }, (_, index) => ({
  id: 'n' + index,
  kind: 'task_changed',
  created_at: '2026-09-27T12:00:00Z',
  read_at: null,
  dismissed_at: null,
  task_id: 't' + index,
  title: 'Physics item ' + (index + 1),
  course_name: 'Physics',
  event_type: index === 0 ? 'exam' : 'assignment',
  priority: index === 0 ? 3 : 2,
  due_at: '2026-09-28T12:00:00Z',
  source_url: 'https://classroom.google.com/c/' + index,
}))

describe('F8 notification center', () => {
  beforeEach(() => {
    vi.mocked(getNotifications).mockResolvedValue({ items, unread_count: items.length })
    vi.mocked(getNotificationPreferences).mockResolvedValue({ assignments: true, exams: true, notices: true, minimum_priority: 2, courses: [{ id: 'c1', name: 'Physics', enabled: true }] })
  })
  afterEach(() => { cleanup(); vi.clearAllMocks() })

  it('groups noisy updates and expands them on demand', async () => {
    render(<MemoryRouter><NotificationsPage /></MemoryRouter>)
    expect(await screen.findByRole('heading', { name: 'Physics' })).toBeInTheDocument()
    expect(screen.getAllByRole('article')).toHaveLength(4)
    fireEvent.click(screen.getByRole('button', { name: 'Show 2 more' }))
    expect(screen.getAllByRole('article')).toHaveLength(6)
  })

  it('marks and dismisses alerts while retaining source actions', async () => {
    render(<MemoryRouter><NotificationsPage /></MemoryRouter>)
    const readButtons = await screen.findAllByRole('button', { name: 'Mark read' })
    fireEvent.click(readButtons[0]!)
    await waitFor(() => expect(markNotificationRead).toHaveBeenCalledWith('n0'))
    const dismissButtons = screen.getAllByRole('button', { name: 'Dismiss' })
    fireEvent.click(dismissButtons[0]!)
    await waitFor(() => expect(dismissNotification).toHaveBeenCalled())
    expect(screen.getAllByRole('link', { name: /Verify in Classroom/ })[0]!).toHaveAttribute('target', '_blank')
  })

  it('explains browser visibility and privacy before permission', async () => {
    render(<MemoryRouter><NotificationsPage /></MemoryRouter>)
    await screen.findByText(/Only relevant items/)
    expect(screen.getByText(/visible on your lock screen/)).toBeInTheDocument()
    expect(screen.getByText(/does not promise background delivery/)).toBeInTheDocument()
  })
})

