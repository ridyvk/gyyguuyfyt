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
    let cancelled = false
    let dispose: (() => void) | undefined
    let started = false
    setReady(false)
    const start = async () => {
      if (started) return
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
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        observer.disconnect()
        void start()
      }
    }, { rootMargin: '80px' })
    observer.observe(element)
    return () => {
      cancelled = true
      observer.disconnect()
      dispose?.()
    }
  }, [up, down, flat, total])

  return (
    <div className={`market-sculpture${ready ? ' is-ready' : ''}`} aria-hidden="true">
      <div className="market-sculpture__fallback" style={{
        background: total
          ? `conic-gradient(#26847c 0deg ${upAngle}deg, #c27687 ${upAngle}deg ${downAngle}deg, #a6b7cf ${downAngle}deg 360deg)`
          : '#cdd8e5',
      }} />
      <div ref={host} className="market-sculpture__canvas" />
    </div>
  )
}
