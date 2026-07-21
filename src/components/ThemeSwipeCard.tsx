import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  type TransitionEvent,
} from 'react'
import {
  applyDeltaTheme,
  getDeltaTheme,
  type DeltaTheme,
} from '../lib/theme'

type SwipeStage =
  | 'idle'
  | 'dragging'
  | 'settling'
  | 'exiting'
  | 'parked'
  | 'entering'

interface RestingGeometry {
  left: number
  width: number
}

interface ViewTransitionHandle {
  finished: Promise<void>
}

type ViewTransitionDocument = Document & {
  startViewTransition?: (update: () => void) => ViewTransitionHandle
}

const swipeThreshold = (width: number) => Math.min(150, width * 0.27)

export default function ThemeSwipeCard() {
  const cardRef = useRef<HTMLDivElement>(null)
  const activePointerRef = useRef<number | null>(null)
  const dragStartRef = useRef(0)
  const lastPointRef = useRef({ x: 0, time: 0 })
  const velocityRef = useRef(0)
  const offsetRef = useRef(0)
  const geometryRef = useRef<RestingGeometry>({ left: 0, width: 560 })
  const nextThemeRef = useRef<DeltaTheme>('light')
  const firstFrameRef = useRef<number | null>(null)
  const secondFrameRef = useRef<number | null>(null)
  const fallbackTimerRef = useRef<number | null>(null)
  const [theme, setTheme] = useState<DeltaTheme>(() => getDeltaTheme())
  const [stage, setStage] = useState<SwipeStage>('idle')
  const [offsetX, setOffsetX] = useState(0)

  const setCardOffset = useCallback((nextOffset: number) => {
    offsetRef.current = nextOffset
    setOffsetX(nextOffset)
  }, [])

  const readRestingGeometry = useCallback(() => {
    const rect = cardRef.current?.getBoundingClientRect()
    if (!rect) return geometryRef.current

    const geometry = {
      left: rect.left - offsetRef.current,
      width: rect.width,
    }
    geometryRef.current = geometry
    return geometry
  }, [])

  const beginEntry = useCallback(() => {
    const { left, width } = geometryRef.current
    setStage('parked')
    setCardOffset(-(left + width + 72))

    firstFrameRef.current = window.requestAnimationFrame(() => {
      secondFrameRef.current = window.requestAnimationFrame(() => {
        setStage('entering')
        setCardOffset(0)
      })
    })
  }, [setCardOffset])

  const commitTheme = useCallback(() => {
    const nextTheme = nextThemeRef.current
    const swapTheme = () => {
      applyDeltaTheme(nextTheme)
      setTheme(nextTheme)
    }
    const reducedMotion = window.matchMedia(
      '(prefers-reduced-motion: reduce)',
    ).matches
    const transitionDocument = document as ViewTransitionDocument

    if (!reducedMotion && transitionDocument.startViewTransition) {
      try {
        const transition = transitionDocument.startViewTransition(swapTheme)
        void transition.finished.then(beginEntry, beginEntry)
        return
      } catch {
        // Fall through to the same switch without the browser transition layer.
      }
    }

    swapTheme()
    fallbackTimerRef.current = window.setTimeout(beginEntry, 90)
  }, [beginEntry])

  const launchExit = useCallback(() => {
    if (stage === 'exiting' || stage === 'parked' || stage === 'entering') {
      return
    }

    const geometry = readRestingGeometry()
    nextThemeRef.current = theme === 'dark' ? 'light' : 'dark'
    setStage('exiting')
    setCardOffset(window.innerWidth - geometry.left + 96)
  }, [readRestingGeometry, setCardOffset, stage, theme])

  const settleCard = useCallback(() => {
    setStage('settling')
    setCardOffset(0)
  }, [setCardOffset])

  const handlePointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (stage !== 'idle' || (event.pointerType === 'mouse' && event.button !== 0)) {
      return
    }

    event.preventDefault()
    event.currentTarget.focus({ preventScroll: true })
    readRestingGeometry()
    activePointerRef.current = event.pointerId
    dragStartRef.current = event.clientX
    lastPointRef.current = { x: event.clientX, time: event.timeStamp }
    velocityRef.current = 0
    setStage('dragging')
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (
      stage !== 'dragging' ||
      activePointerRef.current !== event.pointerId
    ) return

    const rawOffset = event.clientX - dragStartRef.current
    const nextOffset = rawOffset >= 0 ? rawOffset : rawOffset * 0.08
    const elapsed = Math.max(1, event.timeStamp - lastPointRef.current.time)
    velocityRef.current = (event.clientX - lastPointRef.current.x) / elapsed
    lastPointRef.current = { x: event.clientX, time: event.timeStamp }
    setCardOffset(Math.min(nextOffset, window.innerWidth))
  }

  const finishPointerGesture = (
    event: ReactPointerEvent<HTMLDivElement>,
    cancelled = false,
  ) => {
    if (activePointerRef.current !== event.pointerId) return

    activePointerRef.current = null
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }

    const shouldExit =
      !cancelled &&
      (offsetRef.current >= swipeThreshold(geometryRef.current.width) ||
        (offsetRef.current > 42 && velocityRef.current > 0.62))

    if (shouldExit) launchExit()
    else settleCard()
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (
      stage === 'idle' &&
      (event.key === 'Enter' ||
        event.key === ' ' ||
        event.key === 'ArrowRight')
    ) {
      event.preventDefault()
      readRestingGeometry()
      launchExit()
    }
  }

  const handleTransitionEnd = (event: TransitionEvent<HTMLDivElement>) => {
    if (event.target !== event.currentTarget || event.propertyName !== 'transform') {
      return
    }

    if (stage === 'exiting') {
      setStage('parked')
      commitTheme()
    } else if (stage === 'entering' || stage === 'settling') {
      setStage('idle')
      setCardOffset(0)
    }
  }

  useEffect(() => () => {
    if (firstFrameRef.current !== null) {
      window.cancelAnimationFrame(firstFrameRef.current)
    }
    if (secondFrameRef.current !== null) {
      window.cancelAnimationFrame(secondFrameRef.current)
    }
    if (fallbackTimerRef.current !== null) {
      window.clearTimeout(fallbackTimerRef.current)
    }
  }, [])

  const rotation = Math.max(-1.5, Math.min(6, offsetX / 90))
  const cardStyle = {
    '--card-x': `${offsetX}px`,
    '--card-rotation': `${rotation}deg`,
    '--swipe-progress': Math.min(
      1,
      Math.max(0, offsetX / swipeThreshold(geometryRef.current.width)),
    ),
  } as CSSProperties
  const destinationLabel = theme === 'dark' ? '白へ' : 'ダークへ'

  return (
    <div
      ref={cardRef}
      className={`theme-swipe-card is-${stage}`}
      style={cardStyle}
      role="button"
      tabIndex={stage === 'idle' ? 0 : -1}
      aria-label={`カードを右へスライドして${destinationLabel}切り替える`}
      aria-describedby="delta-theme-card-help"
      data-theme-mode={theme}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={(event) => finishPointerGesture(event)}
      onPointerCancel={(event) => finishPointerGesture(event, true)}
      onKeyDown={handleKeyDown}
      onTransitionEnd={handleTransitionEnd}
    >
      <span className="theme-swipe-card__streak" aria-hidden="true" />
      <div className="theme-swipe-card__top">
        <span className="theme-swipe-card__mark">
          <img
            src="./delta-icon-192.png"
            alt=""
            width="48"
            height="48"
            draggable="false"
          />
        </span>
        <span className="theme-swipe-card__system">
          <small>DELTA / THEME ACCESS</small>
          <b>{theme === 'dark' ? 'DARK 01' : 'LIGHT 02'}</b>
        </span>
      </div>

      <div className="theme-swipe-card__visual" aria-hidden="true">
        <svg viewBox="0 0 520 220" role="presentation">
          <defs>
            <linearGradient id="themeCardSignal" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#315be5" stopOpacity="0.1" />
              <stop offset="44%" stopColor="#62a8ff" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#9fdcff" stopOpacity="0.28" />
            </linearGradient>
            <linearGradient id="themeCardArea" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#5b9fff" stopOpacity="0.24" />
              <stop offset="100%" stopColor="#5b9fff" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path className="theme-swipe-card__grid" d="M0 44H520M0 88H520M0 132H520M0 176H520M104 0V220M208 0V220M312 0V220M416 0V220" />
          <circle className="theme-swipe-card__orbit" cx="405" cy="102" r="78" />
          <circle className="theme-swipe-card__orbit theme-swipe-card__orbit--inner" cx="405" cy="102" r="47" />
          <path className="theme-swipe-card__area" d="M0 184 C48 178 75 152 113 159 S185 120 229 132 S297 81 345 94 S431 46 520 54 V220 H0 Z" />
          <path className="theme-swipe-card__signal" d="M0 184 C48 178 75 152 113 159 S185 120 229 132 S297 81 345 94 S431 46 520 54" />
          <g className="theme-swipe-card__nodes">
            <circle cx="113" cy="159" r="3.5" />
            <circle cx="229" cy="132" r="3.5" />
            <circle cx="345" cy="94" r="4" />
            <circle cx="520" cy="54" r="5" />
          </g>
        </svg>
      </div>

      <div className="theme-swipe-card__identity">
        <h1 id="delta-home-title">Delta</h1>
        <span>Company intelligence</span>
      </div>

      <div className="theme-swipe-card__footer">
        <span>Δ–01 · JP MARKET SYSTEM</span>
        <span
          className="theme-swipe-card__insert"
          id="delta-theme-card-help"
        >
          <small>SWIPE {destinationLabel}</small>
          <svg viewBox="0 0 54 20" role="presentation">
            <path d="M2 10H45" />
            <path d="M37 3L46 10L37 17" />
          </svg>
        </span>
      </div>
    </div>
  )
}
