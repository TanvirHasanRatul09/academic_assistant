import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { InstallExperience, type BeforeInstallPromptEvent } from './InstallExperience'

function installEvent(outcome: 'accepted' | 'dismissed' = 'accepted') {
  const event = new Event('beforeinstallprompt', { cancelable: true }) as BeforeInstallPromptEvent
  event.prompt = vi.fn().mockResolvedValue(undefined)
  event.userChoice = Promise.resolve({ outcome, platform: 'web' })
  return event
}

describe('F7 install experience', () => {
  beforeEach(() => sessionStorage.clear())
  afterEach(() => { cleanup(); sessionStorage.clear() })

  it('offers a lightweight install action and invokes the browser prompt', async () => {
    render(<InstallExperience />)
    const event = installEvent()
    window.dispatchEvent(event)
    fireEvent.click(await screen.findByRole('button', { name: 'Install app' }))
    expect(event.prompt).toHaveBeenCalledOnce()
    await waitFor(() => expect(screen.queryByText('Install Academic Assistant')).not.toBeInTheDocument())
  })

  it('keeps a dismissal for the current browser session', async () => {
    render(<InstallExperience />)
    window.dispatchEvent(installEvent())
    fireEvent.click(await screen.findByRole('button', { name: 'Not now' }))
    expect(sessionStorage.getItem('academic-assistant-install-dismissed')).toBe('true')
    expect(screen.queryByText('Install Academic Assistant')).not.toBeInTheDocument()
  })
})
