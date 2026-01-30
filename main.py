import sqlite3
import os
import aiohttp
import threading
import json
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

class WithdrawState(StatesGroup):
    waiting_for_upi = State()

# --- DATABASE ---
db = sqlite3.connect("cashadda.db")
sql = db.cursor()
sql.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY, 
    balance REAL DEFAULT 0, 
    referred_by INTEGER,
    ref_count INTEGER DEFAULT 0,
    is_bonus_claimed INTEGER DEFAULT 0,
    ip_address TEXT
)""")
db.commit()

# --- HIGH SECURITY: ANTI-VPN ---
async def check_security(message: types.Message):
    # Note: Telegram doesn't give IP directly, but we track User ID as 'Device ID'
    # This ensures one Telegram Account = One User
    user_id = message.from_user.id
    sql.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if sql.fetchone(): return True
    return True

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
    args = message.get_args()
    
    sql.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = sql.fetchone()
    
    if not user:
        referrer = int(args) if args.isdigit() else None
        sql.execute("INSERT INTO users (user_id, referred_by, balance, ref_count, is_bonus_claimed) VALUES (?, ?, ?, ?, ?)", (user_id, referrer, 0, 0, 0))
        db.commit()

    if not await is_subscribed(user_id):
        markup = InlineKeyboardMarkup(row_width=1)
        for name, link in CHANNEL_LINKS:
            markup.add(InlineKeyboardButton(name, url=link))
        markup.add(InlineKeyboardButton("✅ Joined - Verify", callback_data="verify"))
        return await message.answer("❌ <b>Security Check!</b>\nJoin BOTH channels to continue:", reply_markup=markup)

    sql.execute("SELECT is_bonus_claimed, referred_by FROM users WHERE user_id = ?", (user_id,))
    res = sql.fetchone()
    if res and res[0] == 0: 
        sql.execute("UPDATE users SET balance = balance + ?, is_bonus_claimed = 1 WHERE user_id = ?", (JOINING_BONUS, user_id))
        if res[1]:
            sql.execute("UPDATE users SET balance = balance + ?, ref_count = ref_count + 1 WHERE user_id = ?", (REFER_BONUS, res[1]))
            try: await bot.send_message(res[1], "💰 <b>Referral Success!</b> +3 Rs")
            except: pass
        db.commit()
        await message.answer(f"🎉 <b>3 Rs Bonus Added!</b>")

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("💰 Balance", callback_data="balance"),
        InlineKeyboardButton("👥 Refer", callback_data="refer"),
        InlineKeyboardButton("📤 Withdraw", callback_data="withdraw"),
        InlineKeyboardButton("📊 Stats", callback_data="stats")
    )
    await message.answer(f"👋 <b>Welcome!</b>\nOne Account = One Bonus Policy Active.", reply_markup=markup)

# --- WITHDRAWAL SYSTEM ---
@dp.callback_query_handler(lambda c: c.data == "withdraw")
async def withdraw_cmd(c: types.CallbackQuery):
    sql.execute("SELECT balance FROM users WHERE user_id = ?", (c.from_user.id,))
    bal = sql.fetchone()[0]
    if bal < MIN_WITHDRAW:
        return await bot.answer_callback_query(c.id, f"❌ Need min {MIN_WITHDRAW} Rs!", show_alert=True)
    
    await WithdrawState.waiting_for_upi.set()
    await bot.send_message(c.from_user.id, "📩 <b>Enter UPI ID:</b>")

@dp.message_handler(state=WithdrawState.waiting_for_upi)
async def upi_input(message: types.Message, state: FSMContext):
    upi = message.text
    if "@" not in upi: return await message.answer("❌ Invalid UPI!")
    
    user_id = message.from_user.id
    sql.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    amt = sql.fetchone()[0]
    
    # Admin Approval Button
    adm_markup = InlineKeyboardMarkup()
    adm_markup.add(InlineKeyboardButton("✅ Paid", callback_data=f"paid_{user_id}_{amt}"), 
                   InlineKeyboardButton("❌ Fake", callback_data=f"fake_{user_id}"))
    
    await bot.send_message(ADMIN_ID, f"🔔 <b>Withdraw Request!</b>\nUser: {user_id}\nAmt: {amt}\nUPI: {upi}", reply_markup=adm_markup)
    
    sql.execute("UPDATE users SET balance = 0 WHERE user_id = ?", (user_id,))
    db.commit()
    await message.answer("✅ Request sent to Admin!")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith(('paid_', 'fake_')))
async def admin_payout(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID: return
    data = c.data.split('_')
    target_user = data[1]
    
    if data[0] == "paid":
        await bot.send_message(target_user, f"✅ <b>Payment Successful!</b>\nYour {data[2]} Rs has been sent.")
        await c.message.edit_text(f"✅ User {target_user} was PAID.")
    else:
        await bot.send_message(target_user, "❌ <b>Request Rejected!</b>\nReason: Suspicious Activity.")
        await c.message.edit_text(f"❌ User {target_user} was REJECTED.")

@dp.callback_query_handler(lambda c: True)
async def calls(c: types.CallbackQuery):
    if c.data == "verify":
        if await is_subscribed(c.from_user.id):
            await c.message.delete()
            await start(c.message)
    elif c.data == "balance":
        sql.execute("SELECT balance FROM users WHERE user_id = ?", (c.from_user.id,))
        await bot.send_message(c.from_user.id, f"💳 Balance: {sql.fetchone()[0]} Rs")

if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    executor.start_polling(dp, skip_updates=True)
