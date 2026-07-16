import type { CSSProperties } from 'react'

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

const dashboardCandles = [
  { x: 302, high: 103, low: 146, open: 116, close: 137, volume: 19 },
  { x: 334, high: 91, low: 132, open: 121, close: 101, volume: 28 },
  { x: 366, high: 84, low: 124, open: 96, close: 113, volume: 23 },
  { x: 398, high: 70, low: 115, open: 105, close: 80, volume: 35 },
  { x: 430, high: 64, low: 101, open: 76, close: 91, volume: 21 },
  { x: 462, high: 57, low: 94, open: 84, close: 67, volume: 31 },
  { x: 494, high: 73, low: 108, open: 70, close: 97, volume: 25 },
  { x: 526, high: 60, low: 99, open: 91, close: 69, volume: 37 },
  { x: 558, high: 48, low: 87, open: 64, close: 55, volume: 30 },
  { x: 590, high: 42, low: 77, open: 52, close: 68, volume: 20 },
  { x: 622, high: 36, low: 72, open: 64, close: 45, volume: 34 },
  { x: 654, high: 50, low: 86, open: 48, close: 75, volume: 26 },
  { x: 686, high: 43, low: 79, open: 70, close: 51, volume: 39 },
  { x: 718, high: 31, low: 66, open: 48, close: 38, volume: 33 },
  { x: 750, high: 25, low: 58, open: 36, close: 49, volume: 29 },
  { x: 782, high: 18, low: 53, open: 46, close: 27, volume: 42 },
]

const dashboardPoints = [
  [286, 132], [318, 122], [350, 108], [382, 111], [414, 88], [446, 82],
  [478, 74], [510, 83], [542, 68], [574, 56], [606, 59], [638, 43],
  [670, 54], [702, 38], [734, 31], [766, 34], [806, 21],
]

const DashboardVisual = () => (
  <svg viewBox="0 0 840 230" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
    <defs>
      <linearGradient id="dashboard-area" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#1677b8" stopOpacity="0.18" />
        <stop offset="1" stopColor="#1677b8" stopOpacity="0" />
      </linearGradient>
      <clipPath id="dashboard-clip">
        <rect x="254" y="12" width="574" height="198" rx="18" />
      </clipPath>
    </defs>
    <g className="dashboard-chart" clipPath="url(#dashboard-clip)">
      <g className="dashboard-grid">
        {[27, 58, 89, 120, 151, 182].map((y) => <path d={`M254 ${y}H828`} key={`h-${y}`} />)}
        {[270, 318, 366, 414, 462, 510, 558, 606, 654, 702, 750, 798].map((x) => <path d={`M${x} 12V210`} key={`v-${x}`} />)}
      </g>
      <path className="dashboard-area" d="M254 153C292 148 304 127 334 124S374 105 398 110S435 82 462 87S503 70 526 79S565 54 590 59S626 40 654 49S691 35 718 39S765 17 828 24V182H254Z" />
      <path className="dashboard-average" pathLength="1" d="M254 153C292 148 304 127 334 124S374 105 398 110S435 82 462 87S503 70 526 79S565 54 590 59S626 40 654 49S691 35 718 39S765 17 828 24" />
      <g className="dashboard-candles">
        {dashboardCandles.map(({ x, high, low, open, close }, index) => {
          const rising = close < open
          return (
            <g className={`dashboard-candle ${rising ? 'is-up' : 'is-down'}`} style={{ '--candle-index': index } as CSSProperties} key={x}>
              <path d={`M${x} ${high}V${low}`} />
              <rect x={x - 6} y={Math.min(open, close)} width="12" height={Math.max(6, Math.abs(close - open))} rx="2" />
            </g>
          )
        })}
      </g>
      <g className="dashboard-volume">
        {dashboardCandles.map(({ x, volume }, index) => (
          <rect x={x - 7} y={208 - volume} width="14" height={volume} rx="2" style={{ '--candle-index': index } as CSSProperties} key={x} />
        ))}
      </g>
      <g className="dashboard-points">
        {dashboardPoints.map(([cx, cy], index) => <circle cx={cx} cy={cy} r="2.4" style={{ '--point-index': index } as CSSProperties} key={`${cx}-${cy}`} />)}
      </g>
      <g className="dashboard-cursor">
        <path d="M0 13V208" />
        <path d="M-13 0H13" />
        <circle r="5" />
        <rect x="9" y="-16" width="46" height="19" rx="6" />
        <path d="M18-7H45" />
      </g>
      <path className="dashboard-baseline" d="M254 182H828" />
    </g>
    <g className="dashboard-mini dashboard-mini--one">
      <rect x="196" y="21" width="88" height="39" rx="11" />
      <path d="M208 48L219 40L230 44L242 31L253 36L271 26" />
    </g>
    <g className="dashboard-mini dashboard-mini--two">
      <rect x="196" y="70" width="66" height="39" rx="11" />
      <circle cx="215" cy="89" r="10" />
      <path d="M215 79A10 10 0 0 1 224 94" />
      <path d="M235 84H250M235 93H246" />
    </g>
  </svg>
)

