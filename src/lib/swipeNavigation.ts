export const primaryRoutes = ['/', '/map', '/universe', '/radar', '/watchlist', '/compare'] as const

export function swipeDestination(path: string, dx: number, dy: number, elapsed: number) {
  const index = primaryRoutes.findIndex((route) => route === path)
  if (index < 0 || elapsed > 650 || elapsed < 0 || Math.abs(dx) < 72 || Math.abs(dx) < Math.abs(dy) * 2.2 || Math.abs(dy) > 36) return null
  const direction = dx < 0 ? 1 : -1
  const next = primaryRoutes[index + direction]
  return next ? { path: next, direction } : null
}
