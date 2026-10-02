import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

import { ApiError, beginGoogleAuth } from '../api'
import { WelcomePage } from './WelcomePage'

vi.mock('../api', async (importOriginal) => {
  const original = await importOriginal<typeof import('../api')>()
  return { ...original, beginGoogleAuth: vi.fn() }
})

describe('F4 welcome experience', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks() })

  it('explains permissions and privacy around one primary sign-in action', () => {
    render(<MemoryRouter><WelcomePage /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: /without the noise/i })).toBeInTheDocument()
    expect(screen.getByText(/read-only Classroom access/i)).toBeInTheDocument()
    expect(screen.getByText(/never asks for or stores your Google password/i)).toBeInTheDocument()
    expect(screen.getAllByRole('button')).toHaveLength(1)
  })

  it('gives actionable network recovery without collecting credentials', async () => {
    vi.mocked(beginGoogleAuth).mockRejectedValue(new ApiError('Network unavailable', 0))
    render(<MemoryRouter><WelcomePage /></MemoryRouter>)
    fireEvent.click(screen.getByRole('button', { name: 'Continue with Google' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/check your connection and try again/i)
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument()
  })
})
