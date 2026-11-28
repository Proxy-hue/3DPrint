# Полный анализ проекта 3DPrint

Документ описывает фактическую архитектуру проекта после исправления основного frontend/backend-разрыва.

## Текущий статус

Проект представляет собой рабочий MVP:

- frontend собран на React, TypeScript, Vite и Tailwind;
- frontend авторизуется через Django JWT;
- файлы загружаются на Django и сохраняются в модели `PrintModel`;
- сервер проверяет STL, OBJ и 3MF;
- сервер рассчитывает цену;
- сервер создает и хранит реальные заказы;
- менеджерские пользователи могут просматривать общую очередь и изменять статус;
- клиенты могут работать только со своими моделями и заказами;
- logout аннулирует refresh-токен;
- Docker Compose может запустить frontend, backend, PostgreSQL, Redis и MinIO-сервис;
- SQLite доступен для локального запуска без Docker.

Проверенное состояние:

- production-сборка frontend проходит;
- Django system check проходит;
- Django test suite проходит: 13 тестов;
- миграции 0001 и 0002 применяются;
- миграции token blacklist применяются.

## Архитектура

```text
React/Vite
  -> VITE_API_URL
  -> Django REST API
  -> JWT SimpleJWT
  -> Django ORM
  -> SQLite или PostgreSQL
  -> локальная media storage

Django REST API
  -> validation.services
  -> server-side material and price catalog
  -> Order model
```

## Технологии

### Frontend

| Технология | Назначение |
|---|---|
| React 18 | Страницы, компоненты, эффекты |
| TypeScript strict | Типы предметной области и API |
| Vite | Development server и сборка |
| Tailwind CSS 4 | Общая тема и utility-классы |
| React Context | Глобальное состояние конфигурации и заказов |
| lucide-react | Иконки |
| clsx/tailwind-merge | Комбинирование классов |
| Fetch API | Авторизация и HTTP-взаимодействие с Django |
| JWT | Access/refresh-токены пользователя |
| localStorage | Только токены и локальные UI-настройки |
| nginx | Раздача production-сборки внутри frontend-контейнера |

### Backend

| Технология | Назначение |
|---|---|
| Django 5.2 | ORM, admin, auth, routing |
| Django REST Framework | REST API |
| Simple JWT | Access/refresh-токены |
| token_blacklist | Аннулирование refresh-токена при logout |
| PostgreSQL 16 | Основная Docker-БД |
| SQLite | Локальная БД без Docker |
| Redis 7 | Инфраструктурный сервис, пока нет application integration |
| Docker Compose | Запуск сервисов |
| Python media storage | Текущий storage для загруженных моделей |

## Структура проекта

```text
3DPrint/
├── ARH/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── index.css
│   │   ├── main.tsx
│   │   ├── types.ts
│   │   ├── context/OrderContext.tsx
│   │   ├── components/ui.tsx
│   │   └── services/api.ts
│   ├── Dockerfile
│   ├── nginx.conf
│   └── package.json
├── backend/
│   ├── config/
│   ├── users/
│   ├── models/
│   ├── validation/
│   └── manage.py
├── docker-compose.yml
├── requirements.txt
├── README.md
└── PROJECT_ANALYSIS.md
```

# Разбор frontend

## `ARH/src/main.tsx`

Функции модуля:

- создаёт React root;
- подключает `OrderProvider`;
- подключает global CSS;
- включает React StrictMode.

## `ARH/src/types.ts`

Основные типы:

- `MaterialId`: PLA, ABS, PETG, Resin, Nylon;
- `PrintingTechnology`: FDM, SLA, SLS;
- `OrderStatus`: Pending, In Production, Shipped, Delivered;
- `PostProcessing`: none, sanding, painting;
- `Material`: цена за грамм, плотность, технология и цвета;
- `UploadedModel`: id сохраненной модели, имя, размер, формат, дата и optional dimensions;
- `PriceBreakdown`: расшифровка стоимости;
- `OrderConfiguration`: параметры печати;
- `Order`: серверный/клиентский результат заказа;
- `NavigationItem`: разделы навигации.

