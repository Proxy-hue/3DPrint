import type {
  CreateOrderPayload,
  Material,
  Order,
  OrderStatus,
  PriceBreakdown,
  PrintingTechnology,
  UploadedModel,
  ValidationResult,
} from '../types';

const STORAGE_KEY = '3dprint.mock-orders';
const delay = (duration = 500) => new Promise((resolve) => window.setTimeout(resolve, duration));

function isOrder(value: unknown): value is Order {
  if (typeof value !== 'object' || value === null) return false;
  const order = value as Partial<Order>;
  return typeof order.id === 'string'
    && typeof order.date === 'string'
    && typeof order.status === 'string'
    && typeof order.model?.name === 'string'
    && typeof order.price?.total === 'number';
}

export const materials: Material[] = [
  {
    id: 'pla',
    name: 'PLA',
    description: 'Универсальный пластик для прототипов и макетов',
    pricePerGram: 3.2,
    density: 1.24,
    technology: 'FDM',
    colors: ['#f1f1ee', '#4b525c', '#ff8a3d', '#4c8df6', '#3fbf8f', '#e5484d'],
    colorNames: ['Белый', 'Графит', 'Оранжевый', 'Синий', 'Зелёный', 'Красный'],
  },
  {
    id: 'abs',
    name: 'ABS',
    description: 'Прочный и термостойкий, для функциональных деталей',
    pricePerGram: 3.8,
    density: 1.04,
    technology: 'FDM',
    colors: ['#f1f1ee', '#4b525c', '#ff8a3d', '#4c8df6', '#e5484d'],
    colorNames: ['Белый', 'Графит', 'Оранжевый', 'Синий', 'Красный'],
  },
  {
    id: 'petg',
    name: 'PETG',
    description: 'Ударопрочный материал с хорошей химической стойкостью',
    pricePerGram: 4.1,
    density: 1.27,
    technology: 'FDM',
    colors: ['#f1f1ee', '#4b525c', '#ff8a3d', '#4c8df6', '#3fbf8f'],
    colorNames: ['Белый', 'Графит', 'Оранжевый', 'Синий', 'Зелёный'],
  },
  {
    id: 'resin',
    name: 'Resin',
    description: 'Высокая детализация и гладкая поверхность',
    pricePerGram: 9.5,
    density: 1.1,
    technology: 'SLA',
    colors: ['#f1f1ee', '#4b525c', '#ff8a3d'],
    colorNames: ['Белый', 'Графит', 'Оранжевый'],
  },
  {
    id: 'nylon',
    name: 'Nylon',
    description: 'Износостойкий инженерный материал для сложных деталей',
    pricePerGram: 8.2,
    density: 1.14,
    technology: 'SLS',
    colors: ['#f1f1ee', '#4b525c'],
    colorNames: ['Белый', 'Графит'],
  },
];

const initialOrders: Order[] = [
  {
    id: 'A-20418',
    date: '2026-10-25T14:12:00.000Z',
    status: 'In Production',
    model: { name: 'sensor_housing.stl', size: 2_400_000, format: 'STL', uploadedAt: '2026-10-25T14:10:00.000Z' },
    material: 'abs',
    technology: 'FDM',
    color: '#4b525c',
    layerHeight: 0.2,
    infill: 20,
    postProcessing: 'none',
    quantity: 12,
    dimensions: { x: 62, y: 40, z: 28 },
    price: { material: 1450, printing: 1240, postProcessing: 0, delivery: 390, total: 3080, leadTimeDays: 4, estimatedWeight: 22.2 },
    equipmentCompatible: true,
  },
  {
    id: 'A-20402',
    date: '2026-10-20T09:32:00.000Z',
    status: 'Delivered',
    model: { name: 'prototype_case.obj', size: 1_850_000, format: 'OBJ', uploadedAt: '2026-10-20T09:30:00.000Z' },
    material: 'pla',
    technology: 'FDM',
    color: '#f1f1ee',
    layerHeight: 0.2,
    infill: 40,
    postProcessing: 'sanding',
    quantity: 2,
    dimensions: { x: 80, y: 52, z: 36 },
    price: { material: 680, printing: 550, postProcessing: 350, delivery: 390, total: 1970, leadTimeDays: 3, estimatedWeight: 32.4 },
    equipmentCompatible: true,
  },
];

