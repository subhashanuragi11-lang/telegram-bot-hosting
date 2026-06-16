

import asyncio
import sqlite3
import os
import zipfile
import shutil
import subprocess
import signal
import time
import json
import psutil
from datetime import datetime, timedelta
from pathlib import Path
from aiogram.client.default import DefaultBotProperties
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile

from flask import Flask
from threading import Thread
import os

from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot Running"

def run_web():
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )

Thread(target=run_web, daemon=True).start()

# ═══════════════════════════════════════════════════
# ⚙️ CONFIGURATION
# ═══════════════════════════════════════════════════

BOT_TOKEN = "8965239565:AAEclEkNLrAUdOsQxBwb0cWhBwcGPzmzWg0"
OWNER_USERNAME = "@Subhash_Anuragi_RAI"
OWNER_ID = 6406769029
FORCE_JOIN_CHANNEL = "https://t.me/raiaddaarmys"
FORCE_JOIN_CHANNEL_ID = "@raiaddaarmys"
BOT_NAME = "Rai Bot Hosting"
BOT_USERNAME = "@RAIBOTHOSTING_bot"
UPLOAD_CHANNEL = -1001234567890

MAX_BOT_SIZE_MB = 50
MAX_FREE_BOTS = 2
MAX_PREMIUM_BOTS = 10
REFERRAL_REWARD = 1  # +1 bot limit per 10 referrals

# ═══════════════════════════════════════════════════
# 📁 PATHS
# ═══════════════════════════════════════════════════

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "database.db"
USERS_DIR = BASE_DIR / "users"
BOTS_DIR = BASE_DIR / "bots"
LOGS_DIR = BASE_DIR / "logs"

for d in [USERS_DIR, BOTS_DIR, LOGS_DIR]:
    d.mkdir(exist_ok=True)

# ═══════════════════════════════════════════════════
# 🗄️ DATABASE
# ═══════════════════════════════════════════════════

def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            join_date TEXT,
            bot_limit INTEGER DEFAULT 2,
            running_bots INTEGER DEFAULT 0,
            referrals INTEGER DEFAULT 0,
            referral_link TEXT,
            referred_by INTEGER,
            is_banned INTEGER DEFAULT 0,
            is_premium INTEGER DEFAULT 0,
            notifications INTEGER DEFAULT 1
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS bots (
            bot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            bot_name TEXT,
            bot_path TEXT,
            language TEXT,
            status TEXT DEFAULT 'offline',
            uptime TEXT DEFAULT '00:00',
            created_at TEXT,
            pid INTEGER,
            log_file TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Default settings
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('maintenance', 'off')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('total_users', '0')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('total_bots', '0')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('upload_channel', '')")
    
    conn.commit()
    conn.close()

init_db()

def get_db():
    return sqlite3.connect(str(DB_PATH))

# ═══════════════════════════════════════════════════
# 🎨 STYLISH UI HELPERS
# ═══════════════════════════════════════════════════

def stylish_text(text, emoji="✨"):
    return f"{emoji} <b>{text}</b> {emoji}"

def divider():
    return "━" * 20

def box_text(text):
    return f"<code>{text}</code>"

def owner_footer():
    return f"\n\n{divider()}\n👑 <b>Owner:</b> {OWNER_USERNAME}\n🤖 <b>Bot:</b> {BOT_USERNAME}"

# ═══════════════════════════════════════════════════
# ⌨️ KEYBOARDS
# ═══════════════════════════════════════════════════

def force_join_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 JOIN OFFICIAL CHANNEL",
                    url=FORCE_JOIN_CHANNEL
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ I HAVE JOINED",
                    callback_data="check_join"
                )
            ]
        ]
    )

def main_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🚀 Host Bot"),
                KeyboardButton(text="🤖 My Bots")
            ],
            [
                KeyboardButton(text="👤 Profile"),
                KeyboardButton(text="💎 Subscription")
            ],
            [
                KeyboardButton(text="🎁 Referral"),
                KeyboardButton(text="⚙️ Settings")
            ],
            [
                KeyboardButton(text="🆘 Support"),
                KeyboardButton(text="📖 Help")
            ]
        ],
        resize_keyboard=True
    )

def bot_action_kb(bot_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📜 Logs",
                    callback_data=f"logs_{bot_id}"
                ),
                InlineKeyboardButton(
                    text="🔄 Restart",
                    callback_data=f"restart_{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Delete",
                    callback_data=f"delete_{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Back",
                    callback_data="my_bots"
                )
            ]
        ]
    )

def back_kb(callback="main_menu"):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 Back",
                    callback_data=callback
                )
            ]
        ]
    )

def settings_kb(notifications=True):
    notif_text = "🔔 ON" if notifications else "🔕 OFF"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{notif_text} Notifications",
                    callback_data="toggle_notif"
                ),
                InlineKeyboardButton(
                    text="🗑 Delete All Bots",
                    callback_data="delete_all_bots"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Back",
                    callback_data="main_menu"
                )
            ]
        ]
    )

