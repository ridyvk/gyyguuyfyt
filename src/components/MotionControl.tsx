import { Pause, Play } from 'lucide-react'
import { useEffect, useState } from 'react'

export default function MotionControl() {
  const [reduced, setReduced] = useState(() => {
    try {
      const value = localStorage.getItem('delta-motion')
      if (value) return value === 'reduce'
    } catch { /* Device preferences remain optional. */ }
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  })
  useEffect(() => {
    document.documentElement.dataset.motion = reduced ? 'reduce' : 'full'
    window.dispatchEvent(new Event('delta-motion-change'))
  }, [reduced])
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const changed = () => {
      if (media.matches) setReduced(true)
    }
    media.addEventListener('change', changed)
    return () => media.removeEventListener('change', changed)
  }, [])
  return (
    <button type="button" className="motion-control" aria-pressed={reduced}
      aria-label="アニメーションを停止" title={reduced ? '動きを再開' : '動きを止める'}
      onClick={() => setReduced((value) => {
        try { localStorage.setItem('delta-motion', value ? 'full' : 'reduce') } catch { /* Optional. */ }
        return !value
      })}>
      {reduced ? <Play size={16} /> : <Pause size={16} />}
    </button>
  )
}
