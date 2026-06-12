

import asyncio
import sqlite3
import os
import zipfile
import shutil
import subprocess
import signal
import time
import json
# import psutil
from datetime import datetime, timedelta
from pathlib import Path
from aiogram.client.default import DefaultBotProperties
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile

from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError

# ═══════════════════════════════════════════════════
# ⚙️ CONFIGURATION
# ═══════════════════════════════════════════════════

BOT_TOKEN = "8965239565:AAEgN9DyGAFHOoYRWWiwseT9-MpkvmUFnbY"
OWNER_USERNAME = "@Subhash_Anuragi_RAI"
OWNER_ID = "6406769029"
FORCE_JOIN_CHANNEL = "https://t.me/raiaddaarmys"
FORCE_JOIN_CHANNEL_ID = "@raiaddaarmys"
BOT_NAME = "Rai Bot Hosting"
BOT_USERNAME = "@RAIBOTHOSTING_bot"

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
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Join Channel", url=FORCE_JOIN_CHANNEL)],
        [InlineKeyboardButton(text="✅ Joined", callback_data="check_join")]
    ])

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Host Bot", callback_data="host_bot"),
         InlineKeyboardButton(text="🤖 My Bots", callback_data="my_bots")],
        [InlineKeyboardButton(text="👤 Profile", callback_data="profile"),
         InlineKeyboardButton(text="💎 Subscription", callback_data="subscription")],
        [InlineKeyboardButton(text="🎁 Referral", callback_data="referral"),
         InlineKeyboardButton(text="⚙️ Settings", callback_data="settings")],
        [InlineKeyboardButton(text="🆘 Support", callback_data="support"),
         InlineKeyboardButton(text="📖 Help", callback_data="help")]
    ])

def bot_action_kb(bot_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Logs", callback_data=f"logs_{bot_id}"),
         InlineKeyboardButton(text="🔄 Restart", callback_data=f"restart_{bot_id}")],
        [InlineKeyboardButton(text="❌ Delete", callback_data=f"delete_{bot_id}")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="my_bots")]
    ])

def back_kb(callback="main_menu"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back", callback_data=callback)]
    ])

def settings_kb(notifications=True):
    notif_text = "🔔 ON" if notifications else "🔕 OFF"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{notif_text} Notifications", callback_data="toggle_notif")],
        [InlineKeyboardButton(text="🗑 Delete All Bots", callback_data="delete_all_bots")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="main_menu")]
    ])

def support_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍💻 Contact Owner", url=f"https://t.me/{OWNER_USERNAME.replace('@', '')}")],
        [InlineKeyboardButton(text="📢 Updates Channel", url=FORCE_JOIN_CHANNEL)],
        [InlineKeyboardButton(text="🔙 Back", callback_data="main_menu")]
    ])

def subscription_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Contact Admin", url=f"https://t.me/{OWNER_USERNAME.replace('@', '')}")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="main_menu")]
    ])

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Status", callback_data="admin_status")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="main_menu")]
    ])

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

# ═══════════════════════════════════════════════════
# 🔧 HELPERS
# ═══════════════════════════════════════════════════

def is_owner(user_id: int) -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key='owner_id'")
    result = c.fetchone()
    conn.close()
    if result and result[0]:
        return int(result[0]) == user_id
    return False

def is_admin(user_id: int) -> bool:
    return is_owner(user_id)

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
{stylish_text("Host Your Bot", "📦")}

{divider()}

🐍 <b>Python Bot:</b>
   • bot.py required
   • requirements.txt optional

🌐 <b>PHP Bot:</b>
   • index.php required

⚡ <b>Upload ZIP to start hosting</b>

{divider()}

📎 <i>Send your ZIP file now...</i>
"""
    await callback.message.edit_text(text, reply_markup=back_kb())
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
        text = f"""
{stylish_text("Your Bots", "📂")}

{divider()}

😔 <b>No bots hosted yet!</b>

🚀 <i>Click "Host Bot" to get started.</i>

{divider()}
"""
        await callback.message.edit_text(text, reply_markup=back_kb())
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
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

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
{stylish_text("Bot Details", "🤖")}

{divider()}

🤖 <b>Bot Name:</b> {bot_info[2]}
{status_emoji} <b>Status:</b> {status.upper()}
🐍 <b>Language:</b> {bot_info[4]}
⏱ <b>Uptime:</b> {bot_info[6]}
📅 <b>Created:</b> {bot_info[7]}

{divider()}
"""
    await callback.message.edit_text(text, reply_markup=bot_action_kb(bot_id))