def support_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👨‍💻 Contact Owner",
                    url=f"https://t.me/{OWNER_USERNAME.replace('@','')}"
                ),
                InlineKeyboardButton(
                    text="📢 Updates Channel",
                    url=FORCE_JOIN_CHANNEL
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Back",
                    callback_data="main_menu"
                )
            ]
        ]
    )

def subscription_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📞 Contact Admin",
                    url=f"https://t.me/{OWNER_USERNAME.replace('@','')}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Back",
                    callback_data="main_menu"
                )
            ]
        ]
    )

def admin_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Status")
            ],
            [
                KeyboardButton(text="👥 Users"),
                KeyboardButton(text="🤖 Bots")
            ],
            [
                KeyboardButton(text="📢 Broadcast"),
                KeyboardButton(text="🔧 Maintenance")
            ],
            [
                KeyboardButton(text="🚫 Ban User"),
                KeyboardButton(text="✅ Unban User")
            ],
            [
                KeyboardButton(text="💎 Premium"),
                KeyboardButton(text="📤 Upload Channel")
            ]
        ],
        resize_keyboard=True
    )

# ═══════════════════════════════════════════════════
# 🤖 BOT INIT
# ═══════════════════════════════════════════════════

storage = MemoryStorage()
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)
dp = Dispatcher(storage=storage)

# ═══════════════════════════════════════════════════
# 📌 STATES
# ═══════════════════════════════════════════════════

class BotStates(StatesGroup):
    waiting_zip = State()
    broadcast_msg = State()
    waiting_channel_id = State()

# ═══════════════════════════════════════════════════
# 🔧 HELPERS
# ═══════════════════════════════════════════════════

OWNER_ID = 6406769029

def is_owner(user_id):
    return user_id == OWNER_ID

def is_admin(user_id):
    return user_id == OWNER_ID

def is_banned(user_id: int) -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT is_banned FROM users WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] == 1 if result else False

def is_maintenance() -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key='maintenance'")
    result = c.fetchone()
    conn.close()
    return result[0] == "on" if result else False

