type MotionPageVariant =
  | 'dashboard'
  | 'finder'
  | 'universe'
  | 'radar'
  | 'watchlist'
  | 'compare'

interface MotionPageHeaderProps {
  title: string
  variant: MotionPageVariant
}

const DashboardVisual = () => (
  <svg viewBox="0 0 560 100" preserveAspectRatio="xMaxYMid meet" aria-hidden="true">
    <g className="compact-grid">
      <path d="M206 24H536M206 50H536M206 76H536" />
      <path d="M254 15V85M326 15V85M398 15V85M470 15V85" />
    </g>
    <g className="compact-dashboard-bars">
      <rect x="235" y="61" width="13" height="17" rx="2" />
      <rect x="276" y="49" width="13" height="29" rx="2" />
      <rect x="317" y="55" width="13" height="23" rx="2" />
      <rect x="358" y="39" width="13" height="39" rx="2" />
      <rect x="399" y="44" width="13" height="34" rx="2" />
      <rect x="440" y="30" width="13" height="48" rx="2" />
      <rect x="481" y="34" width="13" height="44" rx="2" />
    </g>
    <path className="compact-dashboard-line" pathLength="1" d="M218 68L262 57L305 61L347 43L389 48L431 32L473 38L520 21" />
  </svg>
)

const FinderVisual = () => (
  <svg viewBox="0 0 560 100" preserveAspectRatio="xMaxYMid meet" aria-hidden="true">
    <g className="compact-finder-branches">
      <path d="M236 50C290 50 302 21 357 21C410 21 430 50 496 50" />
      <path className="is-selected" d="M236 50H357H496" />
      <path d="M236 50C290 50 302 79 357 79C410 79 430 50 496 50" />
    </g>
    <g className="compact-finder-nodes">
      <circle cx="221" cy="50" r="13" />
      <circle cx="357" cy="21" r="7" />
      <circle className="is-selected" cx="357" cy="50" r="8" />
      <circle cx="357" cy="79" r="7" />
      <circle cx="511" cy="50" r="13" />
    </g>
    <circle className="compact-finder-signal" r="3.5" />
  </svg>
)

const UniverseVisual = () => (
  <svg viewBox="0 0 560 100" preserveAspectRatio="xMaxYMid meet" aria-hidden="true">
    <defs>
      <linearGradient id="compact-planet" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#a8d0dc" stopOpacity="0.75" />
        <stop offset="1" stopColor="#6176af" stopOpacity="0.72" />
      </linearGradient>
      <clipPath id="compact-planet-clip"><circle cx="405" cy="50" r="27" /></clipPath>
    </defs>
    <ellipse className="compact-universe-orbit" cx="405" cy="50" rx="100" ry="34" />
    <g className="compact-universe-planet">
      <circle cx="405" cy="50" r="27" />
      <g clipPath="url(#compact-planet-clip)">
        <ellipse cx="405" cy="50" rx="25" ry="9" />
        <path d="M397 22C387 33 388 45 397 54C405 63 405 73 399 79M417 23C426 35 424 45 417 54C410 64 412 75 419 79" />
      </g>
    </g>
    <g className="compact-universe-satellite">
      <rect x="493" y="44" width="14" height="12" rx="3" />
      <path d="M490 46H480V54H490M510 46H520V54H510M500 44V38" />
    </g>
  </svg>
)

const RadarVisual = () => (
  <svg viewBox="0 0 560 100" preserveAspectRatio="xMaxYMid meet" aria-hidden="true">
    <g className="compact-radar-rings">
      <circle cx="414" cy="50" r="36" />
      <circle cx="414" cy="50" r="24" />
      <circle cx="414" cy="50" r="11" />
      <path d="M378 50H450M414 14V86" />
    </g>
    <g className="compact-radar-sweep">
      <path d="M414 50V14A36 36 0 0 1 443 29Z" />
      <path d="M414 50V14" />
    </g>
    <g className="compact-radar-targets">
      <circle cx="432" cy="31" r="3" />
      <circle cx="395" cy="61" r="2.5" />
    </g>
    <path className="compact-radar-frame" d="M328 22H351M328 22V37M500 78H477M500 78V63" />
  </svg>
)

const WatchlistVisual = () => (
  <svg viewBox="0 0 560 100" preserveAspectRatio="xMaxYMid meet" aria-hidden="true">
    <g className="compact-watch-rows">
      {[24, 50, 76].map((y, index) => (
        <g className={index === 1 ? 'is-selected' : ''} key={y}>
          <rect x="250" y={y - 9} width="218" height="18" rx="6" />
          <circle cx="265" cy={y} r="3" />
          <path d={`M277 ${y}H${index === 1 ? 389 : 370}`} />
          <path d={`M405 ${y}L410 ${y + 4}L418 ${y - 5}`} />
        </g>
      ))}
    </g>
    <path className="compact-watch-bookmark" d="M489 16H513V84L501 76L489 84V16Z" />
  </svg>
)

const CompareVisual = () => (
  <svg viewBox="0 0 560 100" preserveAspectRatio="xMaxYMid meet" aria-hidden="true">
    <g className="compact-compare-card compact-compare-card--a">
      <rect x="254" y="17" width="104" height="66" rx="10" />
      <circle cx="272" cy="34" r="8" />
      <path d="M268 39L272 29L276 39M269 36H275M290 31H337M270 55L288 49L306 53L326 41L343 45M270 68H329" />
    </g>
    <g className="compact-compare-card compact-compare-card--b">
      <rect x="407" y="17" width="104" height="66" rx="10" />
      <circle cx="425" cy="34" r="8" />
      <path d="M421 29H425C431 29 431 34 427 34C432 35 431 39 425 39H421ZM443 31H490M423 55L441 58L459 47L477 51L496 40M423 68H480" />
    </g>
    <g className="compact-compare-arrows">
      <path d="M370 44H394M388 38L394 44L388 50M395 57H371M377 51L371 57L377 63" />
    </g>
  </svg>
)

const visuals: Record<MotionPageVariant, () => JSX.Element> = {
  dashboard: DashboardVisual,
  finder: FinderVisual,
  universe: UniverseVisual,
  radar: RadarVisual,
  watchlist: WatchlistVisual,
  compare: CompareVisual,
}

export default function MotionPageHeader({ title, variant }: MotionPageHeaderProps) {
  const Visual = visuals[variant]
  return (
    <header className={`motion-page-header motion-page-header--${variant}`}>
      <div className="motion-page-header__color-field" aria-hidden="true">
        <span className="motion-page-header__mix motion-page-header__mix--one" />
        <span className="motion-page-header__mix motion-page-header__mix--two" />
      </div>
      <div className="motion-page-header__copy">
        <h1 aria-label={title}>{title}</h1>
      </div>
      <div className="motion-page-header__visual">
        <Visual />
      </div>
    </header>
  )
}
