import { useEffect, useState } from 'react'
import './StartupSplash.css'

export default function StartupSplash() {
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    document.body.classList.add('startup-active')

    const timer = window.setTimeout(() => {
      setVisible(false)
      document.body.classList.remove('startup-active')
      window.dispatchEvent(new Event('kpi-startup-complete'))
    }, 1500)

    const safetyTimer = window.setTimeout(() => {
      setVisible(false)
      document.body.classList.remove('startup-active')
      window.dispatchEvent(new Event('kpi-startup-complete'))
    }, 1900)

    return () => {
      window.clearTimeout(timer)
      window.clearTimeout(safetyTimer)
      document.body.classList.remove('startup-active')
    }
  }, [])

  if (!visible) return null

  return (
    <div className="startup-splash" aria-hidden="true">
      <div className="startup-splash__grid" />
      <div className="startup-splash__boot">
        <span className="startup-splash__core" />
        <span className="startup-splash__ring" />
        <span className="startup-splash__beam" />
      </div>
    </div>
  )
}
