# Модули заказов, расчёта, переписки, уведомлений и клиентский портал

> **Зона ответственности:** А. Г. Видерман  
> **Базовая ветка:** `develop` (поверх реализованных модулей `catalog`, `common` и модели `users.User`).  
> **Статус:** первая рабочая версия для интеграции в `develop` с автономным временным контуром для модулей коллег, которые ещё находятся в разработке.

---

## 1. Какие модули реализованы в этом PR

| Модуль / папка | Назначение | Основные файлы |
| :--- | :--- | :--- |
| **`orders`** | Заказы, 14-статусная FSM, таблица переходов, оптимистичная/пессимистичная блокировка, неизменяемая история `OrderEvent`, REST API | [models.py](models.py), [services.py](services.py), [views.py](views.py), [serializers.py](serializers.py), [urls.py](urls.py) |
| **`pricing`** | Расчёт стоимости/сроков по формулам раздела 6.3 спецификации, сметы `Quote`, корректировки цены администратором | [../pricing/models.py](../pricing/models.py), [../pricing/formulas.py](../pricing/formulas.py), [../pricing/services.py](../pricing/services.py) |
| **`messaging`** | Переписка клиента и менеджера по заказу + досылка исправленной 3D-модели в статусах `DRAFT` / `CLARIFICATION` / `MANUAL_REVIEW` | [../messaging/models.py](../messaging/models.py), [../messaging/services.py](../messaging/services.py) |
| **`notifications`** | Внутренние (`INAPP`) и e-mail (`EMAIL`) уведомления с повторами `[5, 15, 60]` минут и командой `retry_notifications` | [../notifications/models.py](../notifications/models.py), [../notifications/services.py](../notifications/services.py), [../notifications/views.py](../notifications/views.py) |
| **`payment`** | Заглушка оплаты (`StubPaymentProvider`, флаг `PAY_STUB_ENABLED`) по требованию `F-CLI-08` | [../payment/models.py](../payment/models.py), [../payment/services.py](../payment/services.py) |
| **`frontend/`** | **Временный клиентский портал** (регистрация, вход, визард заказа с 3D-просмотром, список заказов, карточка заказа, чат, уведомления). АРМ менеджера выведен в заглушку `ManagerPlaceholder.tsx` | [../../frontend/README.md](../../frontend/README.md) |

Модули коллег (`catalog`, `common`, `users`, `models_app`, `validation`, `scheduling`, `integrations`) **не изменялись**.

---

## 2. Как это стыкуется с остальной архитектурой (для команды)

Чтобы наша ветка уже сейчас запускалась, тестировалась в CI и не создавала конфликтов с ещё не залитыми ветками коллег:

1. **Интеграция с `catalog` и `common` (уже готово в `develop`):**
   - Права доступа берутся из `common.permissions` (`IsAnyRole`, `IsManagerOrAdmin`, `IsAdminRole`, `get_role`, `has_role`).
   - Все модели наследуются от `common.models.BaseModel` (`UUIDField`).
   - Параметры тарифа берутся из `catalog.services.get_tariff_params()` и `catalog.TariffVersion` (вторая таблица тарифов в `pricing` не создавалась).
   - Журнал изменений при корректировке цены админом пишется в `catalog.audit.record` (`catalog_auditlog`).
   - Совместимость параметров заказа проверяется через `catalog.services.check_compatibility(...)`.

2. **Временный адаптер `orders/adapters.py` (до слияния модулей коллег):**
   - Автоматически делегирует вызовы в `models_app.services`, `validation.services` и `scheduling.services`, если соответствующие функции реализованы:
     - `models_app.services`: `add_version`, `current_version`, `get_version`, `clone_current`, `file_info`, `read_bytes`;
     - `validation.services`: `validate`, `latest_for`;
     - `scheduling.services`: `queue_wait_hours`, `current_assignment`, `recommend`, `assign`, `clear_assignment`, `get_printer`.
   - Пока эти модули в `develop` ещё пустые, работает встроенный минимальный fallback (хранение модели в `MEDIA_ROOT`, разбор сетки через `trimesh`, проверка `E-01..E-06`/`W-01..W-05` поверх `catalog.services`).
   - В `messaging.Message` временно используются поля `model_version_id` и `model_version_num` вместо `ForeignKey('models_app.ModelVersion')`.

3. **Временные эндпоинты входа `orders/temp_auth.py`:**
   - В `develop` модуль `users` пока без представлений входа/регистрации, поэтому для работы клиентского портала временно подключены маршруты `/api/auth/*` из `orders/temp_auth.py`.
   - После слияния полноценного `users` от П. А. Юшковой достаточно переключить `/api/auth/*` в `config/urls.py` на `users.urls` и удалить `orders/temp_auth.py`.

---

## 3. Локальный запуск и проверка

```powershell
# 1. Backend (SQLite + локальное хранилище задаются в .env)
cd backend
..\.venv\Scripts\python manage.py migrate
..\.venv\Scripts\python manage.py loaddata initial_catalog
..\.venv\Scripts\python manage.py runserver 127.0.0.1:8000

# 2. Frontend (в другом терминале)
cd frontend
npm run dev
```

### Автотесты и проверки
```powershell
# Проверка миграций, линтер и тесты backend
cd backend
..\.venv\Scripts\flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
..\.venv\Scripts\python manage.py makemigrations --check --dry-run
..\.venv\Scripts\python -m pytest -v

# Тесты и сборка frontend
cd frontend
npm test
npm run build
```
