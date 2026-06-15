import { useEffect, useRef, useState } from 'react'

interface AnimatedNumberProps {
  value: number
  format?: (value: number) => string
  duration?: number
  delay?: number
  className?: string
}

const defaultFormat = (value: number) => Math.round(value).toLocaleString('ja-JP')

export default function AnimatedNumber({
  value,
  format = defaultFormat,
  duration = 680,
  delay = 0,
  className,
}: AnimatedNumberProps) {
  const elementRef = useRef<HTMLSpanElement>(null)
  const currentValue = useRef(0)
  const [displayValue, setDisplayValue] = useState(0)
  const [active, setActive] = useState(false)

  useEffect(() => {
    const element = elementRef.current
    if (!element) return

    let observer: IntersectionObserver | undefined
    const observe = () => {
      if (!('IntersectionObserver' in window)) {
        setActive(true)
        return
      }
      observer = new IntersectionObserver(
        ([entry]) => {
          if (!entry.isIntersecting) return
          setActive(true)
          observer?.disconnect()
        },
        { threshold: 0.2, rootMargin: '0px 0px -5% 0px' },
      )
      observer.observe(element)
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

  useEffect(() => {
    if (!active) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      currentValue.current = value
      setDisplayValue(value)
      return
    }

    let frame = 0
    let startTime = 0
    const startValue = currentValue.current
    const difference = value - startValue
    const tick = (time: number) => {
      if (!startTime) startTime = time
      const elapsed = Math.max(0, time - startTime - delay)
      const progress = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      const nextValue = startValue + difference * eased
      currentValue.current = nextValue
      setDisplayValue(nextValue)
      if (progress < 1) {
        frame = window.requestAnimationFrame(tick)
      } else {
        currentValue.current = value
        setDisplayValue(value)
      }
    }

    frame = window.requestAnimationFrame(tick)
    return () => window.cancelAnimationFrame(frame)
  }, [active, delay, duration, value])

  return (
    <span ref={elementRef} className={className}>
      {format(active ? displayValue : 0)}
    </span>
  )
}
