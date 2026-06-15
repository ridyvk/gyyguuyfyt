import { useEffect, useState } from 'react'
import './StartupSplash.css'

export default function StartupSplash() {
  const [leaving, setLeaving] = useState(false)
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    document.body.classList.add('startup-active')

    const leaveTimer = window.setTimeout(() => setLeaving(true), 1050)
    const removeTimer = window.setTimeout(() => setVisible(false), 1500)

    return () => {
      window.clearTimeout(leaveTimer)
      window.clearTimeout(removeTimer)
      document.body.classList.remove('startup-active')
    }
  }, [])

  useEffect(() => {
    if (!visible) {
      document.body.classList.remove('startup-active')
      window.dispatchEvent(new Event('kpi-startup-complete'))
    }
  }, [visible])

  if (!visible) return null

  return (
    <div
      className={`startup-splash${leaving ? ' is-leaving' : ''}`}
      role="status"
      aria-label="KPI Scopeを起動しています"
    >
      <div className="startup-splash__glow" />
      <div className="startup-splash__content">
        <div className="startup-splash__logo">
          <img src="./icon.svg" alt="" />
          <span className="startup-splash__shine" />
        </div>
        <div className="startup-splash__wordmark">
          <strong>KPI Scope</strong>
          <span>COMPANY INTELLIGENCE</span>
        </div>
        <i className="startup-splash__line" />
      </div>
    </div>
  )
}
