import { useEffect, useMemo, useRef, useState, type ChangeEvent, type DragEvent, type ReactNode } from 'react';
import {
  ArrowDownToLine,
  ArrowRight,
  BadgeCheck,
  Box,
  Boxes,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  Clock3,
  FileBox,
  FileCheck2,
  FileUp,
  Gauge,
  Menu,
  Moon,
  PackageCheck,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sun,
  UserRound,
  X,
} from 'lucide-react';
import { useOrder } from './context/OrderContext';
import { materials } from './services/api';
import type { MaterialId, NavigationItem, Order, OrderStatus, PrintingTechnology } from './types';
import { Badge, Button, Card, Select, Spinner, cn } from './components/ui';

const navigation: NavigationItem[] = [
  { id: 'dashboard', label: 'Новый заказ' },
  { id: 'orders', label: 'Мои заказы' },
  { id: 'help', label: 'Помощь' },
  { id: 'manager', label: 'АРМ менеджера' },
];

const statusOptions: OrderStatus[] = ['Pending', 'In Production', 'Shipped', 'Delivered'];

function formatPrice(value: number) {
  return `${new Intl.NumberFormat('ru-RU').format(value)} ₽`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(value));
}

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace('.', ',')} МБ`;
}

function Logo() {
  return (
    <a className="flex items-center gap-2.5" href="#dashboard" aria-label="3DPrint — главная">
      <span className="grid size-9 place-items-center rounded-xl bg-accent text-[#211106]">
        <Boxes size={21} strokeWidth={2.4} />
      </span>
      <span className="text-[19px] font-extrabold tracking-tight text-foreground">3D<span className="text-accent-light">Print</span></span>
    </a>
  );
}

function AppHeader({
  currentPage,
  onNavigate,
  theme,
  onToggleTheme,
  menuOpen,
  onToggleMenu,
}: {
  currentPage: NavigationItem['id'];
  onNavigate: (id: NavigationItem['id']) => void;
  theme: 'dark' | 'light';
  onToggleTheme: () => void;
  menuOpen: boolean;
  onToggleMenu: () => void;
}) {
  const { orders } = useOrder();
  const navIcons = {
    dashboard: <Plus size={18} />,
    orders: <Box size={18} />,
    help: <CircleHelp size={18} />,
    manager: <Gauge size={18} />,
  };
  const navLabels: Record<NavigationItem['id'], string> = {
    dashboard: 'Новый заказ',
    orders: 'Мои заказы',
    help: 'Помощь',
    manager: 'АРМ менеджера',
  };

  const navLinks = (
    <nav aria-label="Основное меню" className="flex flex-col gap-1">
      {navigation.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onNavigate(item.id)}
          aria-current={currentPage === item.id ? 'page' : undefined}
          className={cn(
            'flex min-h-11 items-center gap-3 rounded-xl px-3 text-left text-sm font-semibold transition',
            currentPage === item.id ? 'bg-accent/10 text-accent-light' : 'text-muted hover:bg-panel-hover hover:text-foreground',
          )}
        >
          {navIcons[item.id]}
          <span className="flex-1">{navLabels[item.id]}</span>
          {item.id === 'orders' && <span className="rounded-full bg-panel-hover px-2 py-0.5 text-xs text-foreground">{orders.length}</span>}
        </button>
      ))}
    </nav>
  );

  return (
    <>
      <aside className="sidebar hidden lg:flex">
        <Logo />
        {navLinks}
        <div className="mt-auto flex items-center gap-3 rounded-xl border border-line bg-app-bg/70 p-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-full bg-panel-hover text-sm font-bold">МС</span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-bold">Мария Смирнова</span>
            <span className="block text-xs text-muted">Клиентский аккаунт</span>
          </span>
        </div>
      </aside>
      <header className="topbar">
        <div className="flex items-center gap-3">
          <button type="button" className="icon-button lg:hidden" aria-label={menuOpen ? 'Закрыть меню' : 'Открыть меню'} onClick={onToggleMenu}>
            {menuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <span className="lg:hidden"><Logo /></span>
          <div className="hidden lg:block">
            <p className="text-xs text-muted">Добро пожаловать, Мария</p>
            <p className="text-sm font-bold">{navLabels[currentPage]}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" className="icon-button" onClick={onToggleTheme} aria-label={theme === 'dark' ? 'Включить светлую тему' : 'Включить тёмную тему'}>
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          </button>
          <span className="hidden size-9 place-items-center rounded-full border border-line bg-panel text-muted sm:grid"><UserRound size={17} /></span>
        </div>
      </header>
      {menuOpen && (
        <div className="mobile-menu lg:hidden">
          {navLinks}
          <div className="mt-4 flex items-center gap-3 border-t border-line pt-4 text-sm">
            <span className="grid size-9 place-items-center rounded-full bg-panel-hover">МС</span>
            <span>Мария Смирнова</span>
          </div>
        </div>
      )}
    </>
  );
}

function UploadCard() {
  const { model, isUploading, uploadFile } = useOrder();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) void uploadFile(file);
    event.target.value = '';
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file) void uploadFile(file);
  }

  return (
    <Card className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="eyebrow">01 / МОДЕЛЬ</p>
          <h2 className="section-title">Загрузите 3D-модель</h2>
        </div>
        <span className="text-xs text-muted">STL, OBJ, 3MF, PLY · до 100 МБ</span>
      </div>
      <input ref={inputRef} className="sr-only" type="file" accept=".stl,.obj,.3mf,.ply" onChange={onFileChange} aria-label="Выберите 3D-модель" />
      <div
        role="button"
        tabIndex={0}
        aria-label="Область загрузки модели. Выберите файл или перетащите его сюда."
        onClick={() => inputRef.current?.click()}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          'flex min-h-48 cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed px-5 py-7 text-center transition',
          dragging ? 'border-accent bg-accent/10' : 'border-line bg-app-bg hover:border-muted hover:bg-panel-hover/40',
        )}
      >
        <span className="mb-3 grid size-12 place-items-center rounded-2xl bg-accent/10 text-accent-light">
          {isUploading ? <Spinner className="size-6" /> : <FileUp size={23} />}
        </span>
        <span className="font-bold">{isUploading ? 'Проверяем модель…' : 'Перетащите файл сюда'}</span>
        <span className="mt-1 text-sm text-muted">или нажмите, чтобы выбрать на устройстве</span>
        <Button type="button" variant="secondary" className="mt-4 min-h-10" disabled={isUploading} onClick={(event) => {
          event.stopPropagation();
          inputRef.current?.click();
        }}>
          {isUploading ? <Spinner /> : <ArrowDownToLine size={16} />}
          {isUploading ? 'Проверка…' : 'Upload 3D Model'}
        </Button>
      </div>
      {model && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-app-bg p-3">
          <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-panel-hover text-accent-light"><FileBox size={21} /></span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-bold">{model.name}</p>
            <p className="mt-1 text-xs text-muted">{model.format} · {formatSize(model.size)} · модель проверена</p>
          </div>
          <span className="flex items-center gap-1.5 text-xs font-semibold text-emerald-300"><CheckCircle2 size={15} />Готово</span>
        </div>
      )}
      <p className="text-xs leading-relaxed text-muted">В демо-режиме файл не покидает устройство. Mock API имитирует проверку, реальную загрузку подключите на сервере.</p>
    </Card>
  );
}

function MaterialCard({ materialId }: { materialId: MaterialId }) {
  const { configuration, setMaterial } = useOrder();
  const material = materials.find((item) => item.id === materialId)!;
  const active = configuration.material === materialId;
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={() => setMaterial(materialId)}
      className={cn('flex min-h-36 flex-col rounded-xl border p-4 text-left transition', active ? 'border-accent bg-accent/5 shadow-[0_0_0_1px_var(--app-accent)]' : 'border-line bg-app-bg hover:border-muted')}
    >
      <span className="flex w-full items-center justify-between gap-2">
        <span className="text-lg font-extrabold">{material.name}</span>
        <span className={cn('grid size-5 place-items-center rounded-full border', active ? 'border-accent bg-accent text-[#211106]' : 'border-muted text-transparent')}>
          {active && <Check size={12} strokeWidth={3} />}
        </span>
      </span>
      <span className="mt-2 text-xs leading-relaxed text-muted">{material.description}</span>
      <span className="mt-auto flex items-center justify-between gap-2 pt-4 text-[11px]">
        <span className="text-muted">{material.technology} · {material.density.toFixed(2)} г/см³</span>
        <span className="whitespace-nowrap font-mono font-semibold text-accent-light">{material.pricePerGram.toLocaleString('ru-RU')} ₽/г</span>
      </span>
    </button>
  );
}

function ConfigurationCard() {
  const { configuration, setTechnology, setColor, setConfiguration } = useOrder();
  const material = materials.find((item) => item.id === configuration.material)!;
  const technologies: PrintingTechnology[] = ['FDM', 'SLA', 'SLS'];
  return (
    <Card className="space-y-6">
      <div>
        <p className="eyebrow">02 / ПАРАМЕТРЫ ПЕЧАТИ</p>
        <h2 className="section-title">Материал и технология</h2>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {materials.map((item) => <MaterialCard key={item.id} materialId={item.id} />)}
      </div>
      <div className="grid gap-6 border-t border-line pt-5 md:grid-cols-2">
        <div className="space-y-3">
          <div className="flex items-baseline justify-between gap-3">
            <p className="text-sm font-bold">Технология печати</p>
            <p className="text-xs text-muted">Совместимость по материалу</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {technologies.map((technology) => {
              const compatible = material.technology === technology;
              return (
                <button
                  type="button"
                  key={technology}
                  aria-pressed={configuration.technology === technology}
                  aria-disabled={!compatible}
                  title={compatible ? technology : `${material.name} несовместим с ${technology}`}
                  onClick={() => setTechnology(technology)}
                  className={cn(
                    'min-h-10 rounded-lg border px-4 text-sm font-bold transition',
                    configuration.technology === technology ? 'border-accent bg-accent text-[#211106]' : 'border-line bg-app-bg text-muted hover:border-muted',
                    !compatible && 'opacity-45',
                  )}
                >
                  {technology}
                </button>
              );
            })}
          </div>
          <p className="flex items-center gap-1.5 text-xs text-muted"><ShieldCheck size={14} className="text-emerald-300" />{material.name} печатается по технологии {material.technology}</p>
        </div>
        <div className="space-y-3">
          <p className="text-sm font-bold">Цвет материала <span className="font-normal text-muted">· {material.colorNames[material.colors.indexOf(configuration.color)]}</span></p>
          <div className="flex flex-wrap gap-3 py-1">
            {material.colors.map((color, index) => (
              <button
                type="button"
                key={color}
                aria-label={material.colorNames[index]}
                aria-pressed={configuration.color === color}
                title={material.colorNames[index]}
                onClick={() => setColor(color)}
                className={cn('size-9 rounded-full border border-white/15 transition', configuration.color === color && 'outline outline-2 outline-accent outline-offset-3')}
                style={{ backgroundColor: color }}
              />
            ))}
          </div>
        </div>
      </div>
      <div className="space-y-3 border-t border-line pt-5">
        <div>
          <p className="text-sm font-bold">Габариты модели, мм</p>
          <p className="mt-1 text-xs text-muted">Рабочая область принтера — от 1 до 250 мм по каждой оси.</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          {(['x', 'y', 'z'] as const).map((axis) => (
            <label key={axis} className="flex flex-col gap-2 text-sm font-semibold text-muted">
              {axis === 'x' ? 'Длина (X)' : axis === 'y' ? 'Ширина (Y)' : 'Высота (Z)'}
              <span className="flex min-h-11 items-center gap-2 rounded-xl border border-line bg-app-bg px-3 focus-within:border-accent">
                <input
                  type="number"
                  min="1"
                  max="250"
                  step="0.1"
                  value={configuration.dimensions[axis] || ''}
                  onChange={(event) => setConfiguration({
                    dimensions: { ...configuration.dimensions, [axis]: Number(event.target.value) },
                  })}
                  className="min-w-0 flex-1 bg-transparent font-mono text-sm text-foreground outline-none"
                  aria-label={axis === 'x' ? 'Длина модели в миллиметрах' : axis === 'y' ? 'Ширина модели в миллиметрах' : 'Высота модели в миллиметрах'}
                />
                <span className="text-xs">мм</span>
              </span>
            </label>
          ))}
        </div>
        {Object.values(configuration.dimensions).some((value) => !Number.isFinite(value) || value < 1 || value > 250) && (
          <p role="alert" className="text-xs leading-relaxed text-red-300">Укажите габариты от 1 до 250 мм по каждой оси, чтобы продолжить.</p>
        )}
      </div>
      <div className="grid gap-4 border-t border-line pt-5 sm:grid-cols-2 lg:grid-cols-4">
        <Select
          label="Высота слоя"
          value={String(configuration.layerHeight)}
          onChange={(event) => setConfiguration({ layerHeight: Number(event.target.value) })}
          options={[{ value: '0.1', label: '0,1 мм · детально' }, { value: '0.2', label: '0,2 мм · стандарт' }, { value: '0.3', label: '0,3 мм · быстро' }]}
        />
        <label className={cn('flex flex-col gap-2 text-sm font-semibold text-muted', configuration.technology === 'SLA' && 'opacity-50')}>
          <span className="flex justify-between">Заполнение <span className="font-mono text-foreground">{configuration.technology === 'SLA' ? 'сплошная' : `${configuration.infill}%`}</span></span>
          <input type="range" min="10" max="100" step="10" value={configuration.infill} disabled={configuration.technology === 'SLA'} onChange={(event) => setConfiguration({ infill: Number(event.target.value) })} className="range-control mt-3 w-full disabled:cursor-not-allowed" />
          <span className="flex justify-between text-[10px] font-medium"><span>{configuration.technology === 'SLA' ? 'Заполнение не настраивается' : '10%'}</span>{configuration.technology !== 'SLA' && <span>100%</span>}</span>
        </label>
        <Select
          label="Постобработка"
          value={configuration.postProcessing}
          onChange={(event) => setConfiguration({ postProcessing: event.target.value as 'none' | 'sanding' | 'painting' })}
          options={[{ value: 'none', label: 'Без обработки' }, { value: 'sanding', label: 'Шлифовка' }, { value: 'painting', label: 'Покраска' }]}
        />
        <label className="flex flex-col gap-2 text-sm font-semibold text-muted">
          Количество
          <span className="flex min-h-11 items-center justify-between rounded-xl border border-line bg-app-bg px-2">
            <button type="button" aria-label="Уменьшить количество" disabled={configuration.quantity <= 1} onClick={() => setConfiguration({ quantity: Math.max(1, configuration.quantity - 1) })} className="grid size-8 place-items-center rounded-lg text-muted hover:bg-panel-hover hover:text-foreground disabled:opacity-40"><span className="text-lg">−</span></button>
            <span className="font-mono text-foreground">{configuration.quantity} шт.</span>
            <button type="button" aria-label="Увеличить количество" disabled={configuration.quantity >= 99} onClick={() => setConfiguration({ quantity: Math.min(99, configuration.quantity + 1) })} className="grid size-8 place-items-center rounded-lg text-muted hover:bg-panel-hover hover:text-foreground disabled:opacity-40"><Plus size={16} /></button>
          </span>
        </label>
      </div>
    </Card>
  );
}

function PriceCard({ onOrder }: { onOrder: () => void }) {
  const { configuration, model, price, isCalculating, isCreatingOrder } = useOrder();
  const invalidDimensions = Object.values(configuration.dimensions).some((value) => !Number.isFinite(value) || value < 1 || value > 250);
  const readyDate = useMemo(() => {
    const date = new Date();
    date.setDate(date.getDate() + (price?.leadTimeDays ?? 0));
    return formatDate(date.toISOString());
  }, [price?.leadTimeDays]);

  return (
    <Card className="price-card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="eyebrow">ВАША СМЕТА</p>
          <h2 className="section-title">Стоимость заказа</h2>
        </div>
        <span className="flex items-center gap-1.5 rounded-full bg-emerald-400/10 px-2.5 py-1 text-xs font-semibold text-emerald-300">
          <span className="live-dot" />Мгновенный расчёт
        </span>
      </div>
      {model ? <p className="truncate text-xs text-muted">{model.name} · {configuration.dimensions.x} × {configuration.dimensions.y} × {configuration.dimensions.z} мм</p> : <p className="text-xs text-muted">Загрузите файл для подготовки заявки</p>}
      <div className="space-y-4 border-y border-line py-5">
        <PriceRow label={`Материал · ${materials.find((item) => item.id === configuration.material)?.name ?? ''}`} value={price ? formatPrice(price.material) : null} />
        <PriceRow label={`Печать · ${configuration.technology}`} value={price ? formatPrice(price.printing) : null} />
        <PriceRow label="Постобработка" value={price ? formatPrice(price.postProcessing) : null} />
        <PriceRow label="Доставка курьером" value={price ? formatPrice(price.delivery) : null} />
      </div>
      <div>
        <p className="text-xs font-semibold text-muted">Итого</p>
        <div className="mt-1 flex items-center gap-2">
          {isCalculating && <Spinner className="text-accent" />}
          <p className="font-mono text-4xl font-semibold tracking-tight">{price ? formatPrice(price.total) : <span className="inline-block h-9 w-36 animate-pulse rounded bg-panel-hover align-middle" />}</p>
        </div>
        <p className="mt-2 text-xs text-muted">{price ? `Ориентировочная готовность · ${readyDate}` : 'Расчёт стоимости…'}</p>
      </div>
      {price && (
        <div className="grid grid-cols-2 gap-3 rounded-xl bg-app-bg p-3">
          <div><p className="text-[11px] text-muted">Расчётный вес</p><p className="mt-1 font-mono text-sm">{price.estimatedWeight} г × {configuration.quantity}</p></div>
          <div><p className="text-[11px] text-muted">Срок производства</p><p className="mt-1 flex items-center gap-1 font-mono text-sm"><Clock3 size={13} />{price.leadTimeDays} дн.</p></div>
        </div>
      )}
      <Button variant="primary" className="w-full" disabled={!model || !price || invalidDimensions || isCalculating || isCreatingOrder} onClick={onOrder}>
        {isCreatingOrder ? <Spinner /> : <ArrowRight size={17} />}
        {isCreatingOrder ? 'Создаём заказ…' : 'Оформить заказ'}
      </Button>
      <p className="text-center text-[11px] leading-relaxed text-muted">Нажимая кнопку, вы создаёте демо-заявку. Платёж и серверная отправка пока не подключены.</p>
    </Card>
  );
}

function PriceRow({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="text-muted">{label}</span>
      {value ? <span className="font-mono font-medium">{value}</span> : <span className="h-4 w-16 animate-pulse rounded bg-panel-hover" />}
    </div>
  );
}

function OrderTable({ rows, onReorder, action }: { rows: Order[]; onReorder?: (order: Order) => void; action?: (order: Order) => ReactNode }) {
  if (rows.length === 0) return <div className="empty-state"><PackageCheck size={30} /><p>Заказов пока нет</p><span>Загрузите модель, чтобы создать первый заказ.</span></div>;
  return (
    <div className="overflow-x-auto">
      <table className="data-table">
        <thead><tr><th>Заказ</th><th>Дата</th><th>Материал</th><th>Стоимость</th><th>Статус</th><th><span className="sr-only">Действия</span></th></tr></thead>
        <tbody>
          {rows.map((order) => (
            <tr key={order.id}>
              <td><span className="block font-mono font-semibold">#{order.id}</span><span className="mt-1 block max-w-36 truncate text-xs text-muted">{order.model.name}</span></td>
              <td className="whitespace-nowrap text-muted">{formatDate(order.date)}</td>
              <td><span className="font-semibold">{materials.find((item) => item.id === order.material)?.name ?? order.material}</span><span className="mt-1 block text-xs text-muted">{order.technology} · {order.quantity} шт.</span></td>
              <td className="whitespace-nowrap font-mono font-semibold">{formatPrice(order.price.total)}</td>
              <td><Badge status={order.status} /></td>
              <td>{action ? action(order) : onReorder && <Button variant="quiet" className="min-h-9 whitespace-nowrap px-2 text-xs" onClick={() => onReorder(order)} icon={<RefreshCw size={14} />}>Повторить</Button>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OrdersPage({ onReorder }: { onReorder: (order: Order) => void }) {
  const { orders } = useOrder();
  const [filter, setFilter] = useState('all');
  const filtered = filter === 'all' ? orders : orders.filter((order) => order.status === filter);
  return (
    <div className="page-stack">
      <PageHeading eyebrow="ВАШИ ЗАКАЗЫ" title="История заказов" description="Следите за статусом печати и повторяйте предыдущие заказы." />
      <Card className="overflow-hidden p-0">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-5">
          <div><h2 className="text-base font-bold">Все заказы</h2><p className="mt-1 text-xs text-muted">{orders.length} заявок в системе</p></div>
          <Select label="Статус" className="min-w-40" value={filter} onChange={(event) => setFilter(event.target.value)} options={[{ value: 'all', label: 'Все статусы' }, ...statusOptions.map((status) => ({ value: status, label: status }))]} />
        </div>
        <OrderTable rows={filtered} onReorder={onReorder} />
      </Card>
    </div>
  );
}

function ManagerPage() {
  const { orders, changeStatus } = useOrder();
  const [filter, setFilter] = useState('all');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [equipmentCompatible, setEquipmentCompatible] = useState<boolean | null>(null);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const visibleOrders = filter === 'all' ? orders : orders.filter((order) => order.status === filter);
  const selectedOrder = orders.find((order) => order.id === selectedId) ?? visibleOrders[0] ?? null;

  useEffect(() => {
    if (!selectedOrder) {
      setEquipmentCompatible(null);
      return;
    }
    setChecking(true);
    setEquipmentCompatible(null);
    const timer = window.setTimeout(() => {
      const { x, y, z } = selectedOrder.dimensions;
      setEquipmentCompatible(Math.max(x, y, z) <= 250);
      setChecking(false);
    }, 750);
    return () => window.clearTimeout(timer);
  }, [selectedOrder]);

  async function advanceOrder(order: Order) {
    const nextStatus: OrderStatus = order.status === 'Pending' ? 'In Production'
      : order.status === 'In Production' ? 'Shipped'
        : order.status === 'Shipped' ? 'Delivered' : 'Delivered';
    setLoadingId(order.id);
    await changeStatus(order.id, nextStatus);
    setLoadingId(null);
  }

  return (
    <div className="page-stack">
      <PageHeading eyebrow="РАБОЧЕЕ МЕСТО" title="АРМ менеджера" description="Входящие заявки, производственная очередь и проверка совместимости оборудования." />
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Всего заявок" value={String(orders.length)} icon={<FileCheck2 size={19} />} />
        <StatCard label="Ожидают запуска" value={String(orders.filter((order) => order.status === 'Pending').length)} icon={<Clock3 size={19} />} />
        <StatCard label="В производстве" value={String(orders.filter((order) => order.status === 'In Production').length)} icon={<Gauge size={19} />} />
      </div>
      <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1.7fr)_minmax(280px,0.8fr)]">
        <Card className="min-w-0 overflow-hidden p-0">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-5">
            <div><h2 className="font-bold">Очередь производства</h2><p className="mt-1 text-xs text-muted">Обновление через mock API</p></div>
            <Select label="Фильтр" className="min-w-44" value={filter} onChange={(event) => setFilter(event.target.value)} options={[{ value: 'all', label: 'Все статусы' }, ...statusOptions.map((status) => ({ value: status, label: status }))]} />
          </div>
          <OrderTable
            rows={visibleOrders}
            action={(order) => (
              <div className="flex items-center gap-1">
                <Button variant="quiet" className="min-h-9 px-2 text-xs" onClick={() => setSelectedId(order.id)}>Детали</Button>
                <Button variant="quiet" disabled={order.status === 'Delivered' || loadingId === order.id} className="min-h-9 px-2 text-xs" onClick={() => void advanceOrder(order)} aria-label={`Изменить статус заказа ${order.id}`}>
                  {loadingId === order.id ? <Spinner /> : <ChevronDown size={15} />}
                </Button>
              </div>
            )}
          />
        </Card>
        <Card className="h-fit space-y-5">
          <div>
            <p className="eyebrow">ПРОВЕРКА ОБОРУДОВАНИЯ</p>
            <h2 className="section-title">Детали заявки</h2>
          </div>
          {selectedOrder ? (
            <>
              <div className="rounded-xl border border-line bg-app-bg p-4">
                <p className="font-mono text-sm font-bold">#{selectedOrder.id}</p>
                <p className="mt-1 truncate text-sm text-muted">{selectedOrder.model.name}</p>
                <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
                  <div><span className="block text-muted">Материал</span><strong className="mt-1 block">{materials.find((item) => item.id === selectedOrder.material)?.name}</strong></div>
                  <div><span className="block text-muted">Технология</span><strong className="mt-1 block">{selectedOrder.technology}</strong></div>
                  <div><span className="block text-muted">Габариты</span><strong className="mt-1 block">{selectedOrder.dimensions.x} × {selectedOrder.dimensions.y} × {selectedOrder.dimensions.z} мм</strong></div>
                  <div><span className="block text-muted">Тираж</span><strong className="mt-1 block">{selectedOrder.quantity} шт.</strong></div>
                </div>
              </div>
              <div className={cn('flex items-start gap-3 rounded-xl border p-4', equipmentCompatible ? 'border-emerald-400/20 bg-emerald-400/5' : 'border-amber-400/20 bg-amber-400/5')}>
                {checking ? <Spinner className="mt-0.5 text-accent" /> : equipmentCompatible ? <BadgeCheck size={19} className="mt-0.5 text-emerald-300" /> : <CircleHelp size={19} className="mt-0.5 text-amber-300" />}
                <div><p className="text-sm font-bold">{checking ? 'Проверяем оборудование…' : equipmentCompatible ? 'Совместим' : 'Требуется уточнение'}</p><p className="mt-1 text-xs leading-relaxed text-muted">{checking ? 'Сверяем габариты с рабочей областью принтера.' : equipmentCompatible ? 'Материал и размеры подходят доступному оборудованию.' : 'Габариты превышают рабочую область принтера.'}</p></div>
              </div>
              <Button className="w-full" disabled={checking || selectedOrder.status === 'Delivered'} onClick={() => void advanceOrder(selectedOrder)} icon={<ArrowRight size={16} />}>
                {selectedOrder.status === 'Pending' ? 'Принять в производство' : selectedOrder.status === 'In Production' ? 'Отметить отправку' : selectedOrder.status === 'Shipped' ? 'Подтвердить доставку' : 'Заказ завершён'}
              </Button>
            </>
          ) : <p className="text-sm text-muted">Выберите заказ из очереди.</p>}
        </Card>
      </div>
    </div>
  );
}

function HelpPage() {
  const items = [
    { title: 'Какие форматы файлов поддерживаются?', text: 'Загрузите STL, OBJ, 3MF или PLY размером до 100 МБ. Проверка выполняется в демонстрационном режиме.' },
    { title: 'Как выбрать материал и технологию?', text: 'Выберите материал. Подходящая технология FDM, SLA или SLS будет отмечена автоматически. Несовместимые технологии недоступны.' },
    { title: 'Как рассчитывается цена?', text: 'Цена зависит от габаритов детали, материала, высоты слоя, заполнения, постобработки, тиража и доставки.' },
    { title: 'Можно ли оплатить заказ?', text: 'Сейчас форма создаёт демонстрационные заявки через mock API. Для приёма платежей и отправки файлов необходимо подключить сервер.' },
  ];
  return (
    <div className="page-stack">
      <PageHeading eyebrow="ЦЕНТР ПОДДЕРЖКИ" title="Помощь" description="Ответы на основные вопросы о загрузке моделей и 3D-печати." />
      <div className="grid gap-4 lg:grid-cols-2">
        {items.map((item) => <Card key={item.title}><div className="flex gap-3"><span className="grid size-9 shrink-0 place-items-center rounded-xl bg-accent/10 text-accent-light"><CircleHelp size={18} /></span><div><h2 className="font-bold">{item.title}</h2><p className="mt-2 text-sm leading-relaxed text-muted">{item.text}</p></div></div></Card>)}
      </div>
      <Card className="flex flex-wrap items-center justify-between gap-4">
        <div><h2 className="font-bold">Нужна помощь с заказом?</h2><p className="mt-1 text-sm text-muted">Свяжитесь с менеджером, чтобы проверить модель перед печатью.</p></div>
        <Button variant="secondary" icon={<CircleHelp size={16} />} onClick={() => window.location.href = 'mailto:support@3dprint.example'}>Написать в поддержку</Button>
      </Card>
    </div>
  );
}

function DashboardPage({ onNavigate }: { onNavigate: (id: NavigationItem['id']) => void }) {
  const { orders, placeOrder, reorder, notify } = useOrder();
  async function submitOrder() {
    const order = await placeOrder();
    if (order) onNavigate('orders');
  }
  return (
    <div className="page-stack">
      <PageHeading eyebrow="КЛИЕНТСКИЙ ПОРТАЛ" title="Новый заказ на печать" description="Настройте параметры модели — стоимость и сроки обновятся автоматически." />
      <div className="grid min-w-0 items-start gap-5 xl:grid-cols-[minmax(0,1fr)_350px]">
        <div className="min-w-0 space-y-5">
          <UploadCard />
          <ConfigurationCard />
        </div>
        <PriceCard onOrder={() => void submitOrder()} />
      </div>
      <Card className="overflow-hidden p-0">
        <div className="flex flex-wrap items-center justify-between gap-3 p-5">
          <div><p className="eyebrow">ОБНОВЛЕНИЯ</p><h2 className="text-lg font-bold">Последние заказы</h2></div>
          <Button variant="quiet" className="min-h-9" onClick={() => onNavigate('orders')} icon={<ArrowRight size={15} />}>Все заказы</Button>
        </div>
        <OrderTable rows={orders.slice(0, 3)} onReorder={(order) => { reorder(order); notify('Параметры заказа загружены в калькулятор.', 'success'); window.scrollTo({ top: 0, behavior: 'smooth' }); }} />
      </Card>
    </div>
  );
}

function PageHeading({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div><p className="eyebrow">{eyebrow}</p><h1 className="mt-2 text-3xl font-extrabold tracking-tight sm:text-[34px]">{title}</h1><p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">{description}</p></div>
      <div className="hidden items-center gap-2 rounded-full border border-line bg-card px-3 py-2 text-xs font-semibold text-muted md:flex"><span className="live-dot" />Личный кабинет · онлайн</div>
    </div>
  );
}

function StatCard({ label, value, icon }: { label: string; value: string; icon: ReactNode }) {
  return <Card className="flex items-center gap-4"><span className="grid size-11 place-items-center rounded-xl bg-accent/10 text-accent-light">{icon}</span><div><p className="text-xs text-muted">{label}</p><p className="mt-1 text-2xl font-bold">{value}</p></div></Card>;
}

function Toast() {
  const { toast, dismissToast } = useOrder();
  if (!toast) return null;
  const tone = toast.tone === 'error' ? 'border-red-400/30 bg-red-950 text-red-100'
    : toast.tone === 'success' ? 'border-emerald-400/30 bg-emerald-950 text-emerald-100'
      : 'border-line bg-panel text-foreground';
  return (
    <div role={toast.tone === 'error' ? 'alert' : 'status'} className={cn('toast-message', tone)}>
      {toast.tone === 'error' ? <CircleHelp size={18} /> : toast.tone === 'success' ? <CheckCircle2 size={18} /> : <FileCheck2 size={18} />}
      <span className="flex-1 text-sm">{toast.message}</span>
      <button type="button" aria-label="Закрыть уведомление" onClick={dismissToast} className="rounded-lg p-1 opacity-70 hover:opacity-100"><X size={16} /></button>
    </div>
  );
}

export default function App() {
  const [currentPage, setCurrentPage] = useState<NavigationItem['id']>('dashboard');
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [menuOpen, setMenuOpen] = useState(false);
  const { reorder, notify } = useOrder();

  function navigate(id: NavigationItem['id']) {
    setCurrentPage(id);
    setMenuOpen(false);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function repeatOrder(order: Order) {
    reorder(order);
    notify('Параметры заказа загружены в калькулятор.', 'success');
    navigate('dashboard');
  }

  return (
    <div className={cn('app-shell min-h-screen', theme === 'light' && 'theme-light')}>
      <AppHeader
        currentPage={currentPage}
        onNavigate={navigate}
        theme={theme}
        onToggleTheme={() => setTheme((value) => value === 'dark' ? 'light' : 'dark')}
        menuOpen={menuOpen}
        onToggleMenu={() => setMenuOpen((value) => !value)}
      />
      <main className="main-content">
        {currentPage === 'dashboard' && <DashboardPage onNavigate={navigate} />}
        {currentPage === 'orders' && <OrdersPage onReorder={repeatOrder} />}
        {currentPage === 'help' && <HelpPage />}
        {currentPage === 'manager' && <ManagerPage />}
        <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-5 text-xs text-muted">
          <span>© 2026 3DPrint · Прототип клиентского портала</span>
          <span>Демо-данные · подключите REST API для публикации</span>
        </footer>
      </main>
      <Toast />
    </div>
  );
}
