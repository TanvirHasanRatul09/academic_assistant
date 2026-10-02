import { cleanup, render } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { AmbientBackground } from './AmbientBackground'

describe('ambient background', () => {
  afterEach(cleanup)

  it('is decorative, inert, and supports restrained surface variants', () => {
    const { container } = render(<AmbientBackground variant="assistant" />)
    const background = container.firstElementChild
    expect(background).toHaveAttribute('aria-hidden', 'true')
    expect(background).toHaveClass('ambient-background-assistant')
    expect(background?.querySelectorAll('span')).toHaveLength(5)
  })
})
