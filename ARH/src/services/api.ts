/// <reference types="vite/client" />

import type {
  CreateOrderPayload,
  Material,
  Order,
  OrderConfiguration,
  OrderStatus,
  PriceBreakdown,
  PrintingTechnology,
  UploadedModel,
  ValidationResult,
} from '../types';

const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') || 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = '3dprint.access';
const REFRESH_TOKEN_KEY = '3dprint.refresh';

export const materials: Material[] = [
  { id: 'pla', name: 'PLA', description: 'Универсальный пластик для прототипов и макетов', pricePerGram: 3.2, density: 1.24, technology: 'FDM', colors: ['#f1f1ee', '#4b525c', '#ff8a3d', '#4c8df6', '#3fbf8f', '#e5484d'], colorNames: ['Белый', 'Графит', 'Оранжевый', 'Синий', 'Зелёный', 'Красный'] },
  { id: 'abs', name: 'ABS', description: 'Прочный и термостойкий, для функциональных деталей', pricePerGram: 3.8, density: 1.04, technology: 'FDM', colors: ['#f1f1ee', '#4b525c', '#ff8a3d', '#4c8df6', '#e5484d'], colorNames: ['Белый', 'Графит', 'Оранжевый', 'Синий', 'Красный'] },
  { id: 'petg', name: 'PETG', description: 'Ударопрочный материал с хорошей химической стойкостью', pricePerGram: 4.1, density: 1.27, technology: 'FDM', colors: ['#f1f1ee', '#4b525c', '#ff8a3d', '#4c8df6', '#3fbf8f'], colorNames: ['Белый', 'Графит', 'Оранжевый', 'Синий', 'Зелёный'] },
  { id: 'resin', name: 'Resin', description: 'Высокая детализация и гладкая поверхность', pricePerGram: 9.5, density: 1.1, technology: 'SLA', colors: ['#f1f1ee', '#4b525c', '#ff8a3d'], colorNames: ['Белый', 'Графит', 'Оранжевый'] },
  { id: 'nylon', name: 'Nylon', description: 'Износостойкий инженерный материал для сложных деталей', pricePerGram: 8.2, density: 1.14, technology: 'SLS', colors: ['#f1f1ee', '#4b525c'], colorNames: ['Белый', 'Графит'] },
];

