import asyncio
import aiosqlite
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
import logging
from datetime import datetime, timedelta

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
API_TOKEN = 'API_TOKEN'
DB_NAME = 'Bot_Name'
ADMIN_IDS = ["ADMIN_ID"]
SYSTEM_ACCOUNT_ID = -1
INSUFFICIENT_FUNDS_MESSAGE = "У вас недостаточно GB Coins."
INITIAL_BALANCE = 200.0

# Storage for last bot message ID and user state
last_bot_message = {}
user_state = {}  # Stack for storing previous menus

# Router for message handling
router = Router()

# Database initialization
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

# Database helper functions
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
        logger.error(f"Error getting user data for {user_id}: {e}")
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
        logger.error(f"Error finding user_id by username {username}: {e}")
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
        logger.error(f"Error updating user data for {user_id}: {e}")

async def notify_admins(bot, message):
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, message)
        except Exception as e:
            logger.error(f"Error sending notification to admin {admin_id}: {e}")

# Delete previous messages
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
        logger.error(f"Error deleting messages for {user_id}: {e}")

# BUTTONS
main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Check Balance", callback_data='balance')],
    [InlineKeyboardButton(text="Transfer GBc", callback_data='transfer')],
    [InlineKeyboardButton(text="Exchange GBc to Chips", callback_data='exchange_gb')],
    [InlineKeyboardButton(text="Top Players", callback_data='top')],
    [InlineKeyboardButton(text="Marketplace", callback_data='marketplace')],
    [InlineKeyboardButton(text="Admin Panel", callback_data='admin')],
    [InlineKeyboardButton(text="Rating System", callback_data='rating_menu')],
])

rating_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Rate User", callback_data='rate_user')],
    [InlineKeyboardButton(text="Rating Top", callback_data='rating_top')],
    [InlineKeyboardButton(text="Back", callback_data='back')]
])

exchange_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="10 kopecks (1 GBc)", callback_data='exchange_1')],
    [InlineKeyboardButton(text="50 kopecks (5 GBc)", callback_data='exchange_5')],
    [InlineKeyboardButton(text="1 ruble (10 GBc)", callback_data='exchange_10')],
    [InlineKeyboardButton(text="2 rubles (20 GBc)", callback_data='exchange_20')],
    [InlineKeyboardButton(text="5 rubles (50 GBc)", callback_data='exchange_50')],
    [InlineKeyboardButton(text="10 rubles (100 GBc)", callback_data='exchange_100')],
    [InlineKeyboardButton(text="Back", callback_data='back')]
])

marketplace_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="List Service", callback_data='list_service')],
    [InlineKeyboardButton(text="Browse Services", callback_data='browse')],
    [InlineKeyboardButton(text="Back", callback_data='back')]
])

admin_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Adjust Balance", callback_data='adjust_balance')],
    [InlineKeyboardButton(text="Adjust Chips", callback_data='adjust_chips')],
    [InlineKeyboardButton(text="Transfer from System Account", callback_data='transfer_system')],
    [InlineKeyboardButton(text="View System Account", callback_data='view_system')],
    [InlineKeyboardButton(text="Remove Service", callback_data='remove_listing')],
    [InlineKeyboardButton(text="Exchange Chips to GBc", callback_data='exchange_chips_to_gb')],
    [InlineKeyboardButton(text="View User Chips", callback_data='view_chips')],
    [InlineKeyboardButton(text="Back", callback_data='back')]
])

def get_back_button():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Back", callback_data='back')]])

# Handlers
@router.message(Command('start'))
async def start(message: Message):
    username = message.from_user.username or message.from_user.first_name
    await get_user_data(message.from_user.id, username)
    user_state[message.from_user.id] = ['main']
    bot_message = await message.answer("Welcome to GB Wallet!", reply_markup=main_menu)
    await delete_previous_messages(message, bot_message)

@router.callback_query(lambda c: c.data == 'rating_menu')
async def show_rating_menu(callback: CallbackQuery):
    user_state[callback.from_user.id].append('rating_menu')
    bot_message = await callback.message.answer("Rating System:", reply_markup=rating_menu)
    await delete_previous_messages(callback.message, bot_message)

