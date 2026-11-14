import { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Boxes, Check, CheckCircle2, FileBox, FileUp, Plus, ArrowRight } from 'lucide-react';
import { Button, Card, Select, Spinner, cn } from '../../components/ui';

function MaterialCard({ material, isActive, onClick }: { material: any, isActive: boolean, onClick: () => void }) {
  return (
    <button onClick={onClick} className={cn('flex flex-col rounded-xl border p-4 text-left transition', isActive ? 'border-accent bg-accent/5' : 'border-line bg-app-bg hover:border-muted')}>
      <span className="flex w-full items-center justify-between">
        <span className="text-lg font-extrabold">{material.name}</span>
        {isActive && <Check size={16} className="text-accent" />}
      </span>
      <span className="mt-2 text-xs text-muted">Технология: {material.technology_name}</span>
      <span className="mt-auto pt-4 text-xs font-mono text-accent-light">{Number(material.price_per_gram).toLocaleString('ru-RU')} ₽/г</span>
    </button>
  );
}

function PriceCard({ price, days, disabled }: { price: number, days: number, disabled: boolean }) {
  const formatPrice = (val: number) => `${new Intl.NumberFormat('ru-RU').format(val)} ₽`;
  return (
    <Card className="price-card">
      <div><p className="eyebrow">ВАША СМЕТА</p><h2 className="section-title">Стоимость</h2></div>
      <div className="space-y-4 border-y border-line py-5">
        <div className="flex justify-between text-sm"><span className="text-muted">Материал</span><span className="font-mono">{formatPrice(price * 0.3)}</span></div>
        <div className="flex justify-between text-sm"><span className="text-muted">Печать</span><span className="font-mono">{formatPrice(price * 0.7)}</span></div>
      </div>
      <div>
        <p className="text-xs font-semibold text-muted">Итого</p>
        <p className="mt-1 font-mono text-4xl font-semibold">{formatPrice(price)}</p>
        <p className="mt-2 text-xs text-muted">Ориентировочно: {days} дня</p>
      </div>
      <Button variant="primary" className="w-full mt-4" disabled={disabled}>
        <ArrowRight size={17} /> Оформить заказ
      </Button>
    </Card>
  );
}

