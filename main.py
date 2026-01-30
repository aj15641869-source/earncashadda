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

# --- RENDER WEB APP HOSTING ---
app = Flask(__name__)

# Fingerprint Scanner UI
HTML_CONTENT = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body { background: #0a0e1a; color: white; font-family: sans-serif; text-align: center; display: flex; flex-direction: column; justify-content: center; height: 100vh; margin: 0; }
        .scanner { position: relative; width: 140px; height: 140px; margin: 0 auto 20px; border: 2px solid #1c7ed6; border-radius: 50%; padding: 20px; box-shadow: 0 0 20px rgba(28, 126, 214, 0.3); }
        .scan-line { position: absolute; width: 80%; height: 3px; background: #4dabf7; left: 10%; top: 20%; box-shadow: 0 0 15px #4dabf7; animation: scan 2s infinite; }
        @keyframes scan { 0%, 100% { top: 20%; } 50% { top: 80%; } }
        .bar { width: 80%; height: 8px; background: #1a1f2e; margin: 20px auto; border-radius: 5px; overflow: hidden; }
        .fill { width: 0%; height: 100%; background: #4dabf7; transition: width 0.2s; }
        h3 { color: #4dabf7; letter-spacing: 1px; }
    </style>
</head>
<body>
    <div class="scanner">
        <img src="https://cdn-icons-png.flaticon.com/512/2566/2566210.png" style="width:100%; filter:invert(1); opacity:0.7;">
        <div class="scan-line"></div>
    </div>
    <h3 id="st">DEVICE VERIFICATION</h3>
    <div class="bar"><div class="fill" id="f"></div></div>
    <p style="font-size:12px; color:gray;">Scanning hardware integrity...</p>
    <script>
        let tg = window.Telegram.WebApp; tg.expand();
        let p = 0;
        let it = setInterval(() => {
            p += Math.floor(Math.random() * 5) + 2;
            if(p > 100) p = 100;
            document.getElementById('f').style.width = p + "%";
            if(p >= 100) { clearInterval(it); setTimeout(() => tg.close(), 600); }
        }, 120);
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
RENDER_URL = "https://earncashadda.onrender.com" 

CHANNELS = [-1001963038072, "@Sheinvoucher4000"] 
CHANNEL_LINKS = [
    ("📢 Private Channel", "https://t.me/+FsXUwNLm67sxYmE1"),
    ("📢 Public Channel", "https://t.me/Sheinvoucher4000")
]

bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=MemoryStorage())

# --- DATABASE (One Device Security) ---
db = sqlite3.connect("cashadda.db")
sql = db.cursor()
sql.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY, 
    balance REAL DEFAULT 0, 
    ip TEXT, 
    referred_by INTEGER, 
    is_claimed INTEGER DEFAULT 0
)""")
db.commit()

async def get_ip():
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("http://api.ipify.org?format=json") as r:
                d = await r.json(); return d['ip']
    except: return "127.0.0.1"

async def is_sub(u_id):
    for c in CHANNELS:
        try:
            m = await bot.get_chat_member(c, u_id)
            if m.status in ["left", "kicked"]: return False
        except: return False
    return True

# --- START COMMAND ---
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    u_id = message.from_user.id
    u_ip = await get_ip()

    # ONE DEVICE SECURITY: Check duplicate IP
    sql.execute("SELECT user_id FROM users WHERE ip = ? AND user_id != ?", (u_ip, u_id))
    dup = sql.fetchone()
    if dup:
        return await message.answer(f"❌ <b>One Device = One Account!</b>\nYou already have an ID ({dup[0]}) registered on this device.")

    sql.execute("SELECT * FROM users WHERE user_id = ?", (u_id,))
    user = sql.fetchone()
    
    if not user:
        args = message.get_args()
        ref = int(args) if args.isdigit() else None
        sql.execute("INSERT INTO users (user_id, ip, referred_by) VALUES (?, ?, ?)", (u_id, u_ip, ref))
        db.commit()
        
        # Security Verification Button
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🛡️ Verify Device", web_app=types.WebAppInfo(url=f"{RENDER_URL}/verify")))
        return await message.answer("🔒 <b>Security Verification</b>\nEstablish a secure connection to start earning.", reply_markup=markup)

    if not await is_sub(u_id):
        markup = InlineKeyboardMarkup(row_width=2)
        for n, l in CHANNEL_LINKS: markup.insert(InlineKeyboardButton(n, url=l))
        markup.add(InlineKeyboardButton("✅ Claim 3 Rs Bonus", callback_data="claim"))
        return await message.answer("👋 <b>Join Both Channels Below To Continue</b>", reply_markup=markup)

    # Main Menu
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("💰 Balance", callback_data="bal"),
        InlineKeyboardButton("👥 Refer", callback_data="ref"),
        InlineKeyboardButton("📊 Stats", callback_data="stats")
    )
    await message.answer(f"👋 <b>Welcome To CashAdda!</b>\nStart inviting friends to earn.", reply_markup=markup)

# --- CALLBACK HANDLERS ---
@dp.callback_query_handler(lambda c: True)
async def callbacks(c: types.CallbackQuery):
    u_id = c.from_user.id
    
    if c.data == "bal":
        sql.execute("SELECT balance FROM users WHERE user_id = ?", (u_id,))
        await bot.send_message(u_id, f"💳 <b>Current Balance:</b> {sql.fetchone()[0]} Rs")
        
    elif c.data == "ref":
        me = await bot.get_me()
        await bot.send_message(u_id, f"👥 <b>Refer & Earn 3 Rs</b>\n\n🔗 Your Link: https://t.me/{me.username}?start={u_id}")
        
    elif c.data == "stats":
        sql.execute("SELECT COUNT(*) FROM users")
        total = sql.fetchone()[0]
        await bot.send_message(u_id, f"📊 <b>Bot Live Stats</b>\nTotal Users: {total}\nSecurity: High (One-Device)")

    elif c.data == "claim":
        if await is_sub(u_id):
            sql.execute("SELECT is_claimed, referred_by FROM users WHERE user_id = ?", (u_id,))
            res = sql.fetchone()
            if res and res[0] == 0:
                # Joining Bonus
                sql.execute("UPDATE users SET balance = balance + 3, is_claimed = 1 WHERE user_id = ?", (u_id,))
                if res[1]:
                    # Referrer Bonus
                    sql.execute("UPDATE users SET balance = balance + 3 WHERE user_id = ?", (res[1],))
                    try: await bot.send_message(res[1], "💰 <b>Referral Success!</b> +3 Rs Added.")
                    except: pass
                db.commit()
                await bot.answer_callback_query(c.id, "🎉 3 Rs Bonus Added!", show_alert=True)
                await start(c.message)
        else:
            await bot.answer_callback_query(c.id, "❌ Join both channels first!", show_alert=True)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    executor.start_polling(dp, skip_updates=True)
