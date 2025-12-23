import asyncio
import aiosqlite
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
import logging
from datetime import datetime, timedelta

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
API_TOKEN = 'API_TOKEN'
DB_NAME = 'Bot_Name'
ADMIN_IDS = ["ADMIN_ID"]
SYSTEM_ACCOUNT_ID = -1
INSUFFICIENT_FUNDS_MESSAGE = "У вас недостаточно GB Coins."
INITIAL_BALANCE = 200.0 # начальный баланс 

# Хранение ID последнего сообщения бота и состояния пользователя
last_bot_message = {}
user_state = {}  # Стек для хранения предыдущих меню

# Роутер для обработки сообщений
router = Router()

# Инициализация базы данных
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
                                user_id INTEGER PRIMARY KEY,
                                username TEXT,
                                balance REAL DEFAULT 0,
                                chips REAL DEFAULT 0)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS ratings (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                rater_id INTEGER,
                                rated_id INTEGER,
                                rating INTEGER,
                                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS daily_ratings (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                user_id INTEGER,
                                points REAL,
                                date DATE)''')
        async with db.execute('PRAGMA table_info(users)') as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            if 'chips' not in columns:
                await db.execute('ALTER TABLE users ADD COLUMN chips REAL DEFAULT 0')
            if 'username' not in columns:
                await db.execute('ALTER TABLE users ADD COLUMN username TEXT')
        await db.execute('''CREATE TABLE IF NOT EXISTS transactions (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                sender_id INTEGER,
                                recipient_id INTEGER,
                                amount REAL,
                                type TEXT,
                                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        async with db.execute('PRAGMA table_info(transactions)') as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            if 'type' not in columns:
                await db.execute('ALTER TABLE transactions ADD COLUMN type TEXT')
        await db.execute('''CREATE TABLE IF NOT EXISTS marketplace (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                seller_id INTEGER,
                                description TEXT,
                                price REAL,
                                status TEXT DEFAULT 'active')''')
        await db.execute('INSERT OR IGNORE INTO users (user_id, balance, chips, username) VALUES (?, 0, 0, ?)', 
                        (SYSTEM_ACCOUNT_ID, 'System'))
        await db.commit()

# Вспомогательные функции для базы данных
async def get_user_data(user_id, username=None):
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('SELECT balance, chips, username FROM users WHERE user_id = ?', (user_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    username = username or f"User_{user_id}"
                    await db.execute('INSERT INTO users (user_id, username, balance, chips) VALUES (?, ?, ?, 0)', 
                                   (user_id, username, INITIAL_BALANCE))
                    await db.commit()
                    return (INITIAL_BALANCE, 0.0, username)
                if username and username != row[2]:
                    await db.execute('UPDATE users SET username = ? WHERE user_id = ?', (username, user_id))
                    await db.commit()
                return row
    except Exception as e:
        logger.error(f"Ошибка при получении данных пользователя {user_id}: {e}")
        return (INITIAL_BALANCE, 0.0, username or f"User_{user_id}")

async def get_user_id_by_username(username):
    try:
        username = username.lstrip('@')
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('SELECT user_id FROM users WHERE username = ? OR username = ?', 
                                (username, f"@{username}")) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
    except Exception as e:
        logger.error(f"Ошибка при поиске user_id по username {username}: {e}")
        return None

async def update_user_data(user_id, balance=None, chips=None, increment=False):
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute('INSERT OR IGNORE INTO users (user_id, username, balance, chips) VALUES (?, ?, ?, 0)', 
                           (user_id, f"User_{user_id}", INITIAL_BALANCE))
            updates = []
            params = []
            if balance is not None:
                updates.append('balance = balance + ?' if increment else 'balance = ?')
                params.append(balance)
            if chips is not None:
                updates.append('chips = chips + ?' if increment else 'chips = ?')
                params.append(chips)
            if updates:
                query = f'UPDATE users SET {", ".join(updates)} WHERE user_id = ?'
                params.append(user_id)
                await db.execute(query, params)
            await db.commit()
    except Exception as e:
        logger.error(f"Ошибка при обновлении данных пользователя {user_id}: {e}")

async def notify_admins(bot, message):
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, message)
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления админу {admin_id}: {e}")

# Удаление предыдущих сообщений
async def delete_previous_messages(message: Message, bot_message: Message = None):
    user_id = message.from_user.id
    try:
        await message.delete()
        if user_id in last_bot_message:
            try:
                await message.bot.delete_message(message.chat.id, last_bot_message[user_id])
            except:
                pass
        if bot_message:
            last_bot_message[user_id] = bot_message.message_id
    except Exception as e:
        logger.error(f"Ошибка при удалении сообщений для {user_id}: {e}")

# КНОПКИ
main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Проверить баланс", callback_data='balance')],
    [InlineKeyboardButton(text="Перевести GBс ", callback_data='transfer')],
    [InlineKeyboardButton(text="Обмен GBс на фишки", callback_data='exchange_gb')],
    [InlineKeyboardButton(text="Топ игроков", callback_data='top')],
    [InlineKeyboardButton(text="Маркетплейс", callback_data='marketplace')],
    [InlineKeyboardButton(text="Админ панель", callback_data='admin')],
    [InlineKeyboardButton(text="Система рейтинга", callback_data='rating_menu')],
])

rating_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Поставить оценку", callback_data='rate_user')],
    [InlineKeyboardButton(text="Топ рейтинга", callback_data='rating_top')],
    [InlineKeyboardButton(text="Назад", callback_data='back')]
])

