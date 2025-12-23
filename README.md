text
# Wallet Bot (Telegram)

Telegram-бот “кошелёк” на Python (aiogram + SQLite): баланс, переводы, обмен GB ↔ GBc, маркетплейс услуг, рейтинги и админ-панель.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Framework](https://img.shields.io/badge/aiogram-v3.x-2ea44f)
![DB](https://img.shields.io/badge/SQLite-aiosqlite-informational)
![License](https://img.shields.io/badge/License-MIT-yellow)

> Репозиторий: https://github.com/Rk-Rk-Rk-Rk/Wallet_Bot_Telegram

---

## Возможности

- **Баланс**: просмотр GB Coins и GBc (chips).
- **Переводы**: отправка GB Coins другому пользователю по username.
- **Обмен**:
  - пользователь: обмен GB → GBc по курсу 1 GB = 10 GBc;
  - админ: обратный обмен GBc → GB (по твоим правилам, заложенным в боте).
- **Топ**: рейтинг по балансу.
- **Маркетплейс**:
  - выставление услуги (описание + цена),
  - просмотр активных лотов,
  - покупка (перевод средств продавцу и пометка “sold”).
- **Рейтинги пользователей**:
  - оценка +1 / -1,
  - ограничение на повторную оценку одного пользователя в течение 24 часов,
  - топ рейтинга за последние 24 часа (через daily-агрегацию).
- **Админ-панель**:
  - изменить баланс/GBc пользователю,
  - переводы от системного аккаунта,
  - просмотр системного аккаунта и истории транзакций,
  - удаление лота по ID.

---

## Быстрый старт

### 1) Клонирование
git clone https://github.com/Rk-Rk-Rk-Rk/Wallet_Bot_Telegram.git
cd Wallet_Bot_Telegram

text

### 2) Установка зависимостей
Рекомендуется виртуальное окружение:

python -m venv venv

Windows:
venv\Scripts\activate

Linux/macOS:
source venv/bin/activate

text

Установи зависимости:
pip install aiogram aiosqlite

text

### 3) Настройка
Открой файл `RU_telegram_bot.py` и укажи значения:
- `API_TOKEN` — токен бота из @BotFather
- `ADMIN_IDS` — список Telegram ID админов
- `BOT_NAME` — имя бота (опционально)
- `DB_NAME` — имя SQLite файла (например `wallet.db`)

> В текущей версии конфиг задан прямо в коде. При желании можно вынести в `.env`/`config.py`.

### 4) Запуск
python RU_telegram_bot.py

text

---

## Использование (в Telegram)

1. Напиши боту команду `/start`.
2. Управляй через **InlineKeyboard** меню:
   - Balance
   - Transfer
   - Exchange
   - Top
   - Marketplace
   - Rating
   - Admin (только для ADMIN_IDS)

---

## Команды и ввод

Некоторые действия требуют текстового ввода:

- **Перевод**:  
  Формат: `<username> <amount>`  
  Пример: `@someuser 10`

- **Оценка**:  
  Формат: `<username> <rating>` где rating = `1` или `-1`  
  Пример: `@someuser 1`

- **Маркетплейс / размещение услуги**:  
  Формат: `<описание>, <цена>`  
  Пример: `Сделаю логотип, 50`

- **Покупка**:  
  Ввод: `ID` лота

---

## База данных (SQLite)

Таблицы создаются автоматически при старте:

- `users`: `user_id`, `username`, `balance`, `chips`
- `transactions`: `sender_id`, `recipient_id`, `amount`, `type`, `timestamp`
- `marketplace`: `seller_id`, `description`, `price`, `status`
- `ratings`: оценки (+1/-1) между пользователями
- `daily_ratings`: агрегация рейтинга по дням

---

## Структура проекта

Минимальная структура (как сейчас):

- `RU_telegram_bot.py` — весь код бота (роутеры, меню, БД-логика, обработчики)

> Если захочешь “по-взрослому”, можно разнести на `handlers/`, `db/`, `keyboards/`, `config/`.

---

## Безопасность и ограничения

- Проверка на недостаток средств при переводах/покупках.
- Запрет на перевод/оценку самого себя.
- Ограничение на повторную оценку одного пользователя: 24 часа.

---

## Идеи улучшений (по желанию)

- Вынести конфиг в `.env` (python-dotenv).
- `requirements.txt` + pin-версии.
- Логи в файл + ротация.
- Dockerfile / docker-compose.
- Тесты для DB-слоя (pytest).
- CI (GitHub Actions).

---

## Описание коммитов

| Тип | Назначение |
|-----|------------|
| feat | Новый функционал |
| fix | Исправление багов |
| refactor | Рефакторинг без изменения поведения |
| perf | Оптимизация производительности |
| docs | Документация/README |
| test | Тесты |
| ci | CI/CD и скрипты |
| build | Сборка/зависимости |
| revert | Откат изменений |
| style | Форматирование/линтер |

---

## Лицензия

MIT (если в репозитории действительно используется MIT).
