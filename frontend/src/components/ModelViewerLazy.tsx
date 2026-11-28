import { lazy, Suspense } from 'react'

const Viewer = lazy(() => import('./ModelViewer'))

type Props = { orderId: string; version: number; format: string; height?: number }

/** Three.js подгружается отдельным чанком только при показе модели. */
export default function ModelViewer(props: Props) {
  return (
    <Suspense fallback={<div className="flex h-40 items-center justify-center text-sm text-slate-500">Загрузка 3D-просмотрщика…</div>}>
      <Viewer {...props} />
    </Suspense>
  )
}