## `ARH/src/App.tsx`

### Общие компоненты

- `formatPrice`: форматирует рубли;
- `formatDate`: форматирует дату по русской локали;
- `formatSize`: переводит байты в КБ/МБ;
- `Logo`: логотип портала;
- `PageHeading`: единый заголовок страницы;
- `StatCard`: карточка метрики АРМ.

### `AppHeader`

- отрисовывает desktop-sidebar;
- отрисовывает mobile-menu;
- переключает тему;
- предоставляет кнопку logout;
- отображает счётчик заказов.

### `UploadCard`

- поддерживает выбор и drag-and-drop;
- принимает только `.stl`, `.obj`, `.3mf`;
- передает файл в API;
- показывает серверный статус загрузки;
- получает dimensions от backend и устанавливает их в конфигурацию;
- не содержит mock-проверки.

### `MaterialCard`

- отрисовывает материал;
- переключает выбор через context;
- синхронизирует технологию и цвет.

### `ConfigurationCard`

- содержит выбор материала;
- проверяет совместимость технологии;
- вводит dimensions;
- управляет высотой слоя, заполнением, обработкой и тиражом;
- проверяет диапазоны UI.

### `PriceCard`

- вызывает серверный расчёт через context;
- показывает расшифровку стоимости;
- блокирует оформление при некорректной конфигурации;
- показывает серверный срок и вес;
- передает создание заказа в backend.

### `OrderTable`

- отрисовывает заказы;
- поддерживает пустое состояние;
- содержит повтор заказа или manager actions;
- переводит данные backend в единый вид.

### `OrdersPage`

- загружает серверные заказы через context;
- фильтрует список на стороне frontend;
- повторно загружает параметры заказа.

### `ManagerPage`

- загружает общую очередь для manager/admin;
- фильтрует производственную очередь;
- проверяет размеры по серверному признаку `equipmentCompatible`;
- переводит статус через API.
- Доступность manager-interface требует server permissions, а frontend пока показывает раздел всем авторизованным пользователям.

### `HelpPage`

- описывает фактически поддерживаемые форматы;
- описывает отсутствие модуля оплаты;
- содержит ссылки поддержки.

### `DashboardPage`

- объединяет загрузку, параметры и смету;
- создает заказ через backend;
- после создания переходит в историю.

### `AuthScreen`

- поддерживает login и register;
- сохраняет access и refresh-токены;
- обрабатывает ошибки Django;
- предоставляет logout из интерфейса;
- по истечении access-токена API-клиент пытается refresh.

### `Toast`

- отображает success/error/info-сообщения;
- поддерживает ручное закрытие.

### `App`

- переключает auth/non-auth state;
- хранит тему;
- хранит страницу и mobile-menu;
- очищает auth state после logout.

## `ARH/src/context/OrderContext.tsx`

### Состояние

Хранит:

- конфигурацию печати;
- загруженную модель;
- серверную цену;
- список заказов;
- loading-состояния;
- toast.

### Функции

- `notify`: добавляет toast и автоматически скрывает его;
- `dismissToast`: закрывает toast;
- `refreshOrders`: загружает заказы через API;
- `setConfiguration`: частично обновляет конфигурацию;
- `setMaterial`: меняет материал и технологию;
- `setTechnology`: не разрешает несовместимые технологии;
- `setColor`: меняет цвет;
- `uploadFile`: загружает модель через backend;
- `placeOrder`: проверяет модель/цену и создает server-side заказ;
- `reorder`: переносит параметры предыдущего заказа;
- `changeStatus`: изменяет статус через API;
- `useOrder`: проверяет наличие provider.

### Эффекты

- загрузка заказов при mount;
- debounce серверного расчета на 250 мс;
- защита от устаревшего ответа через `calculationSequence`.

## `ARH/src/services/api.ts`

### Конфигурация

- API URL берется из `VITE_API_URL`;
- fallback: `http://127.0.0.1:8000`;
- access/refresh-токены хранятся в localStorage.

