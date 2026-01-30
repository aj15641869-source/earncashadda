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
# Sahi GitHub Pages Link
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

# --- STATES ---
class WithdrawState(StatesGroup):
    waiting_for_upi = State()

class AdminState(StatesGroup):
    waiting_for_search = State()
    waiting_for_new_balance = State()

# --- DATABASE SETUP ---
db = sqlite3.connect("cashadda.db")
sql = db.cursor()
sql.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY, 
    balance REAL DEFAULT 0, 
    referred_by INTEGER,
    ref_count INTEGER DEFAULT 0,
    is_bonus_claimed INTEGER DEFAULT 0,
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

# --- MAIN START COMMAND ---
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
        # Save user and show High-Level Verification
        args = message.get_args()
        referrer = int(args) if args.isdigit() else None
        sql.execute("INSERT INTO users (user_id, referred_by, balance) VALUES (?, ?, ?)", (user_id, referrer, 0))
        db.commit()

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(
            text="🛡️ Verify Device & Start", 
            web_app=types.WebAppInfo(url=SECURITY_WEBAPP_URL)
        ))
        
        return await message.answer(
            "🔒 <b>Security Verification Required</b>\n\n"
            "Welcome! To prevent fake accounts, please complete the device scan below.",
            reply_markup=markup
        )

    # Membership Check
    if not await is_subscribed(user_id):
        markup = InlineKeyboardMarkup(row_width=1)
        for name, link in CHANNEL_LINKS:
            markup.add(InlineKeyboardButton(name, url=link))
        markup.add(InlineKeyboardButton("✅ Joined - Verify", callback_data="verify"))
        return await message.answer("👋 <b>Wait!</b> Join our channels to unlock your 3 Rs bonus:", reply_markup=markup)

    # Claim Bonus
    sql.execute("SELECT is_bonus_claimed, referred_by FROM users WHERE user_id = ?", (user_id,))
    res = sql.fetchone()
    if res and res[0] == 0: 
        sql.execute("UPDATE users SET balance = balance + ?, is_bonus_claimed = 1 WHERE user_id = ?", (JOINING_BONUS, user_id))
        if res[1]:
            sql.execute("UPDATE users SET balance = balance + ?, ref_count = ref_count + 1 WHERE user_id = ?", (REFER_BONUS, res[1]))
            try: await bot.send_message(res[1], f"💰 <b>Referral Success!</b> You earned {REFER_BONUS} Rs.")
            except: pass
        db.commit()
        await message.answer(f"🎉 <b>{JOINING_BONUS} Rs Bonus Added!</b>")

    # Main Menu
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("💰 Balance", callback_data="balance"),
        InlineKeyboardButton("👥 Refer", callback_data="refer"),
        InlineKeyboardButton("🎁 Daily Bonus", callback_data="daily_bonus"),
        InlineKeyboardButton("📤 Withdraw", callback_data="withdraw"),
        InlineKeyboardButton("📊 Stats", callback_data="stats")
    )
    await message.answer(f"👋 <b>Welcome back, {message.from_user.first_name}!</b>\nManage your earnings below:", reply_markup=markup)

# --- CALLBACKS ---
@dp.callback_query_handler(lambda c: True, state="*")
async def process_callbacks(c: types.CallbackQuery, state: FSMContext):
    user_id = c.from_user.id
    
    if c.data == "balance":
        sql.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        await bot.send_message(user_id, f"💳 <b>Your Balance:</b> {sql.fetchone()[0]} Rs")
    
    elif c.data == "refer":
        me = await bot.get_me()
        await bot.send_message(user_id, f"👥 <b>Earn {REFER_BONUS} Rs Per Refer</b>\n\n🔗 Your Link: https://t.me/{me.username}?start={user_id}")
    
    elif c.data == "daily_bonus":
        sql.execute("SELECT last_daily_bonus FROM users WHERE user_id = ?", (user_id,))
        last_time = sql.fetchone()[0]
        if int(time.time()) - last_time < 86400:
            return await bot.answer_callback_query(c.id, "❌ Come back tomorrow!", show_alert=True)
        sql.execute("UPDATE users SET balance = balance + ?, last_daily_bonus = ? WHERE user_id = ?", (DAILY_BONUS_AMT, int(time.time()), user_id))
        db.commit()
        await bot.answer_callback_query(c.id, f"🎁 {DAILY_BONUS_AMT} Rs Added!", show_alert=True)

    elif c.data == "stats":
        sql.execute("SELECT COUNT(*), SUM(balance) FROM users")
        res = sql.fetchone()
        await bot.send_message(user_id, f"📊 <b>Bot Stats</b>\nTotal Users: {res[0]}\nTotal Distributed: {res[1] if res[1] else 0} Rs")

    elif c.data == "verify":
        await start(c.message)

    elif c.data == "withdraw":
        sql.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        if sql.fetchone()[0] < MIN_WITHDRAW:
            return await bot.answer_callback_query(c.id, f"❌ Min {MIN_WITHDRAW} Rs needed!", show_alert=True)
        await WithdrawState.waiting_for_upi.set()
        await bot.send_message(user_id, "📩 <b>Enter UPI ID:</b>")

# --- WITHDRAW HANDLER ---
@dp.message_handler(state=WithdrawState.waiting_for_upi)
async def process_withdraw(message: types.Message, state: FSMContext):
    if "@" not in message.text: return await message.answer("❌ Invalid UPI!")
    sql.execute("SELECT balance FROM users WHERE user_id = ?", (message.from_user.id,))
    amt = sql.fetchone()[0]
    await bot.send_message(ADMIN_ID, f"💰 <b>Withdrawal!</b>\nID: {message.from_user.id}\nAmt: {amt} Rs\nUPI: {message.text}")
    sql.execute("UPDATE users SET balance = 0 WHERE user_id = ?", (message.from_user.id,))
    db.commit()
    await message.answer("✅ Request Sent!"); await state.finish()

if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    executor.start_polling(dp, skip_updates=True)
