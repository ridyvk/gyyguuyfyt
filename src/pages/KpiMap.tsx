import {
  Bookmark,
  ChevronRight,
  Crosshair,
  GitCompareArrows,
  Layers3,
  LocateFixed,
  Maximize2,
  MousePointer2,
  Radar,
  Sparkles,
  ZoomIn,
  ZoomOut,
} from 'lucide-react'
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
  type WheelEvent as ReactWheelEvent,
} from 'react'
import { Link } from 'react-router-dom'
import AnimatedNumber from '../components/AnimatedNumber'
import ScoreBadge from '../components/ScoreBadge'
import ScoreBar, { scoreLabels } from '../components/ScoreBar'
import SearchBox from '../components/SearchBox'
import { useApp } from '../context/AppContext'
import { industriesList, marketsList } from '../lib/companyUniverse'
import {
  formatChangePercent,
  formatMetric,
  formatStockPrice,
} from '../lib/formatters'
import { hasFinancialData, hasScorableData } from '../lib/liveData'
import type { Company, KpiKey, Market } from '../types'

type MapMode = 'quality' | 'capital' | 'cash' | 'price'
type SizeMode = 'revenue' | 'score' | 'price'

interface KpiMapFilter {
  query: string
  market: Market | 'all'
  industry: string | 'all'
  watchOnly: boolean
  warningsOnly: boolean
  dataOnly: boolean
}

interface Viewport {
  zoom: number
  panX: number
  panY: number
}

interface MapPoint {
  id: string
  company: Company
  x: number
  y: number
  xRaw?: number
  yRaw?: number
  radius: number
  color: string
  available: boolean
  dataStrength: number
  revenue?: number
}

interface RenderedPoint extends MapPoint {
  screenX: number
  screenY: number
  screenRadius: number
}

interface AxisRange {
  min: number
  max: number
}

interface MapModeConfig {
  label: string
  sublabel: string
  xLabel: string
  yLabel: string
  xRange?: AxisRange
  yRange?: AxisRange
  xValue: (company: Company) => number | undefined
  yValue: (company: Company) => number | undefined
  xDisplay: (company: Company) => string
  yDisplay: (company: Company) => string
}

const initialFilter: KpiMapFilter = {
  query: '',
  market: 'all',
  industry: 'all',
  watchOnly: false,
  warningsOnly: false,
  dataOnly: true,
}

const initialViewport: Viewport = {
  zoom: 1,
  panX: 0,
  panY: 0,
}

const industryPalette = [
  '#007AFF',
  '#34C759',
  '#5856D6',
  '#FF9F0A',
  '#AF52DE',
  '#00A7C7',
  '#FF6B6B',
  '#2DBE92',
  '#5E8CFF',
  '#B56BD8',
  '#D7A51B',
  '#27B6A6',
]

const mapModes: Record<MapMode, MapModeConfig> = {
  quality: {
    label: 'Quality Map',
    sublabel: 'PROFITABILITY / SAFETY',
    xLabel: '収益性',
    yLabel: '安全性',
    xRange: { min: 0, max: 100 },
    yRange: { min: 0, max: 100 },
    xValue: (company) => (hasScorableData(company) ? company.scores.profitability : undefined),
    yValue: (company) => (hasScorableData(company) ? company.scores.safety : undefined),
    xDisplay: (company) =>
      hasScorableData(company) ? Math.round(company.scores.profitability).toString() : '—',
    yDisplay: (company) =>
      hasScorableData(company) ? Math.round(company.scores.safety).toString() : '—',
  },
  capital: {
    label: 'Capital Orbit',
    sublabel: 'ROIC / ROIC-WACC',
    xLabel: 'ROIC',
    yLabel: 'ROIC-WACC',
    xValue: (company) => metricValue(company, 'roic'),
    yValue: (company) => metricValue(company, 'roicWaccSpread'),
    xDisplay: (company) => formatMetric(company.metrics.roic),
    yDisplay: (company) => formatMetric(company.metrics.roicWaccSpread),
  },
  cash: {
    label: 'Cash Signal',
    sublabel: 'OPERATING CF / PROFIT QUALITY',
    xLabel: '営業CF',
    yLabel: 'CF利益差',
    xValue: (company) => metricValue(company, 'operatingCfMargin'),
    yValue: (company) => metricValue(company, 'cashProfitGap'),
    xDisplay: (company) => formatMetric(company.metrics.operatingCfMargin),
    yDisplay: (company) => formatMetric(company.metrics.cashProfitGap),
  },
  price: {
    label: 'Market Reaction',
    sublabel: 'KPI SCORE / PRICE MOVE',
    xLabel: '総合スコア',
    yLabel: '株価変化',
    xRange: { min: 0, max: 100 },
    yRange: { min: -15, max: 15 },
    xValue: (company) => (hasScorableData(company) ? company.scores.overall : undefined),
    yValue: (company) => company.stockPrice?.changePercent,
    xDisplay: (company) =>
      hasScorableData(company) ? Math.round(company.scores.overall).toString() : '—',
    yDisplay: (company) => formatChangePercent(company.stockPrice?.changePercent),
  },
}