const finderBranches = [
  'M286 115C344 115 368 39 430 39',
  'M286 115C347 115 374 88 430 88',
  'M286 115C347 115 374 142 430 142',
  'M286 115C344 115 368 191 430 191',
  'M454 39C515 39 530 29 594 29',
  'M454 39C516 39 535 72 594 72',
  'M454 88C518 88 534 72 594 72',
  'M454 88C519 88 536 111 594 111',
  'M454 142C519 142 536 111 594 111',
  'M454 142C518 142 534 157 594 157',
  'M454 191C516 191 535 157 594 157',
  'M454 191C515 191 530 201 594 201',
  'M618 29C679 29 704 89 775 111',
  'M618 72C682 72 711 98 775 111',
  'M618 111H775',
  'M618 157C682 157 711 124 775 111',
  'M618 201C679 201 704 132 775 111',
]

const FinderVisual = () => (
  <svg viewBox="0 0 840 230" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
    <g className="finder-field">
      {finderBranches.map((d, index) => (
        <path className={`finder-branch finder-branch--${(index % 4) + 1} ${[1, 7, 14].includes(index) ? 'is-selected' : ''}`} pathLength="1" d={d} key={d} />
      ))}
    </g>
    <g className="finder-root">
      <circle cx="272" cy="115" r="29" />
      <circle cx="272" cy="115" r="17" />
      <path d="M260 115H284M272 103V127" />
    </g>
    <g className="finder-choice finder-choice--level-one">
      {[39, 88, 142, 191].map((cy, index) => (
        <g className={index === 1 ? 'is-selected' : ''} key={cy}>
          <rect x="430" y={cy - 12} width="24" height="24" rx="8" />
          <circle cx="442" cy={cy} r="3.5" />
        </g>
      ))}
    </g>
    <g className="finder-choice finder-choice--level-two">
      {[29, 72, 111, 157, 201].map((cy, index) => (
        <g className={index === 2 ? 'is-selected' : ''} key={cy}>
          <rect x="594" y={cy - 12} width="24" height="24" rx="8" />
          <path d={`M602 ${cy}H610`} />
        </g>
      ))}
    </g>
    <g className="finder-result">
      <circle cx="792" cy="111" r="27" />
      <circle cx="792" cy="111" r="15" />
      <path d="M785 111L790 116L800 105" />
    </g>
    <g className="finder-neurons">
      <circle className="finder-neuron finder-neuron--one" r="4.5" />
      <circle className="finder-neuron finder-neuron--two" r="3.8" />
      <circle className="finder-neuron finder-neuron--three" r="4.2" />
      <circle className="finder-neuron finder-neuron--four" r="3.4" />
    </g>
    <g className="finder-halo-nodes">
      {[272, 442, 606, 792].map((cx, index) => <circle cx={cx} cy={[115, 88, 111, 111][index]} r={index === 3 ? 33 : 19} key={cx} />)}
    </g>
  </svg>
)

