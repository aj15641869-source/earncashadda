import sqlite3
import os
import aiohttp
import threading
from flask import Flask, render_template_string
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup

# --- RENDER WEB APP ---
app = Flask(__name__)

HTML_CONTENT = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body { background: #0a0e1a; color: white; font-family: sans-serif; text-align: center; display: flex; flex-direction: column; justify-content: center; height: 100vh; margin: 0; }
        .scanner { position: relative; width: 140px; height: 140px; margin: 0 auto 20px; border: 2px solid #1c7ed6; border-radius: 50%; padding: 20px; }
        .scan-line { position: absolute; width: 80%; height: 3px; background: #4dabf7; left: 10%; top: 20%; box-shadow: 0 0 15px #4dabf7; animation: scan 2s infinite; }
        @keyframes scan { 0%, 100% { top: 20%; } 50% { top: 80%; } }
        .bar { width: 80%; height: 8px; background: #1a1f2e; margin: 20px auto; border-radius: 5px; overflow: hidden; }
        .fill { width: 0%; height: 100%; background: #4dabf7; transition: width 0.2s; }
    </style>
</head>
<body>
    <div class="scanner"><img src="https://cdn-icons-png.flaticon.com/512/2566/2566210.png" style="width:100%; filter:invert(1); opacity:0.7;"><div class="scan-line"></div></div>
    <h3 style="color:#4dabf7;">VERIFYING...</h3>
    <div class="bar"><div class="fill" id="f"></div></div>
    <script>
        let tg = window.Telegram.WebApp; tg.expand();
        let p = 0;
        let it = setInterval(() => {
            p += 10; document.getElementById('f').style.width = p + "%";
            if(p >= 100) { clearInterval(it); tg.sendData("verified"); setTimeout(() => { tg.close(); }, 500); }
        }, 50);
    </script>
</body>
</html>
"""

@app.route('/')
def health(): return "Bot Online"
@app.route('/verify')
def verify_page(): return render_template_string(HTML_CONTENT)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- BOT CONFIG ---
TOKEN = "7891440763:AAEAP5UpVeGCNLzkY07OGH8Svz64-QVZDnI"
ADMIN_ID = 5766303284 
RENDER_URL = "https://earncashadda.onrender.com"

# YAHAN APNE CHANNELS SET KARO
CHANNELS = {
    "@SheinVoucher4000": "https://t.me/SheinVoucher4000", # Public
    "-1001963038072": "https://t.me/+FsXUwNLm67sxYmE1"      # Private (ID aur Link dalo)
}

bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=MemoryStorage())

class AdminStates(StatesGroup):
    broadcast = State()

db = sqlite3.connect("cashadda.db")
sql = db.cursor()
sql.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0, ip TEXT, is_verified INTEGER DEFAULT 0, referred_by INTEGER, ref_count INTEGER DEFAULT 0)")
db.commit()

# --- FORCE JOIN LOGIC ---
async def check_join(user_id):
    for c_id in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=c_id, user_id=user_id)
            if member.status in ["left", "kicked"]: return False
        except: return False
    return True

# --- DASHBOARD ---
async def send_dashboard(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("💰 Balance", callback_data="bal"),
        InlineKeyboardButton("👥 Refer", callback_data="ref"),
        InlineKeyboardButton("📤 Withdraw", callback_data="withdraw"),
        InlineKeyboardButton("🏆 Leaderboard", callback_data="leader")
    )
    if chat_id == ADMIN_ID:
        markup.add(InlineKeyboardButton("👨‍✈️ Admin Panel", callback_data="admin_p"))
    await bot.send_message(chat_id, "👋 <b>Welcome To CashAdda Dashboard!</b>\nStart inviting friends to earn! 💸", reply_markup=markup)

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    u_id = message.from_user.id
    
    # 1. Force Join Check
    if not await check_join(u_id):
        markup = InlineKeyboardMarkup(row_width=1)
        for c_id, link in CHANNELS.items():
            markup.add(InlineKeyboardButton("📢 Join Channel", url=link))
        markup.add(InlineKeyboardButton("🔄 Joined - Verify Again", callback_data="recheck"))
        return await message.answer("⚠️ <b>Access Denied!</b>\n\nYou must join both channels to use the bot.", reply_markup=markup)

    # 2. Verification & One-Device
    sql.execute("SELECT is_verified FROM users WHERE user_id = ?", (u_id,))
    res = sql.fetchone()

    if not res or res[0] == 0:
        if not res:
            args = message.get_args()
            ref = int(args) if args.isdigit() else None
            sql.execute("INSERT INTO users (user_id, referred_by) VALUES (?, ?)", (u_id, ref))
            db.commit()
        
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🛡️ Verify Device", web_app=types.WebAppInfo(url=f"{RENDER_URL}/verify")))
        return await message.answer("🔒 <b>Hardware Verification</b>\nEstablish a secure connection to unlock the dashboard.", reply_markup=markup)

    await send_dashboard(u_id)

@dp.callback_query_handler(lambda c: c.data == "recheck")
async def recheck(c: types.CallbackQuery):
    if await check_join(c.from_user.id):
        await start(c.message)
    else:
        await bot.answer_callback_query(c.id, "❌ Join both channels first!", show_alert=True)

@dp.message_handler(content_types=['web_app_data'])
async def verified(message: types.Message):
    if message.web_app_data.data == "verified":
        sql.execute("UPDATE users SET is_verified = 1, balance = balance + 3 WHERE user_id = ?", (message.from_user.id,))
        db.commit()
        await message.answer("✅ <b>Verified!</b> 3 Rs Bonus Added.")
        await send_dashboard(message.from_user.id)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    executor.start_polling(dp, skip_updates=True)
