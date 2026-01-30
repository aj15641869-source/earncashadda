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
PAYMENT_CHANNEL = "@Sheinvoucher4000" # <-- Apna Payment Proof Channel handle yahan daalo
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
    
    sql.execute("SELECT is_blocked FROM users WHERE user_id = ?", (user_id,))
    res_b = sql.fetchone()
    if res_b and res_b[0] == 1:
        return await message.answer("🚫 <b>You are blocked!</b>")

    ip_info = await get_user_ip()
    current_ip = ip_info['query'] if ip_info else "Unknown"
    
    if ip_info and (ip_info.get('proxy') or ip_info.get('hosting')):
        return await message.answer("❌ <b>VPN Detected!</b> Turn it off to continue.")

    sql.execute("SELECT user_id FROM users WHERE ip_address = ? AND user_id != ?", (current_ip, user_id))
    if sql.fetchone():
        return await message.answer("❌ <b>Multi-Account Alert!</b> One device = One account.")

    sql.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = sql.fetchone()
    if not user:
        args = message.get_args()
        referrer = int(args) if args.isdigit() else None
        sql.execute("INSERT INTO users (user_id, referred_by, balance, ip_address) VALUES (?, ?, ?, ?)", (user_id, referrer, 0, current_ip))
        db.commit()

    if not await is_subscribed(user_id):
        markup = InlineKeyboardMarkup(row_width=1)
        for name, link in CHANNEL_LINKS:
            markup.add(InlineKeyboardButton(name, url=link))
        markup.add(InlineKeyboardButton("✅ Joined - Verify", callback_data="verify"))
        return await message.answer("👋 <b>Welcome!</b>\nJoin our channels to start earning:", reply_markup=markup)

    # Joining Bonus
    sql.execute("SELECT is_bonus_claimed, referred_by FROM users WHERE user_id = ?", (user_id,))
    res = sql.fetchone()
    if res and res[0] == 0: 
        sql.execute("UPDATE users SET balance = balance + ?, is_bonus_claimed = 1 WHERE user_id = ?", (JOINING_BONUS, user_id))
        if res[1]:
            sql.execute("UPDATE users SET balance = balance + ?, ref_count = ref_count + 1 WHERE user_id = ?", (REFER_BONUS, res[1]))
            try: await bot.send_message(res[1], f"💰 <b>Referral Success!</b> You got {REFER_BONUS} Rs.")
            except: pass
        db.commit()
        await message.answer(f"🎉 <b>{JOINING_BONUS} Rs</b> Joining Bonus Added!")

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("💰 Balance", callback_data="balance"),
        InlineKeyboardButton("👥 Refer", callback_data="refer"),
        InlineKeyboardButton("🎁 Daily Bonus", callback_data="daily_bonus"),
        InlineKeyboardButton("📤 Withdraw", callback_data="withdraw"),
        InlineKeyboardButton("📊 Stats", callback_data="stats")
    )
    await message.answer(f"👋 <b>Welcome {message.from_user.first_name}!</b>\nStart inviting friends to earn real cash.", reply_markup=markup)

# --- DAILY BONUS LOGIC ---
@dp.callback_query_handler(lambda c: c.data == "daily_bonus")
async def daily_bonus(c: types.CallbackQuery):
    user_id = c.from_user.id
    sql.execute("SELECT last_daily_bonus FROM users WHERE user_id = ?", (user_id,))
    last_time = sql.fetchone()[0]
    current_time = int(time.time())

    if current_time - last_time < 86400: # 24 Hours
        remaining = 86400 - (current_time - last_time)
        hours = remaining // 3600
        return await bot.answer_callback_query(c.id, f"❌ Come back in {hours} hours!", show_alert=True)

    sql.execute("UPDATE users SET balance = balance + ?, last_daily_bonus = ? WHERE user_id = ?", (DAILY_BONUS_AMT, current_time, user_id))
    db.commit()
    await bot.answer_callback_query(c.id, f"🎁 You got {DAILY_BONUS_AMT} Rs Daily Bonus!", show_alert=True)

