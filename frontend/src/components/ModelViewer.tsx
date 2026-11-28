import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js'
import { ThreeMFLoader } from 'three/examples/jsm/loaders/3MFLoader.js'
import { API_BASE, api } from '../api/client'

interface Props {
  orderId: string
  version: number
  format: string
  height?: number
  colorHex?: string
  transparent?: boolean
}

function applyMaterialStyle(mat: THREE.MeshStandardMaterial, colorHex?: string, transparent?: boolean) {
  const hex = colorHex && colorHex.trim() ? colorHex : (transparent ? '#dbeafe' : '#6366f1')
  mat.color.set(hex)
  mat.transparent = !!transparent
  mat.opacity = transparent ? 0.58 : 1
  mat.roughness = transparent ? 0.18 : 0.45
  mat.metalness = colorHex?.trim().toUpperCase() === '#B0B7BD' ? 0.45 : 0.18
  mat.needsUpdate = true
}

async function fetchBuffer(orderId: string, version: number): Promise<ArrayBuffer> {
  const info = await api<{ url: string | null; download_url: string }>(`/orders/${orderId}/model/${version}/file`)
  if (info.url) {
    try {
      const r = await fetch(info.url)
      if (r.ok) return await r.arrayBuffer()
    } catch { /* резервный путь через backend */ }
  }
  const defaultDownload = `${API_BASE.replace(/\/$/, '')}/orders/${orderId}/model/${version}/download`
  const raw = info.download_url
  const fallbackUrl = raw
    ? (raw.startsWith('/api/') && API_BASE !== '/api'
      ? `${API_BASE.replace(/\/$/, '')}${raw.slice(4)}`
      : raw)
    : defaultDownload
  const r = await fetch(fallbackUrl, { credentials: 'include' })
  if (!r.ok) throw new Error('Не удалось загрузить файл модели.')
  return await r.arrayBuffer()
}

