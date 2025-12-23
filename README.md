# Wallet Bot (Telegram)

Telegram-бот “кошелёк” на Python (aiogram + SQLite): баланс, переводы, обмен GB ↔ GBc, маркетплейс услуг, рейтинги и админ-панель.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Framework](https://img.shields.io/badge/aiogram-v3.x-2ea44f)
![DB](https://img.shields.io/badge/SQLite-aiosqlite-informational)
![License](https://img.shields.io/badge/License-MIT-yellow)

> Репозиторий: https://github.com/Rk-Rk-Rk-Rk/Wallet_Bot_Telegram

---

## Возможности

- **Баланс**: просмотр GB Coins и GBc.
- **Переводы**: отправка GB Coins другому пользователю по username.
- **Обмен**:
  - пользователь: обмен GB → GBc по курсу 1 GB = 10 GBc;
  - админ: обратный обмен GBc → GB .
- **Топ**: рейтинг по балансу.
- **Маркетплейс**:
  - выставление услуги (описание + цена),
  - просмотр активных лотов,
  - покупка (перевод средств продавцу и пометка “sold”).
- **Рейтинги пользователей**:
  - оценка +1 / -1,
  - ограничение на повторную оценку одного пользователя в течение 24 часов,
  - топ рейтинга за последние 24 часа.
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

### 2) Установка зависимостей
Рекомендуется виртуальное окружение:

python -m venv venv

Windows:
venv\Scripts\activate

Linux/macOS:
source venv/bin/activate

Установи зависимости:
pip install aiogram aiosqlite

### 3) Настройка
Открой файл `RU_telegram_bot.py` и укажи значения:
- `API_TOKEN` — токен бота из @BotFather
- `ADMIN_IDS` — список Telegram ID админов
- `BOT_NAME` — имя бота (опционально)
- `DB_NAME` — имя SQLite файла (например `wallet.db`)

### 4) Запуск
python RU_telegram_bot.py

## Использование (в Telegram)

1. Напиши боту команду `/start`.
2. Управляй через клавиатуру :
   - Проверить баланс
   - Перевести GBс
   - Обмен GBс на фишки
   - Топ игроков
   - Маркетплейс
   - Система рейтинга
   - Админ панель

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


## Лицензия

![License](https://img.shields.io/badge/License-MIT-yellow)
