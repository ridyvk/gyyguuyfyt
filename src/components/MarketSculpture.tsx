import { useEffect, useRef, useState } from 'react'
import type { BreadthCounts } from '../lib/marketBreadth'

/** The text/2D chart always works; WebGL progressively enhances the same counts. */
export default function MarketSculpture({ up, down, flat }: BreadthCounts) {
  const host = useRef<HTMLDivElement>(null)
  const [ready, setReady] = useState(false)
  const total = up + down + flat
  const upAngle = total ? (up / total) * 360 : 0
  const downAngle = total ? ((up + down) / total) * 360 : 0

  useEffect(() => {
    const element = host.current
    if (!element || !total) return
    if (!('IntersectionObserver' in window) || !('ResizeObserver' in window)) return
    const client = navigator as Navigator & { connection?: { saveData?: boolean; effectiveType?: string }; deviceMemory?: number }
    if (client.connection?.saveData || ['slow-2g', '2g'].includes(client.connection?.effectiveType ?? '') || (client.deviceMemory ?? 4) <= 2) return
    let cancelled = false
    let dispose: (() => void) | undefined
    let started = false
    let onscreen = false
    let idle = 0
    let timer = 0
    setReady(false)
    const start = async () => {
      if (started || !onscreen || document.documentElement.dataset.motion === 'reduce' || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
      started = true
      try {
        const { createMarketScene } = await import('../lib/marketScene')
        if (cancelled) return
        dispose = createMarketScene(element, { up, down, flat }, (rendered) => {
          if (!cancelled) setReady(rendered)
        })
      } catch {
        // A blocked download or unsupported GPU keeps the complete 2D chart.
      }
    }
    const schedule = () => {
      if (!onscreen || started || idle || timer) return
      if (typeof window.requestIdleCallback === 'function') {
        idle = window.requestIdleCallback(() => { idle = 0; void start() }, { timeout: 1600 })
      } else {
        timer = window.setTimeout(() => { timer = 0; void start() }, 350)
      }
    }
    const observer = new IntersectionObserver(([entry]) => {
      onscreen = entry.isIntersecting
      if (onscreen) schedule()
    }, { rootMargin: '80px' })
    observer.observe(element)
    window.addEventListener('delta-motion-change', schedule)
    return () => {
      cancelled = true
      observer.disconnect()
      window.removeEventListener('delta-motion-change', schedule)
      if (idle) window.cancelIdleCallback(idle)
      window.clearTimeout(timer)
      dispose?.()
    }
  }, [up, down, flat, total])

  return (
    <div className={`market-sculpture${ready ? ' is-ready' : ''}`} aria-hidden="true">
      <div className="market-sculpture__fallback" style={{
        background: total
          ? `conic-gradient(#86ad95 0deg ${upAngle}deg, #c99c8c ${upAngle}deg ${downAngle}deg, #bcc9be ${downAngle}deg 360deg)`
          : '#dce3db',
      }} />
      <div ref={host} className="market-sculpture__canvas" />
    </div>
  )
}
