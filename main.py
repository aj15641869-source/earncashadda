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

# --- CONFIG ---
TOKEN = "7891440763:AAEAP5UpVeGCNLzkY07OGH8Svz64-QVZDnI"
ADMIN_ID = 5766303284 
RENDER_URL = "https://earncashadda.onrender.com"

# YAHAN APNE CHANNELS DALO
# Format: "Channel_ID": "Channel_Invite_Link"
CHANNELS = {
    "@SheinVoucher4000": "https://t.me/SheinVoucher4000",   # Public Channel
    "-1002345678901": "https://t.me/+AbCdEfGh1234"        # Private Channel (ID & Link)
}

bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=MemoryStorage())

db = sqlite3.connect("cashadda.db")
sql = db.cursor()
sql.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0, ip TEXT, is_verified INTEGER DEFAULT 0, referred_by INTEGER, ref_count INTEGER DEFAULT 0)")
db.commit()

# --- FORCE JOIN CHECK ---
async def check_join(user_id):
    for c_id in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=c_id, user_id=user_id)
            if member.status in ["left", "kicked"]: return False
        except Exception: return False
    return True

# --- MAIN DASHBOARD ---
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
    await bot.send_message(chat_id, "👋 <b>Welcome To CashAdda!</b>\nAll channels joined & verified! 💸", reply_markup=markup)

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    u_id = message.from_user.id
    
    # 1. Force Join Check (Public & Private)
    if not await check_join(u_id):
        markup = InlineKeyboardMarkup(row_width=1)
        for c_id, link in CHANNELS.items():
            markup.add(InlineKeyboardButton("📢 Join Channel", url=link))
        markup.add(InlineKeyboardButton("🔄 Joined - Try Again", callback_data="recheck"))
        
        return await message.answer("⚠️ <b>Access Denied!</b>\n\nYou must join both our Public and Private channels to use the bot.", reply_markup=markup)

    # 2. Verification Check
    sql.execute("SELECT is_verified FROM users WHERE user_id = ?", (u_id,))
    res = sql.fetchone()

    if not res or res[0] == 0:
        if not res:
            args = message.get_args()
            ref = int(args) if args.isdigit() else None
            sql.execute("INSERT INTO users (user_id, referred_by) VALUES (?, ?)", (u_id, ref))
            db.commit()
        
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🛡️ Verify Device", web_app=types.WebAppInfo(url=f"{RENDER_URL}/verify")))
        return await message.answer("🔒 <b>Hardware Verification</b>\nPlease verify your device to unlock the dashboard.", reply_markup=markup)

    await send_dashboard(u_id)

@dp.callback_query_handler(lambda c: c.data == "recheck")
async def recheck_join(c: types.CallbackQuery):
    if await check_join(c.from_user.id):
        await start(c.message)
    else:
        await bot.answer_callback_query(c.id, "❌ Join both channels first!", show_alert=True)

# --- APP & POLLING ---
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