### Функции

- `request`: общий fetch, headers JWT и JSON, refresh-токен и обработка API-ошибок;
- `getAccessToken`: читает access-токен;
- `isAuthenticated`: проверяет наличие access-токена;
- `login`: получает JWT-пару;
- `register`: создаёт пользователя и сразу выполняет login;
- `logout`: отправляет refresh-токен на backend и очищает локальное состояние;
- `getProfile`: получает профиль пользователя;
- `uploadModel`: multipart-загрузка и создание `PrintModel`;
- `calculatePrice`: серверный POST расчета;
- `mapOrder`: преобразует API DTO во frontend `Order`;
- `createOrder`: создаёт server-side заказ по ID сохраненной модели;
- `getOrders`: получает серверный список заказов;
- `updateOrderStatus`: обновляет статус заказа.

## Исправления frontend

Исправлено:

- mock-заказы больше не являются основным хранилищем;
- PLY удалён из фактического интерфейса загрузки;
- лимит стал 50 МБ вместо 100 МБ;
- тексты mock/demo заменены на фактические API-состояния;
- добавлен JWT login/register/logout;
- добавлен refresh access-токена;
- цена рассчитывается backend;
- файл загружается backend;
- заказы создаются backend;
- габариты загруженной модели передаются в конфигурацию;
- production frontend включен в Docker Compose;
- добавлен Dockerfile и nginx-конфигурация.

# Разбор backend

## `backend/config/settings.py`

Настраивает:

- Django приложений и middleware;
- SQLite или PostgreSQL;
- JWT REST Framework;
- custom user model;
- CORS;
- media storage;
- token_blacklist.

Секретный ключ по умолчанию стал длиной не менее безопасного уровня для локальной разработки. В production секрет должен задаваться через environment и не попадать в compose-файлы.

## `backend/config/urls.py`

Публикует:

- `/admin/`;
- `/api/users/`;
- `/api/models/`;
- `/api/validation/`;
- `/media/` в DEBUG.

## Users

### `User`

Расширяет `AbstractUser`:

- role;
- phone;
- строковое представление через full name или username.

### Serializer и views

- `UserSerializer`: чтение/частичное обновление профиля;
- `RegisterSerializer`: password validation, lowercase email, unique email;
- `LoginSerializer`: роль и email в JWT;
- `RegisterView`: публичная регистрация клиентом;
- `LoginView`: выдача JWT-пары;
- `RefreshView`: обновление access-токена;
- `ProfileView`: доступ только к своему профилю;
- `LogoutView`: добавляет refresh-токен в blacklist.

Тестами подтверждены регистрация, профиль, login и logout.

## PrintModel

### Модель

`PrintModel` хранит:

- owner;
- file;
- original_name;
- format;
- size;
- status;
- validation_errors;
- width/height/depth;
- timestamps.

Удаление владельца удаляет связанные модели.

### Serializer

- проверяет формат;
- вызывает validation service;
- сохраняет dimensions при первичной загрузке;
- устанавливает status `validated`.

### Views

- список ограничен owner;
- retrieve/delete ограничены owner;
- download ограничен owner;
- поддерживается локальная выдача файла.

## Order

Новая миграция создает доменную модель `Order`.

Поля:

- owner;
- model;
- status;
- configuration;
- server-calculated price;
- equipment_compatible;
- timestamps.

Поведение:

- клиенты получают только свои заказы;
- manager/admin получают общую очередь;
- foreign model должен принадлежать тому же пользователю;
- model должна быть validated;
- цена пересчитывается backend при создании;
- изменение статуса запрещено обычному пользователю;
- список и создание доступны через `/api/models/orders/`.

## Валидация

`backend/validation/services.py` содержит:

- `_bounds`: вычисление bounding box;
- `validate_binary_stl`: binary STL-разбор и проверка facet count;
- `validate_ascii_stl`: ASCII STL-разбор;
- `validate_stl`: выбор ASCII или binary-парсера;
- `validate_obj`: UTF-8 и вершины OBJ;
- `validate_3mf`: ZIP/XML и вершины 3MF;
- `validate_model_file`: общий лимит формата, размера и размеров.

