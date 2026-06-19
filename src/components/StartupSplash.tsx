import { useEffect } from 'react'
import './StartupSplash.css'

export default function StartupSplash() {
  useEffect(() => {
    document.body.classList.remove('startup-active')
    window.dispatchEvent(new Event('kpi-startup-complete'))
  }, [])

  return null
}