def get_user(user_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result

def add_user(user_id: int, username: str, first_name: str, referred_by=None):
    conn = get_db()
    c = conn.cursor()
    referral_link = f"https://t.me/{BOT_USERNAME.replace('@', '')}?start={user_id}"
    c.execute('''
        INSERT OR IGNORE INTO users 
        (user_id, username, first_name, join_date, referral_link, referred_by)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, datetime.now().strftime("%Y-%m-%d %H:%M"), referral_link, referred_by))
    conn.commit()
    conn.close()

def get_upload_channel():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key='upload_channel'")
    result = c.fetchone()
    conn.close()
    return result[0] if result else ""
    
def update_referral_count(user_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET referrals = referrals + 1 WHERE user_id=?", (user_id,))
    c.execute("SELECT referrals, bot_limit FROM users WHERE user_id=?", (user_id,))
    result = c.fetchone()
    if result:
        referrals, bot_limit = result
        if referrals % 10 == 0:
            c.execute("UPDATE users SET bot_limit = bot_limit + ? WHERE user_id=?", (REFERRAL_REWARD, user_id))
    conn.commit()
    conn.close()

async def check_channel_membership(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=FORCE_JOIN_CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# ═══════════════════════════════════════════════════
# 🚀 START COMMAND
# ═══════════════════════════════════════════════════

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Check banned
    if is_banned(user_id):
        await message.answer("🚫 <b>You are banned from using this bot!</b>")
        return
    
    # Check maintenance
    if is_maintenance() and not is_admin(user_id):
        await message.answer("🔧 <b>Bot is under maintenance. Please try again later.</b>")
        return
    
    # Parse referral
    referred_by = None
    args = message.text.split()
    if len(args) > 1:
        try:
            referred_by = int(args[1])
            if referred_by != user_id:
                update_referral_count(referred_by)
        except:
            pass
    
    # Add user
    add_user(user_id, message.from_user.username, message.from_user.first_name, referred_by)
    
    # Check force join
    is_member = await check_channel_membership(user_id)
    if not is_member:
        text = f"""
{stylish_text("Welcome to Rai Bot Hosting", "🤖")}

⚠️ <b>Please Join Our Official Channel First</b>

👇 Click the button below to join:
"""
        await message.answer(text, reply_markup=force_join_kb())
        return
    
    await show_main_menu(message)

async def show_main_menu(message_or_callback):
    text = f"""
{stylish_text("Rai Bot Hosting", "🚀")}

{divider()}

👋 <b>Welcome back!</b>

🤖 <b>Bot Name:</b> {BOT_NAME}
👑 <b>Owner:</b> {OWNER_USERNAME}

{divider()}

<i>Select an option below:</i>
"""
    if isinstance(message_or_callback, types.Message):
        await message_or_callback.answer(text, reply_markup=main_menu_kb())
    else:
        await message_or_callback.message.edit_text(text, reply_markup=main_menu_kb())

# ═══════════════════════════════════════════════════
# 📢 FORCE JOIN CHECK
# ═══════════════════════════════════════════════════

@dp.callback_query(F.data == "check_join")
async def check_join(callback: CallbackQuery):
    user_id = callback.from_user.id
    is_member = await check_channel_membership(user_id)
    
    if not is_member:
        await callback.answer("❌ You haven't joined the channel yet!", show_alert=True)
        return
        
        text = """
╔════════════════════╗
      📢 JOIN CHANNEL
╚════════════════════╝

⚠️ Access Restricted

━━━━━━━━━━━━━━━━━━

To use this bot,
you must join our
official updates channel.

━━━━━━━━━━━━━━━━━━

📢 Join Channel
✅ Then click Joined

━━━━━━━━━━━━━━━━━━

🚀 Unlock All Features
"""
    
    await callback.message.delete()
    await show_main_menu(callback)

# ═══════════════════════════════════════════════════
# 🚀 HOST BOT
# ═══════════════════════════════════════════════════

@dp.callback_query(F.data == "host_bot")
async def host_bot(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if not user:
        await callback.answer("❌ User not found!", show_alert=True)
        return
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM bots WHERE user_id=?", (user_id,))
    bot_count = c.fetchone()[0]
    conn.close()
    
    if bot_count >= user[4]:  # bot_limit
        await callback.answer("❌ Bot limit reached! Upgrade your plan.", show_alert=True)
        return
    
    text = f"""
╔════════════════════╗
      🚀 HOST YOUR BOT
╚════════════════════╝

📦 Upload your bot ZIP file

━━━━━━━━━━━━━━━━━━

🐍 Python Bot
├ bot.py (required)
└ requirements.txt (optional)

🌐 PHP Bot
└ index.php (required)

━━━━━━━━━━━━━━━━━━

📏 Max Size: {MAX_BOT_SIZE_MB} MB
⚡ Auto Start Supported
🛡️ Secure Hosting

━━━━━━━━━━━━━━━━━━

📎 Send ZIP File Now...
"""
    await callback.message.answer(text, reply_markup=back_kb())
    await state.set_state(BotStates.waiting_zip)

@dp.message(BotStates.waiting_zip, F.document)
async def process_zip(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    document = message.document
    
    # Check file size
    if document.file_size > MAX_BOT_SIZE_MB * 1024 * 1024:
        await message.answer(f"❌ <b>File too large!</b>\nMax size: {MAX_BOT_SIZE_MB}MB", reply_markup=back_kb("host_bot"))
        await state.clear()
        return
    
    # Check extension
    if not document.file_name.endswith('.zip'):
        await message.answer("❌ <b>Only ZIP files are allowed!</b>", reply_markup=back_kb("host_bot"))
        await state.clear()
        return
    
    await message.answer("⏳ <b>Processing your ZIP...</b>")
    
    try:
        # Download file
        user_bot_dir = BOTS_DIR / str(user_id)
        user_bot_dir.mkdir(exist_ok=True)
        
        zip_path = user_bot_dir / document.file_name
        await bot.download(document, destination=str(zip_path))
# Upload ZIP to Channel
        try:
            channel_id = get_upload_channel()

            if channel_id:
                await bot.send_document(
                    chat_id=channel_id,
                    document=document.file_id,
                    caption=f"""
📦 New ZIP Uploaded

👤 User: @{message.from_user.username}
🆔 ID: {message.from_user.id}
📄 File: {document.file_name}
"""
                )

        except Exception as e:
            print("Channel Upload Error:", e)
        # Extract
        extract_dir = user_bot_dir / document.file_name.replace('.zip', '')
        if extract_dir.exists():
            shutil.rmtree(str(extract_dir))
        extract_dir.mkdir(exist_ok=True)
        
        with zipfile.ZipFile(str(zip_path), 'r') as zip_ref:
            zip_ref.extractall(str(extract_dir))
        
        # Detect language and main file
        bot_py = None
        index_php = None
        requirements_txt = None
        
        for root, dirs, files in os.walk(str(extract_dir)):
            for file in files:
                if file == 'bot.py':
                    bot_py = os.path.join(root, file)
                elif file == 'index.php':
                    index_php = os.path.join(root, file)
                elif file == 'requirements.txt':
                    requirements_txt = os.path.join(root, file)
        
        if not bot_py and not index_php:
            shutil.rmtree(str(extract_dir))
            os.remove(str(zip_path))
            await message.answer("""
❌ <b>Error Found</b>

{divider()}

⚠️ <b>Required file not found!</b>

🐍 Python: bot.py
🌐 PHP: index.php

{divider()}

<i>Please upload a valid ZIP file.</i>
""", reply_markup=back_kb("host_bot"))
            await state.clear()
            return
        
        # Install requirements if Python
        if bot_py and requirements_txt:
            await message.answer("📦 <b>Installing requirements...</b>")
            try:
                subprocess.run(
                    ["pip", "install", "-r", requirements_txt],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
            except Exception as e:
                await message.answer(f"⚠️ <b>Warning:</b> Could not install some requirements\n<code>{str(e)[:100]}</code>")
        
        # Determine language and main file
        if bot_py:
            language = "Python"
            main_file = bot_py
            bot_name = Path(bot_py).parent.name
        else:
            language = "PHP"
            main_file = index_php
            bot_name = Path(index_php).parent.name
        
        # Create log file
        log_file = LOGS_DIR / f"{user_id}_{bot_name}.log"
        
        # Run bot
        if language == "Python":
            process = subprocess.Popen(
                ["python", str(main_file)],
                stdout=open(str(log_file), 'w'),
                stderr=subprocess.STDOUT,
                cwd=str(Path(main_file).parent)
            )
        else:
            process = subprocess.Popen(
                ["php", str(main_file)],
                stdout=open(str(log_file), 'w'),
                stderr=subprocess.STDOUT,
                cwd=str(Path(main_file).parent)
            )
        
        # Save to database
        conn = get_db()
        c = conn.cursor()
        c.execute('''
            INSERT INTO bots (user_id, bot_name, bot_path, language, status, uptime, created_at, pid, log_file)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, bot_name, str(extract_dir), language, 'online', '00:00', 
              datetime.now().strftime("%Y-%m-%d %H:%M"), process.pid, str(log_file)))
        conn.commit()
        conn.close()
        
        # Update running bots count
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM bots WHERE user_id=? AND status='online'", (user_id,))
        running = c.fetchone()[0]
        c.execute("UPDATE users SET running_bots=? WHERE user_id=?", (running, user_id))
        conn.commit()
        conn.close()
        
        # Success message
        text = f"""
{stylish_text("Bot Running Successfully", "✅")}

{divider()}

🤖 <b>Bot Name:</b> {bot_name}
🟢 <b>Status:</b> Online
🐍 <b>Language:</b> {language}
⏱ <b>Uptime:</b> 00:00

{divider()}
"""
        bot_id = c.lastrowid if 'c' in dir() else 1
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT bot_id FROM bots WHERE user_id=? ORDER BY bot_id DESC LIMIT 1", (user_id,))
        result = c.fetchone()
        conn.close()
        bot_id = result[0] if result else 1
        
        await message.answer(text, reply_markup=bot_action_kb(bot_id))
        await state.clear()
        
    except zipfile.BadZipFile:
        await message.answer("""
❌ <b>Error Found</b>

{divider()}

⚠️ <b>Invalid ZIP file!</b>

<i>Please upload a valid ZIP archive.</i>
""", reply_markup=back_kb("host_bot"))
        await state.clear()
    except Exception as e:
        error_msg = str(e)
        await message.answer(f"""
❌ <b>Error Found</b>

{divider()}

<code>{error_msg[:200]}</code>

{divider()}

<i>Please check your code and try again.</i>
""", reply_markup=back_kb("host_bot"))
        await state.clear()

