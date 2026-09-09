import { useEffect, useRef, type PointerEvent, type ReactNode, type TouchEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useReducedMotion } from '../lib/useReducedMotion'
import { swipeDestination } from '../lib/swipeNavigation'

const revealTargets = '.page > section, .page > article, .page > details, .delta-page-header, .summary-card, .market-pulse__item, .disclosure-card'
const gestureExclusions = 'a, button, input, textarea, select, summary, [contenteditable], [data-no-swipe], table, .chart-wrap, .market-pulse__grid, .market-sculpture, .theme-chart'

export default function PageMotion({ children }: { children: ReactNode }) {
  const root = useRef<HTMLDivElement>(null)
  const animations = useRef(new Set<Animation>())
  const gesture = useRef<{ x: number; y: number; time: number } | null>(null)
  const reduced = useReducedMotion()
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => {
    const element = root.current
    if (!element || reduced || !('IntersectionObserver' in window) || !Element.prototype.animate) return
    const running = animations.current
    const seen = new WeakSet<Element>()
    let frame = 0
    const observer = new IntersectionObserver((entries) => {
      let order = 0
      for (const entry of entries) {
        if (!entry.isIntersecting) continue
        observer.unobserve(entry.target)
        if (entry.target.contains(document.activeElement)) continue
        const compact = entry.target.matches('.summary-card, .market-pulse__item')
        const animation = entry.target.animate([
          { opacity: .25, transform: compact ? 'translateY(10px) scale(.965)' : 'translateY(18px)' },
          { opacity: 1, transform: 'translateY(0) scale(1)' },
        ], { duration: compact ? 520 : 640, delay: Math.min(order++ * 45, 135), easing: 'cubic-bezier(.2,.75,.2,1)' })
        running.add(animation)
        void animation.finished.catch(() => {}).finally(() => running.delete(animation))
      }
    }, { threshold: 0, rootMargin: '0px 0px -5% 0px' })
    const discover = () => {
      frame = 0
      element.querySelectorAll(revealTargets).forEach((node) => {
        if (seen.has(node)) return
        seen.add(node)
        observer.observe(node)
      })
    }
    discover()
    const mutations = new MutationObserver(() => {
      if (!frame) frame = requestAnimationFrame(discover)
    })
    mutations.observe(element, { childList: true, subtree: true })
    return () => {
      observer.disconnect()
      mutations.disconnect()
      cancelAnimationFrame(frame)
      running.forEach((animation) => animation.cancel())
      running.clear()
    }
  }, [reduced])

  const press = (event: PointerEvent<HTMLDivElement>) => {
    if (reduced || !event.isPrimary || event.button !== 0 || !Element.prototype.animate) return
    const target = (event.target as Element).closest('button:not(:disabled), a, summary')
    if (!target) return
    const animation = target.animate([
      { scale: '1' }, { scale: '.965', offset: .35 }, { scale: '1' },
    ], { duration: 280, easing: 'cubic-bezier(.2,.7,.3,1)' })
    animations.current.add(animation)
    void animation.finished.catch(() => {}).finally(() => animations.current.delete(animation))
  }
  const resetGesture = () => {
    gesture.current = null
    root.current?.style.removeProperty('--swipe-shift')
  }
  const touchStart = (event: TouchEvent<HTMLDivElement>) => {
    resetGesture()
    const touch = event.touches[0]
    if (event.touches.length !== 1 || touch.clientX < 28 || touch.clientX > window.innerWidth - 28 || (event.target as Element).closest(gestureExclusions) || window.getSelection()?.type === 'Range') return
    gesture.current = { x: touch.clientX, y: touch.clientY, time: performance.now() }
  }
  const touchMove = (event: TouchEvent<HTMLDivElement>) => {
    const start = gesture.current
    if (!start) return
    if (event.touches.length !== 1) { resetGesture(); return }
    const dx = event.touches[0].clientX - start.x
    const dy = event.touches[0].clientY - start.y
    if (Math.abs(dy) > 24) { resetGesture(); return }
    if (!reduced && Math.abs(dx) > 18 && Math.abs(dx) > Math.abs(dy) * 2.2) {
      root.current?.style.setProperty('--swipe-shift', `${Math.max(-12, Math.min(12, dx * .08))}px`)
    }
  }
  const touchEnd = (event: TouchEvent<HTMLDivElement>) => {
    const start = gesture.current
    if (start && event.changedTouches.length === 1) {
      const touch = event.changedTouches[0]
      const destination = swipeDestination(location.pathname, touch.clientX - start.x, touch.clientY - start.y, performance.now() - start.time)
      if (destination) navigate(destination.path, { state: { deltaDirection: destination.direction } })
    }
    resetGesture()
  }
  return <div ref={root} className="route-transition" data-direction={location.state?.deltaDirection === -1 ? 'back' : 'forward'} onPointerDownCapture={press} onTouchStartCapture={touchStart} onTouchMove={touchMove} onTouchEnd={touchEnd} onTouchCancel={resetGesture}>{children}</div>
}
