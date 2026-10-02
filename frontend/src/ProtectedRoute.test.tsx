import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, getCurrentUser } from './api'
import { ProtectedRoute } from './components/ProtectedRoute'
import { clearOfflineData, getCachedSessionUser } from './offline'

vi.mock('./api', async (importOriginal) => {
  const original = await importOriginal<typeof import('./api')>()
  return { ...original, getCurrentUser: vi.fn() }
})
vi.mock('./offline', () => ({
  clearOfflineData: vi.fn(),
  getCachedSessionUser: vi.fn(),
  setActiveOfflineUser: vi.fn(),
}))

function renderProtected() {
  render(
    <MemoryRouter initialEntries={['/private']}>
      <Routes>
        <Route path="/" element={<p>Signed out</p>} />
        <Route path="/private" element={<ProtectedRoute><p>Private</p></ProtectedRoute>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('authenticated contact and offline data', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(clearOfflineData).mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
  })

  it('clears local academic data when the server says the account no longer exists', async () => {
    vi.mocked(getCurrentUser).mockRejectedValue(new ApiError('Authentication required', 401))
    renderProtected()
    await waitFor(() => expect(clearOfflineData).toHaveBeenCalledOnce())
    expect(await screen.findByText('Signed out')).toBeInTheDocument()
  })

  it('keeps and uses the current account snapshot only while genuinely offline', async () => {
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false })
    vi.mocked(getCurrentUser).mockRejectedValue(new ApiError('Network unavailable', 0))
    vi.mocked(getCachedSessionUser).mockResolvedValue({
      id: 'user-1', email: 'student@example.test', display_name: 'Student', onboarding_complete: true,
    })
    renderProtected()
    expect(await screen.findByText('Private')).toBeInTheDocument()
    expect(clearOfflineData).not.toHaveBeenCalled()
  })
})

