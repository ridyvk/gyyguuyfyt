export type DeltaTheme = 'dark' | 'light'

export const DELTA_THEME_STORAGE_KEY = 'delta-ui-theme'

const isDeltaTheme = (value: unknown): value is DeltaTheme =>
  value === 'dark' || value === 'light'

export const getDeltaTheme = (): DeltaTheme => {
  if (typeof document !== 'undefined') {
    const activeTheme = document.documentElement.dataset.theme
    if (isDeltaTheme(activeTheme)) return activeTheme
  }

  if (typeof window !== 'undefined') {
    try {
      const storedTheme = window.localStorage.getItem(DELTA_THEME_STORAGE_KEY)
      if (isDeltaTheme(storedTheme)) return storedTheme
    } catch {
      // Storage can be unavailable in strict privacy modes. Dark remains default.
    }
  }

  return 'dark'
}

export const applyDeltaTheme = (
  theme: DeltaTheme,
  persist = true,
) => {
  document.documentElement.dataset.theme = theme
  document.documentElement.style.colorScheme = theme
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute('content', theme === 'light' ? '#f3f6fb' : '#05070c')

  if (!persist) return

  try {
    window.localStorage.setItem(DELTA_THEME_STORAGE_KEY, theme)
  } catch {
    // The visual switch still works even when persistence is blocked.
  }
}

export const initializeDeltaTheme = () => {
  const theme = getDeltaTheme()
  applyDeltaTheme(theme, false)
  return theme
}
