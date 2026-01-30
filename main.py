import sqlite3
import os
import aiohttp
import threading
import time
from flask import Flask, render_template_string
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# --- RENDER WEB APP & SECURITY PAGE HOSTING ---
app = Flask(__name__)

# Yahan wahi Fingerprint wala HTML code hai jo ab Render host karega
HTML_CONTENT = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body { background: #0a0e1a; color: white; font-family: sans-serif; text-align: center; display: flex; flex-direction: column; justify-content: center; height: 100vh; margin: 0; }
        .scanner { position: relative; width: 120px; height: 120px; margin: 0 auto 20px; border: 2px solid #3498db; border-radius: 50%; padding: 15px; }
        .scan-line { position: absolute; width: 80%; height: 3px; background: #3498db; left: 10%; top: 20%; box-shadow: 0 0 15px #3498db; animation: scan 2s infinite; }
        @keyframes scan { 0%, 100% { top: 20%; } 50% { top: 80%; } }
        .bar { width: 80%; height: 8px; background: #222; margin: 20px auto; border-radius: 5px; overflow: hidden; }
        .fill { width: 0%; height: 100%; background: #3498db; transition: width 0.2s; }
    </style>
</head>
<body>
    <div class="scanner">
        <img src="https://cdn-icons-png.flaticon.com/512/2566/2566210.png" style="width:100%; filter:invert(1); opacity:0.6;">
        <div class="scan-line"></div>
    </div>
    <h3 id="st">VERIFYING DEVICE...</h3>
    <div class="bar"><div class="fill" id="f"></div></div>
    <script>
        let tg = window.Telegram.WebApp; tg.expand();
        let p = 0;
        let it = setInterval(() => {
            p += 5; document.getElementById('f').style.width = p + "%";
            if(p >= 100) { clearInterval(it); setTimeout(() => tg.close(), 500); }
        }, 100);
    </script>
</body>
</html>
"""

@app.route('/')
def health(): return "Bot is Alive!"

@app.route('/verify')
def verify_page(): return render_template_string(HTML_CONTENT)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- BOT CONFIG ---
TOKEN = "7891440763:AAEcQNKFr7DIzAufHeKDZ1H9UJbQ4FsAl2A"
ADMIN_ID = 5766303284 
# Render ka apna link use karenge
RENDER_URL = "https://earncashadda.onrender.com" # <-- Apna Render URL yahan check karke dalo

CHANNELS = [-1001963038072, "@Sheinvoucher4000"] 
CHANNEL_LINKS = [("Join 1", "https://t.me/+FsXUwNLm67sxYmE1"), ("Join 2", "https://t.me/Sheinvoucher4000")]

bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=MemoryStorage())

# --- DATABASE (One Device Security) ---
db = sqlite3.connect("cashadda.db")
sql = db.cursor()
sql.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0, ip TEXT, is_claimed INTEGER DEFAULT 0)")
db.commit()

async def get_ip():
    async with aiohttp.ClientSession() as s:
        async with s.get("http://api.ipify.org?format=json") as r:
            d = await r.json(); return d['ip']

async def is_sub(u_id):
    for c in CHANNELS:
        try:
            m = await bot.get_chat_member(c, u_id)
            if m.status in ["left", "kicked"]: return False
        except: return False
    return True

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    u_id = message.from_user.id
    u_ip = await get_ip()

    # ONE DEVICE CHECK
    sql.execute("SELECT user_id FROM users WHERE ip = ? AND user_id != ?", (u_ip, u_id))
    if sql.fetchone():
        return await message.answer("❌ <b>Security Alert!</b> One device = One account.")

    sql.execute("SELECT * FROM users WHERE user_id = ?", (u_id,))
    if not sql.fetchone():
        sql.execute("INSERT INTO users (user_id, ip) VALUES (?, ?)", (u_id, u_ip))
        db.commit()
        # Ab link Render se aayega
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🛡️ Verify Device", web_app=types.WebAppInfo(url=f"{RENDER_URL}/verify")))
        return await message.answer("🔒 <b>Verify Yourself</b>", reply_markup=markup)

    if not await is_sub(u_id):
        markup = InlineKeyboardMarkup(row_width=2)
        for n, l in CHANNEL_LINKS: markup.insert(InlineKeyboardButton(n, url=l))
        markup.add(InlineKeyboardButton("✅ Claim Bonus", callback_data="claim"))
        return await message.answer("👋 Join channels to continue:", reply_markup=markup)

    await message.answer("💰 <b>Main Menu</b>\nInvite friends to earn!")

@dp.callback_query_handler(lambda c: c.data == "claim")
async def claim(c: types.CallbackQuery):
    if await is_sub(c.from_user.id):
        sql.execute("UPDATE users SET balance = balance + 3, is_claimed = 1 WHERE user_id = ? AND is_claimed = 0", (c.from_user.id,))
        db.commit()
        await bot.answer_callback_query(c.id, "🎉 Bonus Added!", show_alert=True)
        await start(c.message)
    else: await bot.answer_callback_query(c.id, "❌ Join first!", show_alert=True)

if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    executor.start_polling(dp, skip_updates=True)