const metricValue = (company: Company, key: KpiKey) => {
  const metric = company.metrics[key]
  if (!metric || metric.available === false || !Number.isFinite(metric.value)) {
    return undefined
  }
  return metric.value
}

const clamp = (value: number, min: number, max: number) =>
  Math.max(min, Math.min(max, value))

const easeOutCubic = (value: number) => 1 - (1 - value) ** 3

const hashString = (value: string) =>
  Array.from(value).reduce((hash, char) => {
    const next = (hash << 5) - hash + char.charCodeAt(0)
    return next | 0
  }, 0)

const colorForIndustry = (industry: string) =>
  industryPalette[Math.abs(hashString(industry)) % industryPalette.length]

const latestRevenue = (company: Company) =>
  [...company.history].reverse().find((point) => Number.isFinite(point.revenue))
    ?.revenue

const quantile = (values: number[], ratio: number) => {
  if (!values.length) return 0
  const sorted = [...values].sort((a, b) => a - b)
  const index = clamp(Math.floor((sorted.length - 1) * ratio), 0, sorted.length - 1)
  return sorted[index]
}

const rangeFromValues = (values: number[], fixed?: AxisRange): AxisRange => {
  if (fixed) return fixed
  const finite = values.filter(Number.isFinite)
  if (!finite.length) return { min: 0, max: 1 }
  const min = quantile(finite, 0.04)
  const max = quantile(finite, 0.96)
  if (min === max) return { min: min - 1, max: max + 1 }
  return { min, max }
}

const normalize = (value: number | undefined, range: AxisRange) => {
  if (value === undefined) return 7
  const score = ((value - range.min) / (range.max - range.min)) * 100
  return clamp(score, 3, 97)
}

const jitter = (id: string, salt: string, spread: number) =>
  ((Math.abs(hashString(`${id}:${salt}`)) % 1000) / 1000 - 0.5) * spread

const sizeValueForCompany = (company: Company, sizeMode: SizeMode) => {
  if (sizeMode === 'score') {
    return hasScorableData(company) ? company.scores.overall : undefined
  }
  if (sizeMode === 'price') {
    const change = company.stockPrice?.changePercent
    return change === undefined ? undefined : Math.abs(change)
  }
  const revenue = latestRevenue(company)
  return revenue && revenue > 0 ? Math.log10(revenue + 10) : undefined
}

const sizeRange = (values: number[], sizeMode: SizeMode): AxisRange => {
  if (sizeMode === 'score') return { min: 0, max: 100 }
  if (sizeMode === 'price') return { min: 0, max: 12 }
  return rangeFromValues(values)
}

const confidenceStrength = (company: Company) => {
  if (!hasFinancialData(company)) return 0.12
  const count = company.trustedMetricCount ?? company.liveMetricCount ?? 0
  return clamp(count / 10, 0.28, 1)
}

const projectPoint = (
  point: MapPoint,
  width: number,
  height: number,
  viewport: Viewport,
) => {
  const compact = width < 680
  const left = compact ? 42 : 72
  const right = compact ? 24 : 42
  const top = compact ? 34 : 42
  const bottom = compact ? 52 : 64
  const plotWidth = Math.max(1, width - left - right)
  const plotHeight = Math.max(1, height - top - bottom)
  const baseX = left + (point.x / 100) * plotWidth
  const baseY = height - bottom - (point.y / 100) * plotHeight
  const centerX = width / 2
  const centerY = height / 2
  return {
    x: (baseX - centerX) * viewport.zoom + centerX + viewport.panX,
    y: (baseY - centerY) * viewport.zoom + centerY + viewport.panY,
  }
}

