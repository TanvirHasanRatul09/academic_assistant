import { cleanup, render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MotionController } from './MotionController'

describe('F9 motion controller', () => {
  afterEach(() => {
    cleanup()
    document.documentElement.classList.remove('motion-paused')
    document.documentElement.classList.remove('motion-pointer-capable')
    document.documentElement.style.removeProperty('--ambient-pointer-x')
    document.documentElement.style.removeProperty('--ambient-pointer-y')
    Object.defineProperty(document, 'hidden', { configurable: true, value: false })
    vi.unstubAllGlobals()
  })

  it('pauses continuous animation when the document is hidden', () => {
    Object.defineProperty(document, 'hidden', { configurable: true, value: false })
    render(<MotionController />)
    expect(document.documentElement).not.toHaveClass('motion-paused')

    Object.defineProperty(document, 'hidden', { configurable: true, value: true })
    document.dispatchEvent(new Event('visibilitychange'))
    expect(document.documentElement).toHaveClass('motion-paused')

    Object.defineProperty(document, 'hidden', { configurable: true, value: false })
    document.dispatchEvent(new Event('visibilitychange'))
    expect(document.documentElement).not.toHaveClass('motion-paused')
  })

  it('throttles fine-pointer parallax and removes its state on cleanup', () => {
    const queries = new Map<string, MediaQueryList>([
      ['(hover: hover) and (pointer: fine)', { matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() } as unknown as MediaQueryList],
      ['(prefers-reduced-motion: reduce)', { matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() } as unknown as MediaQueryList],
    ])
    vi.stubGlobal('matchMedia', (query: string) => queries.get(query))
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { callback(0); return 1 })
    vi.stubGlobal('cancelAnimationFrame', vi.fn())

    const view = render(<MotionController />)
    window.dispatchEvent(new PointerEvent('pointermove', { clientX: window.innerWidth, clientY: window.innerHeight }))

    expect(document.documentElement).toHaveClass('motion-pointer-capable')
    expect(document.documentElement.style.getPropertyValue('--ambient-pointer-x')).toBe('1.00')
    expect(document.documentElement.style.getPropertyValue('--ambient-pointer-y')).toBe('1.00')

    view.unmount()
    expect(document.documentElement).not.toHaveClass('motion-pointer-capable')
    expect(document.documentElement.style.getPropertyValue('--ambient-pointer-x')).toBe('')
  })
})