Исправления:

- добавлено сохранение dimensions в `PrintModel`;
- улучшено различение ASCII и binary STL;
- лимиты выровнены с frontend: 50 МБ;
- PLY удалён из фактического интерфейса.

Ограничение остается: валидация определяет структуру и bounding box, но не manifold и printability.

## Серверный pricing

Добавлено в backend:

- GET `/api/models/materials/`;
- POST `/api/models/calculate-price/`;
- server-side конфигурация материалов;
- проверка совместимости technology/material;
- проверка height, infill, quantity и dimensions;
- immutable snapshot цены в `Order`.

Расчет выполняется по формулам:

1. volume = X × Y × Z / 1000;
2. для SLA infill считается 100%;
3. для остальных infill: 0.3 + fill × 0.7;
4. weight = volume × fill × density × 0.035;
5. material cost = weight × pricePerGram × quantity;
6. printing cost = weight × 42 × (0.2 / layerHeight) × quantity;
7. sanding = 350 × quantity;
8. painting = 650 × quantity;
9. delivery = 390;
10. lead time = ceil(weight × quantity × layerFactor / 120), минимум 2 дня.

## API routes

| Метод | Route | Назначение |
|---|---|---|
| POST | `/api/users/register/` | Регистрация |
| POST | `/api/users/login/` | JWT login |
| POST | `/api/users/refresh/` | Refresh access |
| POST | `/api/users/logout/` | Blacklist refresh |
| GET/PATCH | `/api/users/me/` | Профиль |
| GET/POST | `/api/models/` | Модели пользователя |
| GET/DELETE | `/api/models/<id>/` | Модель пользователя |
| GET | `/api/models/<id>/download/` | Скачивание файла |
| POST | `/api/validation/validate/` | Проверка загруженного файла |
| POST | `/api/validation/models/<id>/validate/` | Повторная проверка |
| GET | `/api/models/materials/` | Каталог материалов |
| POST | `/api/models/calculate-price/` | Серверный расчет |
| GET/POST | `/api/models/orders/` | Заказы |
| GET/PATCH | `/api/models/orders/<id>/` | Заказ и статус |

# Исправленные ошибки анализа

## Добавлено или исправлено

- frontend больше не использует localStorage как источник заказов;
- frontend теперь использует реальный REST API;
- backend получил модель `Order`;
- добавлен server-side catalog материалов;
- добавлен server-side pricing;
- добавлена изоляция моделей и заказов по owner;
- добавлены роли для общей очереди manager/admin;
- JWT logout теперь аннулирует refresh-токен;
- добавлен refresh access-токена;
- token blacklist включен в Django;
- форма регистрации и входа добавлена во frontend;
- PLY удалён из фактической поддержки;
- лимиты выровнены на 50 МБ;
- dimensions сохраняются при загрузке и возвращаются frontend;
- frontend добавлен в Docker Compose;
- добавлен frontend Dockerfile;
- добавлен migration для orders;
- добавлены тесты заказов и logout;
- короткий SECRET_KEY заменен на более безопасный development fallback;
- улучшено различение binary и ASCII STL.

# Недостающие части проекта

## Без чего MVP не является production-системой

