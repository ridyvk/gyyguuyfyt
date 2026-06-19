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
    }, 1550)

    const safetyTimer = window.setTimeout(() => {
      setVisible(false)
      document.body.classList.remove('startup-active')
      window.dispatchEvent(new Event('kpi-startup-complete'))
    }, 1950)

    return () => {
      window.clearTimeout(timer)
      window.clearTimeout(safetyTimer)
      document.body.classList.remove('startup-active')
    }
  }, [])

  if (!visible) return null

  return (
    <div className="startup-splash" aria-hidden="true">
      <div className="startup-splash__depth" />
      <div className="startup-splash__portal">
        <span className="startup-splash__core" />
        <span className="startup-splash__wave startup-splash__wave--one" />
        <span className="startup-splash__wave startup-splash__wave--two" />
        <span className="startup-splash__wave startup-splash__wave--three" />
        <span className="startup-splash__wash" />
        <span className="startup-splash__glint startup-splash__glint--one" />
        <span className="startup-splash__glint startup-splash__glint--two" />
        <span className="startup-splash__glint startup-splash__glint--three" />
      </div>
    </div>
  )
}
