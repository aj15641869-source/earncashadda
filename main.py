import sqlite3
import os
import aiohttp
import threading
import time
from flask import Flask, render_template_string, request
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# --- RENDER WEB APP ---
app = Flask(__name__)

HTML_CONTENT = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
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
            if(p >= 100) { 
                clearInterval(it); 
                tg.sendData("verified"); 
                setTimeout(() => { tg.close(); }, 500); 
            }
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
# NAYA TOKEN YAHAN HAI
TOKEN = "7891440763:AAEAP5UpVeGCNLzkY07OGH8Svz64-QVZDnI"
ADMIN_ID = 5766303284 
RENDER_URL = "https://earncashadda.onrender.com" 

bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=MemoryStorage())

class AdminStates(StatesGroup):
    broadcast = State()
    withdraw_upi = State()
    redeem_code = State()

db = sqlite3.connect("cashadda.db")
sql = db.cursor()
sql.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0, ip TEXT, is_verified INTEGER DEFAULT 0, referred_by INTEGER, ref_count INTEGER DEFAULT 0, is_claimed INTEGER DEFAULT 0)")
db.commit()

async def get_ip():
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("http://api.ipify.org?format=json") as r:
                d = await r.json(); return d['ip']
    except: return "127.0.0.1"

async def send_main_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("💰 Balance", callback_data="bal"),
        InlineKeyboardButton("👥 Refer", callback_data="ref"),
        InlineKeyboardButton("📤 Withdraw", callback_data="withdraw_req"),
        InlineKeyboardButton("🏆 Leaderboard", callback_data="leader"),
        InlineKeyboardButton("🎁 Gift Code", callback_data="redeem")
    )
    await bot.send_message(chat_id, "👋 <b>CashAdda Dashboard</b>\n\nVerified Successfully! 💸", reply_markup=markup)

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    u_id = message.from_user.id
    u_ip = await get_ip()

    sql.execute("SELECT user_id FROM users WHERE ip = ? AND user_id != ?", (u_ip, u_id))
    if sql.fetchone():
        return await message.answer("❌ <b>Security Alert!</b> Duplicate account detected.")

    sql.execute("SELECT is_verified FROM users WHERE user_id = ?", (u_id,))
    res = sql.fetchone()

    if not res or res[0] == 0:
        if not res:
            args = message.get_args()
            ref = int(args) if args.isdigit() else None
            sql.execute("INSERT INTO users (user_id, ip, referred_by) VALUES (?, ?, ?)", (u_id, u_ip, ref))
            db.commit()
        
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton("🛡️ Verify Device", web_app=types.WebAppInfo(url=f"{RENDER_URL}/verify")))
        markup.add(InlineKeyboardButton("✅ Open Menu", callback_data="check_verified"))
        return await message.answer("🔒 <b>Verification Required</b>", reply_markup=markup)

    await send_main_menu(u_id)

@dp.message_handler(content_types=['web_app_data'])
async def handle_verified(message: types.Message):
    if message.web_app_data.data == "verified":
        u_id = message.from_user.id
        sql.execute("UPDATE users SET is_verified = 1, balance = balance + 3, is_claimed = 1 WHERE user_id = ? AND is_claimed = 0", (u_id,))
        db.commit()
        
        sql.execute("SELECT referred_by FROM users WHERE user_id = ?", (u_id,))
        ref = sql.fetchone()[0]
        if ref:
            sql.execute("UPDATE users SET balance = balance + 3, ref_count = ref_count + 1 WHERE user_id = ?", (ref,))
            try: await bot.send_message(ref, "💰 <b>Referral Success!</b> +3 Rs added.")
            except: pass
            db.commit()

        await message.answer("✅ <b>Verified!</b> 3 Rs Bonus Added.")
        await send_main_menu(u_id)

@dp.callback_query_handler(lambda c: True)
async def calls(c: types.CallbackQuery):
    u_id = c.from_user.id
    if c.data == "check_verified":
        sql.execute("SELECT is_verified FROM users WHERE user_id = ?", (u_id,))
        res = sql.fetchone()
        if res and res[0] == 1: await send_main_menu(u_id)
        else: await bot.answer_callback_query(c.id, "❌ Verify first!", show_alert=True)
    elif c.data == "bal":
        sql.execute("SELECT balance FROM users WHERE user_id = ?", (u_id,))
        await bot.send_message(u_id, f"💳 <b>Balance:</b> {sql.fetchone()[0]} Rs")

if __name__ == '__main__':
    # Flask thread start
    threading.Thread(target=run_flask, daemon=True).start()
    # Conflict Error fix: skip_updates=True
    executor.start_polling(dp, skip_updates=True)
