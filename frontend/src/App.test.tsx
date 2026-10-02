import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { App } from './App'

describe('App', () => {
  it('renders the accessible welcome heading', async () => {
    render(<App />)
    expect(await screen.findByRole('heading', { name: /without the noise/i })).toBeInTheDocument()
  })
})



