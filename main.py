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

# --- RENDER WEB APP HOSTING ---
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
    <h3 style="color:#4dabf7;">HARDWARE ANALYSIS...</h3>
    <div class="bar"><div class="fill" id="f"></div></div>
    <script>
        let tg = window.Telegram.WebApp; tg.expand();
        let p = 0;
        let it = setInterval(() => {
            p += 5; document.getElementById('f').style.width = p + "%";
            if(p >= 100) { clearInterval(it); tg.sendData("verified"); setTimeout(() => tg.close(), 500); }
        }, 80);
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

# --- CONFIG ---
TOKEN = "7891440763:AAEcQNKFr7DIzAufHeKDZ1H9UJbQ4FsAl2A"
ADMIN_ID = 5766303284 
RENDER_URL = "https://earncashadda.onrender.com" 

bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=MemoryStorage())

class AdminStates(StatesGroup):
    broadcast = State()
    add_bal_id = State()
    add_bal_amt = State()
    withdraw_upi = State()
    change_min = State()

db = sqlite3.connect("cashadda.db")
sql = db.cursor()
sql.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0, ip TEXT, is_verified INTEGER DEFAULT 0, referred_by INTEGER, ref_count INTEGER DEFAULT 0, is_claimed INTEGER DEFAULT 0)")
sql.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
sql.execute("INSERT OR IGNORE INTO settings VALUES ('min_withdraw', '10')")
db.commit()

async def get_ip():
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("http://api.ipify.org?format=json") as r:
                d = await r.json(); return d['ip']
    except: return "127.0.0.1"

# --- START ---
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    u_id = message.from_user.id
    u_ip = await get_ip()

    # One Device Security
    sql.execute("SELECT user_id FROM users WHERE ip = ? AND user_id != ?", (u_ip, u_id))
    if sql.fetchone():
        return await message.answer("❌ <b>Security Alert!</b>\nYou already have an account on this device.")

    sql.execute("SELECT is_verified FROM users WHERE user_id = ?", (u_id,))
    res = sql.fetchone()

    if not res or res[0] == 0:
        if not res:
            args = message.get_args()
            ref = int(args) if args.isdigit() else None
            sql.execute("INSERT INTO users (user_id, ip, referred_by) VALUES (?, ?, ?)", (u_id, u_ip, ref))
            db.commit()
        
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🛡️ Verify Device", web_app=types.WebAppInfo(url=f"{RENDER_URL}/verify")))
        return await message.answer("🔒 <b>Hardware Verification</b>\nEstablish a secure connection to start.", reply_markup=markup)

    # Main Dashboard
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("💰 Balance", callback_data="bal"),
        InlineKeyboardButton("👥 Refer", callback_data="ref"),
        InlineKeyboardButton("📤 Withdraw", callback_data="withdraw_init"),
        InlineKeyboardButton("🏆 Leaderboard", callback_data="leader")
    )
    await message.answer("👋 <b>CashAdda Dashboard</b>\n\n🎁 Top 3 get 50 Rs reward!", reply_markup=markup)

# --- VERIFY SUCCESS ---
@dp.message_handler(content_types=['web_app_data'])
async def verified(message: types.Message):
    if message.web_app_data.data == "verified":
        u_id = message.from_user.id
        sql.execute("SELECT is_claimed, referred_by FROM users WHERE user_id = ?", (u_id,))
        res = sql.fetchone()
        if res and res[0] == 0:
            sql.execute("UPDATE users SET balance = balance + 3, is_verified = 1, is_claimed = 1 WHERE user_id = ?", (u_id,))
            if res[1]:
                sql.execute("UPDATE users SET balance = balance + 3, ref_count = ref_count + 1 WHERE user_id = ?", (res[1],))
                try: await bot.send_message(res[1], "💰 <b>Referral Success!</b> +3 Rs added.")
                except: pass
            db.commit()
        await message.answer("✅ <b>Verified!</b> 3 Rs Bonus added.\nType /start to open menu.")

