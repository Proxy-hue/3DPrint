export type MaterialId = 'pla' | 'abs' | 'petg' | 'resin' | 'nylon';
export type PrintingTechnology = 'FDM' | 'SLA' | 'SLS';
export type OrderStatus = 'Pending' | 'In Production' | 'Shipped' | 'Delivered';
export type PostProcessing = 'none' | 'sanding' | 'painting';

export interface Material {
  id: MaterialId;
  name: string;
  description: string;
  pricePerGram: number;
  density: number;
  technology: PrintingTechnology;
  colors: string[];
  colorNames: string[];
}

export interface UploadedModel {
  name: string;
  size: number;
  format: string;
  uploadedAt: string;
}

export interface ValidationResult {
  valid: boolean;
  message: string;
  errors: string[];
}

export interface PriceBreakdown {
  material: number;
  printing: number;
  postProcessing: number;
  delivery: number;
  total: number;
  leadTimeDays: number;
  estimatedWeight: number;
}

export interface OrderConfiguration {
  material: MaterialId;
  technology: PrintingTechnology;
  color: string;
  layerHeight: number;
  infill: number;
  postProcessing: PostProcessing;
  quantity: number;
  dimensions: { x: number; y: number; z: number };
}

export interface Order extends OrderConfiguration {
  id: string;
  date: string;
  status: OrderStatus;
  model: UploadedModel;
  price: PriceBreakdown;
  equipmentCompatible: boolean;
}

export interface CreateOrderPayload {
  configuration: OrderConfiguration;
  model: UploadedModel;
  price: PriceBreakdown;
}

export interface NavigationItem {
  id: 'dashboard' | 'orders' | 'help' | 'manager';
  label: string;
}
