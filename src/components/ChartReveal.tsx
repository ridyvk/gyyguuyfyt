import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'

interface ChartRevealProps {
  children: ReactNode
  className?: string
}

export default function ChartReveal({
  children,
  className = '',
}: ChartRevealProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    let observer: IntersectionObserver | undefined
    const observe = () => {
      if (!('IntersectionObserver' in window)) {
        setVisible(true)
        return
      }

      observer = new IntersectionObserver(
        ([entry]) => {
          if (!entry.isIntersecting) return
          setVisible(true)
          observer?.disconnect()
        },
        { threshold: 0.18, rootMargin: '0px 0px -8% 0px' },
      )
      observer.observe(container)
    }

    if (document.body.classList.contains('startup-active')) {
      window.addEventListener('kpi-startup-complete', observe, { once: true })
    } else {
      observe()
    }

    return () => {
      window.removeEventListener('kpi-startup-complete', observe)
      observer?.disconnect()
    }
  }, [])

  return (
    <div
      ref={containerRef}
      className={`chart-reveal${visible ? ' is-visible' : ''}${className ? ` ${className}` : ''}`}
    >
      {visible ? children : null}
    </div>
  )
}
