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
    }, 1300)

    const safetyTimer = window.setTimeout(() => {
      setVisible(false)
      document.body.classList.remove('startup-active')
      window.dispatchEvent(new Event('kpi-startup-complete'))
    }, 1700)

    return () => {
      window.clearTimeout(timer)
      window.clearTimeout(safetyTimer)
      document.body.classList.remove('startup-active')
    }
  }, [])

  if (!visible) return null

  return (
    <div className="startup-splash" aria-hidden="true">
      <div className="startup-splash__scan" />
      <div className="startup-splash__dots">
        <span />
        <span />
        <span />
      </div>
    </div>
  )
}
