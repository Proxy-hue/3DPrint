import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { BadgeCheck, Clock3, FileCheck2, Gauge, ArrowRight} from 'lucide-react';
import { Button, Card, Select, Spinner, cn } from '../../components/ui';


const MOCK_ORDERS = [
  { id: 'A-1024', model: { name: 'Кронштейн.stl' }, date: '2026-11-13', status: 'Pending', material: 'PLA', technology: 'FDM', quantity: 2, dimensions: { x: 120, y: 80, z: 40 } },
  { id: 'A-1025', model: { name: 'Шестерня.obj' }, date: '2026-11-13', status: 'In Production', material: 'ABS', technology: 'FDM', quantity: 1, dimensions: { x: 50, y: 50, z: 20 } }
];

export default function ManagerDashboard() {
  const [orders] = useState(MOCK_ORDERS);
  const [printers, setPrinters] = useState<any[]>([]);
  const [filter, setFilter] = useState('all');
  const [selectedId, setSelectedId] = useState<string | null>(MOCK_ORDERS[0]?.id || null);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    fetch('/api/catalog/printers/')
      .then(res => res.json())
      .then(data => setPrinters(data.results || data))
      .catch(err => console.error("Ошибка загрузки принтеров:", err));
  }, []);

  const visibleOrders = filter === 'all' ? orders : orders.filter((order) => order.status === filter);
  const selectedOrder = orders.find((order) => order.id === selectedId) ?? visibleOrders[0] ?? null;

  // Имитация проверки оборудования
  useEffect(() => {
    if (!selectedOrder) return;
    setChecking(true);
    const timer = setTimeout(() => {
      setChecking(false);
    }, 750);
    return () => clearTimeout(timer);
  }, [selectedOrder]);

  return (
    <div className="app-shell min-h-screen p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">АРМ Менеджера</h1>
        <Link to="/client" className="text-sm font-bold text-muted hover:text-foreground">
          На портал клиента <ArrowRight className="inline" size={14}/>
        </Link>
      </div>

      <div className="grid gap-4 sm:grid-cols-3 mb-6">
        <Card className="flex items-center gap-4"><span className="grid size-11 place-items-center rounded-xl bg-accent/10 text-accent-light"><FileCheck2 size={19}/></span><div><p className="text-xs text-muted">Всего заявок</p><p className="mt-1 text-2xl font-bold">{orders.length}</p></div></Card>
        <Card className="flex items-center gap-4"><span className="grid size-11 place-items-center rounded-xl bg-accent/10 text-accent-light"><Clock3 size={19}/></span><div><p className="text-xs text-muted">Ожидают запуска</p><p className="mt-1 text-2xl font-bold">{orders.filter(o => o.status === 'Pending').length}</p></div></Card>
        <Card className="flex items-center gap-4"><span className="grid size-11 place-items-center rounded-xl bg-accent/10 text-accent-light"><Gauge size={19}/></span><div><p className="text-xs text-muted">В производстве</p><p className="mt-1 text-2xl font-bold">{orders.filter(o => o.status === 'In Production').length}</p></div></Card>
      </div>

      <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1.7fr)_minmax(280px,0.8fr)]">
        {/* Таблица заказов */}
        <Card className="min-w-0 overflow-hidden p-0">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-5">
            <div><h2 className="font-bold">Очередь производства</h2></div>
            <Select label="Фильтр" className="min-w-44" value={filter} onChange={(e) => setFilter(e.target.value)} options={[{ value: 'all', label: 'Все статусы' }, { value: 'Pending', label: 'Ожидает' }, { value: 'In Production', label: 'В работе' }]} />
          </div>
          
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead><tr><th>Заказ</th><th>Материал</th><th>Габариты</th><th>Статус</th><th>Действие</th></tr></thead>
              <tbody>
                {visibleOrders.map(order => (
                  <tr key={order.id}>
                    <td><span className="block font-mono font-semibold">#{order.id}</span><span className="text-xs text-muted">{order.model.name}</span></td>
                    <td>{order.material} · {order.quantity} шт.</td>
                    <td className="font-mono text-xs">{order.dimensions.x}×{order.dimensions.y}×{order.dimensions.z}</td>
                    <td><span className="px-2 py-1 bg-panel-hover rounded text-xs">{order.status}</span></td>
                    <td><Button variant="quiet" className="min-h-9 px-2 text-xs" onClick={() => setSelectedId(order.id)}>Детали</Button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Карточка деталей */}
        <Card className="h-fit space-y-5">
          <div><p className="eyebrow">ПРОВЕРКА ОБОРУДОВАНИЯ</p><h2 className="section-title">Детали заявки</h2></div>
          
          {selectedOrder ? (
            <>
              <div className="rounded-xl border border-line bg-app-bg p-4">
                <p className="font-mono text-sm font-bold">#{selectedOrder.id}</p>
                <p className="mt-1 truncate text-sm text-muted">{selectedOrder.model.name}</p>
                <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
                  <div><span className="block text-muted">Материал</span><strong className="mt-1 block">{selectedOrder.material}</strong></div>
                  <div><span className="block text-muted">Технология</span><strong className="mt-1 block">{selectedOrder.technology}</strong></div>
                  <div><span className="block text-muted">Габариты</span><strong className="mt-1 block">{selectedOrder.dimensions.x}×{selectedOrder.dimensions.y}×{selectedOrder.dimensions.z} мм</strong></div>
                  <div><span className="block text-muted">Тираж</span><strong className="mt-1 block">{selectedOrder.quantity} шт.</strong></div>
                </div>
              </div>

              <div className={cn('flex items-start gap-3 rounded-xl border p-4', !checking ? 'border-emerald-400/20 bg-emerald-400/5' : 'border-amber-400/20 bg-amber-400/5')}>
                {checking ? <Spinner className="mt-0.5 text-accent" /> : <BadgeCheck size={19} className="mt-0.5 text-emerald-300" />}
                <div>
                  <p className="text-sm font-bold">{checking ? 'Проверяем...' : 'Совместимо'}</p>
                  <p className="mt-1 text-xs text-muted">{checking ? 'Сверяем габариты с принтерами.' : 'Доступные принтеры: ' + (printers.length > 0 ? printers.map(p => p.name).join(', ') : 'нет')}</p>
                </div>
              </div>

              <Button className="w-full" disabled={checking} icon={<ArrowRight size={16} />}>Принять в производство</Button>
            </>
          ) : <p className="text-sm text-muted">Выберите заказ из очереди.</p>}
        </Card>
      </div>
    </div>
  );
}