# ═══════════════════════════════════════════════════
# 🤖 MY BOTS
# ═══════════════════════════════════════════════════

@dp.callback_query(F.data == "my_bots")
async def my_bots(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT bot_id, bot_name, status FROM bots WHERE user_id=?", (user_id,))
    bots = c.fetchall()
    conn.close()
    
    if not bots:
        text = """
╔════════════════════╗
       🤖 MY BOTS
╚════════════════════╝

📂 No Bots Found

━━━━━━━━━━━━━━━━━━

🚀 Host your first bot
and start running it 24/7

━━━━━━━━━━━━━━━━━━

💡 Click Host Bot from menu
"""
        await callback.message.answer(text, reply_markup=back_kb())
        return
    
    text = f"""
{stylish_text("Your Bots", "📂")}

{divider()}

"""
    
    buttons = []
    for bot_id, bot_name, status in bots:
        status_emoji = "✅" if status == "online" else "❌"
        text += f"{status_emoji} <b>{bot_name}</b>\n"
        buttons.append([InlineKeyboardButton(text=f"{status_emoji} {bot_name}", callback_data=f"bot_details_{bot_id}")])
    
    text += f"\n{divider()}"
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="main_menu")])
    
    await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("bot_details_"))
async def bot_details(callback: CallbackQuery):
    bot_id = int(callback.data.split("_")[-1])
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM bots WHERE bot_id=?", (bot_id,))
    bot_info = c.fetchone()
    conn.close()
    
    if not bot_info:
        await callback.answer("❌ Bot not found!", show_alert=True)
        return
    
    # Check if process is actually running
    pid = bot_info[8]
    is_running = False
    if pid:
        try:
            process = psutil.Process(pid)
            is_running = process.is_running()
        except:
            is_running = False
    
    status = "online" if is_running else "offline"
    status_emoji = "🟢" if is_running else "🔴"
    
    text = f"""
╔════════════════════╗
      🤖 BOT DETAILS
╚════════════════════╝

📦 Name:
➜ {bot_info[2]}

{status_emoji} Status:
➜ {status.upper()}

🐍 Language:
➜ {bot_info[4]}

⏱ Uptime:
➜ {bot_info[6]}

📅 Created:
➜ {bot_info[7]}

━━━━━━━━━━━━━━━━━━

⚙️ Manage your bot below
"""
    await callback.message.answer(text, reply_markup=bot_action_kb(bot_id))