@dp.callback_query(F.data.startswith("logs_"))
@dp.callback_query(F.data.startswith("logs_"))
async def show_logs(callback: CallbackQuery):
    await callback.answer()

    import io

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
    print(f"LOG FILE: {log_file}")

    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            logs = f.read()

        if not logs:
            logs = "No logs available"

        log_buffer = io.BytesIO(logs.encode())
        log_buffer.name = f"{bot_name}_logs.txt"

        await callback.message.answer_document(
            document=log_buffer,
            caption=f"📄 Logs for {bot_name}"
        )

    except Exception as e:
        await callback.answer(
            f"❌ Could not read logs!\n{e}",
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
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if not user:
        await callback.answer("❌ User not found!", show_alert=True)
        return
    
    text = f"""
{stylish_text("Your Profile", "👤")}

{divider()}

👤 <b>Username:</b> @{user[1] if user[1] else 'N/A'}
🆔 <b>Chat ID:</b> <code>{user[0]}</code>

{divider()}

🤖 <b>Bot Limit:</b> {user[4]}
🚀 <b>Running Bots:</b> {user[5]}

🎁 <b>Referrals:</b> {user[6]}
💎 <b>Plan:</b> {'Premium' if user[10] else 'Free'}

{divider()}

👑 <b>Owner:</b> {OWNER_USERNAME}
"""
    await callback.message.edit_text(text, reply_markup=back_kb())

# ═══════════════════════════════════════════════════
# 💎 SUBSCRIPTION
# ═══════════════════════════════════════════════════

@dp.callback_query(F.data == "subscription")
async def subscription(callback: CallbackQuery):
    text = f"""
{stylish_text("Subscription Plans", "💎")}

{divider()}

🆓 <b>Free Plan</b>
   • {MAX_FREE_BOTS} Bot Limit
   • Basic Support

💎 <b>Premium Plan</b>
   • {MAX_PREMIUM_BOTS} Bot Limit
   • Priority Support
   • Auto Restart

{divider()}

👑 <b>Owner:</b> {OWNER_USERNAME}
📞 <b>Contact for Premium</b>

{divider()}
"""
    await callback.message.edit_text(text, reply_markup=subscription_kb())

# ═══════════════════════════════════════════════════
# 🎁 REFERRAL
# ═══════════════════════════════════════════════════

@dp.callback_query(F.data == "referral")
async def referral(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if not user:
        await callback.answer("❌ User not found!", show_alert=True)
        return
    
    referral_link = user[7]
    referrals = user[6]
    needed = 10 - (referrals % 10)
    
    text = f"""
{stylish_text("Referral System", "🎁")}

{divider()}

🔗 <b>Your Referral Link:</b>
<code>{referral_link}</code>

👥 <b>Total Referrals:</b> {referrals}
🎉 <b>Need {needed} more for +1 Bot Slot</b>

{divider()}

📌 <i>Share your link with friends!</i>
<i>Every 10 referrals = +1 Bot Limit</i>

{divider()}
"""
    await callback.message.edit_text(text, reply_markup=back_kb())

# ═══════════════════════════════════════════════════
# ⚙️ SETTINGS
# ═══════════════════════════════════════════════════

@dp.callback_query(F.data == "settings")
async def settings(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if not user:
        await callback.answer("❌ User not found!", show_alert=True)
        return
    
    notifications = bool(user[11])
    
    text = f"""
{stylish_text("Settings", "⚙️")}

{divider()}

<i>Manage your preferences:</i>

{divider()}
"""
    await callback.message.edit_text(text, reply_markup=settings_kb(notifications))

@dp.callback_query(F.data == "toggle_notif")
async def toggle_notif(callback: CallbackQuery):
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
    text = f"""
{stylish_text("Support Center", "🆘")}

{divider()}

<i>Need help? Contact us!</i>

{divider()}

👑 <b>Owner:</b> {OWNER_USERNAME}
📢 <b>Channel:</b> {FORCE_JOIN_CHANNEL}

{divider()}
"""
    await callback.message.edit_text(text, reply_markup=support_kb())

# ═══════════════════════════════════════════════════
# 📖 HELP
# ═══════════════════════════════════════════════════

@dp.callback_query(F.data == "help")
async def help_section(callback: CallbackQuery):
    text = f"""
{stylish_text("Help Center", "📖")}

{divider()}

<b>🚀 How to Host a Bot:</b>

1️⃣ Click "🚀 Host Bot"
2️⃣ Upload your ZIP file
3️⃣ Must include:
   • 🐍 Python: bot.py
   • 🌐 PHP: index.php
   • 📄 requirements.txt (optional)

<b>⚠️ Important:</b>
• Max file size: {MAX_BOT_SIZE_MB}MB
• ZIP format only
• No dangerous files

<b>📋 Commands:</b>
/start - Main menu
/help - This message

{divider()}

👑 <b>Owner:</b> {OWNER_USERNAME}
"""
    await callback.message.edit_text(text, reply_markup=back_kb())

# ═══════════════════════════════════════════════════
# 🔙 BACK HANDLER
# ═══════════════════════════════════════════════════

@dp.callback_query(F.data == "main_menu")
async def back_to_main(callback: CallbackQuery):
    await show_main_menu(callback)

@dp.callback_query(F.data == "host_bot")
async def back_to_host(callback: CallbackQuery, state: FSMContext):
    await host_bot(callback, state)

# ═══════════════════════════════════════════════════
# 👑 ADMIN COMMANDS
# ═══════════════════════════════════════════════════

@dp.message(Command("setowner"))
async def set_owner(message: types.Message):
    # First user to run this becomes owner
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key='owner_id'")
    result = c.fetchone()
    
    if not result or not result[0]:
        c.execute("UPDATE settings SET value=? WHERE key='owner_id'", (str(message.from_user.id),))
        conn.commit()
        conn.close()
        await message.answer(f"✅ <b>You are now the owner!</b>\n\n👑 Owner ID: <code>{message.from_user.id}</code>")
    else:
        conn.close()
        if is_owner(message.from_user.id):
            await message.answer("👑 <b>You are already the owner!</b>")
        else:
            await message.answer("❌ <b>Owner already set!</b>")

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