const drawRoundLabel = (
  context: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  color: string,
) => {
  context.save()
  context.font = '600 11px "Yu Mincho", serif'
  const metrics = context.measureText(text)
  const width = metrics.width + 18
  const height = 24
  const left = x + 12
  const top = y - height - 10
  context.fillStyle = 'rgba(255, 255, 255, 0.86)'
  context.strokeStyle = 'rgba(60, 60, 67, 0.13)'
  context.lineWidth = 1
  context.beginPath()
  context.roundRect(left, top, width, height, 9)
  context.fill()
  context.stroke()
  context.fillStyle = color
  context.fillRect(left + 8, top + 8, 3, 8)
  context.fillStyle = '#1c1c1e'
  context.fillText(text, left + 15, top + 16)
  context.restore()
}

const drawBackdrop = (
  context: CanvasRenderingContext2D,
  width: number,
  height: number,
  mode: MapModeConfig,
) => {
  const compact = width < 680
  const left = compact ? 42 : 72
  const right = compact ? 24 : 42
  const top = compact ? 34 : 42
  const bottom = compact ? 52 : 64
  const plotWidth = Math.max(1, width - left - right)
  const plotHeight = Math.max(1, height - top - bottom)
  const midX = left + plotWidth / 2
  const midY = top + plotHeight / 2

  context.clearRect(0, 0, width, height)
  const background = context.createLinearGradient(0, 0, width, height)
  background.addColorStop(0, '#f8fbff')
  background.addColorStop(0.42, '#f4fbfb')
  background.addColorStop(1, '#fbf8ff')
  context.fillStyle = background
  context.fillRect(0, 0, width, height)

  context.fillStyle = 'rgba(52, 199, 89, 0.055)'
  context.fillRect(midX, top, plotWidth / 2, plotHeight / 2)
  context.fillStyle = 'rgba(0, 122, 255, 0.048)'
  context.fillRect(left, top, plotWidth / 2, plotHeight / 2)
  context.fillStyle = 'rgba(255, 159, 10, 0.052)'
  context.fillRect(midX, midY, plotWidth / 2, plotHeight / 2)
  context.fillStyle = 'rgba(255, 59, 48, 0.042)'
  context.fillRect(left, midY, plotWidth / 2, plotHeight / 2)

  context.strokeStyle = 'rgba(60, 60, 67, 0.08)'
  context.lineWidth = 1
  for (let index = 0; index <= 5; index += 1) {
    const x = left + (plotWidth / 5) * index
    const y = top + (plotHeight / 5) * index
    context.beginPath()
    context.moveTo(x, top)
    context.lineTo(x, top + plotHeight)
    context.stroke()
    context.beginPath()
    context.moveTo(left, y)
    context.lineTo(left + plotWidth, y)
    context.stroke()
  }

  context.strokeStyle = 'rgba(28, 28, 30, 0.18)'
  context.lineWidth = 1.2
  context.strokeRect(left, top, plotWidth, plotHeight)
  context.strokeStyle = 'rgba(28, 28, 30, 0.11)'
  context.beginPath()
  context.moveTo(midX, top)
  context.lineTo(midX, top + plotHeight)
  context.moveTo(left, midY)
  context.lineTo(left + plotWidth, midY)
  context.stroke()

  context.fillStyle = 'rgba(28, 28, 30, 0.52)'
  context.font = '600 10px "Yu Mincho", serif'
  context.fillText(mode.xLabel, left + plotWidth - 64, height - 23)
  context.save()
  context.translate(18, top + 68)
  context.rotate(-Math.PI / 2)
  context.fillText(mode.yLabel, 0, 0)
  context.restore()

  context.fillStyle = 'rgba(0, 122, 255, 0.18)'
  context.font = '700 42px "Yu Mincho", serif'
  context.fillText('KPI', left + 18, top + 52)
  context.fillStyle = 'rgba(88, 86, 214, 0.12)'
  context.fillText('MAP', left + 112, top + 52)
}

