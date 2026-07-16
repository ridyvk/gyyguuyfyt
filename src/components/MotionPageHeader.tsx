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
  <svg viewBox="0 0 420 180" preserveAspectRatio="xMinYMid meet" aria-hidden="true">
    <g className="motion-grid">
      <path d="M24 35H396M24 75H396M24 115H396M24 155H396" />
      <path d="M74 20V164M154 20V164M234 20V164M314 20V164" />
    </g>
    <g className="dashboard-bars">
      <rect x="54" y="112" width="22" height="43" rx="5" />
      <rect x="104" y="88" width="22" height="67" rx="5" />
      <rect x="154" y="102" width="22" height="53" rx="5" />
      <rect x="204" y="66" width="22" height="89" rx="5" />
      <rect x="254" y="77" width="22" height="78" rx="5" />
      <rect x="304" y="43" width="22" height="112" rx="5" />
    </g>
    <path
      className="motion-trace dashboard-trace"
      pathLength="1"
      d="M42 126C78 118 88 97 118 101C149 106 163 75 199 83C234 91 257 55 289 62C321 69 340 35 382 40"
    />
    <g className="dashboard-nodes">
      <circle cx="42" cy="126" r="4" />
      <circle cx="118" cy="101" r="4" />
      <circle cx="199" cy="83" r="4" />
      <circle cx="289" cy="62" r="4" />
      <circle cx="382" cy="40" r="5" />
    </g>
  </svg>
)

const FinderVisual = () => (
  <svg viewBox="0 0 420 180" preserveAspectRatio="xMinYMid meet" aria-hidden="true">
    <g className="finder-input-lines">
      <path d="M34 31H112L191 90" />
      <path d="M34 61H124L191 90" />
      <path d="M34 90H191" />
      <path d="M34 119H124L191 90" />
      <path d="M34 149H112L191 90" />
    </g>
    <g className="finder-input-dots">
      <circle cx="34" cy="31" r="5" />
      <circle cx="34" cy="61" r="5" />
      <circle cx="34" cy="90" r="5" />
      <circle cx="34" cy="119" r="5" />
      <circle cx="34" cy="149" r="5" />
    </g>
    <g className="finder-gates">
      <circle cx="191" cy="90" r="29" />
      <circle cx="191" cy="90" r="16" />
    </g>
    <path className="finder-output-line" pathLength="1" d="M220 90H378" />
    <circle className="finder-runner" cx="252" cy="90" r="4" />
    <circle className="finder-output-ring" cx="378" cy="90" r="18" />
    <circle className="finder-output-dot" cx="378" cy="90" r="6" />
  </svg>
)

const universeNodes = [
  [42, 42, 4], [88, 68, 3], [126, 31, 5], [162, 88, 3],
  [207, 45, 4], [242, 110, 5], [287, 71, 3], [330, 34, 4],
  [374, 89, 5], [64, 131, 5], [134, 143, 3], [192, 130, 4],
  [314, 142, 5], [387, 139, 3],
]

const UniverseVisual = () => (
  <svg viewBox="0 0 420 180" preserveAspectRatio="xMinYMid meet" aria-hidden="true">
    <g className="universe-orbits">
      <ellipse cx="213" cy="89" rx="183" ry="69" />
      <ellipse cx="213" cy="89" rx="119" ry="45" />
      <path d="M30 89H396M213 18V160" />
    </g>
    <g className="universe-links">
      <path d="M42 42L88 68L126 31L207 45L287 71L330 34L374 89L387 139L314 142L242 110L192 130L134 143L64 131L42 42" />
      <path d="M88 68L162 88L242 110L314 142M126 31L162 88L192 130M207 45L242 110L374 89" />
    </g>
    <g className="universe-nodes">
      {universeNodes.map(([cx, cy, radius], index) => (
        <circle cx={cx} cy={cy} r={radius} key={`${cx}-${cy}`} className={`universe-node universe-node--${(index % 4) + 1}`} />
      ))}
    </g>
    <circle className="universe-focus" cx="242" cy="110" r="14" />
  </svg>
)

const RadarVisual = () => (
  <svg viewBox="0 0 420 180" preserveAspectRatio="xMinYMid meet" aria-hidden="true">
    <g className="radar-rings">
      <circle cx="220" cy="90" r="68" />
      <circle cx="220" cy="90" r="46" />
      <circle cx="220" cy="90" r="23" />
      <path d="M220 17V163M147 90H293" />
    </g>
    <g className="radar-sweep">
      <path d="M220 90L220 21A69 69 0 0 1 274 47Z" />
      <path d="M220 90V21" />
    </g>
    <g className="radar-blips">
      <circle cx="255" cy="56" r="5" />
      <circle cx="180" cy="106" r="4" />
      <circle cx="246" cy="126" r="4" />
      <circle cx="220" cy="90" r="3" />
    </g>
    <path className="radar-feed" pathLength="1" d="M20 139H89L106 117L125 151L144 132H170" />
    <path className="radar-feed radar-feed--right" pathLength="1" d="M291 139H315L330 121L346 147L362 132H402" />
  </svg>
)

const WatchlistVisual = () => (
  <svg viewBox="0 0 420 180" preserveAspectRatio="xMinYMid meet" aria-hidden="true">
    <g className="watch-stream">
      {[31, 68, 105, 142].map((y, index) => (
        <g className={`watch-row watch-row--${index + 1}`} key={y}>
          <rect x="27" y={y - 14} width="282" height="28" rx="9" />
          <circle cx="47" cy={y} r="5" />
          <path d={`M65 ${y}H${index % 2 ? 202 : 230}`} />
          <path className="watch-row__short" d={`M${index % 2 ? 220 : 248} ${y}H286`} />
        </g>
      ))}
    </g>
    <path
      className="watch-bookmark"
      pathLength="1"
      d="M343 28H383V151L363 137L343 151V28Z"
    />
    <circle className="watch-lock" cx="363" cy="64" r="7" />
  </svg>
)

const CompareVisual = () => (
  <svg viewBox="0 0 420 180" preserveAspectRatio="xMinYMid meet" aria-hidden="true">
    <g className="compare-axis">
      <circle cx="210" cy="90" r="61" />
      <path d="M210 22V158M142 90H278M162 42L258 138M258 42L162 138" />
    </g>
    <path
      className="compare-shape compare-shape--a"
      pathLength="1"
      d="M210 35L259 63L246 122L195 145L157 104L174 58Z"
    />
    <path
      className="compare-shape compare-shape--b"
      pathLength="1"
      d="M210 48L269 86L238 145L183 132L148 84L188 51Z"
    />
    <g className="compare-differences">
      <circle cx="259" cy="63" r="5" />
      <circle cx="269" cy="86" r="5" />
      <circle cx="195" cy="145" r="5" />
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
      <div className="motion-page-header__copy">
        <h1 data-title={title} aria-label={title}>{title}</h1>
      </div>
      <div className="motion-page-header__visual">
        <Visual />
      </div>
    </header>
  )
}
