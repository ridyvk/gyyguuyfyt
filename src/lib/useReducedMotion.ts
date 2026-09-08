import { useEffect, useState } from 'react'

const readPreference = () => document.documentElement.dataset.motion === 'reduce'
  || window.matchMedia('(prefers-reduced-motion: reduce)').matches

export function useReducedMotion() {
  const [reduced, setReduced] = useState(readPreference)
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const update = () => setReduced(readPreference())
    window.addEventListener('delta-motion-change', update)
    media.addEventListener('change', update)
    update()
    return () => {
      window.removeEventListener('delta-motion-change', update)
      media.removeEventListener('change', update)
    }
  }, [])
  return reduced
}