export default function ModelViewer({ orderId, version, format, height = 360, colorHex, transparent }: Props) {
  const host = useRef<HTMLDivElement>(null)
  const matRef = useRef<THREE.MeshStandardMaterial | null>(null)
  const rootRef = useRef<THREE.Object3D | null>(null)
  const origMatsRef = useRef<Map<THREE.Mesh, THREE.Material | THREE.Material[]>>(new Map())
  const styleRef = useRef({ colorHex, transparent })
  styleRef.current = { colorHex, transparent }
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const syncMeshMaterials = (hex?: string, isTransp?: boolean) => {
    const mat = matRef.current
    if (!mat) return
    applyMaterialStyle(mat, hex, isTransp)
    const root = rootRef.current
    if (!root) return
    const hasCustomColor = !!(hex?.trim() || isTransp)
    root.traverse(c => {
      if ((c as THREE.Mesh).isMesh) {
        const mesh = c as THREE.Mesh
        if (hasCustomColor) {
          mesh.material = mat
        } else {
          const orig = origMatsRef.current.get(mesh)
          mesh.material = orig ?? mat
        }
      }
    })
  }

  useEffect(() => {
    syncMeshMaterials(colorHex, transparent)
  }, [colorHex, transparent])

  useEffect(() => {
    const el = host.current
    if (!el) return
    let disposed = false
    let raf = 0
    setError(''); setLoading(true)

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setPixelRatio(window.devicePixelRatio)
    const w = el.clientWidth || 600
    renderer.setSize(w, height)
    el.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(45, w / height, 0.1, 100000)
    camera.up.set(0, 0, 1)
    scene.add(new THREE.AmbientLight(0xffffff, 0.55))
    scene.add(new THREE.HemisphereLight(0xffffff, 0x475569, 0.75))
    const dir = new THREE.DirectionalLight(0xffffff, 1.0)
    dir.position.set(1, -1, 2)
    scene.add(dir)
    const fillDir = new THREE.DirectionalLight(0xffffff, 0.45)
    fillDir.position.set(-1, 1, -0.5)
    scene.add(fillDir)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true

    const material = new THREE.MeshStandardMaterial()
    applyMaterialStyle(material, styleRef.current.colorHex, styleRef.current.transparent)
    matRef.current = material

    const onResize = () => {
      if (!el || disposed) return
      const nw = el.clientWidth || 600
      camera.aspect = nw / height
      camera.updateProjectionMatrix()
      renderer.setSize(nw, height)
    }
    window.addEventListener('resize', onResize)

    const prepareMeshes = (rootObj: THREE.Object3D, rememberOrig: boolean) => {
      rootObj.traverse(c => {
        if ((c as THREE.Mesh).isMesh) {
          const mesh = c as THREE.Mesh
          if (mesh.geometry && !mesh.geometry.attributes.normal) {
            mesh.geometry.computeVertexNormals()
          }
          if (rememberOrig && mesh.material) {
            origMatsRef.current.set(mesh, mesh.material)
          }
          if (!rememberOrig || !mesh.material) {
            mesh.material = material
          }
        }
      })
    }

    let gridObj: THREE.GridHelper | null = null

    const place = (obj: THREE.Object3D, rememberOrig = false) => {
      prepareMeshes(obj, rememberOrig)
      rootRef.current = obj
      const box = new THREE.Box3().setFromObject(obj)
      const size = box.getSize(new THREE.Vector3())
      const center = box.getCenter(new THREE.Vector3())
      obj.position.sub(center)
      scene.add(obj)
      const r = Math.max(size.x, size.y, size.z) || 1
      camera.position.set(r * 1.6, -r * 1.6, r * 1.2)
      controls.target.set(0, 0, 0)
      controls.update()
      const grid = new THREE.GridHelper(r * 2, 20, 0x888888, 0x444444)
      grid.rotation.x = Math.PI / 2
      grid.position.z = -size.z / 2
      gridObj = grid
      scene.add(grid)
    }

    ;(async () => {
      try {
        const buf = await fetchBuffer(orderId, version)
        if (disposed) return
        if (format === 'STL') {
          const geo = new STLLoader().parse(buf)
          geo.computeVertexNormals()
          place(new THREE.Mesh(geo, material))
        } else if (format === 'OBJ') {
          const obj = new OBJLoader().parse(new TextDecoder().decode(buf))
          place(obj)
        } else {
          place(new ThreeMFLoader().parse(buf), true)
        }
        syncMeshMaterials(styleRef.current.colorHex, styleRef.current.transparent)
        setLoading(false)
      } catch (e) {
        if (!disposed) { setError(e instanceof Error ? e.message : 'Не удалось отобразить модель.'); setLoading(false) }
      }
    })()

    const loop = () => {
      raf = requestAnimationFrame(loop)
      controls.update()
      renderer.render(scene, camera)
    }
    loop()

    return () => {
      disposed = true
      if (rootRef.current) {
        rootRef.current.traverse(c => {
          if ((c as THREE.Mesh).isMesh) {
            (c as THREE.Mesh).geometry?.dispose()
          }
        })
      }
      origMatsRef.current.forEach(m => {
        if (Array.isArray(m)) m.forEach(x => x.dispose())
        else m.dispose()
      })
      if (gridObj) {
        gridObj.geometry.dispose()
        const gm = gridObj.material
        if (Array.isArray(gm)) gm.forEach(x => x.dispose())
        else gm.dispose()
      }
      matRef.current = null
      rootRef.current = null
      origMatsRef.current.clear()
      window.removeEventListener('resize', onResize)
      cancelAnimationFrame(raf)
      controls.dispose()
      renderer.dispose()
      material.dispose()
      if (renderer.domElement.parentNode === el) el.removeChild(renderer.domElement)
    }
  }, [orderId, version, format, height])

  return (
    <div className="relative overflow-hidden rounded-lg border border-slate-200 bg-slate-100 dark:border-slate-800 dark:bg-slate-900" style={{ height }}>
      <div ref={host} className="h-full w-full" />
      {loading && <div className="absolute inset-0 flex items-center justify-center text-sm text-slate-500">Загрузка 3D-модели…</div>}
      {error && <div className="absolute inset-0 flex items-center justify-center p-4 text-center text-sm text-rose-600">{error}</div>}
    </div>
  )
}
