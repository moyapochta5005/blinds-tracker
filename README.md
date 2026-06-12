# Blinds Tracker — Сервис отслеживания заказов

Веб-сервис для учёта и отслеживания заказов на изготовление жалюзи и штор. Клиенты проверяют статус по номеру заказа или QR-коду, сотрудники управляют заказами через панель администратора.

## Функционал

- **Публичное отслеживание** — страница `/static/track.html` для клиентов: поиск заказа по номеру, просмотр текущего статуса и истории этапов.
- **Панель сотрудника** — `/static/admin.html`: создание заказов, смена статусов, просмотр списка заказов, генерация QR-кодов.
- **REST API** — эндпоинты для заказов (`/orders`), авторизации (`/auth`) и QR-кодов (`/orders/{id}/qr`).
- **Роли пользователей** — администратор, мастер цеха и курьер с разграничением доступа через JWT.
- **Telegram-уведомления** — опциональные push-сообщения клиенту при смене статуса (требуется `TELEGRAM_BOT_TOKEN`).
- **SQLite-база данных** — файл `orders.db` с заказами и историей этапов.

### Статусы заказа

| Статус | Описание |
|--------|----------|
| `new` | Принят |
| `in_production` | В производстве |
| `ready` | Готов |
| `delivered` | Доставлен |
| `cancelled` | Отменён |

## Запуск через Docker

### Требования

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

### Быстрый старт

```bash
# Сборка и запуск в фоне
docker compose up -d --build

# Проверка статуса
docker compose ps

# Просмотр логов
docker compose logs -f web
```

Приложение будет доступно по адресу: **http://localhost:8002**

Проверка работоспособности: **http://localhost:8002/health**

### Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `SECRET_KEY` | Секретный ключ для подписи JWT-токенов | `change-me-in-production` |
| `TELEGRAM_BOT_TOKEN` | Токен Telegram-бота для уведомлений | пусто (уведомления отключены) |
| `DATABASE_URL` | URL подключения к SQLite | `sqlite:///./orders.db` (локально) |

Задайте переменные в файле `.env` в корне проекта или передайте при запуске:

```bash
SECRET_KEY=ваш-секретный-ключ TELEGRAM_BOT_TOKEN=123456:ABC docker compose up -d
```

### Остановка и удаление

```bash
# Остановить контейнер
docker compose down

# Остановить и удалить том с базой данных
docker compose down -v
```

База данных `orders.db` хранится в именованном томе `orders_db` (каталог `/app/data` внутри контейнера) и сохраняется между перезапусками.

## Демо-аккаунты

Для входа в панель сотрудника (`/static/admin.html`) используйте:

| Логин | Пароль | Роль |
|-------|--------|------|
| `admin` | `admin123` | Администратор |
| `master` | `master123` | Мастер цеха |
| `courier` | `courier123` | Курьер |

> **Важно:** демо-аккаунты предназначены только для тестирования. В production замените их на полноценную систему пользователей и задайте надёжный `SECRET_KEY`.

## Скриншоты

<!-- TODO: добавить скриншоты после деплоя -->

| Страница | Описание |
|----------|----------|
| ![Отслеживание заказа](docs/screenshots/track.png) | Публичная страница отслеживания |
| ![Панель администратора](docs/screenshots/admin.png) | Панель сотрудника |
| ![QR-код заказа](docs/screenshots/qr.png) | QR-код для клиента |

*Скриншоты будут добавлены после первого деплоя. Заглушки: `docs/screenshots/`.*

## Стек технологий

| Компонент | Технология |
|-----------|------------|
| Backend | Python 3.11, FastAPI |
| ORM | SQLAlchemy |
| Валидация | Pydantic |
| База данных | SQLite |
| Сервер | Uvicorn |
| Авторизация | JWT (PyJWT) |
| QR-коды | qrcode + Pillow |
| Уведомления | python-telegram-bot |
| Контейнеризация | Docker, Docker Compose |

## Локальная разработка (без Docker)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

Приложение: **http://localhost:8001**

## Структура проекта

```
blinds-tracker/
├── app/
│   ├── main.py           # Точка входа FastAPI
│   ├── models.py         # SQLAlchemy-модели
│   ├── schemas.py        # Pydantic-схемы
│   ├── database.py       # Подключение к SQLite
│   ├── routers/          # API-роутеры
│   └── static/           # HTML-страницы фронтенда
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```
