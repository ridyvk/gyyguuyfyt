import {
  ACESFilmicToneMapping, AmbientLight, DirectionalLight, Group,
  Mesh, MeshPhysicalMaterial, PerspectiveCamera, PMREMGenerator,
  Scene, TorusGeometry, WebGLRenderer,
} from 'three'
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js'
import type { BreadthCounts } from './marketBreadth'

export function createMarketScene(
  host: HTMLDivElement,
  counts: BreadthCounts,
  onReady: (ready: boolean) => void,
) {
  const renderer = new WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'low-power' })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5))
  renderer.setClearColor(0xffffff, 0)
  renderer.toneMapping = ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.2
  host.appendChild(renderer.domElement)

  const scene = new Scene()
  const camera = new PerspectiveCamera(35, 1, 0.1, 30)
  camera.position.set(0, 0, 5.9)
  const studio = new RoomEnvironment()
  const pmrem = new PMREMGenerator(renderer)
  let environment
  try {
    environment = pmrem.fromScene(studio, 0.04)
  } catch (error) {
    studio.dispose()
    pmrem.dispose()
    renderer.dispose()
    renderer.forceContextLoss()
    renderer.domElement.remove()
    throw error
  }
  scene.environment = environment.texture
  studio.dispose()
  pmrem.dispose()
  scene.add(new AmbientLight(0xffffff, 1.2))
  const key = new DirectionalLight(0xffffff, 3.8)
  key.position.set(-3, 5, 6)
  scene.add(key)
  const rim = new DirectionalLight(0x9abfff, 2)
  rim.position.set(3, -1, -2)
  scene.add(rim)

  const sculpture = new Group()
  scene.add(sculpture)
  const total = counts.up + counts.down + counts.flat
  const geometries: TorusGeometry[] = []
  const materials: MeshPhysicalMaterial[] = []
  let angle = 0
  for (const [value, color] of [[counts.up, '#26847c'], [counts.down, '#c27687'], [counts.flat, '#a6b7cf']] as const) {
    if (!value) continue
    const arc = (value / total) * Math.PI * 2
    const material = new MeshPhysicalMaterial({
      color, metalness: 0.16, roughness: 0.18, clearcoat: 1,
      clearcoatRoughness: 0.07, transmission: 0.06, thickness: 0.7,
      ior: 1.45, envMapIntensity: 1.8,
    })
    materials.push(material)
    // Every arc is proportional to a real count; no decorative price history.
    const geometry = new TorusGeometry(0.93, 0.245, 20, Math.max(6, Math.ceil(arc * 24)), arc)
    geometries.push(geometry)
    const segment = new Mesh(geometry, material)
    segment.rotation.z = angle
    sculpture.add(segment)
    angle += arc
  }
  sculpture.rotation.set(-0.46, -0.3, 0.6)

  let frame = 0
  let visible = true
  let lost = false
  let disposed = false
  let lastFrame = 0
  let elapsed = 0
  let pointerX = 0
  let pointerY = 0
  const media = window.matchMedia('(prefers-reduced-motion: reduce)')
  const reduced = () => document.documentElement.dataset.motion === 'reduce' || media.matches
  const render = () => {
    if (disposed || lost) return
    try {
      renderer.render(scene, camera)
      onReady(true)
    } catch {
      lost = true
      onReady(false)
      cancelAnimationFrame(frame)
    }
  }
  const tick = (time: number) => {
    frame = 0
    if (disposed || lost || !visible || document.hidden || reduced()) return
    if (time - lastFrame >= 1000 / 30) {
      elapsed += Math.min((time - lastFrame) / 1000, 0.05)
      lastFrame = time
      sculpture.rotation.x += (-0.46 + pointerY * 0.13 - sculpture.rotation.x) * 0.075
      sculpture.rotation.y += (-0.3 + pointerX * 0.2 - sculpture.rotation.y) * 0.075
      sculpture.position.y = Math.sin(elapsed * 0.8) * 0.035
      render()
    }
    if (!lost) frame = requestAnimationFrame(tick)
  }
  const sync = () => {
    cancelAnimationFrame(frame)
    frame = 0
    if (disposed || lost || !visible || document.hidden) return
    render()
    if (!reduced() && !lost) frame = requestAnimationFrame(tick)
  }
  const resize = () => {
    const { width, height } = host.getBoundingClientRect()
    if (!width || !height) return
    camera.aspect = width / height
    camera.updateProjectionMatrix()
    renderer.setSize(width, height, false)
    render()
  }
  const move = (event: PointerEvent) => {
    if (event.pointerType !== 'mouse' || reduced()) return
    const bounds = host.getBoundingClientRect()
    pointerX = ((event.clientX - bounds.left) / bounds.width - 0.5) * 2
    pointerY = ((event.clientY - bounds.top) / bounds.height - 0.5) * 2
  }
  const leave = () => { pointerX = 0; pointerY = 0 }
  const contextLost = (event: Event) => {
    event.preventDefault()
    lost = true
    onReady(false)
    cancelAnimationFrame(frame)
  }
  const contextRestored = () => { lost = false; resize(); sync() }
  const resizeObserver = new ResizeObserver(resize)
  resizeObserver.observe(host)
  const visibilityObserver = new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting
    sync()
  })
  visibilityObserver.observe(host)
  host.addEventListener('pointermove', move, { passive: true })
  host.addEventListener('pointerleave', leave)
  renderer.domElement.addEventListener('webglcontextlost', contextLost)
  renderer.domElement.addEventListener('webglcontextrestored', contextRestored)
  document.addEventListener('visibilitychange', sync)
  window.addEventListener('delta-motion-change', sync)
  media.addEventListener('change', sync)
  resize()
  sync()

  return () => {
    disposed = true
    cancelAnimationFrame(frame)
    resizeObserver.disconnect()
    visibilityObserver.disconnect()
    host.removeEventListener('pointermove', move)
    host.removeEventListener('pointerleave', leave)
    document.removeEventListener('visibilitychange', sync)
    window.removeEventListener('delta-motion-change', sync)
    media.removeEventListener('change', sync)
    renderer.domElement.removeEventListener('webglcontextlost', contextLost)
    renderer.domElement.removeEventListener('webglcontextrestored', contextRestored)
    geometries.forEach((geometry) => geometry.dispose())
    materials.forEach((material) => material.dispose())
    environment.dispose()
    renderer.dispose()
    renderer.forceContextLoss()
    renderer.domElement.remove()
  }
}
