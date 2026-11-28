# 3DPrint

Система заказа 3D-печати. 

**Технологический стек**:
- Python 3.12 (Django 5, DRF)
- React 18 (TypeScript, Vite)
- PostgreSQL 16
- Redis 7
- MinIO / SILO (S3)

## 📋 Предварительные требования
Перед началом работы убедитесь, что у вас установлены:
1. [Git](https://git-scm.com/downloads)
2. [Docker Desktop](https://www.docker.com/products/docker-desktop/) (для Windows/Mac) или Docker Engine (для Linux). **Важно:** Docker Desktop должен быть запущен перед выполнением команд.

## 🚀 Как запустить локально

1. Склонируйте репозиторий и перейдите в папку проекта:

```bash
git clone https://github.com/Proxy-hue/3DPrint.git
cd 3DPrint
```

2. Обязательно переключитесь на рабочую ветку `develop`:

```bash
git checkout develop
```

3. Создайте файл `.env` на основе `.env.example`:

```bash
cp .env.example .env
```

*(Файл `.env` содержит локальные пароли и не попадает в Git. Если на Windows команда `cp` не работает, просто скопируйте файл вручную и переименуйте).*

4. Запустите инфраструктуру (при первом запуске скачаются зависимости и соберутся контейнеры):

```bash
docker compose up -d --build
```

5. Проверка: убедитесь, что все контейнеры запустились (статус `Up` или `Running`):

```bash
docker ps
```

6. Первичная настройка базы данных и хранилища:
Выполните эти команды один раз (в корне проекта), чтобы применить миграции БД и создать бакет для файлов:

```bash
# Применяем миграции Django
docker compose exec backend python manage.py migrate

# Создаем суперпользователя для админки (придумайте логин/пароль)
docker compose exec backend python manage.py createsuperuser

# Устанавливаем boto3 локально и создаем бакет в S3 (если у вас установлен Python)
pip install boto3
python scripts/init_s3.py
```

*(Если локального Python нет, бакет можно создать вручную в веб-интерфейсе SILO).*

## 🔗 Доступные сервисы после запуска:
- Клиентский портал (React): http://localhost:5173/client
- АРМ Менеджера (React): http://localhost:5173/manager
- Backend (Django API): http://localhost:8000
- Админка Django: http://localhost:8000/admin
- Почтовый сервер (Mailpit): http://localhost:8025 (сюда падают все письма от системы)
- PostgreSQL (БД): localhost:5432 (Данные для входа в .env)
- S3-хранилище (SILO/MinIO): http://localhost:9001
    - Логин: `minioadmin`
    - Пароль: `minioadmin`

## 🛑 Как остановить
Остановить контейнеры (данные сохранятся):

```bash
docker compose stop
```

Остановить и удалить контейнеры (данные в БД и файлы в MinIO сохранятся в volumes):

```bash
docker compose down
```

## 🌿 Как работать с Git
Мы используем GitFlow. Прямые коммиты в `main` и `develop` запрещены (защищено правилами GitHub).

### Процесс разработки

1. Переключитесь на `develop` и стяните последние изменения:

```bash
git checkout develop
git pull origin develop
```

2. Создайте ветку под свою задачу от `develop`:

```bash
git checkout -b feature/название-вашей-фичи
# например: git checkout -b feature/auth-login
```

3. Пишите код, делайте коммиты:

```bash
git add .
git commit -m "feat: добавил форму авторизации"
```

4. Пушьте ветку в удаленный репозиторий:

```bash
git push origin feature/название-вашей-фичи
```

5. Перейдите на GitHub, создайте Pull Request из вашей ветки в `develop`.
6. Дождитесь ревью (Code Review) от тимлида или коллеги.

## 📁 Структура проекта (заполняется по мере разработки)
```text
3DPrint/
├── backend/            # Django-проект (API, бизнес-логика)
├── frontend/           # React-приложение (Клиентский портал, АРМ менеджера)
├── scripts/            # Вспомогательные скрипты (init_s3.py)
├── .github/workflows/  # CI пайплайны (GitHub Actions)
├── .env.example        # Шаблон переменных окружения
├── .gitignore          # Исключения для Git
├── docker-compose.yml  # Конфигурация локальной инфраструктуры
└── README.md           # Этот файл
```

## ❓ Частые проблемы (Troubleshooting)
Ошибка `port is already allocated`: У вас на компьютере уже запущен PostgreSQL, Redis или другой Docker-контейнер, который занимает порт. Остановите старые контейнеры (`docker ps` -> `docker stop <id>`) или измените порты в `docker-compose.yml`.