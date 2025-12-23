GB Wallet Bot
Telegram-бот для управления GB Coins, фишками, маркетплейсом услуг, системой рейтинга и админ-панелью. Реализован на aiogram с SQLite базой данных.
​

Установка (Linux)
Требуется Python 3.7+, pip и токен Telegram-бота от @BotFather.
​

Клонирование репозитория
git clone https://github.com/YourUsername/GBWalletBot.git
Переход в директорию
cd GBWalletBot
Создание виртуального окружения
python3 -m venv venv
Активация виртуального окружения
source venv/bin/activate

Создайте requirements.txt:
aiogram>=3.0.0
aiosqlite

Установка зависимостей
pip install -r requirements.txt
Настройка конфигурации в RU_telegram_bot.py:
Замените API_TOKEN на токен вашего бота
Укажите ADMIN_IDS (ваш Telegram ID)

Запуск бота
python RU_telegram_bot.py

Функции бота
  Проверка баланса GB Coins и фишек
  Переводы GB Coins между пользователями
  Обмен GB Coins на фишки (1 GBc = 0.1 рубля)
  Маркетплейс услуг с покупкой/продажей
  Система рейтинга (+1/-1, ежедневный топ)
  Админ-панель (управление балансами, системный счет)
  Топ игроков по балансу
​​
​
Зависимости
Python 3.7+
pip 23.2+
aiogram 3.x (асинхронный Telegram Bot API)
aiosqlite (SQLite с async/await)
​