exchange_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="10 копеек (1 GBc)", callback_data='exchange_1')],
    [InlineKeyboardButton(text="50 копеек (5 GBc)", callback_data='exchange_5')],
    [InlineKeyboardButton(text="1 рубль (10 GBc)", callback_data='exchange_10')],
    [InlineKeyboardButton(text="2 рубля (20 GBc)", callback_data='exchange_20')],
    [InlineKeyboardButton(text="5 рублей (50 GBc)", callback_data='exchange_50')],
    [InlineKeyboardButton(text="10 рублей (100 GBc)", callback_data='exchange_100')],
    [InlineKeyboardButton(text="Назад", callback_data='back')]
])

marketplace_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Выставить услугу", callback_data='list_service')],
    [InlineKeyboardButton(text="Просмотр услуг", callback_data='browse')],
    [InlineKeyboardButton(text="Назад", callback_data='back')]
])

admin_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Изменить баланс", callback_data='adjust_balance')],
    [InlineKeyboardButton(text="Изменить фишки", callback_data='adjust_chips')],
    [InlineKeyboardButton(text="Перевести с системного счёта", callback_data='transfer_system')],
    [InlineKeyboardButton(text="Просмотр системного счёта", callback_data='view_system')],
    [InlineKeyboardButton(text="Удалить услугу", callback_data='remove_listing')],
    [InlineKeyboardButton(text="Обмен фишек в GBc", callback_data='exchange_chips_to_gb')],
    [InlineKeyboardButton(text="Просмотр фишек пользователей", callback_data='view_chips')],
    [InlineKeyboardButton(text="Назад", callback_data='back')]
])

def get_back_button():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data='back')]])

# Обработчики
@router.message(Command('start'))
async def start(message: Message):
    username = message.from_user.username or message.from_user.first_name
    await get_user_data(message.from_user.id, username)
    user_state[message.from_user.id] = ['main']
    bot_message = await message.answer("Добро пожаловать в GB Wallet!", reply_markup=main_menu)
    await delete_previous_messages(message, bot_message)

@router.callback_query(lambda c: c.data == 'rating_menu')
async def show_rating_menu(callback: CallbackQuery):
    user_state[callback.from_user.id].append('rating_menu')
    bot_message = await callback.message.answer("Система рейтинга:", reply_markup=rating_menu)
    await delete_previous_messages(callback.message, bot_message)

@router.callback_query(lambda c: c.data == 'rate_user')
async def rate_user(callback: CallbackQuery):
    user_state[callback.from_user.id].append('rate_user_input')
    bot_message = await callback.message.answer("Введите ник пользователя (с @ или без) и оценку (+1 или -1) через пробел (например, @username +1)", reply_markup=get_back_button())
    await delete_previous_messages(callback.message, bot_message)