export function getAccessToken(): string | null {
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  return Boolean(getAccessToken());
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body instanceof FormData) {
    headers.delete('Content-Type');
  } else if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const access = getAccessToken();
  if (access) headers.set('Authorization', `Bearer ${access}`);

  let response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (response.status === 401) {
    const refresh = window.localStorage.getItem(REFRESH_TOKEN_KEY);
    if (refresh) {
      const refreshResponse = await fetch(`${API_URL}/api/users/refresh/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh }),
      });
      if (refreshResponse.ok) {
        const refreshed = await refreshResponse.json() as { access: string };
        window.localStorage.setItem(ACCESS_TOKEN_KEY, refreshed.access);
        headers.set('Authorization', `Bearer ${refreshed.access}`);
        response = await fetch(`${API_URL}${path}`, { ...options, headers });
      }
    }
  }
  if (response.status === 401) {
    window.localStorage.removeItem(ACCESS_TOKEN_KEY);
    window.localStorage.removeItem(REFRESH_TOKEN_KEY);
  }
  const text = await response.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!response.ok) {
    if (typeof data === 'object' && data !== null) {
      const record = data as Record<string, unknown>;
      const message = record.detail
        ?? record.message
        ?? Object.values(record).flat().join(' ');
      throw new Error(String(message));
    }
    throw new Error(typeof data === 'string' ? data : `Ошибка запроса: ${response.status}`);
  }
  return data as T;
}

export async function login(username: string, password: string): Promise<void> {
  const data = await request<{ access: string; refresh: string }>('/api/users/login/', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
  window.localStorage.setItem(ACCESS_TOKEN_KEY, data.access);
  window.localStorage.setItem(REFRESH_TOKEN_KEY, data.refresh);
}

export async function register(payload: {
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  password: string;
  phone?: string;
}): Promise<void> {
  await request('/api/users/register/', { method: 'POST', body: JSON.stringify(payload) });
  await login(payload.username, payload.password);
}

export async function logout(): Promise<void> {
  const refresh = window.localStorage.getItem(REFRESH_TOKEN_KEY);
  try {
    if (refresh) await request('/api/users/logout/', { method: 'POST', body: JSON.stringify({ refresh }) });
  } finally {
    window.localStorage.removeItem(ACCESS_TOKEN_KEY);
    window.localStorage.removeItem(REFRESH_TOKEN_KEY);
  }
}

export async function getProfile(): Promise<{ id: number; username: string; role: string; first_name: string; last_name: string }> {
  return request('/api/users/me/');
}

export async function uploadModel(file: File): Promise<{ model: UploadedModel; validation: ValidationResult }> {
  const form = new FormData();
  form.append('file', file);
  try {
    const data = await request<{
      id: number;
      original_name: string;
      format: string;
      size: number;
      status: string;
      validation_errors: string[];
      width_mm: number | null;
      height_mm: number | null;
      depth_mm: number | null;
    }>('/api/models/', { method: 'POST', body: form });
    const deadline = Date.now() + 6 * 60 * 1000;
    let validatedModel = data;
    while (validatedModel.status === 'validating') {
      if (Date.now() >= deadline) {
        throw new Error('Проверка модели ещё выполняется. Файл сохранён, повторите проверку позже.');
      }
      await new Promise<void>((resolve) => {
        window.setTimeout(() => resolve(), 1000);
      });
      validatedModel = await request<typeof data>(`/api/models/${data.id}/`);
    }

    const validationErrors = validatedModel.validation_errors ?? [];
    const isValid = validatedModel.status === 'validated';
    return {
      model: {
        id: validatedModel.id,
        name: validatedModel.original_name,
        size: validatedModel.size,
        format: validatedModel.format.toUpperCase(),
        uploadedAt: new Date().toISOString(),
        dimensions: validatedModel.width_mm !== null
          && validatedModel.height_mm !== null
          && validatedModel.depth_mm !== null
          ? {
            x: validatedModel.width_mm,
            y: validatedModel.height_mm,
            z: validatedModel.depth_mm,
          }
          : undefined,
      },
      validation: {
        valid: isValid,
        errors: validationErrors,
        message: isValid
          ? 'Файл проверен и готов к расчёту.'
          : validationErrors.join(' ') || 'Модель отклонена при проверке.',
      },
    };
  } catch (error) {
    return {
      model: { name: file.name, size: file.size, format: file.name.split('.').pop()?.toUpperCase() || '', uploadedAt: new Date().toISOString() },
      validation: {
        valid: false,
        errors: [error instanceof Error ? error.message : 'Не удалось загрузить модель.'],
        message: error instanceof Error ? error.message : 'Не удалось загрузить модель.',
      },
    };
  }
}

export async function calculatePrice(input: {
  materialId: string;
  technology: PrintingTechnology;
  layerHeight: number;
  infill: number;
  postProcessing: string;
  quantity: number;
  dimensions: { x: number; y: number; z: number };
}): Promise<PriceBreakdown> {
  return request('/api/models/calculate-price/', {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

interface ApiOrder {
  id: number;
  status: OrderStatus;
  configuration: OrderConfiguration;
  price: PriceBreakdown;
  equipment_compatible: boolean;
  created_at: string;
  model_id?: number;
  model?: {
    id: number;
    original_name: string;
    size: number;
    format: string;
    created_at: string;
  };
}

function mapOrder(row: ApiOrder): Order {
  const model = row.model;
  return {
    id: `A-${String(row.id).padStart(6, '0')}`,
    date: row.created_at,
    status: row.status,
    model: model ? {
      id: model.id,
      name: model.original_name,
      size: model.size,
      format: model.format.toUpperCase(),
      uploadedAt: model.created_at,
    } : { name: '3D-модель', size: 0, format: '', uploadedAt: row.created_at },
    ...row.configuration,
    price: row.price,
    equipmentCompatible: row.equipment_compatible,
  };
}

export async function createOrder(payload: CreateOrderPayload): Promise<Order> {
  if (!payload.model.id) throw new Error('Сохраненная модель не найдена.');
  const row = await request<ApiOrder>('/api/models/orders/', {
    method: 'POST',
    body: JSON.stringify({
      model_id: payload.model.id,
      configuration: payload.configuration,
    }),
  });
  return mapOrder(row);
}

export async function getOrders(): Promise<Order[]> {
  const rows = await request<ApiOrder[]>('/api/models/orders/');
  return rows.map(mapOrder);
}

export async function updateOrderStatus(id: string, status: OrderStatus): Promise<Order> {
  const numericId = Number(id.replace(/\D/g, ''));
  const row = await request<ApiOrder>(`/api/models/orders/${numericId}/`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });
  return mapOrder(row);
}