@router.callback_query(lambda c: c.data == 'rate_user')
async def rate_user(callback: CallbackQuery):
    user_state[callback.from_user.id].append('rate_user_input')
    bot_message = await callback.message.answer("Enter username (with @ or without) and rating (+1 or -1) separated by space (e.g., @username +1)", reply_markup=get_back_button())
    await delete_previous_messages(callback.message, bot_message)

@router.message(lambda message: user_state.get(message.from_user.id, ['main'])[-1] == 'rate_user_input')
async def process_rate_user(message: Message):
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            bot_message = await message.answer("Invalid format. Use: username rating (e.g., @username +1)", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        username, rating_str = parts
        rating = int(rating_str)
        if rating not in [-1, 1]:
            bot_message = await message.answer("Rating must be +1 or -1.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        rater_id = message.from_user.id
        rated_id = await get_user_id_by_username(username)
        if not rated_id:
            bot_message = await message.answer(f"User {username} not found.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        if rater_id == rated_id:
            bot_message = await message.answer("You cannot rate yourself.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        async with aiosqlite.connect(DB_NAME) as db:
            cutoff = datetime.now() - timedelta(days=1)
            async with db.execute('SELECT COUNT(*) FROM ratings WHERE rater_id = ? AND rated_id = ? AND timestamp > ?', 
                                (rater_id, rated_id, cutoff)) as cursor:
                count = (await cursor.fetchone())[0]
                if count > 0:
                    bot_message = await message.answer("You have already rated this user today.", reply_markup=get_back_button())
                    await delete_previous_messages(message, bot_message)
                    return
            await db.execute('INSERT INTO ratings (rater_id, rated_id, rating) VALUES (?, ?, ?)', 
                           (rater_id, rated_id, rating))
            await db.commit()
        bot_message = await message.answer(f"Rating {rating} for @{username} successfully submitted.", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except ValueError:
        bot_message = await message.answer("Error: invalid rating format. Specify +1 or -1.", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except Exception as e:
        logger.error(f"Error submitting rating: {e}")
        bot_message = await message.answer(f"Error: {e}", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)

@router.callback_query(lambda c: c.data == 'rating_top')
async def rating_top(callback: CallbackQuery):
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            # Award points for the day
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
            # Calculate total rating
            async with db.execute('SELECT user_id, SUM(points) as total FROM daily_ratings GROUP BY user_id ORDER BY total DESC LIMIT 10') as cursor:
                rows = await cursor.fetchall()
                top_list = []
                for row in rows:
                    _, _, username = await get_user_data(row[0])
                    top_list.append(f"@{username}: {row[1]:.2f} points")
                response = "Rating Top:\n" + "\n".join(top_list) if top_list else "List is empty"
                bot_message = await callback.message.answer(response, reply_markup=get_back_button())
                await delete_previous_messages(callback.message, bot_message)
    except Exception as e:
        logger.error(f"Error getting rating top: {e}")
        bot_message = await callback.message.answer("Error getting rating top. Try again later.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)

@router.callback_query(lambda c: c.data == 'back')
async def go_back(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in user_state or len(user_state[user_id]) <= 1:
        user_state[user_id] = ['main']
        bot_message = await callback.message.answer("Choose an action:", reply_markup=main_menu)
        await delete_previous_messages(callback.message, bot_message)
        return
    user_state[user_id].pop()  # Remove last state
    previous_state = user_state[user_id][-1]
    if previous_state == 'main':
        bot_message = await callback.message.answer("Choose an action:", reply_markup=main_menu)
    elif previous_state == 'marketplace':
        bot_message = await callback.message.answer("Marketplace:", reply_markup=marketplace_menu)
    elif previous_state == 'admin':
        bot_message = await callback.message.answer("Admin Panel:", reply_markup=admin_menu)
    elif previous_state == 'rating_menu':
        bot_message = await callback.message.answer("Rating System:", reply_markup=rating_menu)
    else:
        bot_message = await callback.message.answer("Choose an action:", reply_markup=main_menu)
        user_state[user_id] = ['main']
    await delete_previous_messages(callback.message, bot_message)

@router.callback_query(lambda c: c.data == 'balance')
async def check_balance(callback: CallbackQuery):
    try:
        balance, chips, username = await get_user_data(callback.from_user.id, callback.from_user.username or callback.from_user.first_name)
        bot_message = await callback.message.answer(f"Your balance (@{username}):\nGB Coins: {balance:.2f}\nChips: {chips:.2f}", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)
    except Exception as e:
        logger.error(f"Error checking balance for {callback.from_user.id}: {e}")
        bot_message = await callback.message.answer("Error checking balance. Try again later.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)

@router.callback_query(lambda c: c.data == 'transfer')
async def transfer(callback: CallbackQuery):
    user_state[callback.from_user.id].append('transfer_input')
    bot_message = await callback.message.answer("Enter recipient's username (with @ or without) and GB Coins amount separated by space (e.g., @username 10)", reply_markup=get_back_button())
    await delete_previous_messages(callback.message, bot_message)

@router.message(lambda message: user_state.get(message.from_user.id, ['main'])[-1] == 'transfer_input')
async def process_transfer(message: Message):
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            bot_message = await message.answer("Invalid format. Use: username amount (e.g., @username 10)", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        recipient_username, amount = parts
        amount = float(amount)
        if amount <= 0:
            bot_message = await message.answer("Amount must be greater than 0.", reply_markup=get_back_button())
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
            bot_message = await message.answer(f"User {recipient_username} not found.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        if recipient_id == sender_id:
            bot_message = await message.answer("You cannot transfer to yourself.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (amount, sender_id))
            await db.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, recipient_id))
            await db.execute('INSERT INTO transactions (sender_id, recipient_id, amount, type) VALUES (?, ?, ?, ?)', 
                           (sender_id, recipient_id, amount, 'GB'))
            await db.commit()
        bot_message = await message.answer("Transfer completed successfully.", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except ValueError:
        bot_message = await message.answer("Error: invalid amount format. Specify a number (e.g., @username 10).", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except Exception as e:
        logger.error(f"Error transferring from {message.from_user.id} to {recipient_username}: {e}")
        bot_message = await message.answer(f"Error: {e}", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)

@router.callback_query(lambda c: c.data == 'exchange_gb')
async def exchange_gb(callback: CallbackQuery):
    user_state[callback.from_user.id].append('exchange_menu')
    bot_message = await callback.message.answer("Select amount to exchange GBc to chips:", reply_markup=exchange_menu)
    await delete_previous_messages(callback.message, bot_message)

@router.callback_query(lambda c: c.data.startswith('exchange_'))
async def process_exchange(callback: CallbackQuery, bot: Bot):
    try:
        gb = float(callback.data.split('_')[1])
        chips = gb / 10  # 1 GBc = 0.1 ruble
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
        bot_message = await callback.message.answer(f"Exchanged {gb:.2f} GBc for {chips:.2f} chips (1 GBc = 0.1 ruble).", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)
        await notify_admins(bot, f"User @{username} exchanged {gb:.2f} GBc for {chips:.2f} chips.")
    except Exception as e:
        logger.error(f"Error exchanging GBc for {callback.from_user.id}: {e}")
        bot_message = await callback.message.answer(f"Error: {e}", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)

@router.callback_query(lambda c: c.data == 'top')
async def top_players(callback: CallbackQuery):
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('SELECT user_id, balance, username FROM users WHERE user_id != ? ORDER BY balance DESC LIMIT 10', 
                                (SYSTEM_ACCOUNT_ID,)) as cursor:
                rows = await cursor.fetchall()
                top_list = "\n".join([f"@{row[2] or f'User_{row[0]}'}: {row[1]:.2f} GB Coins" for row in rows])
                bot_message = await callback.message.answer(f"Top Players:\n{top_list or 'List is empty'}", reply_markup=get_back_button())
                await delete_previous_messages(callback.message, bot_message)
    except Exception as e:
        logger.error(f"Error getting top players: {e}")
        bot_message = await callback.message.answer("Error getting top players. Try again later.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)

@router.callback_query(lambda c: c.data == 'marketplace')
async def marketplace(callback: CallbackQuery):
    user_state[callback.from_user.id].append('marketplace')
    bot_message = await callback.message.answer("Marketplace:", reply_markup=marketplace_menu)
    await delete_previous_messages(callback.message, bot_message)

@router.callback_query(lambda c: c.data == 'list_service')
async def list_service(callback: CallbackQuery):
    user_state[callback.from_user.id].append('list_service_input')
    bot_message = await callback.message.answer("Enter service description and price separated by '|' (e.g., Code help|50)", reply_markup=get_back_button())
    await delete_previous_messages(callback.message, bot_message)

@router.message(lambda message: user_state.get(message.from_user.id, ['main'])[-1] == 'list_service_input')
async def process_list_service(message: Message):
    try:
        parts = message.text.split('|', 1)
        if len(parts) != 2:
            bot_message = await message.answer("Invalid format. Use: description|price", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        description, price = parts
        price = float(price.strip())
        if price <= 0:
            bot_message = await message.answer("Price must be greater than 0.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        seller_id = message.from_user.id
        await get_user_data(seller_id, message.from_user.username or message.from_user.first_name)
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute('INSERT INTO marketplace (seller_id, description, price) VALUES (?, ?, ?)', 
                           (seller_id, description.strip(), price))
            await db.commit()
        bot_message = await message.answer("Service listed on marketplace.", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except ValueError:
        bot_message = await message.answer("Error: invalid price. Specify a number.", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except Exception as e:
        logger.error(f"Error adding service for {message.from_user.id}: {e}")
        bot_message = await message.answer(f"Error: {e}", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)

@router.callback_query(lambda c: c.data == 'browse')
async def browse_services(callback: CallbackQuery):
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('SELECT id, seller_id, description, price FROM marketplace WHERE status = "active"') as cursor:
                rows = await cursor.fetchall()
                if not rows:
                    bot_message = await callback.message.answer("No active services.", reply_markup=get_back_button())
                    await delete_previous_messages(callback.message, bot_message)
                    return
                response = "Available services:\n"
                for row in rows:
                    _, _, seller_username = await get_user_data(row[1])
                    response += f"ID: {row[0]} | {row[2]} | Price: {row[3]:.2f} GBc | Seller: @{seller_username}\n"
                response += "\nTo purchase, click the button below and enter service ID."
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Buy Service", callback_data='buy')],
                    [InlineKeyboardButton(text="Back", callback_data='back')]
                ])
                bot_message = await callback.message.answer(response, reply_markup=keyboard)
                await delete_previous_messages(callback.message, bot_message)
    except Exception as e:
        logger.error(f"Error browsing services: {e}")
        bot_message = await callback.message.answer("Error browsing services. Try again later.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)

@router.callback_query(lambda c: c.data == 'buy')
async def buy_service_start(callback: CallbackQuery):
    user_state[callback.from_user.id].append('buy_input')
    bot_message = await callback.message.answer("Enter service ID to purchase (e.g., 1)", reply_markup=get_back_button())
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
                    bot_message = await message.answer("Service not found or already sold.", reply_markup=get_back_button())
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
            bot_message = await message.answer("Service purchased successfully.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            try:
                await bot.send_message(seller_id, f"Your service '{description}' was bought by @{buyer_username} for {price:.2f} GB Coins.")
            except Exception as e:
                logger.error(f"Error sending notification to seller {seller_id}: {e}")
    except ValueError:
        bot_message = await message.answer("Error: invalid ID format. Specify a number (e.g., 1).", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except Exception as e:
        logger.error(f"Error purchasing service for {message.from_user.id}: {e}")
        bot_message = await message.answer(f"Error: {e}", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)

@router.callback_query(lambda c: c.data == 'admin')
async def admin_panel(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        bot_message = await callback.message.answer("Access denied.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)
        return
    user_state[callback.from_user.id].append('admin')
    bot_message = await callback.message.answer("Admin Panel:", reply_markup=admin_menu)
    await delete_previous_messages(callback.message, bot_message)

@router.callback_query(lambda c: c.data == 'adjust_balance')
async def adjust_balance(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        bot_message = await callback.message.answer("Access denied.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)
        return
    user_state[callback.from_user.id].append('adjust_balance_input')
    bot_message = await callback.message.answer("Enter username (with @ or without) and new GB Coins balance separated by space (e.g., @username 100)", reply_markup=get_back_button())
    await delete_previous_messages(callback.message, bot_message)

@router.message(lambda message: user_state.get(message.from_user.id, ['main'])[-1] == 'adjust_balance_input')
async def process_adjust_balance(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            bot_message = await message.answer("Invalid format. Use: username amount (e.g., @username 100)", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        username, value = parts
        value = float(value)
        if value < 0:
            bot_message = await message.answer("Value cannot be negative.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        user_id = await get_user_id_by_username(username)
        if not user_id:
            bot_message = await message.answer(f"User {username} not found.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        await update_user_data(user_id, balance=value)
        bot_message = await message.answer(f"GB Coins balance for @{username} successfully changed.", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except ValueError:
        bot_message = await message.answer("Error: invalid amount format. Specify a number (e.g., @username 100).", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except Exception as e:
        logger.error(f"Error processing admin command for {message.from_user.id}: {e}")
        bot_message = await message.answer(f"Error: {e}", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)

@router.callback_query(lambda c: c.data == 'adjust_chips')
async def adjust_chips(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        bot_message = await callback.message.answer("Access denied.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)
        return
    user_state[callback.from_user.id].append('adjust_chips_input')
    bot_message = await callback.message.answer("Enter username (with @ or without) and new chips amount separated by space (e.g., @username 100)", reply_markup=get_back_button())
    await delete_previous_messages(callback.message, bot_message)

@router.message(lambda message: user_state.get(message.from_user.id, ['main'])[-1] == 'adjust_chips_input')
async def process_adjust_chips(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            bot_message = await message.answer("Invalid format. Use: username amount (e.g., @username 100)", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        username, value = parts
        value = float(value)
        if value < 0:
            bot_message = await message.answer("Value cannot be negative.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        user_id = await get_user_id_by_username(username)
        if not user_id:
            bot_message = await message.answer(f"User {username} not found.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        await update_user_data(user_id, chips=value)
        bot_message = await message.answer(f"Chips for @{username} successfully changed.", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except ValueError:
        bot_message = await message.answer("Error: invalid amount format. Specify a number (e.g., @username 100).", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except Exception as e:
        logger.error(f"Error processing admin command for {message.from_user.id}: {e}")
        bot_message = await message.answer(f"Error: {e}", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)

@router.callback_query(lambda c: c.data == 'transfer_system')
async def transfer_system(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        bot_message = await callback.message.answer("Access denied.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)
        return
    user_state[callback.from_user.id].append('transfer_system_input')
    bot_message = await callback.message.answer("Enter recipient's username (with @ or without) and GB Coins amount separated by space (e.g., @username 100)", reply_markup=get_back_button())
    await delete_previous_messages(callback.message, bot_message)

@router.message(lambda message: user_state.get(message.from_user.id, ['main'])[-1] == 'transfer_system_input')
async def process_transfer_system(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            bot_message = await message.answer("Invalid format. Use: username amount (e.g., @username 100)", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        username, value = parts
        value = float(value)
        if value < 0:
            bot_message = await message.answer("Value cannot be negative.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        user_id = await get_user_id_by_username(username)
        if not user_id:
            bot_message = await message.answer(f"User {username} not found.", reply_markup=get_back_button())
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
        bot_message = await message.answer(f"Transfer of {value:.2f} GBc from system account to @{username} completed successfully.", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except ValueError:
        bot_message = await message.answer("Error: invalid amount format. Specify a number (e.g., @username 100).", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except Exception as e:
        logger.error(f"Error processing admin command for {message.from_user.id}: {e}")
        bot_message = await message.answer(f"Error: {e}", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)

@router.callback_query(lambda c: c.data == 'view_system')
async def view_system(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        bot_message = await callback.message.answer("Access denied.", reply_markup=get_back_button())
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
                bot_message = await callback.message.answer(f"System Account:\nBalance: {balance:.2f} GB Coins\n\nTransaction History:\n{history_text or 'Empty'}", reply_markup=get_back_button())
                await delete_previous_messages(callback.message, bot_message)
    except Exception as e:
        logger.error(f"Error viewing system account: {e}")
        bot_message = await callback.message.answer("Error viewing system account. Try again later.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)

@router.callback_query(lambda c: c.data == 'remove_listing')
async def remove_listing(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        bot_message = await callback.message.answer("Access denied.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)
        return
    user_state[callback.from_user.id].append('remove_listing_input')
    bot_message = await callback.message.answer("Enter service ID to remove (e.g., 1)", reply_markup=get_back_button())
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
                    bot_message = await message.answer("Service not found.", reply_markup=get_back_button())
                    await delete_previous_messages(message, bot_message)
                    return
            await db.execute('DELETE FROM marketplace WHERE id = ?', (listing_id,))
            await db.commit()
        bot_message = await message.answer("Service removed.", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except ValueError:
        bot_message = await message.answer("Error: invalid ID format. Specify a number (e.g., 1).", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except Exception as e:
        logger.error(f"Error removing service for {message.from_user.id}: {e}")
        bot_message = await message.answer(f"Error: {e}", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)

@router.callback_query(lambda c: c.data == 'exchange_chips_to_gb')
async def exchange_chips_to_gb(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        bot_message = await callback.message.answer("Access denied.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)
        return
    user_state[callback.from_user.id].append('exchange_chips_input')
    bot_message = await callback.message.answer("Enter username (with @ or without) and amount in rubles to exchange chips to GBc (e.g., @username 11.4). 1 ruble = 10 GBc.", reply_markup=get_back_button())
    await delete_previous_messages(callback.message, bot_message)

@router.message(lambda message: user_state.get(message.from_user.id, ['main'])[-1] == 'exchange_chips_input')
async def process_exchange_chips_to_gb(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            bot_message = await message.answer("Invalid format. Use: username amount (e.g., @username 11.4)", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        username, amount_str = parts
        amount_rub = float(amount_str)
        if amount_rub < 0:
            bot_message = await message.answer("Amount cannot be negative.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        user_id = await get_user_id_by_username(username)
        if not user_id:
            bot_message = await message.answer(f"User {username} not found.", reply_markup=get_back_button())
            await delete_previous_messages(message, bot_message)
            return
        gb = amount_rub * 10  # 1 ruble = 10 GBc
        chips = amount_rub
        _, user_chips, _ = await get_user_data(user_id)
        if user_chips < chips:
            bot_message = await message.answer("User doesn't have enough chips.", reply_markup=get_back_button())
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
        bot_message = await message.answer(f"Exchanged {chips:.2f} chips from user @{username} for {gb:.2f} GBc.", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except ValueError:
        bot_message = await message.answer("Error: invalid amount format. Specify a number (e.g., @username 11.4).", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)
    except Exception as e:
        logger.error(f"Error exchanging chips for {message.from_user.id}: {e}")
        bot_message = await message.answer(f"Error: {e}", reply_markup=get_back_button())
        await delete_previous_messages(message, bot_message)

@router.callback_query(lambda c: c.data == 'view_chips')
async def view_chips(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        bot_message = await callback.message.answer("Access denied.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)
        return
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('SELECT username, chips FROM users WHERE user_id != ? ORDER BY chips DESC', 
                                (SYSTEM_ACCOUNT_ID,)) as cursor:
                rows = await cursor.fetchall()
                response = "User Chips:\n"
                for row in rows:
                    response += f"@{row[0]}: {row[1]:.2f}\n"
                bot_message = await callback.message.answer(response or "List is empty", reply_markup=get_back_button())
                await delete_previous_messages(callback.message, bot_message)
    except Exception as e:
        logger.error(f"Error viewing chips: {e}")
        bot_message = await callback.message.answer("Error viewing chips. Try again later.", reply_markup=get_back_button())
        await delete_previous_messages(callback.message, bot_message)

# Main function
async def main():
    bot = Bot(token=API_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await init_db()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
