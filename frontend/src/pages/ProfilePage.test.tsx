import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getProfile, saveProfile, type Profile } from '../api'
import { ProfilePage } from './ProfilePage'

vi.mock('../api', async (importOriginal) => {
  const original = await importOriginal<typeof import('../api')>()
  return { ...original, getProfile: vi.fn(), saveProfile: vi.fn() }
})

const profile: Profile = {
  user_id: 'u1', email: 'student@example.com', display_name: 'Student', onboarding_complete: true,
  academic_level: 'Third year', program: 'CSE', section: 'A', lab_group: 'A1', timezone: 'Asia/Dhaka',
  selected_course_ids: ['c1'], notification_preferences: { assignments: true, exams: true, notices: true },
  courses: [{ id: 'c1', name: 'CSE 3208', selected: true }, { id: 'c2', name: 'CSE 3210', selected: false }],
  classroom_connected: true, last_successful_sync_at: '2026-09-27T10:00:00Z',
}

describe('profile page', () => {
  beforeEach(() => { vi.mocked(getProfile).mockResolvedValue(profile); vi.mocked(saveProfile).mockResolvedValue(profile) })
  afterEach(() => { cleanup(); vi.clearAllMocks() })

  it('shows identity, connection, courses, and saves academic preferences', async () => {
    render(<ProfilePage />)
    expect(await screen.findByDisplayValue('student@example.com')).toBeInTheDocument()
    expect(screen.getByText('Connected')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Section'), { target: { value: ' B ' } })
    fireEvent.click(screen.getByLabelText(/CSE 3210/))
    fireEvent.click(screen.getByLabelText('Notices'))
    fireEvent.click(screen.getByRole('button', { name: 'Save profile' }))
    await waitFor(() => expect(saveProfile).toHaveBeenCalledWith(expect.objectContaining({ section: 'B', selected_course_ids: ['c1', 'c2'], notification_preferences: expect.objectContaining({ notices: false }) })))
  })
})
