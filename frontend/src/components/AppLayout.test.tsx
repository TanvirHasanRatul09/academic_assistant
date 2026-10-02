import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { AppLayout } from './AppLayout'

const api = vi.hoisted(() => ({
  getShell: vi.fn(), logout: vi.fn(), synchronize: vi.fn(),
}))

vi.mock('../api', async (importOriginal) => {
  const original = await importOriginal<typeof import('../api')>()
  return { ...original, ...api }
})

function renderShell(path = '/dashboard') {
  return render(<MemoryRouter initialEntries={[path]}><Routes><Route element={<AppLayout />}><Route path="dashboard" element={<h1>Dashboard content</h1>} /><Route path="assistant" element={<h1>Assistant content</h1>} /><Route path="notifications" element={<h1>Notifications content</h1>} /><Route path="settings" element={<h1>Settings content</h1>} /></Route></Routes></MemoryRouter>)
}

describe('F3 application shell', () => {
  beforeEach(() => {
    api.getShell.mockResolvedValue({ user: { id: 'user-1', email: 'student@example.com', display_name: 'Student Name', onboarding_complete: true }, unread_notification_count: 4, latest_sync: null })
    api.synchronize.mockResolvedValue({ id: 'sync-1', status: 'succeeded', started_at: '2026-09-27T00:00:00Z', finished_at: '2026-09-27T00:01:00Z', items_seen: 12, items_changed: 2, safe_error_code: null })
    api.logout.mockResolvedValue(undefined)
  })
  afterEach(() => { cleanup(); vi.clearAllMocks() })

  it('shows landmarks, current navigation, unread state, and account actions', async () => {
    renderShell()
    const desktop = await screen.findByRole('navigation', { name: 'Primary navigation' })
    expect(within(desktop).getByRole('link', { name: 'Dashboard' })).toHaveAttribute('aria-current', 'page')
    expect(within(desktop).getByLabelText('4 unread notifications')).toBeInTheDocument()
    expect(screen.getByRole('main')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveAttribute('href', '#main-content')
    const accountTrigger = screen.getByLabelText('Open account menu')
    const accountMenu = accountTrigger.closest('details')!
    accountMenu.open = true
    accountTrigger.focus()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(accountMenu).not.toHaveAttribute('open')
    expect(accountTrigger).toHaveFocus()
    expect(screen.getAllByRole('link', { name: 'Settings' })).toHaveLength(2)
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument()
  })

  it('keeps all compact navigation destinations keyboard-focusable', async () => {
    renderShell('/assistant')
    const mobile = await screen.findByRole('navigation', { name: 'Mobile navigation' })
    const links = within(mobile).getAllByRole('link')
    expect(links).toHaveLength(5)
    for (const link of links) {
      link.focus()
      expect(link).toHaveFocus()
    }
    expect(within(mobile).getByRole('link', { name: /assistant/i })).toHaveAttribute('aria-current', 'page')
  })

  it('prevents repeated synchronization and explains the cooldown', async () => {
    renderShell()
    const sync = await screen.findByRole('button', { name: 'Sync now' })
    fireEvent.click(sync)
    await waitFor(() => expect(api.synchronize).toHaveBeenCalledTimes(1))
    const coolingDown = await screen.findByRole('button', { name: /wait 30s/i })
    expect(coolingDown).toBeDisabled()
    fireEvent.click(coolingDown)
    expect(api.synchronize).toHaveBeenCalledTimes(1)
    expect(screen.getByText(/synchronize again in 30 seconds/i)).toBeInTheDocument()
  })
})