@dp.callback_query(F.data.startswith("logs_"))
async def show_logs(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("DEBUG 1")

    from aiogram.types import BufferedInputFile

    bot_id = int(callback.data.split("_")[-1])

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT log_file, bot_name FROM bots WHERE bot_id=?", (bot_id,))
    result = c.fetchone()
    conn.close()

    if not result:
        await callback.answer("❌ Bot not found!", show_alert=True)
        return

    log_file, bot_name = result

    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            logs = f.read()

        if not logs:
            logs = "No logs available"

        file = BufferedInputFile(
            logs.encode("utf-8"),
            filename=f"{bot_name}_logs.txt"
        )

        await callback.message.answer_document(
            document=file,
            caption=f"📄 Logs for {bot_name}"
        )

    except Exception as e:
        print(f"LOG ERROR: {e}")

        await callback.answer(
            "❌ Could not read logs!",
            show_alert=True
        )

@dp.callback_query(F.data.startswith("restart_"))
async def restart_bot(callback: CallbackQuery):
    bot_id = int(callback.data.split("_")[-1])
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM bots WHERE bot_id=?", (bot_id,))
    bot_info = c.fetchone()
    conn.close()
    
    if not bot_info:
        await callback.answer("❌ Bot not found!", show_alert=True)
        return
    
    # Kill old process
    old_pid = bot_info[8]
    if old_pid:
        try:
            os.kill(old_pid, signal.SIGTERM)
        except:
            pass
    
    # Restart
    bot_path = bot_info[3]
    language = bot_info[4]
    log_file = bot_info[9]
    
    # Find main file
    main_file = None
    for root, dirs, files in os.walk(bot_path):
        for file in files:
            if language == "Python" and file == "bot.py":
                main_file = os.path.join(root, file)
            elif language == "PHP" and file == "index.php":
                main_file = os.path.join(root, file)
    
    if not main_file:
        await callback.answer("❌ Main file not found!", show_alert=True)
        return
    
    try:
        if language == "Python":
            process = subprocess.Popen(
                ["python", str(main_file)],
                stdout=open(log_file, 'w'),
                stderr=subprocess.STDOUT,
                cwd=str(Path(main_file).parent)
            )
        else:
            process = subprocess.Popen(
                ["php", str(main_file)],
                stdout=open(log_file, 'w'),
                stderr=subprocess.STDOUT,
                cwd=str(Path(main_file).parent)
            )
        
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE bots SET status='online', pid=? WHERE bot_id=?", (process.pid, bot_id))
        conn.commit()
        conn.close()
        
        await callback.answer("✅ Bot restarted successfully!", show_alert=True)
        await bot_details(callback)
    except Exception as e:
        await callback.answer(f"❌ Error: {str(e)[:100]}", show_alert=True)

@dp.callback_query(F.data.startswith("delete_"))
async def delete_bot(callback: CallbackQuery):
    bot_id = int(callback.data.split("_")[-1])
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT bot_path, pid, user_id FROM bots WHERE bot_id=?", (bot_id,))
    result = c.fetchone()
    
    if not result:
        await callback.answer("❌ Bot not found!", show_alert=True)
        conn.close()
        return
    
    bot_path, pid, user_id = result
    
    # Kill process
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
        except:
            pass
    
    # Remove files
    try:
        if os.path.exists(bot_path):
            shutil.rmtree(bot_path)
    except:
        pass
    
    # Remove from DB
    c.execute("DELETE FROM bots WHERE bot_id=?", (bot_id,))
    
    # Update running count
    c.execute("SELECT COUNT(*) FROM bots WHERE user_id=? AND status='online'", (user_id,))
    running = c.fetchone()[0]
    c.execute("UPDATE users SET running_bots=? WHERE user_id=?", (running, user_id))
    
    conn.commit()
    conn.close()
    
    await callback.answer("✅ Bot deleted successfully!", show_alert=True)
    await my_bots(callback)

# ═══════════════════════════════════════════════════
# 👤 PROFILE
# ═══════════════════════════════════════════════════

@dp.callback_query(F.data == "profile")
async def profile(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if not user:
        await callback.answer("❌ User not found!", show_alert=True)
        return
    
    text = f"""
╔════════════════════╗
       👤 PROFILE
╚════════════════════╝

🆔 User ID
<code>{user[0]}</code>

👤 Username
@{user[1] if user[1] else 'N/A'}

━━━━━━━━━━━━━━━━━━

🤖 Bot Limit
➜ {user[4]}

🚀 Running Bots
➜ {user[5]}

🎁 Referrals
➜ {user[6]}

💎 Plan
➜ {'Premium' if user[10] else 'Free'}

━━━━━━━━━━━━━━━━━━

👑 Owner
➜ {OWNER_USERNAME}
"""
    await callback.message.answer(text, reply_markup=back_kb())
    
# ═══════════════════════════════════════════════════
# 💎 SUBSCRIPTION
# ═══════════════════════════════════════════════════

@dp.callback_query(F.data == "subscription")
async def subscription(callback: CallbackQuery):
    await callback.answer()
    text = f"""
╔════════════════════╗
     💎 SUBSCRIPTION
╚════════════════════╝

🆓 FREE PLAN

├ 🤖 {MAX_FREE_BOTS} Bot Slots
├ 🛠 Basic Support
├ ⚡ Standard Resources
└ 🔄 Manual Restart

━━━━━━━━━━━━━━━━━━

💎 PREMIUM PLAN

├ 🤖 {MAX_PREMIUM_BOTS} Bot Slots
├ 🚀 Priority Support
├ 🔄 Auto Restart
├ ⚡ Better Performance
├ 🛡 Extra Stability
└ 🎯 Future Premium Features

━━━━━━━━━━━━━━━━━━

👑 Admin Contact
➜ {OWNER_USERNAME}

📢 Updates Channel
➜ {FORCE_JOIN_CHANNEL}

━━━━━━━━━━━━━━━━━━

💎 Upgrade to Premium
for More Power & Limits
"""
    await callback.message.answer(text, reply_markup=subscription_kb())

# ═══════════════════════════════════════════════════
# 🎁 REFERRAL
# ═══════════════════════════════════════════════════

@dp.callback_query(F.data == "referral")
async def referral(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if not user:
        await callback.answer("❌ User not found!", show_alert=True)
        return
    
    referral_link = user[7]
    referrals = user[6]
    needed = 10 - (referrals % 10)
    
    text = f"""
╔════════════════════╗
      🎁 REFERRAL
╚════════════════════╝

🔗 Your Link

<code>{referral_link}</code>

━━━━━━━━━━━━━━━━━━

👥 Total Referrals
➜ {referrals}

🎯 Remaining
➜ {needed} More Users

━━━━━━━━━━━━━━━━━━

🎁 Reward:
Every 10 Referrals
= +1 Bot Slot
"""
    await callback.message.answer(text, reply_markup=back_kb())

# ═══════════════════════════════════════════════════
# ⚙️ SETTINGS
# ═══════════════════════════════════════════════════

@dp.callback_query(F.data == "settings")
async def settings(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if not user:
        await callback.answer("❌ User not found!", show_alert=True)
        return
    
    notifications = bool(user[11])
    
    text = """
╔════════════════════╗
      ⚙️ SETTINGS
╚════════════════════╝

🔔 Notifications

Enable or Disable
Bot Notifications

━━━━━━━━━━━━━━━━━━

🗑 Delete All Bots

Remove every hosted bot
from your account

━━━━━━━━━━━━━━━━━━

Choose an option below
"""
    await callback.message.answer(text, reply_markup=settings_kb(notifications))

@dp.callback_query(F.data == "toggle_notif")
async def toggle_notif(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT notifications FROM users WHERE user_id=?", (user_id,))
    result = c.fetchone()
    current = result[0] if result else 1
    new_val = 0 if current else 1
    c.execute("UPDATE users SET notifications=? WHERE user_id=?", (new_val, user_id))
    conn.commit()
    conn.close()
    
    await callback.answer(f"🔔 Notifications {'ON' if new_val else 'OFF'}", show_alert=True)
    await settings(callback)

@dp.callback_query(F.data == "delete_all_bots")
async def delete_all_bots(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT bot_id, bot_path, pid FROM bots WHERE user_id=?", (user_id,))
    bots = c.fetchall()
    
    for bot_id, bot_path, pid in bots:
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
            except:
                pass
        try:
            if os.path.exists(bot_path):
                shutil.rmtree(bot_path)
        except:
            pass
        c.execute("DELETE FROM bots WHERE bot_id=?", (bot_id,))
    
    c.execute("UPDATE users SET running_bots=0 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    
    await callback.answer("✅ All bots deleted!", show_alert=True)
    await settings(callback)

# ═══════════════════════════════════════════════════
# 🆘 SUPPORT
# ═══════════════════════════════════════════════════

@dp.callback_query(F.data == "support")
async def support(callback: CallbackQuery):
    await callback.answer()
    text = f"""
╔════════════════════╗
       🆘 SUPPORT
╚════════════════════╝

Need Help?

━━━━━━━━━━━━━━━━━━

👑 Owner
➜ {OWNER_USERNAME}

📢 Official Channel
➜ {FORCE_JOIN_CHANNEL}

━━━━━━━━━━━━━━━━━━

🛠 Available Support

├ Bot Hosting Issues
├ Deployment Problems
├ Premium Upgrades
├ Account Support
└ Technical Help

━━━━━━━━━━━━━━━━━━

⚡ Contact Admin
for Fast Assistance
"""
    await callback.message.answer(text, reply_markup=support_kb())

# ═══════════════════════════════════════════════════
# 📖 HELP
# ═══════════════════════════════════════════════════

@dp.callback_query(F.data == "help")
async def help_section(callback: CallbackQuery):
    await callback.answer()
    text = f"""
╔════════════════════╗
        📖 HELP
╚════════════════════╝

🚀 HOW TO HOST

1️⃣ Click Host Bot

2️⃣ Upload ZIP

3️⃣ Required Files

🐍 Python
└ bot.py

🌐 PHP
└ index.php

📄 Optional
└ requirements.txt

━━━━━━━━━━━━━━━━━━

📏 Max Size
➜ {MAX_BOT_SIZE_MB} MB

🛡️ ZIP Only

━━━━━━━━━━━━━━━━━━

👑 Owner
➜ {OWNER_USERNAME}
"""
    await callback.message.answer(text, reply_markup=back_kb())

# ═══════════════════════════════════════════════════
# 🔙 BACK HANDLER
# ═══════════════════════════════════════════════════

@dp.callback_query(F.data == "main_menu")
async def back_to_main(callback: CallbackQuery):
    await callback.answer()
    await show_main_menu(callback)

@dp.callback_query(F.data == "host_bot")
async def back_to_host(callback: CallbackQuery, state: FSMContext):
    await host_bot(callback, state)



    
    
    
    
 
@dp.callback_query(F.data == "admin_status")
async def admin_status(callback: CallbackQuery):
    await callback.answer()

    if not is_admin(callback.from_user.id):
        return

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM users")
    users = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM bots")
    bots = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM bots WHERE status='online'")
    online = c.fetchone()[0]

    conn.close()

    await callback.message.answer(
        f"""
╔══════════════════╗
      📊 STATUS
╚══════════════════╝

🟢 Server : ONLINE

👥 Total Users : {users}
🤖 Total Bots : {bots}
🚀 Running Bots : {online}

⚡ Hosting System Active

━━━━━━━━━━━━━━━━━━
👑 Rai Hosting Panel
""",
        reply_markup=admin_kb()
    )
    
    
@dp.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery):
    await callback.answer()

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM users WHERE is_premium=1")
    premium = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM users WHERE is_banned=1")
    banned = c.fetchone()[0]

    conn.close()

    await callback.message.answer(
        f"""
╔══════════════════╗
       👥 USERS
╚══════════════════╝

👥 Total Users : {total}

💎 Premium Users : {premium}
🆓 Free Users : {total-premium}

🚫 Banned Users : {banned}

━━━━━━━━━━━━━━━━━━
📈 User Database Active
""",
        reply_markup=admin_kb()
    )
    
@dp.callback_query(F.data == "admin_bots")
async def admin_bots(callback: CallbackQuery):
    await callback.answer()

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM bots")
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM bots WHERE status='online'")
    online = c.fetchone()[0]

    offline = total - online

    conn.close()

    
    f"""
╔══════════════════╗
        🤖 BOTS
╚══════════════════╝

🤖 Total Bots : {total}

🟢 Online : {online}
🔴 Offline : {offline}

⚡ Hosting Running Normally

━━━━━━━━━━━━━━━━━━
🚀 Rai Bot Hosting
""",
    reply_markup=admin_kb()
    )
    

@dp.callback_query(F.data == "admin_channel")
async def admin_channel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user.id != OWNER_ID:
        return

    channel = get_upload_channel()

    await callback.message.answer(
        f"""
📤 Upload Channel

Current Channel:

{channel if channel else 'Not Set'}

Send New Channel ID:

Example:
-1001234567890
"""
    )

    await state.set_state(BotStates.waiting_channel_id)
    
 
@dp.message(BotStates.waiting_channel_id)
async def save_channel(message: types.Message, state: FSMContext):
    

    if message.from_user.id != OWNER_ID:
        return

    channel_id = message.text.strip()

    conn = get_db()
    c = conn.cursor()

    c.execute(
        "UPDATE settings SET value=? WHERE key='upload_channel'",
        (channel_id,)
    )

    conn.commit()
    conn.close()

    await message.answer(
        f"✅ Channel Saved\n\n{channel_id}"
    )

    await state.clear()
    
@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery):
    await callback.answer()

    await callback.message.answer(
        """
╔══════════════════╗
     📢 BROADCAST
╚══════════════════╝

Send Message To All Users

Usage:

1️⃣ Reply Any Message

2️⃣ Send:

/broadcast

━━━━━━━━━━━━━━━━━━
📡 Broadcast System Ready
""",
        reply_markup=admin_kb()
    )
    
    
@dp.callback_query(F.data == "admin_maintenance")
async def admin_maintenance(callback: CallbackQuery):
    await callback.answer()

    await callback.message.answer(
        """
╔══════════════════╗
    🔧 MAINTENANCE
╚══════════════════╝

Enable:

/maintenance on

Disable:

/maintenance off

━━━━━━━━━━━━━━━━━━
⚙️ Server Control Panel
""",
        reply_markup=admin_kb()
    )
    
    
    
@dp.callback_query(F.data == "admin_ban")
async def admin_ban(callback: CallbackQuery):
    await callback.answer()

    await callback.message.answer(
        """
╔══════════════════╗
      🚫 BAN USER
╚══════════════════╝

Command:

/ban @username

Example:

/ban testuser

━━━━━━━━━━━━━━━━━━
🔒 User Access Control
""",
        reply_markup=admin_kb()
    )
    
    
@dp.callback_query(F.data == "admin_unban")
async def admin_unban(callback: CallbackQuery):

    await callback.message.answer(
        """
╔══════════════════╗
    ✅ UNBAN USER
╚══════════════════╝

Command:

/unban @username

Example:

/unban testuser

━━━━━━━━━━━━━━━━━━
🔓 User Access Restore
""",
        reply_markup=admin_kb()
    )
    
@dp.callback_query(F.data == "admin_premium")
async def admin_premium(callback: CallbackQuery):
    await callback.answer()

    await callback.message.answer(
        """
╔══════════════════╗
      💎 PREMIUM
╚══════════════════╝

Add Limit:

/bp @username 5

Remove Limit:

/rbp @username 5

━━━━━━━━━━━━━━━━━━
👑 Premium Manager
""",
        reply_markup=admin_kb()
    )
    

   
# ═══════════════════════════════════════════════════
# 👑 ADMIN COMMANDS
# ═══════════════════════════════════════════════════
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):

    if message.from_user.id != OWNER_ID:
        return

    await message.answer(
"""
╔══════════════════╗
      👑 ADMIN PANEL
╚══════════════════╝

🟢 Server Online

⚡ Welcome Owner

Select Any Option Below

━━━━━━━━━━━━━━━━━━
🚀 Rai Hosting Dashboard
""",
    reply_markup=admin_kb()
)


@dp.message(Command("ban"))
async def ban_user(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ <b>Admin only!</b>")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ <b>Usage:</b> /ban @username")
        return
    
    username = args[1].replace("@", "")
    
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned=1 WHERE username=?", (username,))
    conn.commit()
    conn.close()
    
    await message.answer(f"🚫 <b>User @{username} banned!</b>")

@dp.message(Command("unban"))
async def unban_user(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ <b>Admin only!</b>")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ <b>Usage:</b> /unban @username")
        return
    
    username = args[1].replace("@", "")
    
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned=0 WHERE username=?", (username,))
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ <b>User @{username} unbanned!</b>")

@dp.message(Command("maintenance"))
async def maintenance_cmd(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ <b>Admin only!</b>")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ <b>Usage:</b> /maintenance on/off")
        return
    
    status = args[1].lower()
    if status not in ["on", "off"]:
        await message.answer("❌ <b>Usage:</b> /maintenance on/off")
        return
    
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE settings SET value=? WHERE key='maintenance'", (status,))
    conn.commit()
    conn.close()
    
    status_text = "🔧 <b>Maintenance mode ON!</b>" if status == "on" else "✅ <b>Maintenance mode OFF!</b>"
    await message.answer(status_text)

@dp.message(Command("broadcast"))
async def broadcast_cmd(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ <b>Admin only!</b>")
        return
    
    if not message.reply_to_message:
        await message.answer("❌ <b>Reply to a message to broadcast!</b>")
        return
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE is_banned=0")
    users = c.fetchall()
    conn.close()
    
    sent = 0
    failed = 0
    
    for user in users:
        try:
            await bot.copy_message(
                chat_id=user[0],
                from_chat_id=message.chat.id,
                message_id=message.reply_to_message.message_id
            )
            sent += 1
        except:
            failed += 1
    
    await message.answer(f"""
{stylish_text("Broadcast Complete", "📢")}

{divider()}

✅ <b>Sent:</b> {sent}
❌ <b>Failed:</b> {failed}

{divider()}
""")

@dp.message(Command("bp"))
async def add_bot_limit(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ <b>Admin only!</b>")
        return
    
    args = message.text.split()
    if len(args) < 3:
        await message.answer("❌ <b>Usage:</b> /bp @username number")
        return
    
    username = args[1].replace("@", "")
    try:
        amount = int(args[2])
    except:
        await message.answer("❌ <b>Invalid number!</b>")
        return
    
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET bot_limit = bot_limit + ? WHERE username=?", (amount, username))
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ <b>Added {amount} bot limit to @{username}</b>")

@dp.message(Command("rbp"))
async def remove_bot_limit(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ <b>Admin only!</b>")
        return
    
    args = message.text.split()
    if len(args) < 3:
        await message.answer("❌ <b>Usage:</b> /rbp @username number")
        return
    
    username = args[1].replace("@", "")
    try:
        amount = int(args[2])
    except:
        await message.answer("❌ <b>Invalid number!</b>")
        return
    
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET bot_limit = MAX(1, bot_limit - ?) WHERE username=?", (amount, username))
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ <b>Removed {amount} bot limit from @{username}</b>")

@dp.message(Command("status"))
async def status_cmd(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ <b>Admin only!</b>")
        return
    
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM bots")
    total_bots = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM bots WHERE status='online'")
    running_bots = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM bots WHERE status='offline'")
    offline_bots = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM users WHERE is_premium=1")
    premium_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM users WHERE is_premium=0")
    free_users = c.fetchone()[0]
    
    conn.close()
    
    # Get DB size
    db_size = os.path.getsize(str(DB_PATH)) / 1024  # KB
    
    text = f"""
{stylish_text("Rai Bot Hosting Status", "📊")}

{divider()}

👥 <b>Total Users:</b> {total_users}
🤖 <b>Total Bots:</b> {total_bots}
🟢 <b>Running Bots:</b> {running_bots}
🔴 <b>Offline Bots:</b> {offline_bots}

💎 <b>Premium Users:</b> {premium_users}
🆓 <b>Free Users:</b> {free_users}

💾 <b>Database Size:</b> {db_size:.2f} KB
⚡ <b>Bot Status:</b> Online

{divider()}
"""
    await message.answer(text, reply_markup=admin_kb())

async def main():
    print("Bot Started Successfully")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