1. Нет платежного провайдера.
2. Нет счета, чека и подтверждения оплаты.
3. Нет полноценной базы оборудования и проверки совместимости модели.
4. Нет production-манифеста принтеров: только bool `equipmentCompatible`.
5. Нет менеджерской панели со server-side ролевым контролем в frontend.
6. Нет полноценной модели статуса с запретами запрещенных переходов.
7. Нет статических истории событий статуса.
8. Нет notifications/email/SMS.
9. Нет документов заказа и производства.
10. Нет отзывов, учета брака или возвратов.
11. Нет админского управления ценами и материалами.
12. Нет интеграционного API-клиента для ERP/MES.
13. Файлы моделей выдаются через защищенный owner/staff endpoint; публичные ссылки клиентам не возвращаются.
14. Django storage переключается между частным локальным каталогом и закрытым S3/MinIO bucket через `USE_S3_STORAGE`.
15. Проверка сохраненной модели запускается через `django-rq` и Redis; статус и полный результат сохраняются в записи модели.
16. Нет автоматического retry/recovery для упавших worker-задач; отдельный endpoint проверки временного файла пока работает синхронно.
17. Нет real mesh validation/manifold checking.
18. Нет preview/thumbnail модели.
18. Нет нормализации единиц и ориентации детали.
20. Нет проверки shell closure, self-intersections или минимальной толщины.
21. Нет пагинации моделей и заказов.
22. Нет фильтрации, поиска и сортировки backend.
23. Нет frontend unit/E2E-тестов.
24. Нет CI workflow.
25. Нет lint/type-check workflow.
26. Нет production Gunicorn/Uvicorn вместо runserver.
27. Нет reverse proxy и HTTPS.
28. Нет централизованного логирования и Sentry/аналитики.
29. Нет резервного копирования PostgreSQL/media.
30. Нет `.env` секретного значения в production.
31. Нет корректной настройки `ALLOWED_HOSTS` для конкретного домена.
32. Нет файловых quota и antivirus/scanner проверки.
33. Нет content-type validation по magic bytes.
34. Нет ограничения concurrency загрузки.
35. Нет защиты от repeated fraud payment/orders.
36. Нет production-конфигурации static files через `collectstatic`.

# Что нужно реализовать далее

## Приоритет P0

1. Подключить платежный провайдер и изменить статус только после подтверждения.
2. Добавить print equipment model и server-side совместимость.
3. Ввести state machine статусов.
4. Добавить manager/admin UI guards по роли.
5. Скрыть/разрешить API по `role`, а не только через frontend.
6. Добавить пагинацию и file/quota restrictions.

## Приоритет P1

1. Создать для production отдельные least-privilege S3/MinIO credentials вместо root credentials из Compose.
2. Добавить retry/backoff и восстановление статуса при сбоях фоновых задач; рассмотреть асинхронную проверку временных файлов.
3. Использовать Trimesh/libigl или аналогичный mesh pipeline.
4. Проверять manifold, faces, пересечения и толщину.
5. Сохранять audit log статусов.
6. Добавить уведомления клиенту и менеджеру.
7. Добавить Product/Material admin для администратора.

## Приоритет P2

1. Добавить React unit-тесты и Playwright E2E.
2. Добавить backend OpenAPI/Swagger.
3. Добавить CI для tests/build/migrations.
4. Настроить production Docker/Compose profile.
5. Подключить Gunicorn и nginx.
6. Подключить HTTPS и централизованные логи.
7. Добавить backup/restore procedures.

# Тестирование

## Проверенные команды

Frontend:

```powershell
cd ARH
npm run build
```

Backend:

```powershell
cd backend
$env:USE_SQLITE="True"
& ..\.venv\Scripts\python.exe manage.py check
& ..\.venv\Scripts\python.exe manage.py test
```

Ожидаемый backend-результат: 13 тестов успешно.

## Backend тесты

Существующие группы:

- users: регистрация, login, profile, logout;
- PrintModel: upload, unsupported format, 50 MB limit, owner isolation;
- validation: empty file, OBJ dimensions, saved model revalidation;
- Order: создание своей модели, owner isolation.

# Запуск без Docker

## Backend

```powershell
cd backend
$env:USE_SQLITE="True"
& ..\.venv\Scripts\python.exe manage.py migrate
& ..\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

## Frontend

```powershell
cd ARH
npm ci
npm run dev -- --host 127.0.0.1
```

Адрес frontend: `http://127.0.0.1:5173`.

# Docker-запуск

```bash
docker compose up --build
```

Frontend: `http://localhost:5173`.

Backend: `http://localhost:8000`.

Админка: `http://localhost:8000/admin`.
