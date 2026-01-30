import sqlite3
import os
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# --- CONFIG ---
TOKEN = "7891440763:AAEcQNKFr7DIzAufHeKDZ1H9UJbQ4FsAl2A"
ADMIN_ID = 5766303284
REFER_BONUS = 3  
JOINING_BONUS = 3 
MIN_WITHDRAW = 10

# Yahan dono dalo: Private ID aur Public Username
CHANNELS = [-1001963038072, "@SheinVoucher4000"] 
# Buttons ke liye links
CHANNEL_LINKS = [
    ("📢 Private Channel", "https://t.me/+FsXUwNLm67sxYmE1"),
    ("📢 Public Channel", "https://t.me/SheinVoucher4000")
]

# Gateway Setup (Optional)
GATEWAY_API_URL = "https://your-gateway.com/api"
GATEWAY_KEY = "YOUR_API_KEY"

bot = Bot(token=TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- STATES FOR WITHDRAW ---
class WithdrawState(StatesGroup):
    waiting_for_upi = State()

# --- DATABASE SETUP ---
db = sqlite3.connect("cashadda.db")
sql = db.cursor()
sql.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY, 
    balance REAL DEFAULT 0, 
    referred_by INTEGER,
    ref_count INTEGER DEFAULT 0,
    is_bonus_claimed INTEGER DEFAULT 0
)""")
db.commit()

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
        return await message.answer("❌ <b>Access Denied!</b>\n\nJoin <b>BOTH</b> channels to unlock your bonus:", reply_markup=markup)

    # Claim Joining Bonus
    sql.execute("SELECT is_bonus_claimed, referred_by FROM users WHERE user_id = ?", (user_id,))
    res = sql.fetchone()
    if res[0] == 0: 
        sql.execute("UPDATE users SET balance = balance + ?, is_bonus_claimed = 1 WHERE user_id = ?", (JOINING_BONUS, user_id))
        if res[1]:
            sql.execute("UPDATE users SET balance = balance + ?, ref_count = ref_count + 1 WHERE user_id = ?", (REFER_BONUS, res[1]))
            try: await bot.send_message(res[1], "💰 <b>Referral Success!</b> You earned 3 Rs.")
            except: pass
        db.commit()
        await message.answer(f"🎉 <b>Congratulations!</b> You received {JOINING_BONUS} Rs Joining Bonus!")

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("💰 Balance", callback_data="balance"),
        InlineKeyboardButton("👥 Refer", callback_data="refer"),
        InlineKeyboardButton("📤 Withdraw", callback_data="withdraw"),
        InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard")
    )
    await message.answer(f"👋 Welcome {message.from_user.first_name}!", reply_markup=markup)

# --- WITHDRAWAL PROCESS ---
@dp.callback_query_handler(lambda c: c.data == "withdraw")
async def withdraw_init(c: types.CallbackQuery):
    user_id = c.from_user.id
    sql.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance = sql.fetchone()[0]
    
    if balance < MIN_WITHDRAW:
        return await bot.answer_callback_query(c.id, f"❌ Min withdraw is {MIN_WITHDRAW} Rs!", show_alert=True)
    
    await
