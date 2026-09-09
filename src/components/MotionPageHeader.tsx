import { Bookmark, Building2, GitCompareArrows, LayoutDashboard, ListFilter, Radar } from 'lucide-react'

type MotionPageVariant = 'dashboard' | 'finder' | 'universe' | 'radar' | 'watchlist' | 'compare'
const pages = {
  dashboard: { icon: LayoutDashboard },
  finder: { icon: ListFilter },
  universe: { icon: Building2 },
  radar: { icon: Radar },
  watchlist: { icon: Bookmark },
  compare: { icon: GitCompareArrows },
}

export default function MotionPageHeader({ title, variant }: { title: string; variant: MotionPageVariant }) {
  const page = pages[variant]
  const Icon = page.icon
  return (
    <header className={`delta-page-header delta-page-header--${variant}`}>
      <h1 lang="en">{title}</h1>
      <span className="delta-page-header__icon" aria-hidden="true"><Icon size={25} strokeWidth={1.5} /></span>
    </header>
  )
}
