type MotionPageVariant = 'dashboard' | 'finder' | 'universe' | 'radar' | 'watchlist' | 'compare'

export default function MotionPageHeader({ title, variant }: { title: string; variant: MotionPageVariant }) {
  return (
    <header className={`delta-page-header delta-page-header--${variant}`}>
      <h1 lang="en">{title}</h1>
    </header>
  )
}
