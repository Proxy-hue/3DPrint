import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js'
import { ThreeMFLoader } from 'three/examples/jsm/loaders/3MFLoader.js'
import { api } from '../api/client'

const API_BASE: string = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api'

interface Props { orderId: string; version: number; format: string; height?: number }

async function fetchBuffer(orderId: string, version: number): Promise<ArrayBuffer> {
  const info = await api<{ url: string | null; download_url: string }>(`/orders/${orderId}/model/${version}/file`)
  if (info.url) {
    try {
      const r = await fetch(info.url)
      if (r.ok) return await r.arrayBuffer()
    } catch { /* резервный путь через backend */ }
  }
  const fallbackUrl = info.download_url || `${API_BASE}/orders/${orderId}/model/${version}/download`
  const r = await fetch(fallbackUrl, { credentials: 'include' })
  if (!r.ok) throw new Error('Не удалось загрузить файл модели.')
  return await r.arrayBuffer()
}

export default function ModelViewer({ orderId, version, format, height = 360 }: Props) {
  const host = useRef<HTMLDivElement>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

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
    scene.add(new THREE.AmbientLight(0xffffff, 0.7))
    const dir = new THREE.DirectionalLight(0xffffff, 1.1)
    dir.position.set(1, -1, 2)
    scene.add(dir)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true

    const material = new THREE.MeshStandardMaterial({ color: 0x6366f1, metalness: 0.2, roughness: 0.55 })

    const onResize = () => {
      if (!el || disposed) return
      const nw = el.clientWidth || 600
      camera.aspect = nw / height
      camera.updateProjectionMatrix()
      renderer.setSize(nw, height)
    }
    window.addEventListener('resize', onResize)

    const prepareMeshes = (rootObj: THREE.Object3D) => {
      rootObj.traverse(c => {
        if ((c as THREE.Mesh).isMesh) {
          const mesh = c as THREE.Mesh
          if (mesh.geometry && !mesh.geometry.attributes.normal) {
            mesh.geometry.computeVertexNormals()
          }
          if (!mesh.material) mesh.material = material
        }
      })
    }

    const place = (obj: THREE.Object3D) => {
      prepareMeshes(obj)
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
          obj.traverse(c => { if ((c as THREE.Mesh).isMesh) (c as THREE.Mesh).material = material })
          place(obj)
        } else {
          place(new ThreeMFLoader().parse(buf))
        }
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