@router.message(lambda message: user_state.get(message.from_user.id, ['main'])[-1] == 'rate_user_input')
async def process_rate_user(message: Message):
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            bot_message = await message.answer("Неверный формат. Используйте: ник оценка (например, @username +1)", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        username, rating_str = parts
        rating = int(rating_str)
        if rating not in [-1, 1]:
            bot_message = await message.answer("Оценка должна быть +1 или -1.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        rater_id = message.from_user.id
        rated_id = await get_user_id_by_username(username)
        if not rated_id:
            bot_message = await message.answer(f"Пользователь {username} не найден.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        if rater_id == rated_id:
            bot_message = await message.answer("Нельзя оценивать самого себя.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        async with aiosqlite.connect(DB_NAME) as db:
            cutoff = datetime.now() - timedelta(days=1)
            async with db.execute('SELECT COUNT(*) FROM ratings WHERE rater_id = ? AND rated_id = ? AND timestamp > ?', 
                                (rater_id, rated_id, cutoff)) as cursor:
                count = (await cursor.fetchone())[0]
                if count > 0:
                    bot_message = await message.answer("Вы уже оценивали этого пользователя сегодня.", reply_markup=get_back_button())
                    await delete_previous_messages(message, bot_message)
                    return
            await db.execute('INSERT INTO ratings (rater_id, rated_id, rating) VALUES (?, ?, ?)', 
                           (rater_id, rated_id, rating))
            await db.commit()
        bot_message = await message.answer(f"Оценка {rating} для @{username} успешно поставлена.", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except ValueError:
        bot_message = await message.answer("Ошибка: неверный формат оценки. Укажите +1 или -1.", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except Exception as e:
        logger.error(f"Ошибка при постановке оценки: {e}")
        bot_message = await message.answer(f"Ошибка: {e}", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)

@router.callback_query(lambda c: c.data == 'rating_top')
async def rating_top(callback: CallbackQuery):
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            # Начисление очков за день
            today = datetime.now().date()
            async with db.execute('SELECT DISTINCT date FROM daily_ratings') as cursor:
                last_date = (await cursor.fetchone())
                if not last_date or last_date[0] != str(today):
                    await db.execute('DELETE FROM daily_ratings WHERE date != ?', (str(today),))
                    async with db.execute('SELECT rated_id, SUM(rating) as points FROM ratings WHERE timestamp > ? GROUP BY rated_id', 
                                        (datetime.now() - timedelta(days=1),)) as cursor:
                        ratings = await cursor.fetchall()
                        for rated_id, points in ratings:
                            await db.execute('INSERT INTO daily_ratings (user_id, points, date) VALUES (?, ?, ?)', 
                                           (rated_id, points, today))
                        await db.commit()
            # Подсчет общего рейтинга
            async with db.execute('SELECT user_id, SUM(points) as total FROM daily_ratings GROUP BY user_id ORDER BY total DESC LIMIT 10') as cursor:
                rows = await cursor.fetchall()
                top_list = []
                for row in rows:
                    _, _, username = await get_user_data(row[0])
                    top_list.append(f"@{username}: {row[1]:.2f} очков")
                response = "Топ рейтинга:\n" + "\n".join(top_list) if top_list else "Список пуст"
                bot_message = await callback.message.answer(response, reply_markup=get_back_button())
                await delete_previous_messages(callback.message, bot_message)
    except Exception as e:
        logger.error(f"Ошибка при получении топа рейтинга: {e}")
        bot_message = await callback.message.answer("Ошибка при получении топа. Попробуйте позже.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)

@router.callback_query(lambda c: c.data == 'back')
async def go_back(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in user_state or len(user_state[user_id]) <= 1:
        user_state[user_id] = ['main']
        bot_message = await callback.message.answer("Выберите действие:", reply_markup=main_menu)
        await delete_previous_messages(callback.message, bot_message)
        return
    user_state[user_id].pop()  # Удаляем последнее состояние
    previous_state = user_state[user_id][-1]
    if previous_state == 'main':
        bot_message = await callback.message.answer("Выберите действие:", reply_markup=main_menu)
    elif previous_state == 'marketplace':
        bot_message = await callback.message.answer("Маркетплейс:", reply_markup=marketplace_menu)
    elif previous_state == 'admin':
        bot_message = await callback.message.answer("Админ панель:", reply_markup=admin_menu)
    elif previous_state == 'rating_menu':
        bot_message = await callback.message.answer("Система рейтинга:", reply_markup=rating_menu)
    else:
        bot_message = await callback.message.answer("Выберите действие:", reply_markup=main_menu)
        user_state[user_id] = ['main']
    await delete_previous_messages(callback.message, bot_message)

@router.callback_query(lambda c: c.data == 'balance')
async def check_balance(callback: CallbackQuery):
    try:
        balance, chips, username = await get_user_data(callback.from_user.id, callback.from_user.username or callback.from_user.first_name)
        bot_message = await callback.message.answer(f"Ваш баланс (@{username}):\nGB Coins: {balance:.2f}\nФишки: {chips:.2f}", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)
    except Exception as e:
        logger.error(f"Ошибка при проверке баланса для {callback.from_user.id}: {e}")
        bot_message = await callback.message.answer("Ошибка при проверке баланса. Попробуйте позже.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)

@router.callback_query(lambda c: c.data == 'transfer')
async def transfer(callback: CallbackQuery):
    user_state[callback.from_user.id].append('transfer_input')
    bot_message = await callback.message.answer("Введите ник получателя (с @ или без) и сумму GB Coins через пробел (например, @username 10)", reply_markup=get_back_button())
    await delete_previous_messages(callback.message, bot_message)

@router.message(lambda message: user_state.get(message.from_user.id, ['main'])[-1] == 'transfer_input')
async def process_transfer(message: Message):
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            bot_message = await message.answer("Неверный формат. Используйте: ник сумма (например, @username 10)", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        recipient_username, amount = parts
        amount = float(amount)
        if amount <= 0:
            bot_message = await message.answer("Сумма должна быть больше 0.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        sender_id = message.from_user.id
        sender_balance, _, _ = await get_user_data(sender_id, message.from_user.username or message.from_user.first_name)
        if sender_balance < amount:
            bot_message = await message.answer(INSUFFICIENT_FUNDS_MESSAGE, reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        recipient_id = await get_user_id_by_username(recipient_username)
        if not recipient_id:
            bot_message = await message.answer(f"Пользователь {recipient_username} не найден.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        if recipient_id == sender_id:
            bot_message = await message.answer("Нельзя переводить самому себе.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (amount, sender_id))
            await db.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, recipient_id))
            await db.execute('INSERT INTO transactions (sender_id, recipient_id, amount, type) VALUES (?, ?, ?, ?)', 
                           (sender_id, recipient_id, amount, 'GB'))
            await db.commit()
        bot_message = await message.answer("Перевод выполнен успешно.", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except ValueError:
        bot_message = await message.answer("Ошибка: неверный формат суммы. Укажите число (например, @username 10).", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except Exception as e:
        logger.error(f"Ошибка при переводе от {message.from_user.id} к {recipient_username}: {e}")
        bot_message = await message.answer(f"Ошибка: {e}", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)

@router.callback_query(lambda c: c.data == 'exchange_gb')
async def exchange_gb(callback: CallbackQuery):
    user_state[callback.from_user.id].append('exchange_menu')
    bot_message = await callback.message.answer("Выберите сумму для обмена GBc на фишки:", reply_markup=exchange_menu)
    await delete_previous_messages(callback.message, bot_message)

@router.callback_query(lambda c: c.data.startswith('exchange_'))
async def process_exchange(callback: CallbackQuery, bot: Bot):
    try:
        gb = float(callback.data.split('_')[1])
        chips = gb / 10  # 1 GBc = 0.1 рубля
        user_id = callback.from_user.id
        user_balance, _, username = await get_user_data(user_id, callback.from_user.username or callback.from_user.first_name)
        if user_balance < gb:
            bot_message = await callback.message.answer(INSUFFICIENT_FUNDS_MESSAGE, reply_markup=get_back_button())
            await delete_previous_messages(callback.message, bot_message)
            return
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute('UPDATE users SET balance = balance - ?, chips = chips + ? WHERE user_id = ?', 
                           (gb, chips, user_id))
            await db.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (gb, SYSTEM_ACCOUNT_ID))
            await db.execute('INSERT INTO transactions (sender_id, recipient_id, amount, type) VALUES (?, ?, ?, ?)', 
                           (user_id, SYSTEM_ACCOUNT_ID, gb, 'GB'))
            await db.execute('INSERT INTO transactions (sender_id, recipient_id, amount, type) VALUES (?, ?, ?, ?)', 
                           (SYSTEM_ACCOUNT_ID, user_id, chips, 'chips'))
            await db.commit()
        bot_message = await callback.message.answer(f"Обменено {gb:.2f} GBc на {chips:.2f} фишек (1 GBc = 0.1 рубля).", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)
        await notify_admins(bot, f"Пользователь @{username} обменял {gb:.2f} GBc на {chips:.2f} фишек.")
    except Exception as e:
        logger.error(f"Ошибка при обмене GBc для {callback.from_user.id}: {e}")
        bot_message = await callback.message.answer(f"Ошибка: {e}", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)

@router.callback_query(lambda c: c.data == 'top')
async def top_players(callback: CallbackQuery):
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('SELECT user_id, balance, username FROM users WHERE user_id != ? ORDER BY balance DESC LIMIT 10', 
                                (SYSTEM_ACCOUNT_ID,)) as cursor:
                rows = await cursor.fetchall()
                top_list = "\n".join([f"@{row[2] or f'User_{row[0]}'}: {row[1]:.2f} GB Coins" for row in rows])
                bot_message = await callback.message.answer(f"Топ игроков:\n{top_list or 'Список пуст'}", reply_markup=get_back_button())
                await delete_previous_messages(callback.message, bot_message)
    except Exception as e:
        logger.error(f"Ошибка при получении топа игроков: {e}")
        bot_message = await callback.message.answer("Ошибка при получении топа. Попробуйте позже.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)

@router.callback_query(lambda c: c.data == 'marketplace')
async def marketplace(callback: CallbackQuery):
    user_state[callback.from_user.id].append('marketplace')
    bot_message = await callback.message.answer("Маркетплейс:", reply_markup=marketplace_menu)
    await delete_previous_messages(callback.message, bot_message)

@router.callback_query(lambda c: c.data == 'list_service')
async def list_service(callback: CallbackQuery):
    user_state[callback.from_user.id].append('list_service_input')
    bot_message = await callback.message.answer("Введите описание услуги и цену через '|' (например, Помощь с кодом|50)", reply_markup=get_back_button())
    await delete_previous_messages(callback.message, bot_message)

@router.message(lambda message: user_state.get(message.from_user.id, ['main'])[-1] == 'list_service_input')
async def process_list_service(message: Message):
    try:
        parts = message.text.split('|', 1)
        if len(parts) != 2:
            bot_message = await message.answer("Неверный формат. Используйте: описание|цена", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        description, price = parts
        price = float(price.strip())
        if price <= 0:
            bot_message = await message.answer("Цена должна быть больше 0.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        seller_id = message.from_user.id
        await get_user_data(seller_id, message.from_user.username or message.from_user.first_name)
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute('INSERT INTO marketplace (seller_id, description, price) VALUES (?, ?, ?)', 
                           (seller_id, description.strip(), price))
            await db.commit()
        bot_message = await message.answer("Услуга выставлена на маркетплейс.", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except ValueError:
        bot_message = await message.answer("Ошибка: неверная цена. Укажите число.", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except Exception as e:
        logger.error(f"Ошибка при добавлении услуги для {message.from_user.id}: {e}")
        bot_message = await message.answer(f"Ошибка: {e}", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)

@router.callback_query(lambda c: c.data == 'browse')
async def browse_services(callback: CallbackQuery):
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('SELECT id, seller_id, description, price FROM marketplace WHERE status = "active"') as cursor:
                rows = await cursor.fetchall()
                if not rows:
                    bot_message = await callback.message.answer("Нет активных услуг.", reply_markup=get_back_button())
                    await delete_previous_messages(callback.message, bot_message)
                    return
                response = "Доступные услуги:\n"
                for row in rows:
                    _, _, seller_username = await get_user_data(row[1])
                    response += f"ID: {row[0]} | {row[2]} | Цена: {row[3]:.2f} GBc | Продавец: @{seller_username}\n"
                response += "\nДля покупки нажмите кнопку ниже и введите ID услуги."
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Купить услугу", callback_data='buy')],
                    [InlineKeyboardButton(text="Назад", callback_data='back')]
                ])
                bot_message = await callback.message.answer(response, reply_markup=keyboard)
                await delete_previous_messages(callback.message, bot_message)
    except Exception as e:
        logger.error(f"Ошибка при просмотре услуг: {e}")
        bot_message = await callback.message.answer("Ошибка при просмотре услуг. Попробуйте позже.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)

@router.callback_query(lambda c: c.data == 'buy')
async def buy_service_start(callback: CallbackQuery):
    user_state[callback.from_user.id].append('buy_input')
    bot_message = await callback.message.answer("Введите ID услуги для покупки (например, 1)", reply_markup=get_back_button())
    await delete_previous_messages(callback.message, bot_message)

@router.message(lambda message: user_state.get(message.from_user.id, ['main'])[-1] == 'buy_input')
async def process_buy_service(message: Message, bot: Bot):
    try:
        listing_id = int(message.text)
        buyer_id = message.from_user.id
        buyer_username = message.from_user.username or message.from_user.first_name
        _, _, buyer_username = await get_user_data(buyer_id, buyer_username)
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('SELECT seller_id, price, status, description FROM marketplace WHERE id = ?', (listing_id,)) as cursor:
                row = await cursor.fetchone()
                if not row or row[2] != 'active':
                    bot_message = await message.answer("Услуга не найдена или уже продана.", reply_markup=get_back_button())
                    await delete_previous_messages(message, bot_message)
                    return
                seller_id, price, _, description = row
                buyer_balance, _, _ = await get_user_data(buyer_id)
                if buyer_balance < price:
                    bot_message = await message.answer(INSUFFICIENT_FUNDS_MESSAGE, reply_markup=get_back_button())
                    await delete_previous_messages(message, bot_message)
                    return
                await db.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (price, buyer_id))
                await db.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (price, seller_id))
                await db.execute('UPDATE marketplace SET status = "sold" WHERE id = ?', (listing_id,))
                await db.execute('INSERT INTO transactions (sender_id, recipient_id, amount, type) VALUES (?, ?, ?, ?)', 
                               (buyer_id, seller_id, price, 'GB'))
                await db.commit()
            bot_message = await message.answer("Услуга успешно приобретена.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            try:
                await bot.send_message(seller_id, f"Ваш товар '{description}' купил @{buyer_username} за {price:.2f} GB Coins.")
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления продавцу {seller_id}: {e}")
    except ValueError:
        bot_message = await message.answer("Ошибка: неверный формат ID. Укажите число (например, 1).", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except Exception as e:
        logger.error(f"Ошибка при покупке услуги для {message.from_user.id}: {e}")
        bot_message = await message.answer(f"Ошибка: {e}", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)

@router.callback_query(lambda c: c.data == 'admin')
async def admin_panel(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        bot_message = await callback.message.answer("Доступ запрещён.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)
        return
    user_state[callback.from_user.id].append('admin')
    bot_message = await callback.message.answer("Админ панель:", reply_markup=admin_menu)
    await delete_previous_messages(callback.message, bot_message)

@router.callback_query(lambda c: c.data == 'adjust_balance')
async def adjust_balance(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        bot_message = await callback.message.answer("Доступ запрещён.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)
        return
    user_state[callback.from_user.id].append('adjust_balance_input')
    bot_message = await callback.message.answer("Введите ник пользователя (с @ или без) и новый баланс GB Coins через пробел (например, @username 100)", reply_markup=get_back_button())
    await delete_previous_messages(callback.message, bot_message)

@router.message(lambda message: user_state.get(message.from_user.id, ['main'])[-1] == 'adjust_balance_input')
async def process_adjust_balance(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            bot_message = await message.answer("Неверный формат. Используйте: ник количество (например, @username 100)", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        username, value = parts
        value = float(value)
        if value < 0:
            bot_message = await message.answer("Значение не может быть отрицательным.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        user_id = await get_user_id_by_username(username)
        if not user_id:
            bot_message = await message.answer(f"Пользователь {username} не найден.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        await update_user_data(user_id, balance=value)
        bot_message = await message.answer(f"Баланс GB Coins для @{username} успешно изменён.", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except ValueError:
        bot_message = await message.answer("Ошибка: неверный формат суммы. Укажите число (например, @username 100).", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except Exception as e:
        logger.error(f"Ошибка при обработке админ-команды для {message.from_user.id}: {e}")
        bot_message = await message.answer(f"Ошибка: {e}", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)

@router.callback_query(lambda c: c.data == 'adjust_chips')
async def adjust_chips(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        bot_message = await callback.message.answer("Доступ запрещён.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)
        return
    user_state[callback.from_user.id].append('adjust_chips_input')
    bot_message = await callback.message.answer("Введите ник пользователя (с @ или без) и новое количество фишек через пробел (например, @username 100)", reply_markup=get_back_button())
    await delete_previous_messages(callback.message, bot_message)

@router.message(lambda message: user_state.get(message.from_user.id, ['main'])[-1] == 'adjust_chips_input')
async def process_adjust_chips(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            bot_message = await message.answer("Неверный формат. Используйте: ник количество (например, @username 100)", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        username, value = parts
        value = float(value)
        if value < 0:
            bot_message = await message.answer("Значение не может быть отрицательным.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        user_id = await get_user_id_by_username(username)
        if not user_id:
            bot_message = await message.answer(f"Пользователь {username} не найден.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        await update_user_data(user_id, chips=value)
        bot_message = await message.answer(f"Фишки для @{username} успешно изменены.", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except ValueError:
        bot_message = await message.answer("Ошибка: неверный формат суммы. Укажите число (например, @username 100).", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except Exception as e:
        logger.error(f"Ошибка при обработке админ-команды для {message.from_user.id}: {e}")
        bot_message = await message.answer(f"Ошибка: {e}", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)

@router.callback_query(lambda c: c.data == 'transfer_system')
async def transfer_system(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        bot_message = await callback.message.answer("Доступ запрещён.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)
        return
    user_state[callback.from_user.id].append('transfer_system_input')
    bot_message = await callback.message.answer("Введите ник получателя (с @ или без) и сумму GB Coins через пробел (например, @username 100)", reply_markup=get_back_button())
    await delete_previous_messages(callback.message, bot_message)

@router.message(lambda message: user_state.get(message.from_user.id, ['main'])[-1] == 'transfer_system_input')
async def process_transfer_system(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            bot_message = await message.answer("Неверный формат. Используйте: ник количество (например, @username 100)", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        username, value = parts
        value = float(value)
        if value < 0:
            bot_message = await message.answer("Значение не может быть отрицательным.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        user_id = await get_user_id_by_username(username)
        if not user_id:
            bot_message = await message.answer(f"Пользователь {username} не найден.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        system_balance, _, _ = await get_user_data(SYSTEM_ACCOUNT_ID)
        if system_balance < value:
            bot_message = await message.answer(INSUFFICIENT_FUNDS_MESSAGE, reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (value, SYSTEM_ACCOUNT_ID))
            await db.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (value, user_id))
            await db.execute('INSERT INTO transactions (sender_id, recipient_id, amount, type) VALUES (?, ?, ?, ?)', 
                           (SYSTEM_ACCOUNT_ID, user_id, value, 'GB'))
            await db.commit()
        bot_message = await message.answer(f"Перевод {value:.2f} GBc с системного счёта для @{username} выполнен успешно.", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except ValueError:
        bot_message = await message.answer("Ошибка: неверный формат суммы. Укажите число (например, @username 100).", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except Exception as e:
        logger.error(f"Ошибка при обработке админ-команды для {message.from_user.id}: {e}")
        bot_message = await message.answer(f"Ошибка: {e}", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)

@router.callback_query(lambda c: c.data == 'view_system')
async def view_system(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        bot_message = await callback.message.answer("Доступ запрещён.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)
        return
    try:
        balance, _, _ = await get_user_data(SYSTEM_ACCOUNT_ID)
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('SELECT sender_id, recipient_id, amount, type, timestamp FROM transactions WHERE sender_id = ? OR recipient_id = ?', 
                                (SYSTEM_ACCOUNT_ID, SYSTEM_ACCOUNT_ID)) as cursor:
                rows = await cursor.fetchall()
                history = []
                for row in rows:
                    sender_username = (await get_user_data(row[0]))[2] or f"User_{row[0]}"
                    recipient_username = (await get_user_data(row[1]))[2] or f"User_{row[1]}"
                    history.append(f"{row[4]}: @{sender_username} -> @{recipient_username}, {row[2]:.2f} {row[3]}")
                history_text = "\n".join(history)
                bot_message = await callback.message.answer(f"Системный счёт:\nБаланс: {balance:.2f} GB Coins\n\nИстория транзакций:\n{history_text or 'Пусто'}", reply_markup=get_back_button())
                await delete_previous_messages(callback.message, bot_message)
    except Exception as e:
        logger.error(f"Ошибка при просмотре системного счёта: {e}")
        bot_message = await callback.message.answer("Ошибка при просмотре системного счёта. Попробуйте позже.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)

@router.callback_query(lambda c: c.data == 'remove_listing')
async def remove_listing(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        bot_message = await callback.message.answer("Доступ запрещён.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)
        return
    user_state[callback.from_user.id].append('remove_listing_input')
    bot_message = await callback.message.answer("Введите ID услуги для удаления (например, 1)", reply_markup=get_back_button())
    await delete_previous_messages(callback.message, bot_message)

@router.message(lambda message: user_state.get(message.from_user.id, ['main'])[-1] == 'remove_listing_input')
async def process_remove_listing(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        listing_id = int(message.text)
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('SELECT 1 FROM marketplace WHERE id = ?', (listing_id,)) as cursor:
                if not await cursor.fetchone():
                    bot_message = await message.answer("Услуга не найдена.", reply_markup=get_back_button())
                    await delete_previous_messages(message, bot_message)
                    return
            await db.execute('DELETE FROM marketplace WHERE id = ?', (listing_id,))
            await db.commit()
        bot_message = await message.answer("Услуга удалена.", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except ValueError:
        bot_message = await message.answer("Ошибка: неверный формат ID. Укажите число (например, 1).", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except Exception as e:
        logger.error(f"Ошибка при удалении услуги для {message.from_user.id}: {e}")
        bot_message = await message.answer(f"Ошибка: {e}", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)

@router.callback_query(lambda c: c.data == 'exchange_chips_to_gb')
async def exchange_chips_to_gb(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        bot_message = await callback.message.answer("Доступ запрещён.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)
        return
    user_state[callback.from_user.id].append('exchange_chips_input')
    bot_message = await callback.message.answer("Введите ник пользователя (с @ или без) и сумму в рублях для обмена фишек в GBc (например, @username 11.4). 1 рубль = 10 GBc.", reply_markup=get_back_button())
    await delete_previous_messages(callback.message, bot_message)

@router.message(lambda message: user_state.get(message.from_user.id, ['main'])[-1] == 'exchange_chips_input')
async def process_exchange_chips_to_gb(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            bot_message = await message.answer("Неверный формат. Используйте: ник сумма (например, @username 11.4)", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        username, amount_str = parts
        amount_rub = float(amount_str)
        if amount_rub < 0:
            bot_message = await message.answer("Сумма не может быть отрицательной.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        user_id = await get_user_id_by_username(username)
        if not user_id:
            bot_message = await message.answer(f"Пользователь {username} не найден.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        gb = amount_rub * 10  # 1 рубль = 10 GBc
        chips = amount_rub
        _, user_chips, _ = await get_user_data(user_id)
        if user_chips < chips:
            bot_message = await message.answer("У пользователя недостаточно фишек.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        system_balance, _, _ = await get_user_data(SYSTEM_ACCOUNT_ID)
        if system_balance < gb:
            bot_message = await message.answer(INSUFFICIENT_FUNDS_MESSAGE, reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute('UPDATE users SET chips = chips - ?, balance = balance + ? WHERE user_id = ?', 
                           (chips, gb, user_id))
            await db.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (gb, SYSTEM_ACCOUNT_ID))
            await db.execute('INSERT INTO transactions (sender_id, recipient_id, amount, type) VALUES (?, ?, ?, ?)', 
                           (user_id, SYSTEM_ACCOUNT_ID, chips, 'chips'))
            await db.execute('INSERT INTO transactions (sender_id, recipient_id, amount, type) VALUES (?, ?, ?, ?)', 
                           (SYSTEM_ACCOUNT_ID, user_id, gb, 'GB'))
            await db.commit()
        bot_message = await message.answer(f"Обменено {chips:.2f} фишек пользователя @{username} на {gb:.2f} GBc.", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except ValueError:
        bot_message = await message.answer("Ошибка: неверный формат суммы. Укажите число (например, @username 11.4).", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except Exception as e:
        logger.error(f"Ошибка при обмене фишек для {message.from_user.id}: {e}")
        bot_message = await message.answer(f"Ошибка: {e}", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)

@router.callback_query(lambda c: c.data == 'view_chips')
async def view_chips(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        bot_message = await callback.message.answer("Доступ запрещён.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)
        return
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('SELECT username, chips FROM users WHERE user_id != ? ORDER BY chips DESC', 
                                (SYSTEM_ACCOUNT_ID,)) as cursor:
                rows = await cursor.fetchall()
                response = "Фишки пользователей:\n"
                for row in rows:
                    response += f"@{row[0]}: {row[1]:.2f}\n"
                bot_message = await callback.message.answer(response or "Список пуст", reply_markup=get_back_button())
                await delete_previous_messages(callback.message, bot_message)
    except Exception as e:
        logger.error(f"Ошибка при просмотре фишек: {e}")
        bot_message = await callback.message.answer("Ошибка при просмотре фишек. Попробуйте позже.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)

# Главная функция
async def main():
    bot = Bot(token=API_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await init_db()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())