const drawPoints = (
  context: CanvasRenderingContext2D,
  points: MapPoint[],
  width: number,
  height: number,
  viewport: Viewport,
  selectedId: string | null,
  hoveredId: string | null,
  watchedIds: Set<string>,
  elapsed: number,
) => {
  const progress = easeOutCubic(clamp(elapsed / 950, 0, 1))
  const rendered: RenderedPoint[] = []

  points.forEach((point, index) => {
    const projected = projectPoint(point, width, height, viewport)
    const inView =
      projected.x > -30 &&
      projected.x < width + 30 &&
      projected.y > -30 &&
      projected.y < height + 30
    if (!inView) return

    const isSelected = point.id === selectedId
    const isHovered = point.id === hoveredId
    const isWatched = watchedIds.has(point.id)
    const quoteChange = point.company.stockPrice?.changePercent ?? 0
    const delay = (index % 36) * 0.009
    const localProgress = clamp((progress - delay) / 0.78, 0, 1)
    const pulse = 1 + Math.sin(elapsed / 380 + index) * 0.055
    const radius =
      (point.radius + (isSelected ? 5.4 : isHovered ? 3.8 : isWatched ? 1.8 : 0)) *
      viewport.zoom ** 0.34 *
      localProgress *
      pulse
    const alpha =
      (point.available ? 0.32 + point.dataStrength * 0.55 : 0.16) *
      localProgress

    context.save()
    context.globalAlpha = alpha
    context.fillStyle = point.color
    context.beginPath()
    context.arc(projected.x, projected.y, radius, 0, Math.PI * 2)
    context.fill()

    if (point.available) {
      context.globalAlpha = clamp(alpha + 0.16, 0, 0.9)
      context.strokeStyle =
        quoteChange > 0
          ? 'rgba(52, 199, 89, 0.82)'
          : quoteChange < 0
            ? 'rgba(255, 59, 48, 0.78)'
            : 'rgba(255, 255, 255, 0.78)'
      context.lineWidth = isSelected || isHovered ? 2.2 : 1
      context.beginPath()
      context.arc(projected.x, projected.y, radius + 2, 0, Math.PI * 2)
      context.stroke()
    }

    if (isWatched || isSelected || isHovered) {
      context.globalAlpha = isSelected || isHovered ? 0.28 : 0.16
      context.strokeStyle = point.color
      context.lineWidth = 1.2
      context.beginPath()
      context.arc(projected.x, projected.y, radius + 8, 0, Math.PI * 2)
      context.stroke()
    }
    context.restore()

    rendered.push({
      ...point,
      screenX: projected.x,
      screenY: projected.y,
      screenRadius: Math.max(5, radius),
    })
  })

  rendered
    .filter((point) => point.id === selectedId || point.id === hoveredId)
    .forEach((point) => {
      drawRoundLabel(context, point.company.name, point.screenX, point.screenY, point.color)
    })

  return rendered
}