const UniverseVisual = () => (
  <svg viewBox="0 0 840 230" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
    <defs>
      <linearGradient id="universe-sphere" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#b7dbe4" stopOpacity="0.86" />
        <stop offset="0.46" stopColor="#4d8fb0" stopOpacity="0.78" />
        <stop offset="1" stopColor="#586ab4" stopOpacity="0.72" />
      </linearGradient>
      <clipPath id="universe-sphere-clip">
        <circle cx="612" cy="115" r="73" />
      </clipPath>
    </defs>
    <g className="universe-orbit-plane universe-orbit-plane--back">
      <ellipse cx="612" cy="115" rx="226" ry="78" />
      <ellipse cx="612" cy="115" rx="184" ry="48" transform="rotate(18 612 115)" />
    </g>
    <g className="universe-planet">
      <circle className="universe-sphere-base" cx="612" cy="115" r="73" />
      <g clipPath="url(#universe-sphere-clip)">
        <g className="universe-surface">
          <path d="M535 82C557 64 574 73 590 59C607 44 624 52 635 67C647 84 668 75 686 93L691 129C670 122 657 134 643 128C625 120 617 134 601 144C584 155 566 145 542 157Z" />
          <path d="M558 42C568 63 559 78 569 92C578 105 570 121 554 132C545 139 540 152 544 168M613 41C601 61 605 80 615 94C626 108 626 126 614 144C606 156 607 173 617 189M666 53C648 70 650 90 663 103C674 115 676 138 661 163" />
          <ellipse cx="612" cy="115" rx="71" ry="24" />
          <ellipse cx="612" cy="115" rx="70" ry="48" />
        </g>
      </g>
      <circle className="universe-sphere-outline" cx="612" cy="115" r="73" />
      <path className="universe-terminator" d="M637 47C611 68 602 92 607 118C612 143 631 165 653 174" />
    </g>
    <g className="universe-orbit-plane universe-orbit-plane--front">
      <path d="M394 134C452 174 533 192 620 190C714 188 793 161 828 122" />
    </g>
    <g className="universe-satellite universe-satellite--one">
      <g className="universe-satellite__body">
        <rect x="795" y="105" width="22" height="18" rx="4" />
        <path d="M792 109H778V119H792M820 109H834V119H820" />
        <path d="M784 109V119M828 109V119M806 105V97M802 97H810" />
        <circle cx="806" cy="114" r="3" />
      </g>
    </g>
    <g className="universe-satellite universe-satellite--two">
      <g className="universe-satellite__body">
        <rect x="440" y="55" width="18" height="16" rx="4" />
        <path d="M437 58H425V68H437M461 58H473V68H461" />
        <path d="M449 55V48M445 48H453" />
      </g>
    </g>
    <g className="universe-moon-orbit">
      <circle cx="612" cy="115" r="101" />
      <circle className="universe-moon" cx="711" cy="115" r="7" />
    </g>
    <g className="universe-telemetry">
      <path d="M338 178H430L454 160" />
      <circle cx="338" cy="178" r="3" />
      <path d="M349 170H393M349 178H415M349 186H382" />
    </g>
  </svg>
)

const radarTicks = Array.from({ length: 24 }, (_, index) => index * 15)

