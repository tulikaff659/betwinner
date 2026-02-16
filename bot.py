import asyncio
import random
import sqlite3
import logging
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Logging sozlamalari
logging.basicConfig(level=logging.INFO)

# ============= KONFIGURATSIYA =============
# Railway environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "123456789").split(",") if id.strip()]
APK_URL = os.getenv("APK_URL", "https://example.com/app.apk")

# Ma'lumotlar bazasi uchun papka yaratish
DB_DIR = "/data" if os.path.exists("/data") else os.getcwd()
DATABASE_FILE = os.path.join(DB_DIR, "apple_fortune.db")

logging.info(f"📁 Ma'lumotlar bazasi joylashuvi: {DATABASE_FILE}")

# ============= MA'LUMOTLAR BAZASI =============
def init_database():
    """Ma'lumotlar bazasini yaratish va jadvallarni sozlash"""
    global conn, cursor
    
    try:
        conn = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
        cursor = conn.cursor()
        
        # Bazani yaratish
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_date TIMESTAMP,
            balance INTEGER DEFAULT 0,
            referrer_id INTEGER,
            promo_used BOOLEAN DEFAULT FALSE,
            apk_access BOOLEAN DEFAULT FALSE
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            referred_id INTEGER,
            date TIMESTAMP,
            bonus_given BOOLEAN DEFAULT FALSE
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            game_type TEXT,
            signal_data TEXT,
            created_at TIMESTAMP
        )
        ''')
        
        conn.commit()
        logging.info("✅ Ma'lumotlar bazasi muvaffaqiyatli yaratildi")
        
    except Exception as e:
        logging.error(f"❌ Ma'lumotlar bazasini yaratishda xatolik: {e}")
        raise

# Bazani ishga tushirish
init_database()

# ============= FSM HOLATLARI =============
class SignalStates(StatesGroup):
    waiting_for_bet_id = State()
    waiting_for_game_start = State()
    waiting_for_game_continue = State()

class AdminStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_apk_url = State()
    waiting_for_balance_amount = State()
    waiting_for_remove_apk = State()

# ============= YORDAMCHI FUNKSIYALAR =============
def generate_game_row():
    """Random olma qatorini yaratish"""
    apples = ["❓", "❓", "❓", "❓", "🍎"]  # 4 sirli, 1 butun olma
    random.shuffle(apples)
    return apples

def generate_game_field(rows=4):
    """O'yin maydonini yaratish"""
    field = []
    for i in range(rows):
        row = generate_game_row()
        field.append(row)
    return field

def format_game_field(field):
    """O'yin maydonini matn ko'rinishiga o'tkazish"""
    result = "🎰 *APPLE OF FORTUNE* 🎰\n\n"
    
    for i, row in enumerate(field):
        row_text = " ".join(row)
        result += f"`{row_text}`\n"
    
    result += "\n⚡️ Qatorlarni o'zgartirish uchun pastdagi tugmani bosing!"
    return result

def check_bet_id(bet_id):
    """Bet ID ni tekshirish (9-12 raqam)"""
    if bet_id and bet_id.isdigit() and 9 <= len(bet_id) <= 12:
        return True
    return False

def generate_referral_link(bot_username, user_id):
    """Referal link yaratish"""
    return f"https://t.me/{bot_username}?start=ref_{user_id}"

# ============= DATABASE FUNKSIYALARI =============
def add_user(user_id, username, first_name, referrer_id=None):
    """Yangi foydalanuvchi qo'shish"""
    try:
        cursor.execute(
            "INSERT INTO users (user_id, username, first_name, joined_date, referrer_id) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, first_name, datetime.now(), referrer_id)
        )
        conn.commit()
        return True
    except Exception as e:
        logging.error(f"Error adding user: {e}")
        return False

def get_user(user_id):
    """Foydalanuvchi ma'lumotlarini olish"""
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    return cursor.fetchone()

def update_balance(user_id, amount):
    """Balansni yangilash"""
    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (amount, user_id)
    )
    conn.commit()

def use_promo(user_id):
    """Promokodni ishlatish"""
    cursor.execute(
        "UPDATE users SET promo_used = TRUE, balance = balance + 10, apk_access = TRUE WHERE user_id = ?",
        (user_id,)
    )
    conn.commit()
    
    # Referalga bonus
    cursor.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
    referrer = cursor.fetchone()
    
    if referrer and referrer[0]:
        update_balance(referrer[0], 3)
        cursor.execute(
            "UPDATE referrals SET bonus_given = TRUE WHERE user_id = ? AND referred_id = ?",
            (referrer[0], user_id)
        )
        conn.commit()

def add_referral(user_id, referred_id):
    """Referal qo'shish"""
    try:
        cursor.execute(
            "INSERT INTO referrals (user_id, referred_id, date) VALUES (?, ?, ?)",
            (user_id, referred_id, datetime.now())
        )
        conn.commit()
        return True
    except:
        return False

def get_referrals_count(user_id):
    """Referallar sonini olish"""
    cursor.execute(
        "SELECT COUNT(*) FROM referrals WHERE user_id = ? AND bonus_given = 1",
        (user_id,)
    )
    return cursor.fetchone()[0]

def set_apk_access(user_id, access):
    """APK huquqini sozlash"""
    cursor.execute(
        "UPDATE users SET apk_access = ? WHERE user_id = ?",
        (access, user_id)
    )
    conn.commit()

def get_stats():
    """Statistika olish"""
    stats = {}
    
    cursor.execute("SELECT COUNT(*) FROM users")
    stats['total_users'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(balance) FROM users")
    stats['total_balance'] = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(*) FROM referrals")
    stats['total_refs'] = cursor.fetchone()[0]
    
    return stats

# ============= KLAVIATURALAR =============
def main_menu_keyboard():
    """Asosiy menyu"""
    kb = InlineKeyboardBuilder()
    kb.button(text="🎮 Signal olish", callback_data="get_signal")
    kb.button(text="💰 Balans", callback_data="check_balance")
    kb.button(text="👥 Referallar", callback_data="referrals")
    kb.button(text="📱 APK yuklash", callback_data="download_apk")
    kb.button(text="ℹ️ Yordam", callback_data="help")
    kb.adjust(2)
    return kb.as_markup()

def game_control_keyboard():
    """O'yin boshqaruvi"""
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Keyingi qator", callback_data="next_row")
    kb.button(text="⏹️ O'yinni tugatish", callback_data="end_game")
    kb.button(text="🏠 Asosiy menyu", callback_data="main_menu")
    kb.adjust(1, 2)
    return kb.as_markup()

def admin_panel_keyboard():
    """Admin paneli"""
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Statistika", callback_data="admin_stats")
    kb.button(text="👤 Foydalanuvchi", callback_data="admin_user")
    kb.button(text="🔗 APK qo'shish", callback_data="admin_add_apk")
    kb.button(text="❌ APK o'chirish", callback_data="admin_remove_apk")
    kb.button(text="💰 Ball berish", callback_data="admin_add_balance")
    kb.button(text="🏠 Chiqish", callback_data="main_menu")
    kb.adjust(2)
    return kb.as_markup()

def back_button(callback_data="main_menu"):
    """Orqaga tugmasi"""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Orqaga", callback_data=callback_data)]]
    )

# ============= BOTNI ISHGA TUSHIRISH =============
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ============= HANDLERLAR =============
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    first_name = message.from_user.first_name
    
    # Referal tekshirish
    referrer_id = None
    if len(message.text.split()) > 1:
        ref_param = message.text.split()[1]
        if ref_param.startswith("ref_"):
            try:
                referrer_id = int(ref_param.replace("ref_", ""))
                if referrer_id == user_id:
                    referrer_id = None  # O'ziga o'zi referal bo'lmasligi
            except:
                pass
    
    # Foydalanuvchini tekshirish
    user = get_user(user_id)
    if not user:
        add_user(user_id, username, first_name, referrer_id)
        if referrer_id:
            add_referral(referrer_id, user_id)
    
    welcome_text = f"👋 Assalomu alaykum, {first_name}!\n\n"
    welcome_text += "🎮 Apple of Fortune Signal botiga xush kelibsiz!\n\n"
    welcome_text += "📝 Ro'yxatdan o'tish uchun: SIGNAL7\n\n"
    welcome_text += "👇 Quyidagi menyudan tanlang:"
    
    await message.answer(welcome_text, reply_markup=main_menu_keyboard())

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        await message.answer("🔐 Admin panel", reply_markup=admin_panel_keyboard())
    else:
        await message.answer("🚫 Siz admin emassiz!")

# Promokod handler
@dp.message(lambda message: message.text and "SIGNAL7" in message.text.upper())
async def use_promocode(message: types.Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if user and not user[6]:  # promo_used = False
        use_promo(user_id)
        
        await message.answer(
            "✅ *SIGNAL7 promokodi muvaffaqiyatli faollashtirildi!*\n\n"
            "💰 Hisobingizga 10 ball qo'shildi!\n"
            "📱 APK yuklash huquqi berildi!",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    else:
        await message.answer(
            "❌ Siz allaqachon promokodni ishlatgansiz!",
            reply_markup=main_menu_keyboard()
        )

# ============= ASOSIY MENYU CALLBACKLARI =============
@dp.callback_query(F.data == "get_signal")
async def get_signal(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    
    user = get_user(callback.from_user.id)
    if user and user[4] >= 1:  # balance >= 1
        await state.set_state(SignalStates.waiting_for_bet_id)
        await callback.message.edit_text(
            "🎫 Iltimos, Betwinner ID raqamingizni kiriting:\n\n"
            "🔢 Raqam 9 dan 12 gacha xonadan iborat bo'lishi kerak.",
            reply_markup=back_button()
        )
    else:
        await callback.message.edit_text(
            "❌ Sizda yetarli ball mavjud emas!\n\n"
            "💰 Ball to'plash uchun do'stlaringizni taklif qiling!",
            reply_markup=main_menu_keyboard()
        )

@dp.callback_query(F.data == "check_balance")
async def check_balance(callback: types.CallbackQuery):
    await callback.answer()
    
    user = get_user(callback.from_user.id)
    if user:
        await callback.message.edit_text(
            f"💰 Sizning balansingiz: *{user[4]} ball*",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )

@dp.callback_query(F.data == "referrals")
async def referrals_menu(callback: types.CallbackQuery):
    await callback.answer()
    
    count = get_referrals_count(callback.from_user.id)
    bot_username = (await bot.get_me()).username
    link = generate_referral_link(bot_username, callback.from_user.id)
    
    text = f"👥 *Sizning referallaringiz*\n\n"
    text += f"📊 Taklif qilganlar: *{count}*\n"
    text += f"💰 Umumiy daromad: *{count * 3} ball*\n\n"
    text += f"🔗 Sizning referal linkingiz:\n`{link}`"
    
    kb = InlineKeyboardBuilder()
    kb.button(text="📢 Ulashish", switch_inline_query=f"Ro'yxatdan o'tish: {link}")
    kb.button(text="🏠 Asosiy menyu", callback_data="main_menu")
    kb.adjust(1)
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=kb.as_markup()
    )

@dp.callback_query(F.data == "download_apk")
async def download_apk(callback: types.CallbackQuery):
    await callback.answer()
    
    user = get_user(callback.from_user.id)
    if user and user[7]:  # apk_access = True
        kb = InlineKeyboardBuilder()
        kb.button(text="📱 APK yuklash", url=APK_URL)
        kb.button(text="🏠 Asosiy menyu", callback_data="main_menu")
        kb.adjust(1)
        
        await callback.message.edit_text(
            "📱 *Apple of Fortune APK*\n\n"
            "Quyidagi tugma orqali ilovani yuklab oling:",
            parse_mode="Markdown",
            reply_markup=kb.as_markup()
        )
    else:
        await callback.message.edit_text(
            "❌ Sizda APK yuklash uchun ruxsat yo'q!\n\n"
            "SIGNAL7 promokodi orqali ro'yxatdan o'ting!",
            reply_markup=main_menu_keyboard()
        )

@dp.callback_query(F.data == "help")
async def help_menu(callback: types.CallbackQuery):
    await callback.answer()
    
    text = "ℹ️ *Yordam*\n\n"
    text += "🎮 *Apple of Fortune Signal Bot*\n\n"
    text += "📌 *Qanday ishlaydi?*\n"
    text += "1. SIGNAL7 promokodi orqali ro'yxatdan o'ting\n"
    text += "2. Do'stlaringizni taklif qilib ball to'plang\n"
    text += "3. Ballar evaziga signallarni oling\n"
    text += "4. Betwinner ID kiriting va o'yinni boshlang\n\n"
    text += "📊 *Ball to'plash:*\n"
    text += "• Har bir referal uchun: 3 ball\n"
    text += "• SIGNAL7 promokodi: 10 ball"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

@dp.callback_query(F.data == "main_menu")
async def return_to_main(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    
    await callback.message.edit_text(
        "🏠 Asosiy menyu",
        reply_markup=main_menu_keyboard()
    )

# ============= SIGNAL OLISH =============
@dp.message(SignalStates.waiting_for_bet_id)
async def process_bet_id(message: types.Message, state: FSMContext):
    bet_id = message.text.strip()
    
    if check_bet_id(bet_id):
        await state.update_data(bet_id=bet_id)
        await state.set_state(SignalStates.waiting_for_game_start)
        
        kb = InlineKeyboardBuilder()
        kb.button(text="🍎 O'yinni boshlash", callback_data="start_game")
        kb.button(text="◀️ Orqaga", callback_data="get_signal")
        kb.adjust(1)
        
        await message.answer(
            f"✅ Betwinner ID qabul qilindi: `{bet_id}`\n\n"
            "🎮 Endi o'yinni boshlash uchun tugmani bosing:",
            parse_mode="Markdown",
            reply_markup=kb.as_markup()
        )
    else:
        await message.answer(
            "❌ Noto'g'ri ID formati! ID 9-12 oraliqda faqat raqamlardan iborat bo'lishi kerak.\n\n"
            "Qaytadan kiriting:",
            reply_markup=back_button("get_signal")
        )

@dp.callback_query(F.data == "start_game", SignalStates.waiting_for_game_start)
async def start_game(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    
    # Balansdan 1 ball yechish
    update_balance(callback.from_user.id, -1)
    
    # O'yin maydonini yaratish
    game_field = generate_game_field(rows=4)
    await state.update_data(game_field=game_field, current_row=0)
    await state.set_state(SignalStates.waiting_for_game_continue)
    
    await callback.message.edit_text(
        format_game_field(game_field),
        parse_mode="Markdown",
        reply_markup=game_control_keyboard()
    )

@dp.callback_query(F.data == "next_row", SignalStates.waiting_for_game_continue)
async def next_row(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    
    data = await state.get_data()
    current_row = data.get('current_row', 0)
    game_field = data.get('game_field', [])
    
    if current_row < 5:  # 6 qatorgacha (0-5)
        current_row += 1
        await state.update_data(current_row=current_row)
        
        # Yangi qator qo'shish
        new_row = generate_game_row()
        game_field.append(new_row)
        await state.update_data(game_field=game_field)
        
        await callback.message.edit_text(
            format_game_field(game_field),
            parse_mode="Markdown",
            reply_markup=game_control_keyboard()
        )
    else:
        kb = InlineKeyboardBuilder()
        kb.button(text="🔄 Qayta boshlash", callback_data="restart_game")
        kb.button(text="🏠 Asosiy menyu", callback_data="main_menu")
        kb.adjust(1)
        
        await callback.message.edit_text(
            "🎉 O'yin tugadi! Yutuqni oling! 🎉\n\n"
            "Qayta boshlash uchun tugmani bosing.",
            reply_markup=kb.as_markup()
        )

@dp.callback_query(F.data == "end_game", SignalStates.waiting_for_game_continue)
async def end_game(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🎮 Yangi signal", callback_data="get_signal")
    kb.button(text="🏠 Asosiy menyu", callback_data="main_menu")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "⏹️ O'yin tugatildi!\n\n"
        "Yana o'ynash uchun yangi signal oling.",
        reply_markup=kb.as_markup()
    )
    
    await state.clear()

@dp.callback_query(F.data == "restart_game")
async def restart_game(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    
    # Yangi o'yin
    game_field = generate_game_field(rows=4)
    await state.update_data(game_field=game_field, current_row=0)
    await state.set_state(SignalStates.waiting_for_game_continue)
    
    await callback.message.edit_text(
        format_game_field(game_field),
        parse_mode="Markdown",
        reply_markup=game_control_keyboard()
    )

# ============= ADMIN PANEL =============
@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Ruxsat yo'q!", show_alert=True)
        return
    
    await callback.answer()
    stats = get_stats()
    
    text = f"📊 *Bot statistikasi*\n\n"
    text += f"👥 Jami foydalanuvchilar: {stats['total_users']}\n"
    text += f"💰 Jami ballar: {stats['total_balance']}\n"
    text += f"👥 Referallar: {stats['total_refs']}\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=admin_panel_keyboard()
    )

@dp.callback_query(F.data == "admin_user")
async def admin_user(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Ruxsat yo'q!", show_alert=True)
        return
    
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_user_id)
    
    await callback.message.edit_text(
        "👤 Foydalanuvchi ID sini kiriting:",
        reply_markup=back_button("admin_panel")
    )

@dp.callback_query(F.data == "admin_add_apk")
async def admin_add_apk(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Ruxsat yo'q!", show_alert=True)
        return
    
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_apk_url)
    
    await callback.message.edit_text(
        "🔗 Yangi APK havolasini kiriting:",
        reply_markup=back_button("admin_panel")
    )

@dp.callback_query(F.data == "admin_remove_apk")
async def admin_remove_apk(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Ruxsat yo'q!", show_alert=True)
        return
    
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_remove_apk)
    
    await callback.message.edit_text(
        "❌ APK huquqini olib tashlash uchun user ID kiriting:",
        reply_markup=back_button("admin_panel")
    )

@dp.callback_query(F.data == "admin_add_balance")
async def admin_add_balance(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Ruxsat yo'q!", show_alert=True)
        return
    
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_balance_amount)
    
    await callback.message.edit_text(
        "💰 Ball qo'shish formati: `user_id ball_miqdori`\n\n"
        "Misol: 123456789 10",
        parse_mode="Markdown",
        reply_markup=back_button("admin_panel")
    )

@dp.callback_query(F.data == "admin_panel")
async def return_to_admin(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Ruxsat yo'q!", show_alert=True)
        return
    
    await callback.answer()
    await state.clear()
    
    await callback.message.edit_text(
        "🔐 Admin panel",
        reply_markup=admin_panel_keyboard()
    )

# Admin state handlerlari
@dp.message(AdminStates.waiting_for_user_id)
async def process_user_info(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        user_id = int(message.text.strip())
        user = get_user(user_id)
        
        if user:
            text = f"👤 *Foydalanuvchi ma'lumotlari*\n\n"
            text += f"🆔 ID: {user[0]}\n"
            text += f"📛 Username: @{user[1]}\n"
            text += f"👤 Ism: {user[2]}\n"
            text += f"📅 Qo'shilgan: {user[3]}\n"
            text += f"💰 Balans: {user[4]}\n"
            text += f"👥 Referal: {user[5]}\n"
            text += f"📱 APK: {'Ha' if user[7] else 'Yo‘q'}\n"
            
            await message.answer(text, parse_mode="Markdown")
        else:
            await message.answer("❌ Foydalanuvchi topilmadi!")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}")
    
    await state.clear()
    await message.answer("🔐 Admin panel", reply_markup=admin_panel_keyboard())

@dp.message(AdminStates.waiting_for_apk_url)
async def process_apk_url(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    global APK_URL
    APK_URL = message.text.strip()
    
    await message.answer(f"✅ APK havolasi yangilandi:\n{APK_URL}")
    
    await state.clear()
    await message.answer("🔐 Admin panel", reply_markup=admin_panel_keyboard())

@dp.message(AdminStates.waiting_for_remove_apk)
async def process_remove_apk(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        user_id = int(message.text.strip())
        set_apk_access(user_id, False)
        
        await message.answer(f"✅ Foydalanuvchi {user_id} dan APK huquqi olib tashlandi!")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}")
    
    await state.clear()
    await message.answer("🔐 Admin panel", reply_markup=admin_panel_keyboard())

@dp.message(AdminStates.waiting_for_balance_amount)
async def process_add_balance(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        parts = message.text.strip().split()
        if len(parts) == 2:
            user_id = int(parts[0])
            amount = int(parts[1])
            
            update_balance(user_id, amount)
            
            await message.answer(f"✅ Foydalanuvchi {user_id} ga {amount} ball qo'shildi!")
        else:
            await message.answer("❌ Noto'g'ri format! `user_id ball` shaklida kiriting.")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}")
    
    await state.clear()
    await message.answer("🔐 Admin panel", reply_markup=admin_panel_keyboard())

# ============= STARTUP VA SHUTDOWN =============
async def on_startup():
    logging.info("🍎 Apple of Fortune Signal Bot ishga tushdi!")
    
    # Adminlarga xabar yuborish
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, "✅ Bot ishga tushdi!")
        except:
            pass

async def on_shutdown():
    logging.info("Bot to'xtatilmoqda...")
    conn.close()
    await bot.session.close()

# ============= ASOSIY FUNKSIYA =============
async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
