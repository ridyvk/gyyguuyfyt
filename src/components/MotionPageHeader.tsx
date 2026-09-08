import { Bookmark, Building2, GitCompareArrows, LayoutDashboard, ListFilter, Radar } from 'lucide-react'

type MotionPageVariant = 'dashboard' | 'finder' | 'universe' | 'radar' | 'watchlist' | 'compare'
const pages = {
  dashboard: { number: '01', label: '概況', icon: LayoutDashboard },
  finder: { number: '02', label: '指標から、次の発見へ。', icon: ListFilter },
  universe: { number: '03', label: '企業を探す。事業を知る。', icon: Building2 },
  radar: { number: '04', label: '企業の変化を、見逃さない。', icon: Radar },
  watchlist: { number: '05', label: '気になる企業を、手元に。', icon: Bookmark },
  compare: { number: '06', label: '並べて見つかる、企業の違い。', icon: GitCompareArrows },
}

export default function MotionPageHeader({ title, variant }: { title: string; variant: MotionPageVariant }) {
  const page = pages[variant]
  const Icon = page.icon
  return (
    <header className={`delta-page-header delta-page-header--${variant}`}>
      <div>
        <span className="page-eyebrow">{page.number} / RESEARCH</span>
        <h1>{title}<span className="title-period">.</span></h1>
        <p>{page.label}</p>
      </div>
      <span className="delta-page-header__icon" aria-hidden="true"><Icon size={34} strokeWidth={1.4} /></span>
    </header>
  )
}
