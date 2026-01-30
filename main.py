import sqlite3
import os
import aiohttp
import threading
import time
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# --- RENDER PORT JUGAD ---
app = Flask(__name__)
@app.route('/')
def health_check(): return "Bot is Running!"
def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- CONFIG ---
TOKEN = "7891440763:AAEcQNKFr7DIzAufHeKDZ1H9UJbQ4FsAl2A"
ADMIN_ID = 5766303284 
SECURITY_WEBAPP_URL = "https://aj15641869-source.github.io/earncashadda/" 

REFER_BONUS = 3  
JOINING_BONUS = 3 
DAILY_BONUS_AMT = 1
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
    is_bonus_claimed INTEGER DEFAULT 0,
    ip_address TEXT,
    is_blocked INTEGER DEFAULT 0,
    last_daily_bonus INTEGER DEFAULT 0
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
    
    # Block Check
    sql.execute("SELECT is_blocked FROM users WHERE user_id = ?", (user_id,))
    res_b = sql.fetchone()
    if res_b and res_b[0] == 1:
        return await message.answer("🚫 <b>You are blocked!</b>")

    sql.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = sql.fetchone()
    
    if not user:
        # Save user first
        args = message.get_args()
        referrer = int(args) if args.isdigit() else None
        sql.execute("INSERT INTO users (user_id, referred_by, balance) VALUES (?, ?, ?)", (user_id, referrer, 0))
        db.commit()

        # Show Fingerprint Verification Only Once
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(text="🛡️ Verify Yourself", web_app=types.WebAppInfo(url=SECURITY_WEBAPP_URL)))
        return await message.answer("🔒 <b>Security Verification</b>\nClick below to verify your device.", reply_markup=markup)

    if not await is_subscribed(user_id):
        markup = InlineKeyboardMarkup(row_width=1)
        for name, link in CHANNEL_LINKS:
            markup.add(InlineKeyboardButton(name, url=link))
        markup.add(InlineKeyboardButton("✅ Joined - Verify", callback_data="verify"))
        return await message.answer("👋 Join both channels to get 3 Rs bonus:", reply_markup=markup)

    # Bonus Credit
    sql.execute("SELECT is_bonus_claimed, referred_by FROM users WHERE user_id = ?", (user_id,))
    res = sql.fetchone()
    if res and res[0] == 0: 
        sql.execute("UPDATE users SET balance = balance + ?, is_bonus_claimed = 1 WHERE user_id = ?", (JOINING_BONUS, user_id))
        if res[1]:
            sql.execute("UPDATE users SET balance = balance + ?, ref_count = ref_count + 1 WHERE user_id = ?", (REFER_BONUS, res[1]))
            try: await bot.send_message(res[1], f"💰 <b>Referral Success!</b> +{REFER_BONUS} Rs")
            except: pass
        db.commit()
        await message.answer(f"🎉 <b>Bonus Added!</b>")

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("💰 Balance", callback_data="balance"),
        InlineKeyboardButton("👥 Refer", callback_data="refer"),
        InlineKeyboardButton("🎁 Daily Bonus", callback_data="daily_bonus"),
        InlineKeyboardButton("📤 Withdraw", callback_data="withdraw"),
        InlineKeyboardButton("📊 Stats", callback_data="stats")
    )
    await message.answer(f"👋 <b>Main Menu</b>", reply_markup=markup)

# --- DAILY BONUS ---
@dp.callback_query_handler(lambda c: c.data == "daily_bonus")
async def daily_bonus(c: types.CallbackQuery):
    user_id = c.from_user.id
    sql.execute("SELECT last_daily_bonus FROM users WHERE user_id = ?", (user_id,))
    last_time = sql.fetchone()[0]
    if int(time.time()) - last_time < 86400:
        return await bot.answer_callback_query(c.id, "❌ Come back tomorrow!", show_alert=True)
    sql.execute("UPDATE users SET balance = balance + ?, last_daily_bonus = ? WHERE user_id = ?", (DAILY_BONUS_AMT, int(time.time()), user_id))
    db.commit()
    await bot.answer_callback_query(c.id, f"🎁 {DAILY_BONUS_AMT} Rs Added!", show_alert=True)

# --- STATS ---
@dp.callback_query_handler(lambda c: c.data == "stats")
async def stats_call(c: types.CallbackQuery):
    sql.execute("SELECT COUNT(*) FROM users")
    total = sql.fetchone()[0]
    await bot.send_message(c.from_user.id, f"📊 <b>Total Users:</b> {total}\n🚀 Bot is 100% Secure!")

# --- BALANCE & REFER ---
@dp.callback_query_handler(lambda c: c.data in ["balance", "refer", "verify"])
async def other_calls(c: types.CallbackQuery):
    if c.data == "balance":
        sql.execute("SELECT balance FROM users WHERE user_id = ?", (c.from_user.id,))
        await bot.send_message(c.from_user.id, f"💳 <b>Balance:</b> {sql.fetchone()[0]} Rs")
    elif c.data == "refer":
        me = await bot.get_me()
        await bot.send_message(c.from_user.id, f"🔗 <b>Link:</b> https://t.me/{me.username}?start={c.from_user.id}")
    elif c.data == "verify":
        await start(c.message)

if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    executor.start_polling(dp, skip_updates=True)
