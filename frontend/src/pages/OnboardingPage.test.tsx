import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { ApiError, getCourses, getProfile, saveProfile } from '../api'
import { OnboardingPage } from './OnboardingPage'

vi.mock('../api', async (importOriginal) => {
  const original = await importOriginal<typeof import('../api')>()
  return { ...original, getCourses: vi.fn(), getProfile: vi.fn(), reconnectGoogle: vi.fn(), saveProfile: vi.fn() }
})

const profile = { user_id: 'u1', email: 'student@example.com', display_name: 'Student', onboarding_complete: false, section: null, lab_group: null, timezone: 'Asia/Dhaka', selected_course_ids: [], notification_preferences: { assignments: true } }

function renderOnboarding() {
  return render(<MemoryRouter initialEntries={['/onboarding']}><Routes><Route path="/onboarding" element={<OnboardingPage />} /><Route path="/dashboard" element={<h1>Dashboard destination</h1>} /></Routes></MemoryRouter>)
}

describe('F4 onboarding', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.mocked(getProfile).mockResolvedValue(profile)
    vi.mocked(getCourses).mockResolvedValue([{ id: 'c1', name: 'Physics', selected: true }])
    vi.mocked(saveProfile).mockResolvedValue({ ...profile, onboarding_complete: true })
  })
  afterEach(() => { cleanup(); vi.clearAllMocks(); sessionStorage.clear() })

  it('redirects a returning user who already completed onboarding', async () => {
    vi.mocked(getProfile).mockResolvedValue({ ...profile, onboarding_complete: true })
    renderOnboarding()
    expect(await screen.findByRole('heading', { name: 'Dashboard destination' })).toBeInTheDocument()
  })

  it('validates inline and preserves entries after a recoverable save error', async () => {
    vi.mocked(saveProfile).mockRejectedValue(new ApiError('Network unavailable', 0))
    renderOnboarding()
    const timezone = await screen.findByLabelText(/timezone/i)
    fireEvent.change(screen.getByLabelText('Section'), { target: { value: 'B' } })
    fireEvent.change(timezone, { target: { value: 'not-a-timezone' } })
    fireEvent.click(screen.getByRole('button', { name: /continue to courses/i }))
    expect(screen.getByRole('alert')).toHaveTextContent(/valid IANA timezone/i)
    fireEvent.change(timezone, { target: { value: 'Asia/Dhaka' } })
    fireEvent.click(screen.getByRole('button', { name: /continue to courses/i }))
    fireEvent.click(await screen.findByRole('button', { name: /save and open dashboard/i }))
    expect(await screen.findByText(/entries are still here/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Back' }))
    expect(screen.getByLabelText('Section')).toHaveValue('B')
  })

  it('resumes a saved browser-tab draft', async () => {
    sessionStorage.setItem('academic-assistant-onboarding-draft', JSON.stringify({ section: 'C', labGroup: '4', timezone: 'UTC', notifications: false, selectedCourseIds: [], step: 2 }))
    renderOnboarding()
    expect(await screen.findByRole('heading', { name: /courses and reminders/i })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Back' }))
    await waitFor(() => expect(screen.getByLabelText('Section')).toHaveValue('C'))
    expect(screen.getByLabelText('Lab group')).toHaveValue('4')
  })
})
