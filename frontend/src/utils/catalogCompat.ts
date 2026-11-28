export interface TechItem { id: string; code: string; name: string }
export interface MaterialItem { id: string; name: string; technologies: string[]; colors: string[] }
export interface QualityItem { id: string; technology: string; name: string; layer_height_mm: number }
export interface ColorItem { id: string; name: string; hex: string; is_transparent: boolean }
export interface PostProcItem { id: string; code?: string; name: string; price: number | string; hours: number }
export interface DeliveryItem { id: string; type: string; name: string; price: number | string; days: number }
export interface PickupItem { id: string; delivery_method: string; name: string; address: string }

export interface CompatMatrix {
  materials: { id: string; technologies: string[]; colors: string[] }[]
  quality_profiles: { id: string; technology: string }[]
  post_processing: {
    id: string
    code: string
    incompatible_technologies: string[]
    forbids_transparent: boolean
    requires_multibody_3mf: boolean
  }[]
  delivery_methods: { id: string; type: string; pickup_points: string[] }[]
}

export interface CatalogData {
  technologies: TechItem[]
  materials: MaterialItem[]
  quality: QualityItem[]
  colors: ColorItem[]
  pp: PostProcItem[]
  delivery: DeliveryItem[]
  pickup: PickupItem[]
  compat: CompatMatrix
}

export function unwrapList<T>(res: T[] | { results?: T[] }): T[] {
  return Array.isArray(res) ? res : (res.results ?? [])
}

export function filterMaterials(cat: CatalogData, techId?: string): MaterialItem[] {
  if (!techId) return []
  return cat.materials.filter(m => m.technologies.includes(techId))
}

export function filterColors(cat: CatalogData, material?: MaterialItem): ColorItem[] {
  if (!material) return []
  return cat.colors.filter(c => material.colors.includes(c.id))
}

export function filterQualities(cat: CatalogData, techId?: string): QualityItem[] {
  if (!techId) return []
  return cat.quality.filter(q => q.technology === techId)
}

export function postProcessingBlockReason(
  pp: PostProcItem,
  cat: CatalogData,
  opts: { techId?: string; colorId?: string; isMultibody3mf: boolean },
): string | null {
  const rule = cat.compat.post_processing.find(r => r.id === pp.id)
  if (rule) {
    if (opts.techId && rule.incompatible_technologies.includes(opts.techId)) {
      return 'Недоступно для выбранной технологии'
    }
    const color = cat.colors.find(c => c.id === opts.colorId)
    if (color?.is_transparent && rule.forbids_transparent) {
      return 'Недоступно для прозрачного цвета'
    }
    if (rule.requires_multibody_3mf && !opts.isMultibody3mf) {
      return 'Только для 3MF-модели из нескольких тел'
    }
    return null
  }
  if (pp.code === 'ASSEMBLY' && !opts.isMultibody3mf) {
    return 'Только для 3MF-модели из нескольких тел'
  }
  return null
}
