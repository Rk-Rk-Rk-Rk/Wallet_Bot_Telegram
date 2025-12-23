GB Wallet Bot
Telegram-бот для управления GB Coins, фишками, маркетплейсом услуг, системой рейтинга и админ-панелью. Реализован на aiogram с SQLite базой данных.
​

![Static Badge](https://img.shields.io/badge/YourUsernamehttps://img.shields.io/github/languages/top/YourUsername/GBWalletBothttps://img.shields.io/github/license/Yourhttps://img.shields.io/github/stars/YourUsernamehttps://img.shields.io/github/issues/Your

Установка (Linux)
Требуется Python 3.7+, pip и токен Telegram-бота от @BotFather.
​

Клонирование репозитория

bash
git clone https://github.com/YourUsername/GBWalletBot.git
Переход в директорию

bash
cd GBWalletBot
Создание виртуального окружения

bash
python3 -m venv venv
Активация виртуального окружения

bash
source venv/bin/activate
Создайте requirements.txt:

text
aiogram>=3.0.0
aiosqlite
Установка зависимостей

bash
pip install -r requirements.txt
Настройка конфигурации в RU_telegram_bot.py:

Замените API_TOKEN на токен вашего бота

Укажите ADMIN_IDS (ваш Telegram ID)

Запуск бота

bash
python RU_telegram_bot.py
Функции бота
💰 Проверка баланса GB Coins и фишек

💸 Переводы GB Coins между пользователями

🔄 Обмен GB Coins на фишки (1 GBc = 0.1 рубля)

🏪 Маркетплейс услуг с покупкой/продажей

⭐ Система рейтинга (+1/-1, ежедневный топ)

👑 Админ-панель (управление балансами, системный счет)

📊 Топ игроков по балансу
​

Документация
Полная пользовательская документация: docs/ru/index.md
​

Поддержка
Создайте обсуждение или напишите на email: your.email@example.com
​

Зависимости
Python 3.7+

pip 23.2+

aiogram 3.x (асинхронный Telegram Bot API)

aiosqlite (SQLite с async/await)
​
​