function readOrders(): Order[] {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return initialOrders;
  const parsed: unknown = JSON.parse(raw);
  if (!Array.isArray(parsed) || !parsed.every(isOrder)) throw new Error('Некорректный формат ответа со списком заказов.');
  return parsed;
}

function saveOrders(orders: Order[]) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(orders));
}

export async function uploadModel(file: File): Promise<{ model: UploadedModel; validation: ValidationResult }> {
  await delay(700);
  const extension = file.name.split('.').pop()?.toLowerCase() ?? '';
  const supported = ['stl', 'obj', '3mf', 'ply'];
  const errors: string[] = [];
  if (!supported.includes(extension)) errors.push('Поддерживаются форматы STL, OBJ, 3MF и PLY.');
  if (file.size === 0) errors.push('Файл пустой.');
  if (file.size > 100 * 1024 * 1024) errors.push('Размер файла не должен превышать 100 МБ.');

  const validation: ValidationResult = {
    valid: errors.length === 0,
    errors,
    message: errors.length ? errors.join(' ') : 'Файл проверен и готов к расчёту.',
  };
  if (!validation.valid) return { model: { name: file.name, size: file.size, format: extension.toUpperCase(), uploadedAt: new Date().toISOString() }, validation };

  return {
    model: { name: file.name, size: file.size, format: extension.toUpperCase(), uploadedAt: new Date().toISOString() },
    validation,
  };
}

export async function calculatePrice(
  input: {
    materialId: string;
    technology: PrintingTechnology;
    layerHeight: number;
    infill: number;
    postProcessing: string;
    quantity: number;
    dimensions: { x: number; y: number; z: number };
  },
): Promise<PriceBreakdown> {
  await delay(500);
  const material = materials.find((item) => item.id === input.materialId);
  if (!material) throw new Error('Выбранный материал не найден.');

  const volume = (input.dimensions.x * input.dimensions.y * input.dimensions.z) / 1000;
  const fillFactor = input.technology === 'SLA' ? 1 : 0.3 + (input.infill / 100) * 0.7;
  const estimatedWeight = Math.max(1, volume * fillFactor * material.density * 0.035);
  const layerFactor = 0.2 / input.layerHeight;
  const materialCost = estimatedWeight * material.pricePerGram * input.quantity;
  const printingCost = estimatedWeight * 42 * layerFactor * input.quantity;
  const postProcessingCost = input.postProcessing === 'sanding'
    ? 350 * input.quantity
    : input.postProcessing === 'painting' ? 650 * input.quantity : 0;
  const delivery = 390;
  const leadTimeDays = Math.max(2, Math.ceil((estimatedWeight * input.quantity * layerFactor) / 120));

  return {
    material: Math.round(materialCost),
    printing: Math.round(printingCost),
    postProcessing: postProcessingCost,
    delivery,
    total: Math.round(materialCost + printingCost + postProcessingCost + delivery),
    leadTimeDays,
    estimatedWeight: Math.round(estimatedWeight * 10) / 10,
  };
}

export async function createOrder(payload: CreateOrderPayload): Promise<Order> {
  await delay(600);
  const order: Order = {
    ...payload.configuration,
    id: `A-${String(Date.now()).slice(-6)}`,
    date: new Date().toISOString(),
    status: 'Pending',
    model: payload.model,
    price: payload.price,
    equipmentCompatible: true,
  };
  const orders = readOrders();
  saveOrders([order, ...orders]);
  return order;
}

export async function getOrders(): Promise<Order[]> {
  await delay(500);
  return [...readOrders()].sort((a, b) => b.date.localeCompare(a.date));
}

export async function updateOrderStatus(id: string, status: OrderStatus): Promise<Order> {
  await delay(500);
  const orders = readOrders();
  const index = orders.findIndex((order) => order.id === id);
  if (index === -1) throw new Error(`Заказ ${id} не найден.`);
  const updated = { ...orders[index], status };
  orders[index] = updated;
  saveOrders(orders);
  return updated;
}
