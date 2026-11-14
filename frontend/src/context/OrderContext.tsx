import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { calculatePrice, createOrder, getOrders, materials, updateOrderStatus, uploadModel } from '../services/api';
import type {
  MaterialId,
  Order,
  OrderConfiguration,
  OrderStatus,
  PriceBreakdown,
  PrintingTechnology,
  UploadedModel,
} from '../types';

interface ToastMessage {
  id: number;
  message: string;
  tone: 'success' | 'error' | 'info';
}

interface OrderContextValue {
  configuration: OrderConfiguration;
  model: UploadedModel | null;
  price: PriceBreakdown | null;
  orders: Order[];
  isUploading: boolean;
  isCalculating: boolean;
  isCreatingOrder: boolean;
  toast: ToastMessage | null;
  setMaterial: (id: MaterialId) => void;
  setTechnology: (technology: PrintingTechnology) => void;
  setColor: (color: string) => void;
  setConfiguration: (patch: Partial<OrderConfiguration>) => void;
  uploadFile: (file: File) => Promise<void>;
  placeOrder: () => Promise<Order | null>;
  reorder: (order: Order) => void;
  changeStatus: (id: string, status: OrderStatus) => Promise<void>;
  notify: (message: string, tone?: ToastMessage['tone']) => void;
  dismissToast: () => void;
}

const initialConfiguration: OrderConfiguration = {
  material: 'pla',
  technology: 'FDM',
  color: materials[0].colors[0],
  layerHeight: 0.2,
  infill: 20,
  postProcessing: 'none',
  quantity: 1,
  dimensions: { x: 62, y: 40, z: 28 },
};

const OrderContext = createContext<OrderContextValue | null>(null);

export function OrderProvider({ children }: { children: ReactNode }) {
  const [configuration, setConfigurationState] = useState(initialConfiguration);
  const [model, setModel] = useState<UploadedModel | null>(null);
  const [price, setPrice] = useState<PriceBreakdown | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isCalculating, setIsCalculating] = useState(false);
  const [isCreatingOrder, setIsCreatingOrder] = useState(false);
  const [toast, setToast] = useState<ToastMessage | null>(null);
  const toastSequence = useRef(0);
  const calculationSequence = useRef(0);

  const notify = useCallback((message: string, tone: ToastMessage['tone'] = 'info') => {
    const id = ++toastSequence.current;
    setToast({ id, message, tone });
    window.setTimeout(() => setToast((current) => current?.id === id ? null : current), 4500);
  }, []);

  const dismissToast = useCallback(() => setToast(null), []);

  const refreshOrders = useCallback(async () => {
    try {
      setOrders(await getOrders());
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Не удалось загрузить заказы.', 'error');
    }
  }, [notify]);

  useEffect(() => {
    void refreshOrders();
  }, [refreshOrders]);

  useEffect(() => {
    const requestId = ++calculationSequence.current;
    const timer = window.setTimeout(async () => {
      setIsCalculating(true);
      try {
        const nextPrice = await calculatePrice({
          materialId: configuration.material,
          technology: configuration.technology,
          layerHeight: configuration.layerHeight,
          infill: configuration.infill,
          postProcessing: configuration.postProcessing,
          quantity: configuration.quantity,
          dimensions: configuration.dimensions,
        });
        if (requestId === calculationSequence.current) setPrice(nextPrice);
      } catch (error) {
        if (requestId === calculationSequence.current) {
          notify(error instanceof Error ? error.message : 'Не удалось рассчитать стоимость.', 'error');
        }
      } finally {
        if (requestId === calculationSequence.current) setIsCalculating(false);
      }
    }, 250);
    return () => window.clearTimeout(timer);
  }, [configuration, notify]);

  const setConfiguration = useCallback((patch: Partial<OrderConfiguration>) => {
    setConfigurationState((current) => ({ ...current, ...patch }));
  }, []);

  const setMaterial = useCallback((id: MaterialId) => {
    const selected = materials.find((item) => item.id === id);
    if (!selected) return;
    setConfigurationState((current) => ({
      ...current,
      material: id,
      technology: selected.technology,
      color: selected.colors.includes(current.color) ? current.color : selected.colors[0],
    }));
  }, []);

  const setTechnology = useCallback((technology: PrintingTechnology) => {
    const selected = materials.find((item) => item.id === configuration.material);
    if (selected?.technology !== technology) {
      notify(`${selected?.name ?? 'Материал'} совместим только с технологией ${selected?.technology ?? 'FDM'}.`, 'error');
      return;
    }
    setConfigurationState((current) => ({ ...current, technology }));
  }, [configuration.material, notify]);

  const setColor = useCallback((color: string) => {
    setConfigurationState((current) => ({ ...current, color }));
  }, []);

  const uploadFile = useCallback(async (file: File) => {
    setIsUploading(true);
    try {
      const result = await uploadModel(file);
      if (!result.validation.valid) {
        notify(result.validation.message, 'error');
        return;
      }
      setModel(result.model);
      notify(result.validation.message, 'success');
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Не удалось проверить модель.', 'error');
    } finally {
      setIsUploading(false);
    }
  }, [notify]);

  const placeOrder = useCallback(async () => {
    if (!model) {
      notify('Сначала загрузите 3D-модель.', 'error');
      return null;
    }
    if (!price) {
      notify('Подождите завершения расчёта стоимости.', 'info');
      return null;
    }
    setIsCreatingOrder(true);
    try {
      const order = await createOrder({ configuration, model, price });
      setOrders((current) => [order, ...current]);
      notify(`Заказ ${order.id} создан.`, 'success');
      return order;
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Не удалось создать заказ.', 'error');
      return null;
    } finally {
      setIsCreatingOrder(false);
    }
  }, [configuration, model, notify, price]);

  const reorder = useCallback((order: Order) => {
    setConfigurationState({
      material: order.material,
      technology: order.technology,
      color: order.color,
      layerHeight: order.layerHeight,
      infill: order.infill,
      postProcessing: order.postProcessing,
      quantity: order.quantity,
      dimensions: order.dimensions,
    });
    setModel(order.model);
  }, []);

  const changeStatus = useCallback(async (id: string, status: OrderStatus) => {
    try {
      const updated = await updateOrderStatus(id, status);
      setOrders((current) => current.map((order) => order.id === id ? updated : order));
      notify(`Статус заказа ${id} обновлён.`, 'success');
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Не удалось обновить заказ.', 'error');
    }
  }, [notify]);

  const value = useMemo<OrderContextValue>(() => ({
    configuration,
    model,
    price,
    orders,
    isUploading,
    isCalculating,
    isCreatingOrder,
    toast,
    setMaterial,
    setTechnology,
    setColor,
    setConfiguration,
    uploadFile,
    placeOrder,
    reorder,
    changeStatus,
    notify,
    dismissToast,
  }), [
    configuration, model, price, orders, isUploading, isCalculating, isCreatingOrder, toast,
    setMaterial, setTechnology, setColor, setConfiguration, uploadFile, placeOrder, reorder,
    changeStatus, notify, dismissToast,
  ]);

  return <OrderContext.Provider value={value}>{children}</OrderContext.Provider>;
}

export function useOrder() {
  const context = useContext(OrderContext);
  if (!context) throw new Error('useOrder должен вызываться внутри OrderProvider.');
  return context;
}
