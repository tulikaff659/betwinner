import asyncio
import random
import sqlite3
import logging
import os
from datetime import datetime, timedelta
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
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "123456789").split(",") if id.strip()]
APK_URL = os.getenv("APK_URL", "https://example.com/app.apk")

# Ballar konfiguratsiyasi
FREE_SIGNALS = 3  # Bepul signallar soni
SIGNAL_PRICE = 1500  # Signal narxi
REFERRAL_BONUS = 500  # Referal uchun bonus

# Ma'lumotlar bazasi
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
        
        # Foydalanuvchilar jadvali
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_date TIMESTAMP,
            balance INTEGER DEFAULT 0,
            free_signals_used INTEGER DEFAULT 0,
            total_signals INTEGER DEFAULT 0,
            referrer_id INTEGER,
            promo_used BOOLEAN DEFAULT FALSE,
            apk_access BOOLEAN DEFAULT FALSE
        )
        ''')
        
        # Referallar jadvali
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            referred_id INTEGER,
            date TIMESTAMP,
            bonus_given BOOLEAN DEFAULT FALSE
        )
        ''')
        
        # Signallar jadvali
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            game_type TEXT,
            signal_data TEXT,
            created_at TIMESTAMP,
            used BOOLEAN DEFAULT FALSE
        )
        ''')
        
        # Balans o'zgarishlarini kuzatish uchun jadval
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS balance_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            reason TEXT,
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
    # 4 ta sirli (❓) va 1 ta butun olma (🍎)
    apples = ["❓", "❓", "❓", "❓", "🍎"]
    random.shuffle(apples)
    return apples

def generate_game_field(rows=1):
    """O'yin maydonini yaratish (1 qatordan boshlanadi)"""
    field = []
    for i in range(rows):
        row = generate_game_row()
        field.append(row)
    return field

def format_game_field(field, current_row, total_rows):
    """O'yin maydonini matn ko'rinishiga o'tkazish"""
    result = "🎰 *APPLE OF FORTUNE SIGNAL* 🎰\n\n"
    
    # Qatorlarni chiroyli ko'rsatish
    for i, row in enumerate(field):
        row_text = " ".join(row)
        # Butun olmani belgilash (🍎)
        if "🍎" in row:
            # Butun olma qaysi pozitsiyada ekanligini topish
            pos = row.index("🍎") + 1
            result += f"`{row_text}`  👈 Butun olma {i+1}-qator, {pos}-katakda\n"
        else:
            result += f"`{row_text}`\n"
    
    result += f"\n📊 *Qatorlar:* {current_row}/{total_rows}\n"
    result += "\n🎯 *Betwinner Apple of Fortune o'yiniga kiring*"
    result += "\n📌 *Ko'rsatilgan qatorlar bo'yicha yuring*"
    result += "\n\n⚡️ Keyingi qatorni ochish uchun tugmani bosing!"
    
    return result

def check_bet_id(bet_id):
    """Bet ID ni tekshirish (9-12 raqam)"""
    if bet_id and bet_id.isdigit() and 9 <= len(bet_id) <= 12:
        return True
    return False

def generate_referral_link(bot_username, user_id):
    """Referal link yaratish"""
    return f"https://t.me/{bot_username}?start=ref_{user_id}"

def format_balance_message(balance):
    """Balansni formatlash"""
    if balance >= 1000:
        return f"💰 *{balance/1000:.1f}K* ball"
    return f"💰 *{balance}* ball"

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

def update_balance(user_id, amount, reason=""):
    """Balansni yangilash va xabar yozish"""
    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (amount, user_id)
    )
    
    # Balans o'zgarish tarixiga yozish
    cursor.execute(
        "INSERT INTO balance_history (user_id, amount, reason, created_at) VALUES (?, ?, ?, ?)",
        (user_id, amount, reason, datetime.now())
    )
    
    conn.commit()
    
    # Yangi balansni olish
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    new_balance = cursor.fetchone()[0]
    
    return new_balance

def can_get_free_signal(user_id):
    """Bepul signal olish mumkinligini tekshirish"""
    user = get_user(user_id)
    if user:
        return user[4] < FREE_SIGNALS  # free_signals_used < FREE_SIGNALS
    return False

def use_free_signal(user_id):
    """Bepul signaldan foydalanish"""
    cursor.execute(
        "UPDATE users SET free_signals_used = free_signals_used + 1 WHERE user_id = ?",
        (user_id,)
    )
    conn.commit()

def increment_total_signals(user_id):
    """Jami signallarni oshirish"""
    cursor.execute(
        "UPDATE users SET total_signals = total_signals + 1 WHERE user_id = ?",
        (user_id,)
    )
    conn.commit()

def use_promo(user_id):
    """Promokodni ishlatish"""
    cursor.execute(
        "UPDATE users SET promo_used = TRUE, apk_access = TRUE WHERE user_id = ?",
        (user_id,)
    )
    conn.commit()
    
    # Referalga bonus
    cursor.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
    referrer = cursor.fetchone()
    
    if referrer and referrer[0]:
        # Referalga bonus berish
        new_balance = update_balance(referrer[0], REFERRAL_BONUS, f"referal_bonus_{user_id}")
        
        cursor.execute(
            "UPDATE referrals SET bonus_given = TRUE WHERE user_id = ? AND referred_id = ?",
            (referrer[0], user_id)
        )
        conn.commit()
        
        return referrer[0], new_balance
    
    return None, None

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
        "SELECT COUNT(*) FROM referrals WHERE user_id = ?",
        (user_id,)
    )
    return cursor.fetchone()[0]

def get_referrals_with_bonus(user_id):
    """Bonus berilgan referallar sonini olish"""
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
    
    cursor.execute("SELECT SUM(total_signals) FROM users")
    stats['total_signals'] = cursor.fetchone()[0] or 0
    
    return stats

# ============= KLAVIATURALAR =============
def main_menu_keyboard():
    """Asosiy menyu"""
    kb = InlineKeyboardBuilder()
    kb.button(text="🎮 Signal olish", callback_data="get_signal")
    kb.button(text="💰 Balans", callback_data="check_balance")
    kb.button(text="👥 Referallar", callback_data="referrals")
    kb.button(text="📊 Statistika", callback_data="user_stats")
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
                    referrer_id = None
            except:
                pass
    
    # Foydalanuvchini tekshirish
    user = get_user(user_id)
    if not user:
        add_user(user_id, username, first_name, referrer_id)
        if referrer_id:
            add_referral(referrer_id, user_id)
            
            # Referalga xabar yuborish
            try:
                await bot.send_message(
                    referrer_id,
                    f"🎉 *Yangi referal!*\n\n"
                    f"👤 {first_name} sizning havolangiz orqali ro'yxatdan o'tdi!\n\n"
                    f"💰 U SIGNAL7 promokodini ishlatganda {REFERRAL_BONUS} ball olasiz!",
                    parse_mode="Markdown"
                )
            except:
                pass
    
    free_left = FREE_SIGNALS - (user[4] if user else 0)
    
    welcome_text = f"👋 Assalomu alaykum, {first_name}!\n\n"
    welcome_text += "🎮 *Apple of Fortune Signal Bot* ga xush kelibsiz!\n\n"
    welcome_text += f"🎁 Sizda *{free_left} ta bepul signal* mavjud!\n"
    welcome_text += f"💰 Keyingi signallar: *{SIGNAL_PRICE} ball*\n"
    welcome_text += f"👥 Referal taklif: *{REFERRAL_BONUS} ball*\n\n"
    welcome_text += "📝 Ro'yxatdan o'tish uchun: SIGNAL7"
    
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=main_menu_keyboard())

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
    
    if user and not user[8]:  # promo_used = False (index 8)
        # Promokodni ishlatish
        cursor.execute(
            "UPDATE users SET promo_used = TRUE, apk_access = TRUE WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()
        
        # Referalga bonus
        cursor.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
        referrer = cursor.fetchone()
        
        referrer_balance = None
        if referrer and referrer[0]:
            # Referalga bonus berish
            new_balance = update_balance(referrer[0], REFERRAL_BONUS, f"referal_bonus_{user_id}")
            referrer_balance = new_balance
            
            cursor.execute(
                "UPDATE referrals SET bonus_given = TRUE WHERE user_id = ? AND referred_id = ?",
                (referrer[0], user_id)
            )
            conn.commit()
        
        text = "✅ *SIGNAL7 promokodi muvaffaqiyatli faollashtirildi!*\n\n"
        text += "📱 APK yuklash huquqi berildi!\n\n"
        
        if referrer and referrer[0]:
            text += f"👤 Sizni taklif qilgan foydalanuvchi {REFERRAL_BONUS} ball bilan taqdirlandi!"
        
        await message.answer(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())
        
        # Referalga xabar yuborish
        if referrer and referrer[0]:
            try:
                await bot.send_message(
                    referrer[0],
                    f"💰 *Balans yangilandi!*\n\n"
                    f"Sizning referalingiz SIGNAL7 promokodini ishlatdi!\n"
                    f"Hisobingizga +{REFERRAL_BONUS} ball qo'shildi.\n"
                    f"💳 Yangi balans: {format_balance_message(referrer_balance)}",
                    parse_mode="Markdown"
                )
            except:
                pass
    else:
        await message.answer(
            "❌ Siz allaqachon promokodni ishlatgansiz!",
            reply_markup=main_menu_keyboard()
        )

# ============= ASOSIY MENYU CALLBACKLARI =============
@dp.callback_query(F.data == "get_signal")
async def get_signal(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if not user:
        await callback.message.edit_text("❌ Foydalanuvchi topilmadi!")
        return
    
    free_signals_used = user[4]  # free_signals_used
    balance = user[3]  # balance
    
    # Bepul signal tekshirish
    if free_signals_used < FREE_SIGNALS:
        # Bepul signal
        await state.set_state(SignalStates.waiting_for_bet_id)
        await state.update_data(is_free=True)
        
        free_left = FREE_SIGNALS - free_signals_used - 1
        
        await callback.message.edit_text(
            f"🎁 *Bepul signal* ({free_signals_used + 1}/{FREE_SIGNALS})\n\n"
            f"🎫 Iltimos, Betwinner ID raqamingizni kiriting:\n\n"
            f"🔢 Raqam 9 dan 12 gacha xonadan iborat bo'lishi kerak.\n\n"
            f"⚡️ Qolgan bepul signallar: {free_left}",
            parse_mode="Markdown",
            reply_markup=back_button()
        )
    elif balance >= SIGNAL_PRICE:
        # Pullik signal
        await state.set_state(SignalStates.waiting_for_bet_id)
        await state.update_data(is_free=False)
        
        await callback.message.edit_text(
            f"💰 *Pullik signal*\n\n"
            f"🎫 Iltimos, Betwinner ID raqamingizni kiriting:\n\n"
            f"🔢 Raqam 9 dan 12 gacha xonadan iborat bo'lishi kerak.\n\n"
            f"💳 Signal narxi: {SIGNAL_PRICE} ball",
            parse_mode="Markdown",
            reply_markup=back_button()
        )
    else:
        await callback.message.edit_text(
            f"❌ Sizda yetarli ball mavjud emas!\n\n"
            f"💰 Sizning balansingiz: {format_balance_message(balance)}\n"
            f"🎫 Signal narxi: {SIGNAL_PRICE} ball\n\n"
            f"👥 Do'stlaringizni taklif qiling va {REFERRAL_BONUS} ball oling!",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )

@dp.callback_query(F.data == "check_balance")
async def check_balance(callback: types.CallbackQuery):
    await callback.answer()
    
    user = get_user(callback.from_user.id)
    if user:
        free_left = FREE_SIGNALS - user[4]
        
        text = f"💰 *Sizning balansingiz*\n\n"
        text += f"💳 Ballar: {format_balance_message(user[3])}\n"
        text += f"🎁 Bepul signallar: {free_left}/{FREE_SIGNALS}\n"
        text += f"📊 Jami signallar: {user[5]}\n\n"
        text += f"⚡️ 1 signal narxi: {SIGNAL_PRICE} ball\n"
        text += f"👥 1 referal bonusi: {REFERRAL_BONUS} ball"
        
        await callback.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )

@dp.callback_query(F.data == "user_stats")
async def user_stats(callback: types.CallbackQuery):
    await callback.answer()
    
    user = get_user(callback.from_user.id)
    if user:
        referrals = get_referrals_count(callback.from_user.id)
        referrals_with_bonus = get_referrals_with_bonus(callback.from_user.id)
        total_earned = referrals_with_bonus * REFERRAL_BONUS
        
        text = f"📊 *Sizning statistikangiz*\n\n"
        text += f"📅 Ro'yxatdan o'tgan: {user[2][:10]}\n"
        text += f"📊 Jami signallar: {user[5]}\n"
        text += f"👥 Referallar: {referrals}\n"
        text += f"💰 Referallardan daromad: {format_balance_message(total_earned)}\n"
        text += f"💳 Joriy balans: {format_balance_message(user[3])}"
        
        await callback.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )

@dp.callback_query(F.data == "referrals")
async def referrals_menu(callback: types.CallbackQuery):
    await callback.answer()
    
    count = get_referrals_count(callback.from_user.id)
    count_with_bonus = get_referrals_with_bonus(callback.from_user.id)
    total_earned = count_with_bonus * REFERRAL_BONUS
    
    bot_username = (await bot.get_me()).username
    link = generate_referral_link(bot_username, callback.from_user.id)
    
    text = f"👥 *Sizning referallaringiz*\n\n"
    text += f"📊 Jami takliflar: *{count}*\n"
    text += f"✅ Faol referallar: *{count_with_bonus}*\n"
    text += f"💰 Umumiy daromad: *{format_balance_message(total_earned)}*\n\n"
    text += f"🔗 Sizning referal linkingiz:\n`{link}`\n\n"
    text += f"💡 Do'stlaringiz SIGNAL7 promokodini ishlatganda {REFERRAL_BONUS} ball olasiz!"
    
    kb = InlineKeyboardBuilder()
    kb.button(text="📢 Ulashish", switch_inline_query=f"🎮 Apple of Fortune Signal Bot\n\n🔗 Ro'yxatdan o'tish: {link}")
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
    if user and user[9]:  # apk_access = True (index 9)
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
    text += f"• Yangi foydalanuvchilarga {FREE_SIGNALS} ta bepul signal\n"
    text += f"• Keyingi signallar: {SIGNAL_PRICE} ball\n"
    text += f"• Referal taklif: {REFERRAL_BONUS} ball\n\n"
    text += "📝 *Promokod:* SIGNAL7\n"
    text += "   • APK yuklash huquqi\n"
    text += "   • Referalga bonus\n\n"
    text += "👥 *Referal tizim:*\n"
    text += "1. Do'stlaringizga link yuboring\n"
    text += "2. Ular SIGNAL7 kodini ishlatsin\n"
    text += f"3. Siz {REFERRAL_BONUS} ball olasiz"
    
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
        
        data = await state.get_data()
        is_free = data.get('is_free', False)
        
        if is_free:
            text = f"✅ Betwinner ID qabul qilindi: `{bet_id}`\n\n"
            text += "🎁 *Bepul signal* bilan o'yinni boshlang!"
        else:
            text = f"✅ Betwinner ID qabul qilindi: `{bet_id}`\n\n"
            text += f"💰 Hisobingizdan {SIGNAL_PRICE} ball yechiladi.\n"
            text += "🎮 O'yinni boshlash uchun tugmani bosing!"
        
        kb = InlineKeyboardBuilder()
        kb.button(text="🍎 O'yinni boshlash", callback_data="start_game")
        kb.button(text="◀️ Orqaga", callback_data="get_signal")
        kb.adjust(1)
        
        await message.answer(
            text,
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
    
    user_id = callback.from_user.id
    data = await state.get_data()
    is_free = data.get('is_free', False)
    
    # Balansni tekshirish va yangilash
    if is_free:
        use_free_signal(user_id)
        balance_change = 0
        reason = "free_signal"
    else:
        update_balance(user_id, -SIGNAL_PRICE, f"signal_purchase")
        balance_change = -SIGNAL_PRICE
    
    increment_total_signals(user_id)
    
    # Yangi balansni olish
    user = get_user(user_id)
    new_balance = user[3]
    
    # Balans o'zgarishi haqida xabar
    if not is_free:
        await callback.message.answer(
            f"💰 *Balans yangilandi!*\n\n"
            f"Signal uchun {SIGNAL_PRICE} ball yechildi.\n"
            f"💳 Yangi balans: {format_balance_message(new_balance)}",
            parse_mode="Markdown"
        )
    
    # O'yin maydonini yaratish - 1 qatordan boshlanadi
    game_field = generate_game_field(rows=1)
    await state.update_data(game_field=game_field, current_row=1, max_rows=6)
    
    # Signal matni
    signal_text = f"🎰 *APPLE OF FORTUNE SIGNAL* 🎰\n\n"
    signal_text += f"🎫 Betwinner ID: `{data.get('bet_id')}`\n\n"
    signal_text += format_game_field(game_field, 1, 6)
    
    await callback.message.edit_text(
        signal_text,
        parse_mode="Markdown",
        reply_markup=game_control_keyboard()
    )
    
    await state.set_state(SignalStates.waiting_for_game_continue)

@dp.callback_query(F.data == "next_row", SignalStates.waiting_for_game_continue)
async def next_row(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    
    data = await state.get_data()
    current_row = data.get('current_row', 1)
    max_rows = data.get('max_rows', 6)
    game_field = data.get('game_field', [])
    bet_id = data.get('bet_id', '')
    
    if current_row < max_rows:
        current_row += 1
        await state.update_data(current_row=current_row)
        
        # Yangi qator qo'shish
        new_row = generate_game_row()
        game_field.append(new_row)
        await state.update_data(game_field=game_field)
        
        # Signal matni
        signal_text = f"🎰 *APPLE OF FORTUNE SIGNAL* 🎰\n\n"
        signal_text += f"🎫 Betwinner ID: `{bet_id}`\n\n"
        signal_text += format_game_field(game_field, current_row, max_rows)
        
        await callback.message.edit_text(
            signal_text,
            parse_mode="Markdown",
            reply_markup=game_control_keyboard()
        )
    else:
        # O'yin tugadi - 6 qator
        signal_text = f"🎰 *APPLE OF FORTUNE SIGNAL* 🎰\n\n"
        signal_text += f"🎫 Betwinner ID: `{bet_id}`\n\n"
        signal_text += format_game_field(game_field, current_row, max_rows)
        signal_text += "\n\n🎉 *O'YIN TUGADI!* 🎉\n"
        signal_text += "💰 Yutuqni olish uchun Betwinner'ga kiring!\n\n"
        signal_text += "🔄 Qayta boshlash uchun tugmani bosing."
        
        kb = InlineKeyboardBuilder()
        kb.button(text="🔄 Qayta boshlash", callback_data="restart_game")
        kb.button(text="🏠 Asosiy menyu", callback_data="main_menu")
        kb.adjust(1)
        
        await callback.message.edit_text(
            signal_text,
            parse_mode="Markdown",
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
    
    data = await state.get_data()
    bet_id = data.get('bet_id', '')
    
    # Yangi o'yin - 1 qatordan boshlanadi
    game_field = generate_game_field(rows=1)
    await state.update_data(game_field=game_field, current_row=1, max_rows=6)
    await state.set_state(SignalStates.waiting_for_game_continue)
    
    # Signal matni
    signal_text = f"🎰 *APPLE OF FORTUNE SIGNAL* 🎰\n\n"
    signal_text += f"🎫 Betwinner ID: `{bet_id}`\n\n"
    signal_text += format_game_field(game_field, 1, 6)
    
    await callback.message.edit_text(
        signal_text,
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
    text += f"💰 Jami ballar: {format_balance_message(stats['total_balance'])}\n"
    text += f"👥 Referallar: {stats['total_refs']}\n"
    text += f"🎮 Jami signallar: {stats['total_signals']}\n"
    
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
            text += f"💰 Balans: {user[3]}\n"
            text += f"🎁 Bepul signallar: {user[4]}/{FREE_SIGNALS}\n"
            text += f"📊 Jami signallar: {user[5]}\n"
            text += f"👥 Referal: {user[6]}\n"
            text += f"📱 APK: {'Ha' if user[9] else 'Yo‘q'}\n"
            
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
            
            new_balance = update_balance(user_id, amount, "admin_add")
            
            await message.answer(f"✅ Foydalanuvchi {user_id} ga {amount} ball qo'shildi!\n💳 Yangi balans: {new_balance}")
            
            # Foydalanuvchiga xabar yuborish
            try:
                await bot.send_message(
                    user_id,
                    f"💰 *Balans yangilandi!*\n\n"
                    f"Hisobingizga +{amount} ball qo'shildi.\n"
                    f"💳 Yangi balans: {format_balance_message(new_balance)}",
                    parse_mode="Markdown"
                )
            except:
                pass
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
            await bot.send_message(
                admin_id,
                f"✅ *Bot ishga tushdi!*\n\n"
                f"⚡️ Bepul signallar: {FREE_SIGNALS}\n"
                f"💰 Signal narxi: {SIGNAL_PRICE}\n"
                f"👥 Referal bonusi: {REFERRAL_BONUS}",
                parse_mode="Markdown"
            )
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
