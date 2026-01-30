import sqlite3
import os
import aiohttp
import threading
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# --- RENDER/KOYEB PORT JUGAD ---
app = Flask(__name__)
@app.route('/')
def health_check():
    return "Bot is Running!"

def run_flask():
    # Render uses 'PORT' environment variable automatically
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- CONFIG ---
TOKEN = "7891440763:AAEcQNKFr7DIzAufHeKDZ1H9UJbQ4FsAl2A"
ADMIN_ID = 5766303284 
REFER_BONUS = 3  
JOINING_BONUS = 3 
MIN_WITHDRAW = 10

CHANNELS = [-1001963038072, "@Sheinvoucher4000"] 
CHANNEL_LINKS = [
    ("📢 Private Channel", "https://t.me/+FsXUwNLm67sxYmE1"),
    ("📢 Public Channel", "https://t.me/Sheinvoucher4000")
]

bot = Bot(token=TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- DATABASE SETUP ---
db = sqlite3.connect("cashadda.db")
sql = db.cursor()
sql.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY, 
    balance REAL DEFAULT 0, 
    referred_by INTEGER,
    ref_count INTEGER DEFAULT 0,
    is_bonus_claimed INTEGER DEFAULT 0
)""")
db.commit()

async def is_subscribed(user_id):
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]: return False
        except: return False
    return True

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = message.from_user.id
    args = message.get_args()
    
    sql.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = sql.fetchone()
    
    if not user:
        referrer = int(args) if args.isdigit() else None
        sql.execute("INSERT INTO users (user_id, referred_by, balance, ref_count, is_bonus_claimed) VALUES (?, ?, ?, ?, ?)", (user_id, referrer, 0, 0, 0))
        db.commit()

    if not await is_subscribed(user_id):
        markup = InlineKeyboardMarkup(row_width=1)
        for name, link in CHANNEL_LINKS:
            markup.add(InlineKeyboardButton(name, url=link))
        markup.add(InlineKeyboardButton("✅ Joined - Verify", callback_data="verify"))
        return await message.answer("❌ <b>Access Denied!</b>\n\nJoin BOTH channels:", reply_markup=markup)

    sql.execute("SELECT is_bonus_claimed, referred_by FROM users WHERE user_id = ?", (user_id,))
    res = sql.fetchone()
    if res and res[0] == 0: 
        sql.execute("UPDATE users SET balance = balance + ?, is_bonus_claimed = 1 WHERE user_id = ?", (JOINING_BONUS, user_id))
        if res[1]:
            sql.execute("UPDATE users SET balance = balance + ?, ref_count = ref_count + 1 WHERE user_id = ?", (REFER_BONUS, res[1]))
            try: await bot.send_message(res[1], "💰 <b>Referral Success!</b> +3 Rs")
            except: pass
        db.commit()
        await message.answer(f"🎉 Bonus Added!")

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("💰 Balance", callback_data="balance"),
        InlineKeyboardButton("👥 Refer", callback_data="refer"),
        InlineKeyboardButton("📤 Withdraw", callback_data="withdraw"),
        InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard")
    )
    await message.answer(f"👋 Welcome!", reply_markup=markup)

@dp.callback_query_handler(lambda c: True)
async def all_callbacks(c: types.CallbackQuery):
    user_id = c.from_user.id
    if c.data == "verify":
        if await is_subscribed(user_id):
            await c.message.delete()
            await start(c.message)
    elif c.data == "balance":
        sql.execute("SELECT balance, ref_count FROM users WHERE user_id = ?", (user_id,))
        res = sql.fetchone()
        await bot.send_message(user_id, f"💳 Balance: {res[0]} Rs")
    elif c.data == "refer":
        me = await bot.get_me()
        await bot.send_message(user_id, f"🔗 Link: https://t.me/{me.username}?start={user_id}")

if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    executor.start_polling(dp, skip_updates=True)