export default function KpiMap() {
  const {
    companies,
    watchlist,
    compareList,
    isWatched,
    isCompared,
    toggleWatchlist,
    toggleCompare,
  } = useApp()
  const [filter, setFilter] = useState<KpiMapFilter>(initialFilter)
  const [mode, setMode] = useState<MapMode>('quality')
  const [sizeMode, setSizeMode] = useState<SizeMode>('revenue')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [hoverPosition, setHoverPosition] = useState({ x: 0, y: 0 })
  const [viewport, setViewport] = useState<Viewport>(initialViewport)
  const [compareNotice, setCompareNotice] = useState('')
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const renderedRef = useRef<RenderedPoint[]>([])
  const viewportRef = useRef(viewport)
  const dragRef = useRef({
    active: false,
    moved: false,
    pointerId: 0,
    lastX: 0,
    lastY: 0,
    totalX: 0,
    totalY: 0,
  })

  useEffect(() => {
    viewportRef.current = viewport
  }, [viewport])

  const watchedIds = useMemo(() => new Set(watchlist), [watchlist])
  const modeConfig = mapModes[mode]

  const filteredCompanies = useMemo(() => {
    const query = filter.query.trim().toLowerCase()
    return companies.filter((company) => {
      const matchesQuery =
        !query ||
        company.name.toLowerCase().includes(query) ||
        company.code.toLowerCase().includes(query)
      const matchesMarket = filter.market === 'all' || company.market === filter.market
      const matchesIndustry =
        filter.industry === 'all' || company.industry === filter.industry
      const matchesWatch = !filter.watchOnly || watchedIds.has(company.id)
      const matchesWarning = !filter.warningsOnly || company.hasWarning
      const matchesData = !filter.dataOnly || hasFinancialData(company)
      return (
        matchesQuery &&
        matchesMarket &&
        matchesIndustry &&
        matchesWatch &&
        matchesWarning &&
        matchesData
      )
    })
  }, [companies, filter, watchedIds])

  const points = useMemo<MapPoint[]>(() => {
    const raw = filteredCompanies.map((company) => ({
      company,
      xRaw: modeConfig.xValue(company),
      yRaw: modeConfig.yValue(company),
      sizeRaw: sizeValueForCompany(company, sizeMode),
      revenue: latestRevenue(company),
    }))
    const xRange = rangeFromValues(
      raw.map((point) => point.xRaw).filter((value): value is number => value !== undefined),
      modeConfig.xRange,
    )
    const yRange = rangeFromValues(
      raw.map((point) => point.yRaw).filter((value): value is number => value !== undefined),
      modeConfig.yRange,
    )
    const radiusRange = sizeRange(
      raw
        .map((point) => point.sizeRaw)
        .filter((value): value is number => value !== undefined),
      sizeMode,
    )

    return raw
      .map(({ company, xRaw, yRaw, sizeRaw, revenue }) => {
        const available = xRaw !== undefined && yRaw !== undefined
        const sizeScore = normalize(sizeRaw, radiusRange)
        const x = normalize(xRaw, xRange)
        const y = normalize(yRaw, yRange)
        return {
          id: company.id,
          company,
          x: clamp(x + jitter(company.id, 'x', 7.2), 3, 97),
          y: clamp(y + jitter(company.id, 'y', 17.5), 3, 97),
          xRaw,
          yRaw,
          radius: 2.4 + (sizeScore / 100) * 7.6,
          color: colorForIndustry(company.industry),
          available,
          dataStrength: confidenceStrength(company),
          revenue,
        }
      })
      .sort((a, b) => {
        if (a.available !== b.available) return a.available ? 1 : -1
        return a.radius - b.radius
      })
  }, [filteredCompanies, modeConfig, sizeMode])

  const selectedPoint = useMemo(
    () => points.find((point) => point.id === selectedId) ?? null,
    [points, selectedId],
  )
  const selectedCompany = selectedPoint?.company ?? null
  const hoveredPoint = useMemo(
    () => points.find((point) => point.id === hoveredId) ?? null,
    [points, hoveredId],
  )
  const scorableCount = filteredCompanies.filter(hasScorableData).length
  const stockCount = filteredCompanies.filter((company) => company.stockPrice).length

  useEffect(() => {
    if (selectedId && !points.some((point) => point.id === selectedId)) {
      setSelectedId(null)
    }
  }, [points, selectedId])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const context = canvas.getContext('2d')
    if (!context) return

    let frameId = 0
    let startTime = performance.now()

    const resize = () => {
      const rect = canvas.getBoundingClientRect()
      const ratio = window.devicePixelRatio || 1
      const nextWidth = Math.max(1, Math.floor(rect.width * ratio))
      const nextHeight = Math.max(1, Math.floor(rect.height * ratio))
      if (canvas.width !== nextWidth || canvas.height !== nextHeight) {
        canvas.width = nextWidth
        canvas.height = nextHeight
      }
      context.setTransform(ratio, 0, 0, ratio, 0, 0)
    }

    const render = (now: number) => {
      resize()
      const rect = canvas.getBoundingClientRect()
      drawBackdrop(context, rect.width, rect.height, modeConfig)
      renderedRef.current = drawPoints(
        context,
        points,
        rect.width,
        rect.height,
        viewportRef.current,
        selectedId,
        hoveredId,
        watchedIds,
        now - startTime,
      )
      frameId = window.requestAnimationFrame(render)
    }

    const observer = new ResizeObserver(() => {
      startTime = performance.now() - 500
      resize()
    })
    observer.observe(canvas)
    frameId = window.requestAnimationFrame(render)

    return () => {
      observer.disconnect()
      window.cancelAnimationFrame(frameId)
    }
  }, [hoveredId, modeConfig, points, selectedId, watchedIds])

  const hitTest = useCallback((x: number, y: number) => {
    for (let index = renderedRef.current.length - 1; index >= 0; index -= 1) {
      const point = renderedRef.current[index]
      const distance = Math.hypot(point.screenX - x, point.screenY - y)
      if (distance <= Math.max(9, point.screenRadius + 4)) return point
    }
    return null
  }, [])

  const focusPoint = useCallback((point: MapPoint | null) => {
    const canvas = canvasRef.current
    if (!canvas || !point) return
    const rect = canvas.getBoundingClientRect()
    const projected = projectPoint(point, rect.width, rect.height, {
      zoom: viewportRef.current.zoom,
      panX: 0,
      panY: 0,
    })
    setViewport((current) => ({
      zoom: Math.max(current.zoom, 1.38),
      panX: rect.width / 2 - projected.x,
      panY: rect.height / 2 - projected.y,
    }))
  }, [])

  const selectPoint = useCallback(
    (point: MapPoint | null) => {
      setSelectedId(point?.id ?? null)
      if (point) focusPoint(point)
    },
    [focusPoint],
  )

  const pointerPosition = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    return {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    }
  }

  const handlePointerDown = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const position = pointerPosition(event)
    dragRef.current = {
      active: true,
      moved: false,
      pointerId: event.pointerId,
      lastX: position.x,
      lastY: position.y,
      totalX: 0,
      totalY: 0,
    }
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const handlePointerMove = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const position = pointerPosition(event)
    if (dragRef.current.active) {
      const deltaX = position.x - dragRef.current.lastX
      const deltaY = position.y - dragRef.current.lastY
      dragRef.current.lastX = position.x
      dragRef.current.lastY = position.y
      dragRef.current.totalX += Math.abs(deltaX)
      dragRef.current.totalY += Math.abs(deltaY)
      if (dragRef.current.totalX + dragRef.current.totalY > 5) {
        dragRef.current.moved = true
        setViewport((current) => ({
          ...current,
          panX: current.panX + deltaX,
          panY: current.panY + deltaY,
        }))
      }
      return
    }

    const point = hitTest(position.x, position.y)
    setHoverPosition(position)
    setHoveredId(point?.id ?? null)
  }

  const handlePointerUp = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const position = pointerPosition(event)
    const wasMoved = dragRef.current.moved
    dragRef.current.active = false
    event.currentTarget.releasePointerCapture(event.pointerId)
    if (!wasMoved) {
      selectPoint(hitTest(position.x, position.y))
    }
  }

  const handleWheel = (event: ReactWheelEvent<HTMLCanvasElement>) => {
    event.preventDefault()
    const delta = event.deltaY > 0 ? 0.9 : 1.1
    setViewport((current) => ({
      ...current,
      zoom: clamp(current.zoom * delta, 0.72, 4.2),
    }))
  }

  const zoomBy = (delta: number) => {
    setViewport((current) => ({
      ...current,
      zoom: clamp(current.zoom * delta, 0.72, 4.2),
    }))
  }

  const resetViewport = () => setViewport(initialViewport)

  const handleCompare = (company: Company) => {
    const ok = toggleCompare(company.id)
    setCompareNotice(ok ? '' : '比較は最大5社までです')
  }

  return (
    <div className="page kpi-map-page">
      <header className="kpi-map-hero">
        <div>
          <span className="page-eyebrow">KPI MAP / VISUAL INTELLIGENCE</span>
          <h1>KPI Map</h1>
          <p>
            財務の形、株価の反応、資本効率の温度をひとつの視界に集約します。
          </p>
        </div>
        <div className="kpi-map-hero__stats">
          <div>
            <span>VISIBLE</span>
            <strong><AnimatedNumber value={filteredCompanies.length} /></strong>
          </div>
          <div>
            <span>SCORABLE</span>
            <strong><AnimatedNumber value={scorableCount} /></strong>
          </div>
          <div>
            <span>QUOTES</span>
            <strong><AnimatedNumber value={stockCount} /></strong>
          </div>
        </div>
      </header>

      <section className="kpi-map-console">
        <div className="kpi-map-controls">
          <div className="kpi-map-control-row kpi-map-control-row--modes">
            {Object.entries(mapModes).map(([key, item]) => (
              <button
                key={key}
                type="button"
                className={mode === key ? 'is-active' : ''}
                onClick={() => {
                  setMode(key as MapMode)
                  setViewport(initialViewport)
                }}
              >
                <span>{item.sublabel}</span>
                <strong>{item.label}</strong>
              </button>
            ))}
          </div>

          <div className="kpi-map-filter-grid">
            <SearchBox
              value={filter.query}
              onChange={(query) => setFilter((current) => ({ ...current, query }))}
            />
            <label>
              市場
              <select
                value={filter.market}
                onChange={(event) =>
                  setFilter((current) => ({
                    ...current,
                    market: event.target.value as KpiMapFilter['market'],
                  }))
                }
              >
                <option value="all">すべて</option>
                {marketsList.map((market) => (
                  <option value={market} key={market}>
                    {market}
                  </option>
                ))}
              </select>
            </label>
            <label>
              業種
              <select
                value={filter.industry}
                onChange={(event) =>
                  setFilter((current) => ({
                    ...current,
                    industry: event.target.value,
                  }))
                }
              >
                <option value="all">すべて</option>
                {industriesList.map((industry) => (
                  <option value={industry} key={industry}>
                    {industry}
                  </option>
                ))}
              </select>
            </label>
            <label>
              サイズ
              <select
                value={sizeMode}
                onChange={(event) => setSizeMode(event.target.value as SizeMode)}
              >
                <option value="revenue">売上規模</option>
                <option value="score">総合スコア</option>
                <option value="price">株価変化</option>
              </select>
            </label>
          </div>

          <div className="kpi-map-toggles">
            <label>
              <input
                type="checkbox"
                checked={filter.dataOnly}
                onChange={(event) =>
                  setFilter((current) => ({
                    ...current,
                    dataOnly: event.target.checked,
                  }))
                }
              />
              財務取得済み
            </label>
            <label>
              <input
                type="checkbox"
                checked={filter.watchOnly}
                onChange={(event) =>
                  setFilter((current) => ({
                    ...current,
                    watchOnly: event.target.checked,
                  }))
                }
              />
              Watchlist
            </label>
            <label>
              <input
                type="checkbox"
                checked={filter.warningsOnly}
                onChange={(event) =>
                  setFilter((current) => ({
                    ...current,
                    warningsOnly: event.target.checked,
                  }))
                }
              />
              注意フラグ
            </label>
            <button
              type="button"
              onClick={() => {
                setFilter(initialFilter)
                setSelectedId(null)
                setViewport(initialViewport)
              }}
            >
              Reset
            </button>
          </div>
        </div>

        <div className="kpi-map-workspace">
          <div className="kpi-map-stage">
            <div className="kpi-map-stage__toolbar">
              <div>
                <Radar size={17} />
                <span>{modeConfig.label}</span>
              </div>
              <div>
                <button type="button" onClick={() => zoomBy(1.16)} aria-label="拡大">
                  <ZoomIn size={16} />
                </button>
                <button type="button" onClick={() => zoomBy(0.86)} aria-label="縮小">
                  <ZoomOut size={16} />
                </button>
                <button type="button" onClick={resetViewport} aria-label="全体表示">
                  <Maximize2 size={16} />
                </button>
                <button
                  type="button"
                  onClick={() => focusPoint(selectedPoint)}
                  disabled={!selectedPoint}
                  aria-label="選択企業へ移動"
                >
                  <LocateFixed size={16} />
                </button>
              </div>
            </div>
            <canvas
              ref={canvasRef}
              className="kpi-map-canvas"
              onPointerDown={handlePointerDown}
              onPointerMove={handlePointerMove}
              onPointerUp={handlePointerUp}
              onPointerLeave={() => {
                if (!dragRef.current.active) setHoveredId(null)
              }}
              onWheel={handleWheel}
            />
            {hoveredPoint && (
              <div
                className="kpi-map-tooltip"
                style={
                  {
                    '--tooltip-x': `${hoverPosition.x}px`,
                    '--tooltip-y': `${hoverPosition.y}px`,
                    '--tooltip-color': hoveredPoint.color,
                  } as CSSProperties
                }
              >
                <strong>{hoveredPoint.company.name}</strong>
                <span>{hoveredPoint.company.code} / {hoveredPoint.company.industry}</span>
              </div>
            )}
            <div className="kpi-map-stage__legend">
              <span><i className="is-positive" />株価上昇</span>
              <span><i className="is-negative" />株価下落</span>
              <span><i className="is-watch" />Watchlist</span>
            </div>
          </div>

          <aside className={selectedCompany ? 'kpi-map-detail is-open' : 'kpi-map-detail'}>
            {selectedCompany ? (
              <>
                <div className="kpi-map-detail__head">
                  <div>
                    <span>{selectedCompany.code} / {selectedCompany.market}</span>
                    <h2>{selectedCompany.name}</h2>
                    <p>{selectedCompany.industry}</p>
                  </div>
                  <ScoreBadge
                    score={selectedCompany.scores.overall}
                    compact
                    available={hasScorableData(selectedCompany)}
                  />
                </div>

                <div className="kpi-map-detail__axis">
                  <div>
                    <span>{modeConfig.xLabel}</span>
                    <strong>{modeConfig.xDisplay(selectedCompany)}</strong>
                  </div>
                  <div>
                    <span>{modeConfig.yLabel}</span>
                    <strong>{modeConfig.yDisplay(selectedCompany)}</strong>
                  </div>
                </div>

                <div className="kpi-map-score-stack">
                  <ScoreBar
                    label={scoreLabels.profitability}
                    score={selectedCompany.scores.profitability}
                    available={hasScorableData(selectedCompany)}
                  />
                  <ScoreBar
                    label={scoreLabels.safety}
                    score={selectedCompany.scores.safety}
                    available={hasScorableData(selectedCompany)}
                  />
                  <ScoreBar
                    label={scoreLabels.cashGeneration}
                    score={selectedCompany.scores.cashGeneration}
                    available={hasScorableData(selectedCompany)}
                  />
                </div>

                <div className="kpi-map-metrics">
                  <div>
                    <span>ROIC</span>
                    <strong>{formatMetric(selectedCompany.metrics.roic)}</strong>
                  </div>
                  <div>
                    <span>WACC</span>
                    <strong>{formatMetric(selectedCompany.metrics.wacc)}</strong>
                  </div>
                  <div>
                    <span>ROIC-WACC</span>
                    <strong>{formatMetric(selectedCompany.metrics.roicWaccSpread)}</strong>
                  </div>
                  <div>
                    <span>自己資本比率</span>
                    <strong>{formatMetric(selectedCompany.metrics.equityRatio)}</strong>
                  </div>
                  <div>
                    <span>株価</span>
                    <strong>
                      {selectedCompany.stockPrice
                        ? formatStockPrice(selectedCompany.stockPrice.close)
                        : '—'}
                    </strong>
                  </div>
                  <div>
                    <span>前日比</span>
                    <strong>{formatChangePercent(selectedCompany.stockPrice?.changePercent)}</strong>
                  </div>
                </div>

                <div className="kpi-map-detail__badges">
                  <span className={hasFinancialData(selectedCompany) ? 'is-ready' : ''}>
                    {hasFinancialData(selectedCompany)
                      ? `${selectedCompany.dataSource} / ${selectedCompany.trustedMetricCount ?? selectedCompany.liveMetricCount ?? 0}指標`
                      : '財務データ未取得'}
                  </span>
                  <span className={selectedCompany.hasWarning ? 'is-warning' : 'is-ready'}>
                    {selectedCompany.hasWarning
                      ? `注意 ${selectedCompany.warnings.length}件`
                      : '注意なし'}
                  </span>
                </div>

                {selectedCompany.warnings.length > 0 && (
                  <p className="kpi-map-detail__warning">
                    {selectedCompany.warnings[0]}
                  </p>
                )}

                <div className="kpi-map-detail__actions">
                  <button
                    type="button"
                    className={`button ${isWatched(selectedCompany.id) ? 'button--active' : 'button--secondary'}`}
                    onClick={() => toggleWatchlist(selectedCompany.id)}
                  >
                    <Bookmark
                      size={16}
                      fill={isWatched(selectedCompany.id) ? 'currentColor' : 'none'}
                    />
                    {isWatched(selectedCompany.id) ? '登録済み' : 'ウォッチ'}
                  </button>
                  <button
                    type="button"
                    className={`button ${isCompared(selectedCompany.id) ? 'button--active' : 'button--secondary'}`}
                    disabled={!hasFinancialData(selectedCompany) || (!isCompared(selectedCompany.id) && compareList.length >= 5)}
                    onClick={() => handleCompare(selectedCompany)}
                  >
                    <GitCompareArrows size={16} />
                    {isCompared(selectedCompany.id) ? '比較中' : '比較'}
                  </button>
                  <Link className="button button--ghost" to={`/company/${selectedCompany.id}`}>
                    詳細
                    <ChevronRight size={16} />
                  </Link>
                </div>
                {compareNotice && <small className="kpi-map-notice">{compareNotice}</small>}
              </>
            ) : (
              <div className="kpi-map-detail__empty">
                <MousePointer2 size={26} />
                <strong>Signal standby</strong>
                <span>選択中の企業はありません</span>
              </div>
            )}
          </aside>
        </div>
      </section>

      <section className="kpi-map-insight-strip">
        <div>
          <Sparkles size={18} />
          <span>右上ほど強い</span>
          <strong>{modeConfig.xLabel} × {modeConfig.yLabel}</strong>
        </div>
        <div>
          <Layers3 size={18} />
          <span>色</span>
          <strong>業種クラスター</strong>
        </div>
        <div>
          <Crosshair size={18} />
          <span>輪郭</span>
          <strong>株価反応</strong>
        </div>
      </section>
    </div>
  )
}