const RadarVisual = () => (
  <svg viewBox="0 0 840 230" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
    <defs>
      <linearGradient id="radar-sweep-fill" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#0086c9" stopOpacity="0.02" />
        <stop offset="1" stopColor="#4e76c7" stopOpacity="0.17" />
      </linearGradient>
    </defs>
    <g className="radar-frame">
      <path d="M272 24H319M272 24V57M819 24H772M819 24V57M272 206H319M272 206V173M819 206H772M819 206V173" />
      <path d="M288 76H360M288 88H339M288 100H350" />
      <path d="M288 157H346L359 144L370 168L384 153H408" />
    </g>
    <g className="radar-rings">
      <circle cx="626" cy="115" r="91" />
      <circle cx="626" cy="115" r="68" />
      <circle cx="626" cy="115" r="45" />
      <circle cx="626" cy="115" r="22" />
      <path d="M535 115H717M626 24V206M562 51L690 179M690 51L562 179" />
    </g>
    <g className="radar-ticks">
      {radarTicks.map((angle) => <path d="M626 19V27" transform={`rotate(${angle} 626 115)`} key={angle} />)}
    </g>
    <g className="radar-sweep">
      <path className="radar-sweep__field" d="M626 115L626 24A91 91 0 0 1 699 61Z" />
      <path className="radar-sweep__edge" d="M626 115V24" />
    </g>
    <g className="radar-targets">
      <g className="radar-target radar-target--one">
        <circle cx="674" cy="72" r="4" />
        <path d="M663 65V60H669M679 60H685V66M685 78V84H679M669 84H663V78" />
      </g>
      <g className="radar-target radar-target--two">
        <circle cx="580" cy="99" r="3.5" />
        <path d="M570 92V87H576M586 87H592V93M592 105V111H586M576 111H570V105" />
      </g>
      <g className="radar-target radar-target--three">
        <circle cx="650" cy="160" r="4" />
        <path d="M639 153V148H645M655 148H661V154M661 166V172H655M645 172H639V166" />
      </g>
    </g>
    <g className="radar-tracking-lines">
      <path pathLength="1" d="M674 72L749 49H810" />
      <path pathLength="1" d="M650 160L735 182H810" />
      <path pathLength="1" d="M580 99L516 71H451" />
    </g>
    <g className="radar-monitor-cells">
      <g><rect x="754" y="36" width="64" height="27" rx="7" /><path d="M765 50H807" /></g>
      <g><rect x="754" y="169" width="64" height="27" rx="7" /><path d="M765 183H797" /></g>
      <g><rect x="393" y="56" width="62" height="27" rx="7" /><path d="M404 70H443" /></g>
    </g>
    <g className="radar-reticle">
      <circle cx="626" cy="115" r="7" />
      <path d="M607 115H617M635 115H645M626 96V106M626 124V134" />
    </g>
    <path className="radar-scanline" d="M536 115H716" />
  </svg>
)

const watchRows = [
  { y: 43, line: 'M340 39H472M340 48H431', spark: 'M594 49L610 43L626 46L642 34L658 39L677 29' },
  { y: 91, line: 'M340 87H451M340 96H486', spark: 'M594 97L610 91L626 94L642 83L658 86L677 76' },
  { y: 139, line: 'M340 135H488M340 144H445', spark: 'M594 145L610 139L626 142L642 130L658 135L677 124' },
  { y: 187, line: 'M340 183H459M340 192H478', spark: 'M594 193L610 187L626 190L642 180L658 183L677 173' },
]

const WatchlistVisual = () => (
  <svg viewBox="0 0 840 230" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
    <g className="watch-rail">
      <path d="M280 22V208" />
      {[43, 91, 139, 187].map((cy) => <circle cx="280" cy={cy} r="4" key={cy} />)}
    </g>
    <g className="watch-stream">
      {watchRows.map(({ y, line, spark }, index) => (
        <g className={`watch-row watch-row--${index + 1} ${index === 1 ? 'is-active' : ''}`} style={{ '--watch-index': index } as CSSProperties} key={y}>
          <rect className="watch-row__card" x="297" y={y - 18} width="447" height="36" rx="11" />
          <circle className="watch-row__status" cx="317" cy={y} r="5" />
          <path className="watch-row__copy" d={line} />
          <path className="watch-row__spark" pathLength="1" d={spark} />
          <circle className="watch-row__spark-point" cx="677" cy={index === 0 ? 29 : index === 1 ? 76 : index === 2 ? 124 : 173} r="3" />
          <path className="watch-row__check" d={`M705 ${y}L710 ${y + 5}L720 ${y - 6}`} />
          <rect className="watch-row__progress" x="297" y={y + 16} width="447" height="1.5" rx="1" />
        </g>
      ))}
    </g>
    <g className="watch-bookmark-wrap">
      <path className="watch-bookmark" pathLength="1" d="M772 30H810V202L791 188L772 202V30Z" />
      <circle className="watch-bookmark-dot" cx="791" cy="60" r="6" />
      <path className="watch-bookmark-tick" d="M787 60L790 63L796 56" />
    </g>
  </svg>
)

