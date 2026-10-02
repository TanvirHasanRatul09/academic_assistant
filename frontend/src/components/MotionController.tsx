import { useEffect } from 'react'

export function MotionController() {
  useEffect(() => {
    const root = document.documentElement
    const finePointer = window.matchMedia?.('(hover: hover) and (pointer: fine)')
    const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    let animationFrame = 0
    let pointerX = 0
    let pointerY = 0

    const updateVisibility = () => root.classList.toggle('motion-paused', document.hidden)
    const resetPointer = () => {
      root.style.removeProperty('--ambient-pointer-x')
      root.style.removeProperty('--ambient-pointer-y')
    }
    const paintPointer = () => {
      animationFrame = 0
      root.style.setProperty('--ambient-pointer-x', pointerX.toFixed(2))
      root.style.setProperty('--ambient-pointer-y', pointerY.toFixed(2))
    }
    const handlePointer = (event: PointerEvent) => {
      if (document.hidden || !finePointer?.matches || reducedMotion?.matches) return
      pointerX = ((event.clientX / Math.max(window.innerWidth, 1)) - .5) * 2
      pointerY = ((event.clientY / Math.max(window.innerHeight, 1)) - .5) * 2
      if (!animationFrame) animationFrame = window.requestAnimationFrame(paintPointer)
    }
    const updatePointerCapability = () => {
      const enabled = Boolean(finePointer?.matches && !reducedMotion?.matches)
      root.classList.toggle('motion-pointer-capable', enabled)
      if (!enabled) resetPointer()
    }

    updateVisibility()
    updatePointerCapability()
    document.addEventListener('visibilitychange', updateVisibility)
    window.addEventListener('pointermove', handlePointer, { passive: true })
    finePointer?.addEventListener?.('change', updatePointerCapability)
    reducedMotion?.addEventListener?.('change', updatePointerCapability)
    return () => {
      document.removeEventListener('visibilitychange', updateVisibility)
      window.removeEventListener('pointermove', handlePointer)
      finePointer?.removeEventListener?.('change', updatePointerCapability)
      reducedMotion?.removeEventListener?.('change', updatePointerCapability)
      if (animationFrame) window.cancelAnimationFrame(animationFrame)
      root.classList.remove('motion-paused', 'motion-pointer-capable')
      resetPointer()
    }
  }, [])
  return null
}