# --- ADMIN PANEL ---
@dp.message_handler(commands=['admin'])
async def admin(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("📢 Broadcast", callback_data="bc"),
            InlineKeyboardButton("➕ Add Balance", callback_data="add_bal"),
            InlineKeyboardButton("⚙️ Change Min Withdraw", callback_data="set_min")
        )
        await message.answer("👨‍✈️ <b>Admin Controls</b>", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data == "set_min")
async def set_min_init(c: types.CallbackQuery):
    await AdminStates.change_min.set()
    await bot.send_message(c.from_user.id, "Enter New Minimum Withdraw Limit (Rs):")

@dp.message_handler(state=AdminStates.change_min)
async def update_min(message: types.Message, state: FSMContext):
    if message.text.isdigit():
        sql.execute("UPDATE settings SET value = ? WHERE key = 'min_withdraw'", (message.text,))
        db.commit()
        await message.answer(f"✅ Minimum Withdraw updated to {message.text} Rs")
    await state.finish()

# --- WITHDRAWAL LOGIC ---
@dp.callback_query_handler(lambda c: c.data == "withdraw_init")
async def withdraw_start(c: types.CallbackQuery):
    sql.execute("SELECT value FROM settings WHERE key = 'min_withdraw'")
    min_val = int(sql.fetchone()[0])
    sql.execute("SELECT balance FROM users WHERE user_id = ?", (c.from_user.id,))
    bal = sql.fetchone()[0]
    if bal < min_val:
        return await bot.answer_callback_query(c.id, f"❌ Minimum {min_val} Rs needed!", show_alert=True)
    await AdminStates.withdraw_upi.set()
    await bot.send_message(c.from_user.id, "📩 <b>Enter UPI ID:</b>")

@dp.message_handler(state=AdminStates.withdraw_upi)
async def process_withdraw(message: types.Message, state: FSMContext):
    upi = message.text
    if "@" not in upi: return await message.answer("❌ Invalid UPI!")
    sql.execute("SELECT balance FROM users WHERE user_id = ?", (message.from_user.id,))
    amt = sql.fetchone()[0]
    
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Mark Paid", callback_data=f"pay_{message.from_user.id}_{amt}"))
    await bot.send_message(ADMIN_ID, f"📤 <b>Withdraw Request!</b>\nID: {message.from_user.id}\nAmt: {amt} Rs\nUPI: {upi}", reply_markup=markup)
    
    sql.execute("UPDATE users SET balance = 0 WHERE user_id = ?", (message.from_user.id,))
    db.commit()
    await message.answer("✅ Request Sent! Wait for approval."); await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith("pay_"))
async def mark_paid(c: types.CallbackQuery):
    _, uid, amt = c.data.split("_")
    try:
        await bot.send_message(uid, f"🎊 <b>Payment Sent!</b>\nYour withdrawal of {amt} Rs has been processed.")
        await bot.edit_message_text(f"✅ <b>Paid</b>\nID: {uid}\nAmt: {amt} Rs", ADMIN_ID, c.message.message_id)
    except: pass

# --- OTHER CALLBACKS ---
@dp.callback_query_handler(lambda c: True)
async def calls(c: types.CallbackQuery):
    u_id = c.from_user.id
    if c.data == "bal":
        sql.execute("SELECT balance FROM users WHERE user_id = ?", (u_id,))
        await bot.send_message(u_id, f"💳 <b>Balance:</b> {sql.fetchone()[0]} Rs")
    elif c.data == "leader":
        sql.execute("SELECT user_id, ref_count FROM users ORDER BY ref_count DESC LIMIT 3")
        top = sql.fetchall()
        text = "🏆 <b>Leaderboard</b>\nTop 3 winners get 50 Rs!\n\n"
        for i, u in enumerate(top, 1): text += f"{i}. ID: {u[0]} | {u[1]} Refers\n"
        await bot.send_message(u_id, text)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    executor.start_polling(dp, skip_updates=True)