const CompareVisual = () => (
  <svg viewBox="0 0 840 230" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
    <defs>
      <clipPath id="compare-card-a"><rect x="288" y="25" width="218" height="177" rx="16" /></clipPath>
      <clipPath id="compare-card-b"><rect x="570" y="25" width="218" height="177" rx="16" /></clipPath>
    </defs>
    <g className="compare-card compare-card--a">
      <rect className="compare-card__frame" x="288" y="25" width="218" height="177" rx="16" />
      <circle className="compare-card__badge" cx="316" cy="52" r="13" />
      <path className="compare-card__badge-mark" d="M310 58L316 44L322 58M312 54H320" />
      <path className="compare-card__heading" d="M342 47H430M342 57H398" />
      <g className="compare-card__grid" clipPath="url(#compare-card-a)">
        <path d="M306 82H488M306 106H488M306 130H488" />
        <path d="M329 72V137M374 72V137M419 72V137M464 72V137" />
      </g>
      <path className="compare-line compare-line--a" pathLength="1" d="M306 125L332 112L358 116L384 94L410 101L436 80L462 88L488 70" />
      <g className="compare-metrics compare-metrics--a">
        <rect x="306" y="151" width="168" height="5" rx="2.5" /><rect className="compare-metric-value compare-metric-value--one" x="306" y="151" width="132" height="5" rx="2.5" />
        <rect x="306" y="166" width="168" height="5" rx="2.5" /><rect className="compare-metric-value compare-metric-value--two" x="306" y="166" width="98" height="5" rx="2.5" />
        <rect x="306" y="181" width="168" height="5" rx="2.5" /><rect className="compare-metric-value compare-metric-value--three" x="306" y="181" width="146" height="5" rx="2.5" />
      </g>
      <g className="compare-cursor compare-cursor--a"><path d="M0 70V137" /><circle cy="96" r="4" /></g>
    </g>
    <g className="compare-card compare-card--b">
      <rect className="compare-card__frame" x="570" y="25" width="218" height="177" rx="16" />
      <circle className="compare-card__badge" cx="598" cy="52" r="13" />
      <path className="compare-card__badge-mark" d="M593 44H599C605 44 605 51 600 52C607 53 607 60 600 60H593Z" />
      <path className="compare-card__heading" d="M624 47H712M624 57H680" />
      <g className="compare-card__grid" clipPath="url(#compare-card-b)">
        <path d="M588 82H770M588 106H770M588 130H770" />
        <path d="M611 72V137M656 72V137M701 72V137M746 72V137" />
      </g>
      <path className="compare-line compare-line--b" pathLength="1" d="M588 119L614 124L640 102L666 108L692 87L718 96L744 74L770 82" />
      <g className="compare-metrics compare-metrics--b">
        <rect x="588" y="151" width="168" height="5" rx="2.5" /><rect className="compare-metric-value compare-metric-value--one" x="588" y="151" width="112" height="5" rx="2.5" />
        <rect x="588" y="166" width="168" height="5" rx="2.5" /><rect className="compare-metric-value compare-metric-value--two" x="588" y="166" width="139" height="5" rx="2.5" />
        <rect x="588" y="181" width="168" height="5" rx="2.5" /><rect className="compare-metric-value compare-metric-value--three" x="588" y="181" width="119" height="5" rx="2.5" />
      </g>
      <g className="compare-cursor compare-cursor--b"><path d="M0 70V137" /><circle cy="96" r="4" /></g>
    </g>
    <g className="compare-bridge">
      <circle cx="538" cy="114" r="20" />
      <path d="M524 108H550M544 102L550 108L544 114M552 120H526M532 114L526 120L532 126" />
    </g>
    <g className="compare-deltas">
      <path pathLength="1" d="M474 153C516 153 530 153 570 153" />
      <path pathLength="1" d="M474 168C516 168 530 168 570 168" />
      <path pathLength="1" d="M474 183C516 183 530 183 570 183" />
      <circle cx="538" cy="153" r="3" /><circle cx="538" cy="168" r="3" /><circle cx="538" cy="183" r="3" />
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
        <span className="motion-page-header__mix motion-page-header__mix--three" />
      </div>
      <div className="motion-page-header__copy">
        <h1 data-title={title} aria-label={title}>{title}</h1>
      </div>
      <div className="motion-page-header__visual">
        <Visual />
      </div>
    </header>
  )
}