export default function ClientHome() {
  const [materials, setMaterials] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [configuration, setConfiguration] = useState({
    material: '',
    technology: 'FDM',
    layerHeight: 0.2,
    quantity: 1,
    dimensions: { x: 62, y: 40, z: 28 }
  });
  
  const [model, setModel] = useState<{name: string, size: number, format: string} | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Загрузка материалов из Django
  useEffect(() => {
    fetch('/api/catalog/materials/')
      .then((res) => { if (!res.ok) throw new Error('Ошибка'); return res.json(); })
      .then((data) => {
        const loadedMaterials = data.results || data;
        setMaterials(loadedMaterials);
        if (loadedMaterials.length > 0) {
          setConfiguration(prev => ({ ...prev, material: loadedMaterials[0].id, technology: loadedMaterials[0].technology }));
        }
        setIsLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setError('Не удалось загрузить материалы из базы данных.');
        setIsLoading(false);
      });
  }, []);

  if (isLoading) return <div className="p-10 text-center">Загрузка справочников из БД...</div>;
  if (error) return <div className="p-10 text-center text-red-500">{error}</div>;
  if (materials.length === 0) return <div className="p-10 text-center">В базе нет материалов. Добавьте их в админке Django.</div>;

  const activeMaterial = materials.find(m => m.id === configuration.material) || materials[0];

  // Имитация загрузки файла (позже заменим на реальный POST запрос в MinIO)
  function handleFile(file: File) {
    setIsUploading(true);
    setTimeout(() => {
      setModel({ name: file.name, size: file.size, format: file.name.split('.').pop()?.toUpperCase() || 'STL' });
      setIsUploading(false);
    }, 1000);
  }

  const formatSize = (bytes: number) => `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;

  return (
    <div className="app-shell min-h-screen">
      <header className="topbar">
        <Link to="/client" className="flex items-center gap-2.5">
          <span className="grid size-9 place-items-center rounded-xl bg-accent text-[#211106]"><Boxes size={21} /></span>
          <span className="text-[19px] font-extrabold text-foreground">3D<span className="text-accent-light">Print</span></span>
        </Link>
        <div className="flex items-center gap-2">
          <Link to="/manager" className="text-sm font-bold text-muted hover:text-foreground">АРМ Менеджера <ArrowRight className="inline" size={14}/></Link>
        </div>
      </header>

      <main className="main-content" style={{ marginLeft: 0 }}>
        <div className="page-stack">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div><p className="eyebrow">КЛИЕНТСКИЙ ПОРТАЛ</p><h1 className="mt-2 text-3xl font-extrabold tracking-tight sm:text-[34px]">Новый заказ на печать</h1><p className="mt-2 text-sm text-muted">Настройте параметры модели — стоимость и сроки обновятся автоматически.</p></div>
          </div>

          <div className="grid min-w-0 items-start gap-5 xl:grid-cols-[minmax(0,1fr)_350px]">
            <div className="min-w-0 space-y-5">
              
              {/* --- ЗАГРУЗКА МОДЕЛИ --- */}
              <Card className="space-y-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div><p className="eyebrow">01 / МОДЕЛЬ</p><h2 className="section-title">Загрузите 3D-модель</h2></div>
                  <span className="text-xs text-muted">STL, OBJ, 3MF · до 100 МБ</span>
                </div>
                <input ref={fileInputRef} className="sr-only" type="file" accept=".stl,.obj,.3mf" onChange={(e) => { if(e.target.files?.[0]) handleFile(e.target.files[0]); e.target.value = ''; }} />
                <div
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={(e) => { e.preventDefault(); setDragging(false); if(e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]); }}
                  className={cn('flex min-h-48 cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed px-5 py-7 text-center transition', dragging ? 'border-accent bg-accent/10' : 'border-line bg-app-bg hover:border-muted')}
                >
                  <span className="mb-3 grid size-12 place-items-center rounded-2xl bg-accent/10 text-accent-light">{isUploading ? <Spinner className="size-6" /> : <FileUp size={23} />}</span>
                  <span className="font-bold">{isUploading ? 'Проверяем...' : 'Перетащите файл сюда'}</span>
                  <span className="mt-1 text-sm text-muted">или нажмите, чтобы выбрать</span>
                </div>
                {model && (
                  <div className="flex items-center gap-3 rounded-xl border border-line bg-app-bg p-3">
                    <span className="grid size-11 place-items-center rounded-xl bg-panel-hover text-accent-light"><FileBox size={21} /></span>
                    <div className="min-w-0 flex-1"><p className="truncate text-sm font-bold">{model.name}</p><p className="mt-1 text-xs text-muted">{model.format} · {formatSize(model.size)}</p></div>
                    <span className="flex items-center gap-1.5 text-xs font-semibold text-emerald-300"><CheckCircle2 size={15} />Готово</span>
                  </div>
                )}
              </Card>

              {/* --- ПАРАМЕТРЫ --- */}
              <Card className="space-y-6">
                <div><p className="eyebrow">02 / ПАРАМЕТРЫ ПЕЧАТИ</p><h2 className="section-title">Материал и технология</h2></div>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  {materials.map((m) => (
                    <MaterialCard 
                      key={m.id} 
                      material={m} 
                      isActive={configuration.material === m.id} 
                      onClick={() => setConfiguration({...configuration, material: m.id, technology: m.technology})} 
                    />
                  ))}
                </div>
                
                <div className="grid gap-4 border-t border-line pt-5 sm:grid-cols-3">
                  <Select label="Высота слоя" value={String(configuration.layerHeight)} onChange={(e) => setConfiguration({...configuration, layerHeight: Number(e.target.value)})} options={[{ value: '0.1', label: '0,1 мм' }, { value: '0.2', label: '0,2 мм' }, { value: '0.3', label: '0,3 мм' }]} />
                  <Select label="Постобработка" value="none" options={[{ value: 'none', label: 'Без обработки' }, { value: 'sanding', label: 'Шлифовка' }, { value: 'painting', label: 'Покраска' }]} onChange={() => {}} />
                  <label className="flex flex-col gap-2 text-sm font-semibold text-muted">
                    Количество
                    <span className="flex min-h-11 items-center justify-between rounded-xl border border-line bg-app-bg px-2">
                      <button onClick={() => setConfiguration({...configuration, quantity: Math.max(1, configuration.quantity - 1)})} className="size-8 rounded-lg hover:bg-panel-hover">-</button>
                      <span className="font-mono text-foreground">{configuration.quantity}</span>
                      <button onClick={() => setConfiguration({...configuration, quantity: configuration.quantity + 1})} className="size-8 rounded-lg hover:bg-panel-hover"><Plus size={16}/></button>
                    </span>
                  </label>
                </div>
              </Card>
            </div>

            {/* --- КАРТОЧКА ЦЕНЫ --- */}
            <PriceCard 
              price={activeMaterial.price_per_gram * configuration.dimensions.x * configuration.quantity * 0.1 + 300} // Временная формула
              days={3} 
              disabled={!model} 
            />
          </div>
        </div>
      </main>
    </div>
  );
}
