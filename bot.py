import json
import logging
import os
import asyncio
import random
import traceback
from pathlib import Path
from typing import Dict, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# ------------------- SOZLAMALAR -------------------
TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = 6935090105  # Admin Telegram ID
DATA_FILE = "games.json"
USERS_FILE = "users.json"

REFERRAL_BONUS = 2500        # Har bir taklif uchun bonus
START_BONUS = 15000          # Startdan keyin beriladigan bonus
MIN_WITHDRAW = 25000         # Minimal yechish summasi
BOT_USERNAME = "Betwinner_premium_bot"  # Botning @username (havola yaratish uchun, @ belgisisiz)
WITHDRAW_SITE_URL = "https://betwinner.com/withdraw"  # Pul yechish sayti

# ------------------- LOGLASH -------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ------------------- MAʼLUMOTLAR SAQLASH -------------------
def load_games() -> Dict:
    if Path(DATA_FILE).exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_games(games: Dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(games, f, ensure_ascii=False, indent=4)

games_data = load_games()

def load_users() -> Dict:
    if Path(USERS_FILE).exists():
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_users(users: Dict):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

users_data = load_users()

# ------------------- YORDAMCHI FUNKSIYALAR -------------------
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def generate_unique_code() -> str:
    """7 xonali unikal kod generatsiya qiladi (mavjud kodlar bilan solishtiradi)."""
    while True:
        code = f"{random.randint(0, 9999999):07d}"  # 7 xonali, yetakchi nol bilan
        existing_codes = [u.get("withdraw_code") for u in users_data.values() if u.get("withdraw_code")]
        if code not in existing_codes:
            return code

def get_game_keyboard() -> InlineKeyboardMarkup:
    """O‘yinlar ro‘yxati + bosh menyu tugmasi."""
    keyboard = []
    for game in games_data.keys():
        keyboard.append([InlineKeyboardButton(game, callback_data=f"game_{game}")])
    keyboard.append([InlineKeyboardButton("◀️ Bosh menyu", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("➕ O'yin qo'shish", callback_data="admin_add")],
        [InlineKeyboardButton("➖ O'yin o'chirish", callback_data="admin_remove_list")],
        [InlineKeyboardButton("✏️ O'yin tahrirlash", callback_data="admin_edit_list")],
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("❌ Yopish", callback_data="admin_close")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_games_list_keyboard(action_prefix: str) -> InlineKeyboardMarkup:
    keyboard = []
    for game in games_data.keys():
        keyboard.append([InlineKeyboardButton(game, callback_data=f"{action_prefix}{game}")])
    keyboard.append([InlineKeyboardButton("◀️ Orqaga", callback_data="admin_back")])
    return InlineKeyboardMarkup(keyboard)

def get_main_keyboard() -> InlineKeyboardMarkup:
    """Asosiy menyu tugmalari - Betwinner uchun moslashtirilgan"""
    keyboard = [
        [InlineKeyboardButton("🎮 Sport tikish", callback_data="show_games")],
        [
            InlineKeyboardButton("💰 Pul ishlash", callback_data="earn"),
            InlineKeyboardButton("💵 Balans", callback_data="balance")
        ],
        [InlineKeyboardButton("📱 APK yuklash", callback_data="download_apk")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_referral_link(user_id: int) -> str:
    """Foydalanuvchi uchun referral havola yaratish."""
    return f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"

async def ensure_user(user_id: int) -> dict:
    """Foydalanuvchi maʼlumotlarini yaratish yoki olish (referralni hisobga olmagan holda)."""
    user_id_str = str(user_id)
    if user_id_str not in users_data:
        # Yangi foydalanuvchi: unikal kod yaratish, referred_by = None
        new_code = generate_unique_code()
        users_data[user_id_str] = {
            "balance": 0,
            "referred_by": None,
            "referrals": 0,
            "start_bonus_given": False,
            "withdraw_code": new_code,
            "total_earned": 0,
            "joined_date": str(asyncio.get_event_loop().time())
        }
        save_users(users_data)
    return users_data[user_id_str]

async def give_start_bonus(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """1-2 daqiqadan so‘ng start bonusini berish."""
    await asyncio.sleep(90)  # 1.5 daqiqa
    user_id_str = str(user_id)
    if user_id_str in users_data and not users_data[user_id_str].get("start_bonus_given", False):
        users_data[user_id_str]["balance"] += START_BONUS
        users_data[user_id_str]["total_earned"] = users_data[user_id_str].get("total_earned", 0) + START_BONUS
        users_data[user_id_str]["start_bonus_given"] = True
        save_users(users_data)
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"🎉 *Betwinner Premium bonus!*\n\n"
                    f"Sizga start bonusi sifatida *{START_BONUS} so‘m* berildi!\n"
                    f"💳 Hozirgi balansingiz: *{users_data[user_id_str]['balance']} so‘m*\n\n"
                    f"🔥 Endi sport tiking va katta yutuqlarni qo'lga kiriting!"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Bonus xabarini yuborishda xatolik: {e}")

# ------------------- START HANDLER -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start komandasi – Betwinner uchun moslashtirilgan"""
    user = update.effective_user
    user_id = user.id
    args = context.args

    # Foydalanuvchini yaratish
    user_data = await ensure_user(user_id)

    # Referralni tekshirish va bonus berish
    if args and args[0].startswith("ref_"):
        try:
            ref_user_id = int(args[0].replace("ref_", ""))
            # O‘zini o‘zi taklif qilmasligi va taklif qiluvchi mavjud bo‘lishi kerak
            if ref_user_id != user_id and str(ref_user_id) in users_data:
                # Agar bu foydalanuvchi hali hech kim tomonidan taklif qilinmagan bo‘lsa
                if user_data.get("referred_by") is None:
                    # Referralni belgilash
                    user_data["referred_by"] = ref_user_id
                    # Taklif qiluvchiga bonus
                    referer_data = users_data[str(ref_user_id)]
                    referer_data["balance"] += REFERRAL_BONUS
                    referer_data["total_earned"] = referer_data.get("total_earned", 0) + REFERRAL_BONUS
                    referer_data["referrals"] = referer_data.get("referrals", 0) + 1
                    save_users(users_data)
                    # Bildirishnoma yuborish
                    try:
                        await context.bot.send_message(
                            chat_id=ref_user_id,
                            text=(
                                f"🎉 *Yangi taklif!*\n\n"
                                f"Sizning taklifingiz orqali @{user.username or user.first_name} "
                                f"*Betwinner* botiga qo‘shildi!\n"
                                f"💰 Balansingizga *{REFERRAL_BONUS} so‘m* qo‘shildi.\n"
                                f"💳 Hozirgi balans: *{referer_data['balance']} so‘m*"
                            ),
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Refererga xabar yuborishda xatolik: {e}")
        except:
            pass

    # Start bonusini rejalashtirish (agar hali berilmagan bo‘lsa)
    if not user_data.get("start_bonus_given", False):
        asyncio.create_task(give_start_bonus(user_id, context))

    # Betwinner uchun moslashtirilgan start xabari
    text = (
        "🎰 *BETWINNER PREMIUM* 🎰\n\n"
        "✨ *Rasmiy botga xush kelibsiz!* ✨\n\n"
        "📱 Endi Telegramdan *chiqmagan holda* sport tiking va yutuqlarni qo'lga kiriting.\n\n"
        "🔥 *Premium imkoniyatlar:*\n"
        "• 🎮 1000+ sport o'yinlari\n"
        "• 💰 Yuqori koeffitsientlar\n"
        "• 🎁 Haftalik bonuslar\n"
        "• 📊 Jonli statistikalar\n\n"
        "💰 *Pul ishlash imkoniyati:*\n"
        "• Do'stlaringizni taklif qiling: +2500 so'm\n"
        "• Start bonus: +15000 so'm\n"
        "• Minimal yechish: 25000 so'm\n\n"
        "👇 Quyidagi tugmalar orqali boshlang:"
    )
    
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

# ------------------- BOSH MENYUGA QAYTISH -------------------
async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bosh menyu tugmasi bosilganda yangi xabar yuboradi."""
    query = update.callback_query
    await query.answer()
    text = (
        "🎰 *BETWINNER PREMIUM* 🎰\n\n"
        "✨ *Asosiy menyu* ✨\n\n"
        "📱 Sport tikish va yutuqlarni qo'lga kiriting.\n\n"
        "💰 *Pul ishlash imkoniyati:*\n"
        "• Do'stlaringizni taklif qiling: +2500 so'm\n"
        "• Start bonus: +15000 so'm\n"
        "• Minimal yechish: 25000 so'm\n\n"
        "👇 Kerakli bo'limni tanlang:"
    )
    await query.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

# ------------------- APK YUKLASH -------------------
async def download_apk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """APK yuklash tugmasi bosilganda"""
    query = update.callback_query
    await query.answer()
    
    # APK havolasi yoki fayl
    apk_url = "https://betwinner.com/download/app"
    
    keyboard = [
        [InlineKeyboardButton("📥 APK yuklash", url=apk_url)],
        [InlineKeyboardButton("◀️ Bosh menyu", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        "📱 *Betwinner APK*\n\n"
        "Eng so'nggi versiyani yuklab oling:\n"
        "• Android 5.0+\n"
        "• Hajmi: 45 MB\n"
        "• Tezkor va xavfsiz\n\n"
        "👇 Yuklash uchun tugmani bosing:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ------------------- O‘YINLAR -------------------
async def show_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not games_data:
        await query.edit_message_text(
            "Hozircha hech qanday sport o'yinlari mavjud emas.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Bosh menyu", callback_data="main_menu")]])
        )
        return
    text = "🎮 *Sport o'yinlari:*\n\nQuyidagilardan birini tanlang:"
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_game_keyboard())

async def game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game_name = query.data.replace("game_", "")
    game = games_data.get(game_name)
    if not game:
        await query.message.reply_text("Bu o‘yin topilmadi.")
        return

    game["views"] = game.get("views", 0) + 1
    save_games(games_data)

    text = game.get("text", "Maʼlumot hozircha kiritilmagan.")
    photo_id = game.get("photo_id")
    file_id = game.get("file_id")
    button_text = game.get("button_text")
    button_url = game.get("button_url")

    # Bosh menyuga qaytish tugmasi
    back_button = [[InlineKeyboardButton("◀️ Bosh menyu", callback_data="main_menu")]]

    # Agar tashqi havola tugmasi bo‘lsa, uni ham qo‘shamiz
    reply_markup = None
    if button_text and button_url:
        keyboard = [[InlineKeyboardButton(button_text, url=button_url)], back_button[0]]
        reply_markup = InlineKeyboardMarkup(keyboard)
    else:
        reply_markup = InlineKeyboardMarkup(back_button)

    # 1. APK faylini yuborish (agar mavjud bo‘lsa)
    if file_id:
        await query.message.reply_document(document=file_id)

    # 2. Rasm yoki matnni yuborish
    if photo_id:
        await query.message.reply_photo(
            photo=photo_id,
            caption=text,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    else:
        await query.message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=reply_markup
        )

# ------------------- PUL ISHLASH VA BALANS -------------------
async def earn_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_data = await ensure_user(user_id)

    referral_link = get_referral_link(user_id)
    text = (
        "💰 *Betwinner-da pul ishlash*\n\n"
        "✅ *Do'stlaringizni taklif qiling:*\n"
        "Har bir do'stingiz botga kirganda *2500 so'm* olasiz\n\n"
        "✅ *Start bonusi:*\n"
        "Botga birinchi marta kirganingizda *15000 so'm*\n\n"
        "✅ *O'yinlar orqali:*\n"
        "Sport tikish orqali katta yutuqlarni qo'lga kiriting\n\n"
        "🔗 *Sizning taklif havolangiz:*\n"
        f"`{referral_link}`\n\n"
        "Havolani do'stlaringizga yuboring va pul ishlang!"
    )
    share_url = f"https://t.me/share/url?url={referral_link}&text=Betwinner%20premium%20botiga%20keling%2C%20birga%20pul%20ishlaymiz!"
    keyboard = [
        [InlineKeyboardButton("📤 Ulashish", url=share_url)],
        [InlineKeyboardButton("💸 Pul chiqarish", callback_data="withdraw")],
        [InlineKeyboardButton("◀️ Bosh menyu", callback_data="main_menu")]
    ]
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_data = await ensure_user(user_id)
    balance = user_data.get("balance", 0)
    referrals = user_data.get("referrals", 0)
    total_earned = user_data.get("total_earned", 0)
    
    text = (
        f"💳 *Betwinner balansingiz*\n\n"
        f"💰 Jami balans: *{balance} so‘m*\n"
        f"👥 Takliflar: *{referrals} ta*\n"
        f"📈 Umumiy daromad: *{total_earned} so‘m*\n\n"
        f"💸 Minimal yechish: *{MIN_WITHDRAW} so‘m*\n\n"
        f"🔥 Ko'proq pul ishlash uchun do'stlaringizni taklif qiling!"
    )
    keyboard = [
        [InlineKeyboardButton("💸 Pul chiqarish", callback_data="withdraw")],
        [InlineKeyboardButton("◀️ Bosh menyu", callback_data="main_menu")]
    ]
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def withdraw_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pul chiqarish – kodni ko‘rsatadi va saytga yo‘naltiradi."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_data = await ensure_user(user_id)
    balance = user_data.get("balance", 0)

    if balance < MIN_WITHDRAW:
        await query.edit_message_text(
            f"❌ Pul chiqarish uchun minimal balans {MIN_WITHDRAW} so‘m.\n"
            f"Sizda hozir {balance} so‘m bor.\n\n"
            f"Do'stlaringizni taklif qilib balansingizni oshiring!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Bosh menyu", callback_data="main_menu")]])
        )
        return

    code = user_data.get("withdraw_code")
    text = (
        f"💸 *Betwinner-dan pul chiqarish*\n\n"
        f"✅ Sizning maxsus kodingiz: `{code}`\n\n"
        f"📌 *Qanday yechish:*\n"
        f"1. Quyidagi tugma orqali saytga o'ting\n"
        f"2. Kodingizni kiriting\n"
        f"3. Summani tanlang\n"
        f"4. To'lovni tasdiqlang\n\n"
        f"⏳ Pul 5-10 daqiqada hisobingizga tushadi!"
    )
    keyboard = [
        [InlineKeyboardButton("💳 Saytga o‘tish", url=WITHDRAW_SITE_URL)],
        [InlineKeyboardButton("◀️ Bosh menyu", callback_data="main_menu")]
    ]
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ------------------- ADMIN PANEL -------------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Siz admin emassiz.")
        return
    await update.message.reply_text(
        "👨‍💻 *Betwinner Admin Panel*",
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard()
    )

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panelidagi callbacklarni boshqaradi"""
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Siz admin emassiz.")
        return

    data = query.data

    if data == "admin_remove_list":
        if not games_data:
            await query.edit_message_text("Hech qanday o‘yin mavjud emas.")
            return
        await query.edit_message_text(
            "O‘chiriladigan o‘yinni tanlang:",
            reply_markup=get_games_list_keyboard("remove_")
        )

    elif data == "admin_edit_list":
        if not games_data:
            await query.edit_message_text("Hech qanday o‘yin mavjud emas.")
            return
        await query.edit_message_text(
            "Tahrirlanadigan o‘yinni tanlang:",
            reply_markup=get_games_list_keyboard("edit_")
        )

    elif data == "admin_stats":
        total_users = len(users_data)
        total_balance = sum(u.get("balance", 0) for u in users_data.values())
        total_earned = sum(u.get("total_earned", 0) for u in users_data.values())
        total_referrals = sum(u.get("referrals", 0) for u in users_data.values())
        
        lines = [
            "📊 *Betwinner Statistikasi*\n",
            f"👥 Foydalanuvchilar: *{total_users}*",
            f"💰 Jami balans: *{total_balance} so‘m*",
            f"📈 Umumiy daromad: *{total_earned} so‘m*",
            f"👥 Jami takliflar: *{total_referrals}*",
            f"🎮 O'yinlar: *{len(games_data)}*",
            "\n*O'yinlar statistikasi:*"
        ]
        
        for name, game in games_data.items():
            views = game.get("views", 0)
            lines.append(f"• {name}: {views} marta")
        
        await query.edit_message_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard()
        )

    elif data == "admin_close":
        await query.edit_message_text("✅ Admin panel yopildi.")

    elif data == "admin_back":
        await query.edit_message_text(
            "👨‍💻 *Betwinner Admin Panel*",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard()
        )

    elif data.startswith("remove_"):
        game_name = data.replace("remove_", "")
        context.user_data["remove_game"] = game_name
        keyboard = [
            [InlineKeyboardButton("✅ Ha", callback_data="confirm_remove")],
            [InlineKeyboardButton("❌ Yo‘q", callback_data="admin_back")]
        ]
        await query.edit_message_text(
            f"'{game_name}' o‘yinini o‘chirishni tasdiqlaysizmi?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "confirm_remove":
        game_name = context.user_data.get("remove_game")
        if game_name and game_name in games_data:
            del games_data[game_name]
            save_games(games_data)
            await query.edit_message_text(
                f"✅ '{game_name}' o‘chirildi.",
                reply_markup=get_admin_keyboard()
            )
        else:
            await query.edit_message_text("Xatolik yuz berdi.", reply_markup=get_admin_keyboard())

    elif data.startswith("edit_"):
        game_name = data.replace("edit_", "")
        context.user_data["edit_game"] = game_name
        keyboard = [
            [InlineKeyboardButton("✏️ Matn", callback_data=f"edit_text_{game_name}")],
            [InlineKeyboardButton("🖼 Rasm", callback_data=f"edit_photo_{game_name}")],
            [InlineKeyboardButton("📁 Fayl (APK)", callback_data=f"edit_file_{game_name}")],
            [InlineKeyboardButton("🔗 Tugma", callback_data=f"edit_button_{game_name}")],
            [InlineKeyboardButton("◀️ Orqaga", callback_data="admin_back")]
        ]
        await query.edit_message_text(
            f"✏️ *{game_name}* – nimani tahrirlaysiz?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    return

# ------------------- ADD GAME KONVERSATSIYASI -------------------
ADD_NAME, ADD_TEXT, ADD_PHOTO, ADD_FILE, ADD_BUTTON_TEXT, ADD_BUTTON_URL = range(6)

async def admin_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add Game tugmasi bosilganda ishga tushadi."""
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("Siz admin emassiz.")
        return ConversationHandler.END

    context.user_data.clear()
    context.user_data["add_game"] = {}
    await query.edit_message_text("➕ *Yangi sport o'yini qo'shish*\n\nO'yin nomini kiriting:", parse_mode="Markdown")
    return ADD_NAME

async def add_game_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        name = update.message.text.strip()
        if not name:
            await update.message.reply_text("❌ Nom bo‘sh bo‘lishi mumkin emas. Qayta kiriting:")
            return ADD_NAME
        if name in games_data:
            await update.message.reply_text("❌ Bu nom allaqachon mavjud. Boshqa nom kiriting:")
            return ADD_NAME
        context.user_data["add_game"]["name"] = name
        await update.message.reply_text("✅ Endi o'yin matnini kiriting (HTML teglar bilan):")
        return ADD_TEXT
    except Exception as e:
        logger.error(f"add_game_name xatosi: {traceback.format_exc()}")
        await update.message.reply_text("❌ Xatolik yuz berdi. Qaytadan urinib ko‘ring.")
        return ConversationHandler.END

async def add_game_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text
        context.user_data["add_game"]["text"] = text
        await update.message.reply_text(
            "✅ Matn saqlandi.\n\nEndi rasm yuboring (ixtiyoriy) yoki /skip ni bosing."
        )
        return ADD_PHOTO
    except Exception as e:
        logger.error(f"add_game_text xatosi: {traceback.format_exc()}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")
        return ConversationHandler.END

async def add_game_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.message.photo:
            photo_id = update.message.photo[-1].file_id
            context.user_data["add_game"]["photo_id"] = photo_id
            await update.message.reply_text("✅ Rasm saqlandi.\n\nEndi APK fayl yuboring (ixtiyoriy) yoki /skip ni bosing.")
        else:
            await update.message.reply_text("❌ Iltimos, rasm yuboring yoki /skip ni bosing.")
            return ADD_PHOTO
        return ADD_FILE
    except Exception as e:
        logger.error(f"add_game_photo xatosi: {traceback.format_exc()}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")
        return ConversationHandler.END

async def add_game_photo_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["add_game"]["photo_id"] = None
        await update.message.reply_text("⏭ Rasm o‘tkazib yuborildi.\n\nEndi APK fayl yuboring (ixtiyoriy) yoki /skip ni bosing.")
        return ADD_FILE
    except Exception as e:
        logger.error(f"add_game_photo_skip xatosi: {traceback.format_exc()}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")
        return ConversationHandler.END

async def add_game_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.message.document:
            file_id = update.message.document.file_id
            context.user_data["add_game"]["file_id"] = file_id
        else:
            context.user_data["add_game"]["file_id"] = None
        await update.message.reply_text(
            "✅ Fayl saqlandi.\n\nEndi tugma matnini kiriting (ixtiyoriy) yoki /skip ni bosing.\n"
            "Masalan: '🎮 Tikish qilish'"
        )
        return ADD_BUTTON_TEXT
    except Exception as e:
        logger.error(f"add_game_file xatosi: {traceback.format_exc()}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")
        return ConversationHandler.END

async def add_game_file_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["add_game"]["file_id"] = None
        await update.message.reply_text(
            "⏭ Fayl o‘tkazib yuborildi.\n\nEndi tugma matnini kiriting (ixtiyoriy) yoki /skip ni bosing.\n"
            "Masalan: '🎮 Tikish qilish'"
        )
        return ADD_BUTTON_TEXT
    except Exception as e:
        logger.error(f"add_game_file_skip xatosi: {traceback.format_exc()}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")
        return ConversationHandler.END

async def add_game_button_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        button_text = update.message.text.strip()
        context.user_data["add_game"]["button_text"] = button_text
        await update.message.reply_text(
            "✅ Tugma matni saqlandi.\n\nEndi tugma havolasini (URL) kiriting (ixtiyoriy) yoki /skip ni bosing.\n"
            "Masalan: https://betwinner.com/game"
        )
        return ADD_BUTTON_URL
    except Exception as e:
        logger.error(f"add_game_button_text xatosi: {traceback.format_exc()}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")
        return ConversationHandler.END

async def add_game_button_text_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["add_game"]["button_text"] = None
        await update.message.reply_text(
            "⏭ Tugma matni o‘tkazib yuborildi.\n\nEndi tugma havolasini (URL) kiriting (ixtiyoriy) yoki /skip ni bosing."
        )
        return ADD_BUTTON_URL
    except Exception as e:
        logger.error(f"add_game_button_text_skip xatosi: {traceback.format_exc()}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")
        return ConversationHandler.END

async def add_game_button_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        button_url = update.message.text.strip()
        if not button_url.startswith(('http://', 'https://')):
            await update.message.reply_text("❌ URL 'http://' yoki 'https://' bilan boshlanishi kerak. Qayta kiriting:")
            return ADD_BUTTON_URL
            
        context.user_data["add_game"]["button_url"] = button_url
        # Saqlash
        game_data = context.user_data["add_game"]
        games_data[game_data["name"]] = {
            "text": game_data["text"],
            "photo_id": game_data.get("photo_id"),
            "file_id": game_data.get("file_id"),
            "button_text": game_data.get("button_text"),
            "button_url": game_data.get("button_url"),
            "views": 0
        }
        save_games(games_data)
        await update.message.reply_text(
            f"✅ *{game_data['name']}* o‘yini muvaffaqiyatli qo‘shildi!",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard()
        )
        context.user_data.pop("add_game", None)
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"add_game_button_url xatosi: {traceback.format_exc()}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")
        return ConversationHandler.END

async def add_game_button_url_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["add_game"]["button_url"] = None
        game_data = context.user_data["add_game"]
        games_data[game_data["name"]] = {
            "text": game_data["text"],
            "photo_id": game_data.get("photo_id"),
            "file_id": game_data.get("file_id"),
            "button_text": game_data.get("button_text"),
            "button_url": None,
            "views": 0
        }
        save_games(games_data)
        await update.message.reply_text(
            f"✅ *{game_data['name']}* o‘yini muvaffaqiyatli qo‘shildi!",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard()
        )
        context.user_data.pop("add_game", None)
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"add_game_button_url_skip xatosi: {traceback.format_exc()}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")
        return ConversationHandler.END

async def add_game_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🚫 Qo‘shish bekor qilindi.", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

# ------------------- EDIT GAME KONVERSATSIYALARI -------------------
EDIT_ACTION, EDIT_TEXT, EDIT_PHOTO, EDIT_FILE, EDIT_BUTTON_TEXT, EDIT_BUTTON_URL = range(6, 12)

async def edit_text_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("edit_text_"):
        game_name = data.replace("edit_text_", "")
    else:
        game_name = context.user_data.get("edit_game")
        if not game_name:
            await query.edit_message_text("Xatolik: o'yin nomi topilmadi.")
            return ConversationHandler.END
    context.user_data.clear()
    context.user_data["edit_game"] = game_name
    await query.edit_message_text(f"✏️ *{game_name}* uchun yangi matnni kiriting:", parse_mode="Markdown")
    return EDIT_TEXT

async def edit_photo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("edit_photo_"):
        game_name = data.replace("edit_photo_", "")
    else:
        game_name = context.user_data.get("edit_game")
        if not game_name:
            await query.edit_message_text("Xatolik: o'yin nomi topilmadi.")
            return ConversationHandler.END
    context.user_data.clear()
    context.user_data["edit_game"] = game_name
    await query.edit_message_text(f"🖼 *{game_name}* uchun yangi rasm yuboring:", parse_mode="Markdown")
    return EDIT_PHOTO

async def edit_file_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("edit_file_"):
        game_name = data.replace("edit_file_", "")
    else:
        game_name = context.user_data.get("edit_game")
        if not game_name:
            await query.edit_message_text("Xatolik: o'yin nomi topilmadi.")
            return ConversationHandler.END
    context.user_data.clear()
    context.user_data["edit_game"] = game_name
    await query.edit_message_text(f"📁 *{game_name}* uchun yangi APK fayl yuboring:", parse_mode="Markdown")
    return EDIT_FILE

async def edit_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("edit_button_"):
        game_name = data.replace("edit_button_", "")
    else:
        game_name = context.user_data.get("edit_game")
        if not game_name:
            await query.edit_message_text("Xatolik: o'yin nomi topilmadi.")
            return ConversationHandler.END
    context.user_data.clear()
    context.user_data["edit_game"] = game_name
    await query.edit_message_text(f"🔗 *{game_name}* uchun yangi tugma matnini kiriting:", parse_mode="Markdown")
    return EDIT_BUTTON_TEXT

async def edit_game_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        game_name = context.user_data["edit_game"]
        new_text = update.message.text
        games_data[game_name]["text"] = new_text
        save_games(games_data)
        await update.message.reply_text(
            f"✅ Matn yangilandi.",
            reply_markup=get_admin_keyboard()
        )
        context.user_data.clear()
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"edit_game_text xatosi: {traceback.format_exc()}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")
        return ConversationHandler.END

async def edit_game_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.message.photo:
            photo_id = update.message.photo[-1].file_id
            game_name = context.user_data["edit_game"]
            games_data[game_name]["photo_id"] = photo_id
            save_games(games_data)
            await update.message.reply_text(
                f"✅ Rasm yangilandi.",
                reply_markup=get_admin_keyboard()
            )
            context.user_data.clear()
            return ConversationHandler.END
        else:
            await update.message.reply_text("❌ Iltimos, rasm yuboring.")
            return EDIT_PHOTO
    except Exception as e:
        logger.error(f"edit_game_photo xatosi: {traceback.format_exc()}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")
        return ConversationHandler.END

async def edit_game_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.message.document:
            file_id = update.message.document.file_id
            game_name = context.user_data["edit_game"]
            games_data[game_name]["file_id"] = file_id
            save_games(games_data)
            await update.message.reply_text(
                f"✅ Fayl yangilandi.",
                reply_markup=get_admin_keyboard()
            )
            context.user_data.clear()
            return ConversationHandler.END
        else:
            await update.message.reply_text("❌ Iltimos, fayl yuboring.")
            return EDIT_FILE
    except Exception as e:
        logger.error(f"edit_game_file xatosi: {traceback.format_exc()}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")
        return ConversationHandler.END

async def edit_button_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        button_text = update.message.text.strip()
        context.user_data["edit_button_text"] = button_text
        await update.message.reply_text(
            "✅ Tugma matni saqlandi.\n\nEndi tugma havolasini (URL) kiriting (ixtiyoriy, /skip):"
        )
        return EDIT_BUTTON_URL
    except Exception as e:
        logger.error(f"edit_button_text xatosi: {traceback.format_exc()}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")
        return ConversationHandler.END

async def edit_button_text_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["edit_button_text"] = None
        await update.message.reply_text("⏭ Tugma matni o‘tkazib yuborildi.\n\nEndi tugma havolasini (URL) kiriting (ixtiyoriy, /skip):")
        return EDIT_BUTTON_URL
    except Exception as e:
        logger.error(f"edit_button_text_skip xatosi: {traceback.format_exc()}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")
        return ConversationHandler.END

async def edit_button_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        button_url = update.message.text.strip()
        if not button_url.startswith(('http://', 'https://')):
            await update.message.reply_text("❌ URL 'http://' yoki 'https://' bilan boshlanishi kerak. Qayta kiriting:")
            return EDIT_BUTTON_URL
            
        game_name = context.user_data["edit_game"]
        button_text = context.user_data.get("edit_button_text")
        games_data[game_name]["button_text"] = button_text
        games_data[game_name]["button_url"] = button_url
        save_games(games_data)
        await update.message.reply_text(
            f"✅ Tugma maʼlumotlari yangilandi.",
            reply_markup=get_admin_keyboard()
        )
        context.user_data.clear()
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"edit_button_url xatosi: {traceback.format_exc()}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")
        return ConversationHandler.END

async def edit_button_url_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        game_name = context.user_data["edit_game"]
        button_text = context.user_data.get("edit_button_text")
        games_data[game_name]["button_text"] = button_text
        games_data[game_name]["button_url"] = None
        save_games(games_data)
        await update.message.reply_text(
            f"✅ Tugma maʼlumotlari yangilandi.",
            reply_markup=get_admin_keyboard()
        )
        context.user_data.clear()
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"edit_button_url_skip xatosi: {traceback.format_exc()}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")
        return ConversationHandler.END

async def edit_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🚫 Tahrirlash bekor qilindi.", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

# ------------------- ASOSIY -------------------
def main():
    app = Application.builder().token(TOKEN).build()

    # Asosiy handlerlar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(show_games, pattern="^show_games$"))
    app.add_handler(CallbackQueryHandler(game_callback, pattern="^game_"))
    app.add_handler(CallbackQueryHandler(earn_callback, pattern="^earn$"))
    app.add_handler(CallbackQueryHandler(balance_callback, pattern="^balance$"))
    app.add_handler(CallbackQueryHandler(withdraw_callback, pattern="^withdraw$"))
    app.add_handler(CallbackQueryHandler(download_apk, pattern="^download_apk$"))
    app.add_handler(CallbackQueryHandler(back_to_main, pattern="^main_menu$"))

    # Admin panel
    app.add_handler(CallbackQueryHandler(
        admin_callback_handler,
        pattern="^(admin_remove_list|admin_edit_list|admin_stats|admin_close|admin_back|remove_|confirm_remove)$"
    ))
    app.add_handler(CommandHandler("admin", admin_panel))

    # ADD GAME conversation
    add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_callback, pattern="^admin_add$")],
        states={
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_game_name)],
            ADD_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_game_text)],
            ADD_PHOTO: [
                MessageHandler(filters.PHOTO, add_game_photo),
                CommandHandler("skip", add_game_photo_skip)
            ],
            ADD_FILE: [
                MessageHandler(filters.Document.ALL, add_game_file),
                CommandHandler("skip", add_game_file_skip)
            ],
            ADD_BUTTON_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_game_button_text),
                CommandHandler("skip", add_game_button_text_skip)
            ],
            ADD_BUTTON_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_game_button_url),
                CommandHandler("skip", add_game_button_url_skip)
            ],
        },
        fallbacks=[CommandHandler("cancel", add_game_cancel)],
    )
    app.add_handler(add_conv)

    # EDIT GAME conversations
    edit_text_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_text_callback, pattern="^edit_text_")],
        states={
            EDIT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_game_text)],
        },
        fallbacks=[CommandHandler("cancel", edit_cancel)],
    )
    app.add_handler(edit_text_conv)

    edit_photo_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_photo_callback, pattern="^edit_photo_")],
        states={
            EDIT_PHOTO: [MessageHandler(filters.PHOTO, edit_game_photo)],
        },
        fallbacks=[CommandHandler("cancel", edit_cancel)],
    )
    app.add_handler(edit_photo_conv)

    edit_file_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_file_callback, pattern="^edit_file_")],
        states={
            EDIT_FILE: [MessageHandler(filters.Document.ALL, edit_game_file)],
        },
        fallbacks=[CommandHandler("cancel", edit_cancel)],
    )
    app.add_handler(edit_file_conv)

    edit_button_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_button_callback, pattern="^edit_button_")],
        states={
            EDIT_BUTTON_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_button_text),
                CommandHandler("skip", edit_button_text_skip)
            ],
            EDIT_BUTTON_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_button_url),
                CommandHandler("skip", edit_button_url_skip)
            ],
        },
        fallbacks=[CommandHandler("cancel", edit_cancel)],
    )
    app.add_handler(edit_button_conv)

    logger.info("🤖 Betwinner Premium Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