# --- ADMIN SEARCH & EDIT ---
@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔍 Search User", callback_data="admin_search"),
        InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
        InlineKeyboardButton("📊 Bot Stats", callback_data="admin_stats")
    )
    await message.answer("👑 <b>Pro Admin Panel</b>", reply_markup=markup)

# --- CALLBACK HANDLER (ALL) ---
@dp.callback_query_handler(lambda c: True, state="*")
async def process_callbacks(c: types.CallbackQuery, state: FSMContext):
    user_id = c.from_user.id
    
    if c.data == "balance":
        sql.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        await bot.send_message(user_id, f"💳 <b>Current Balance:</b> {sql.fetchone()[0]} Rs")
    
    elif c.data == "refer":
        me = await bot.get_me()
        await bot.send_message(user_id, f"👥 <b>Invite & Earn {REFER_BONUS} Rs</b>\n\n🔗 Your Link: https://t.me/{me.username}?start={user_id}")
    
    elif c.data == "stats":
        sql.execute("SELECT COUNT(*), SUM(balance) FROM users")
        res = sql.fetchone()
        sql.execute("SELECT user_id, ref_count FROM users ORDER BY ref_count DESC LIMIT 5")
        top = sql.fetchall()
        lb = "\n".join([f"{i+1}. {str(u[0])[:4]}**** - {u[1]} Ref" for i,u in enumerate(top)])
        await bot.send_message(user_id, f"📊 <b>Bot Stats</b>\nTotal Users: {res[0]}\n\n🏆 <b>Leaderboard:</b>\n{lb}")

    elif c.data == "withdraw":
        sql.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        if sql.fetchone()[0] < MIN_WITHDRAW:
            return await bot.answer_callback_query(c.id, f"❌ Min {MIN_WITHDRAW} Rs needed!", show_alert=True)
        await WithdrawState.waiting_for_upi.set()
        await bot.send_message(user_id, "📩 <b>Enter your UPI ID:</b>")

    # Admin Logic
    elif c.data == "admin_search" and user_id == ADMIN_ID:
        await AdminState.waiting_for_search.set()
        await bot.send_message(ADMIN_ID, "🔍 Send User ID:")
    
    elif c.data.startswith("paid_") and user_id == ADMIN_ID:
        _, target_id, amt = c.data.split("_")
        try:
            await bot.send_message(target_id, f"✅ <b>Withdrawal Success!</b>\n{amt} Rs sent to your UPI.")
            await bot.send_message(PAYMENT_CHANNEL, f"✅ <b>New Payout Success!</b>\nUser: {target_id[:4]}****\nAmount: {amt} Rs\nStatus: Paid")
            await c.message.edit_text(f"✅ User {target_id} Paid!")
        except: pass

# --- STATE HANDLERS ---
@dp.message_handler(state=WithdrawState.waiting_for_upi)
async def withdraw_process(message: types.Message, state: FSMContext):
    upi = message.text
    if "@" not in upi: return await message.answer("❌ Invalid UPI ID!")
    sql.execute("SELECT balance FROM users WHERE user_id = ?", (message.from_user.id,))
    amt = sql.fetchone()[0]
    
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Mark Paid", callback_data=f"paid_{message.from_user.id}_{amt}"))
    await bot.send_message(ADMIN_ID, f"💰 <b>Withdrawal Request!</b>\nID: {message.from_user.id}\nAmt: {amt} Rs\nUPI: {upi}", reply_markup=markup)
    
    sql.execute("UPDATE users SET balance = 0 WHERE user_id = ?", (message.from_user.id,))
    db.commit()
    await message.answer("✅ Request Sent! Wait for Admin approval."); await state.finish()

if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    executor.start_polling(dp, skip_updates=True)
