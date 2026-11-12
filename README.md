# 3DPrint

Система заказа 3D-печати. 

**Технологический стек**:
- Python (Django REST Framework)
- React (TypeScript)
- PostgreSQL 16
- Redis 7
- MinIO (S3)

## 📋 Предварительные требования
Перед началом работы убедитесь, что у вас установлены:
1. [Git](https://git-scm.com/downloads)
2. [Docker Desktop](https://www.docker.com/products/docker-desktop/) (для Windows/Mac) или Docker Engine (для Linux). **Важно:** Docker Desktop должен быть запущен перед выполнением команд.

## 🚀 Как запустить локально

1. Склонируйте репозиторий:

```bash
git https://github.com/Proxy-hue/3DPrint.git
cd 3DPrint
```

2. Создайте файл `.env` на основе `.env.example`:

```bash
cp .env.example .env
```

*(Файл `.env` содержит локальные пароли и не попадает в Git. Если на Windows команда `cp` не работает, просто скопируйте файл вручную и переименуйте).*

3. Запустите инфраструктуру в фоне:

```bash
docker compose up -d
```

4. **Проверка**: Убедитесь, что все контейнеры запустились (статус `Up` или `Running`):

```bash
docker ps
```

## 🔗 Доступные сервисы после запуска:
- **PostgreSQL (БД)**: `localhost:5432` (Данные для входа в `.env`)
- **MinIO (Хранилище 3D-моделей)**: http://localhost:9001
    - *Логин*: `minioadmin`
    - *Пароль*: `minioadmin`

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
├── .env.example        # Шаблон переменных окружения
├── .gitignore          # Исключения для Git
├── docker-compose.yml  # Конфигурация локальной инфраструктуры
└── README.md           # Этот файл
```

## ❓ Частые проблемы (Troubleshooting)
Ошибка `port is already allocated`: У вас на компьютере уже запущен PostgreSQL, Redis или другой Docker-контейнер, который занимает порт. Остановите старые контейнеры (`docker ps` -> `docker stop <id>`) или измените порты в `docker-compose.yml`.