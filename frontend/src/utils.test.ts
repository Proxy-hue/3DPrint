import { describe, expect, it } from 'vitest'
import { EVENT_LABELS, STATUSES, eventLabel, rub } from './components/ui'
import {
  type CatalogData,
  filterColors,
  filterMaterials,
  filterQualities,
  postProcessingBlockReason,
  unwrapList,
} from './utils/catalogCompat'

describe('ui helpers', () => {
  it('содержит 14 статусов', () => expect(STATUSES).toHaveLength(14))
  it('форматирует рубли из числа и строки DRF Decimal', () => {
    expect(rub(1748)).toContain('₽')
    expect(rub('350.00')).toContain('350')
    expect(rub(null)).toBe('—')
  })
  it('переводит события заказа на русский язык', () => {
    expect(EVENT_LABELS.CREATED).toBe('Создание черновика')
    expect(eventLabel({ type: 'STATUS_CHANGED', from_status: 'DRAFT', to_status: 'NEW' })).toBe(
      'Статус: Черновик → «Новый»',
    )
  })
})

describe('catalog compatibility helpers', () => {
  const cat: CatalogData = {
    technologies: [{ id: 't1', code: 'FDM', name: 'FDM' }, { id: 't2', code: 'DMLS', name: 'DMLS' }],
    materials: [{ id: 'm1', name: 'PLA', technologies: ['t1'], colors: ['c1', 'c2'] }],
    quality: [{ id: 'q1', technology: 't1', name: 'Стандарт', layer_height_mm: 0.2 }],
    colors: [
      { id: 'c1', name: 'белый', hex: '#fff', is_transparent: false },
      { id: 'c2', name: 'прозрачный', hex: '#eee', is_transparent: true },
    ],
    pp: [
      { id: 'p1', code: 'PAINTING', name: 'Покраска', price: '500.00', hours: 2 },
      { id: 'p2', code: 'ASSEMBLY', name: 'Сборка', price: '300.00', hours: 1 },
    ],
    delivery: [],
    pickup: [],
    compat: {
      materials: [{ id: 'm1', technologies: ['t1'], colors: ['c1', 'c2'] }],
      quality_profiles: [{ id: 'q1', technology: 't1' }],
      post_processing: [
        {
          id: 'p1',
          code: 'PAINTING',
          incompatible_technologies: ['t2'],
          forbids_transparent: true,
          requires_multibody_3mf: false,
        },
        {
          id: 'p2',
          code: 'ASSEMBLY',
          incompatible_technologies: [],
          forbids_transparent: false,
          requires_multibody_3mf: true,
        },
      ],
      delivery_methods: [],
    },
  }

  it('распаковывает пагинированные ответы DRF', () => {
    expect(unwrapList({ results: [1, 2] })).toEqual([1, 2])
    expect(unwrapList([3, 4])).toEqual([3, 4])
  })

  it('фильтрует материалы, цвета и профили качества', () => {
    const mats = filterMaterials(cat, 't1')
    expect(mats).toHaveLength(1)
    expect(filterColors(cat, mats[0])).toHaveLength(2)
    expect(filterQualities(cat, 't1')).toHaveLength(1)
    expect(filterMaterials(cat, 't2')).toEqual([])
  })

  it('проверяет ограничения постобработки', () => {
    expect(postProcessingBlockReason(cat.pp[0], cat, { techId: 't2', colorId: 'c1', isMultibody3mf: false })).toBeTruthy()
    expect(postProcessingBlockReason(cat.pp[0], cat, { techId: 't1', colorId: 'c2', isMultibody3mf: false })).toBeTruthy()
    expect(postProcessingBlockReason(cat.pp[0], cat, { techId: 't1', colorId: 'c1', isMultibody3mf: false })).toBeNull()
    expect(postProcessingBlockReason(cat.pp[1], cat, { techId: 't1', colorId: 'c1', isMultibody3mf: false })).toBeTruthy()
    expect(postProcessingBlockReason(cat.pp[1], cat, { techId: 't1', colorId: 'c1', isMultibody3mf: true })).toBeNull()
  })
})
