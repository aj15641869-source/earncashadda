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
# APNA GITHUB PAGES LINK YAHAN DALO
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
    waiting_for_broadcast = State()
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
    ip_address TEXT,
    is_blocked INTEGER DEFAULT 0,
    last_daily_bonus INTEGER DEFAULT 0
)""")
db.commit()

# --- SECURITY: VPN & IP CHECK ---
async def get_user_ip():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://ip-api.com/json/?fields=status,proxy,hosting,query") as resp:
                data = await resp.json()
                return data
    except: return None

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
    
    # 1. Block Check
    sql.execute("SELECT is_blocked FROM users WHERE user_id = ?", (user_id,))
    res_b = sql.fetchone()
    if res_b and res_b[0] == 1:
        return await message.answer("🚫 <b>You are blocked!</b>")

    # 2. IP & VPN Security Check
    ip_info = await get_user_ip()
    current_ip = ip_info['query'] if ip_info else "Unknown"
    if ip_info and (ip_info.get('proxy') or ip_info.get('hosting')):
        return await message.answer("❌ <b>VPN Detected!</b> Turn it off.")

    # 3. High-Level Security Verification Button
    # Check if user already exists to skip verification if needed
    sql.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = sql.fetchone()
    
    if not user:
        # User ko pehle verification dikhao (Animation)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(
            text="🛡️ Verify Yourself to Start Bot", 
            web_app=types.WebAppInfo(url=SECURITY_WEBAPP_URL)
        ))
        
        # Database entry with IP
        args = message.get_args()
        referrer = int(args) if args.isdigit() else None
        sql.execute("INSERT INTO users (user_id, referred_by, balance, ip_address) VALUES (?, ?, ?, ?)", (user_id, referrer, 0, current_ip))
        db.commit()

        return await message.answer(
            "🔒 <b>Verify Yourself To Start Bot</b>\n\n"
            "Click below to establish a secure handshake and scan your device for multi-accounts.",
            reply_markup=markup
        )

    # 4. Membership Check
    if not await is_subscribed(user_id):
        markup = InlineKeyboardMarkup(row_width=1)
        for name, link in CHANNEL_LINKS:
            markup.add(InlineKeyboardButton(name, url=link))
        markup.add(InlineKeyboardButton("✅ Joined - Verify", callback_data="verify"))
        return await message.answer("👋 Join both channels to get 3 Rs bonus:", reply_markup=markup)

    # 5. Bonus Logic
    sql.execute("SELECT is_bonus_claimed, referred_by FROM users WHERE user_id = ?", (user_id,))
    res = sql.fetchone()
    if res and res[0] == 0: 
        sql.execute("UPDATE users SET balance = balance + ?, is_bonus_claimed = 1 WHERE user_id = ?", (JOINING_BONUS, user_id))
        if res[1]:
            sql.execute("UPDATE users SET balance = balance + ?, ref_count = ref_count + 1 WHERE user_id = ?", (REFER_BONUS, res[1]))
            try: await bot.send_message(res[1], f"💰 <b>Referral Success!</b> +{REFER_BONUS} Rs")
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
    await message.answer(f"👋 <b>Welcome to CashAdda!</b>", reply_markup=markup)

# --- ADD ALL PREVIOUS CALLBACKS (Balance, Refer, Stats, Daily Bonus, Admin) YAHAN ---
# (Upar wale code ki tarah hi baaki logic add kar dena)

if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    executor.start_polling(dp, skip_updates=True)
