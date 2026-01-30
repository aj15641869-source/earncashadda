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
    is_blocked INTEGER DEFAULT 0
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

# --- ADMIN PANEL ---
@dp.message_handler(commands=['admin'])
async def admin_menu(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    sql.execute("SELECT COUNT(*) FROM users")
    total = sql.fetchone()[0]
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
        InlineKeyboardButton("🔍 Search User", callback_data="admin_search"),
        InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")
    )
    await message.answer(f"👑 <b>Admin Panel</b>\nTotal Users: {total}", reply_markup=markup)

# --- MAIN START COMMAND ---
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = message.from_user.id
    
    # Block Check
    sql.execute("SELECT is_blocked FROM users WHERE user_id = ?", (user_id,))
    res_b = sql.fetchone()
    if res_b and res_b[0] == 1:
        return await message.answer("🚫 You are blocked!")

    # Security Check
    ip_info = await get_user_ip()
    current_ip = ip_info['query'] if ip_info else "Unknown"
    if ip_info and (ip_info.get('proxy') or ip_info.get('hosting')):
        return await message.answer("❌ VPN/Proxy detected. Turn it off!")

    sql.execute("SELECT user_id FROM users WHERE ip_address = ? AND user_id != ?", (current_ip, user_id))
    if sql.fetchone():
        return await message.answer("❌ Multiple accounts detected on this device!")

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
        return await message.answer("👋 Join channels to unlock bonus:", reply_markup=markup)

    # Bonus Logic
    sql.execute("SELECT is_bonus_claimed, referred_by FROM users WHERE user_id = ?", (user_id,))
    res = sql.fetchone()
    if res and res[0] == 0: 
        sql.execute("UPDATE users SET balance = balance + ?, is_bonus_claimed = 1 WHERE user_id = ?", (JOINING_BONUS, user_id))
        if res[1]:
            sql.execute("UPDATE users SET balance = balance + ?, ref_count = ref_count + 1 WHERE user_id = ?", (REFER_BONUS, res[1]))
            try: await bot.send_message(res[1], "💰 <b>Referral Success!</b> +3 Rs")
            except: pass
        db.commit()
        await message.answer("🎉 3 Rs Joining Bonus Added!")

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("💰 Balance", callback_data="balance"),
        InlineKeyboardButton("👥 Refer", callback_data="refer"),
        InlineKeyboardButton("📤 Withdraw", callback_data="withdraw"),
        InlineKeyboardButton("📊 Stats", callback_data="stats")
    )
    await message.answer(f"👋 Welcome to CashAdda!", reply_markup=markup)

# --- STATS & LEADERBOARD ---
@dp.message_handler(commands=['stats'])
async def stats_cmd(message: types.Message):
    sql.execute("SELECT COUNT(*), SUM(balance) FROM users")
    res = sql.fetchone()
    sql.execute("SELECT user_id, ref_count FROM users ORDER BY ref_count DESC LIMIT 10")
    top = sql.fetchall()
    lb = "🏆 <b>Top 10 Referrers:</b>\n"
    for i, u in enumerate(top, 1):
        lb += f"{i}. {str(u[0])[:4]}**** — {u[1]} Refers\n"
    
    await message.answer(f"📊 <b>Bot Stats</b>\nUsers: {res[0]}\nPayouts: {res[1] if res[1] else 0} Rs\n\n{lb}")

# --- CALLBACKS ---
@dp.callback_query_handler(lambda c: True, state="*")
async def calls(c: types.CallbackQuery, state: FSMContext):
    user_id = c.from_user.id
    if c.data == "verify":
        if await is_subscribed(user_id):
            await c.message.delete()
            await start(c.message)
    elif c.data == "balance":
        sql.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        await bot.send_message(user_id, f"💳 Balance: {sql.fetchone()[0]} Rs")
    elif c.data == "refer":
        me = await bot.get_me()
        await bot.send_message(user_id, f"🔗 Invite Link: https://t.me/{me.username}?start={user_id}")
    elif c.data == "stats":
        await stats_cmd(c.message)
    elif c.data == "withdraw":
        sql.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        if sql.fetchone()[0] < MIN_WITHDRAW:
            return await bot.answer_callback_query(c.id, f"❌ Min {MIN_WITHDRAW} Rs required!", show_alert=True)
        await WithdrawState.waiting_for_upi.set()
        await bot.send_message(user_id, "📩 Send your UPI ID:")
    
    # Admin Search/Edit Callbacks
    elif c.data == "admin_search" and user_id == ADMIN_ID:
        await AdminState.waiting_for_search.set()
        await bot.send_message(ADMIN_ID, "🔍 Send User ID:")
    elif c.data.startswith("editbal_") and user_id == ADMIN_ID:
        target = c.data.split("_")[1]
        async with state.proxy() as data: data['t_id'] = target
        await AdminState.waiting_for_new_balance.set()
        await bot.send_message(ADMIN_ID, "💰 Send new balance:")
    elif c.data.startswith(("block_", "unblock_")) and user_id == ADMIN_ID:
        act, t_id = c.data.split("_")
        sql.execute("UPDATE users SET is_blocked = ? WHERE user_id = ?", (1 if act=="block" else 0, t_id))
        db.commit()
        await bot.answer_callback_query(c.id, "✅ Done!")

# --- STATE HANDLERS ---
@dp.message_handler(state=WithdrawState.waiting_for_upi)
async def get_upi(message: types.Message, state: FSMContext):
    upi = message.text
    if "@" not in upi: return await message.answer("❌ Invalid UPI!")
    sql.execute("SELECT balance FROM users WHERE user_id = ?", (message.from_user.id,))
    amt = sql.fetchone()[0]
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Paid", callback_data=f"paid_{message.from_user.id}_{amt}"))
    await bot.send_message(ADMIN_ID, f"💰 <b>Withdraw!</b>\nID: {message.from_user.id}\nAmt: {amt}\nUPI: {upi}", reply_markup=markup)
    sql.execute("UPDATE users SET balance = 0 WHERE user_id = ?", (message.from_user.id,))
    db.commit()
    await message.answer("✅ Request Sent!"); await state.finish()

@dp.message_handler(state=AdminState.waiting_for_search)
async def search_user(message: types.Message, state: FSMContext):
    sql.execute("SELECT user_id, balance, is_blocked FROM users WHERE user_id = ?", (message.text,))
    u = sql.fetchone()
    if not u: await message.answer("❌ Not found")
    else:
        m = InlineKeyboardMarkup().add(InlineKeyboardButton("💰 Edit Bal", callback_data=f"editbal_{u[0]}"), InlineKeyboardButton("🚫 Block" if u[2]==0 else "🔓 Unblock", callback_data=f"block_{u[0]}" if u[2]==0 else f"unblock_{u[0]}"))
        await message.answer(f"👤 ID: {u[0]}\nBal: {u[1]}\nStatus: {'Blocked' if u[2]==1 else 'Active'}", reply_markup=m)
    await state.finish()

@dp.message_handler(state=AdminState.waiting_for_new_balance)
async def set_bal(message: types.Message, state: FSMContext):
    async with state.proxy() as d: t_id = d['t_id']
    sql.execute("UPDATE users SET balance = ? WHERE user_id = ?", (message.text, t_id))
    db.commit()
    await message.answer("✅ Balance Updated!"); await state.finish()

if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    executor.start_polling(dp, skip_updates=True)
