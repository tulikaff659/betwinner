import json
import logging
import os
import asyncio
import random
import traceback
import sqlite3
from pathlib import Path
from typing import Dict

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

from config import *
import database

# ------------------- LOGLASH -------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ------------------- O'YINLAR MA'LUMOTLARI -------------------
def load_games() -> Dict:
    if Path(DATA_FILE).exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_games(games: Dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(games, f, ensure_ascii=False, indent=4)

games_data = load_games()

# ------------------- YORDAMCHI FUNKSIYALAR -------------------
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def get_game_keyboard() -> InlineKeyboardMarkup:
    keyboard = []
    for game in games_data.keys():
        keyboard.append([InlineKeyboardButton(game, callback_data=f"game_{game}")])
    keyboard.append([InlineKeyboardButton("◀️ Bosh menyu", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("➕ Add Game", callback_data="admin_add")],
        [InlineKeyboardButton("➖ Remove Game", callback_data="admin_remove_list")],
        [InlineKeyboardButton("✏️ Edit Game", callback_data="admin_edit_list")],
        [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton("📨 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("👥 Users Count", callback_data="admin_users_count")],
        [InlineKeyboardButton("❌ Close", callback_data="admin_close")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_main_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📊 Kun stavkasi", callback_data="show_games")],
        [
            InlineKeyboardButton("💰 Pul ishlash", callback_data="earn"),
            InlineKeyboardButton("💵 Balans", callback_data="balance")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_referral_link(user_id: int) -> str:
    return f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"

# ------------------- START HANDLER -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or user.first_name
    args = context.args

    user_data = await database.get_user(user_id, username)

    if args and args[0].startswith("ref_"):
        try:
            ref_user_id = int(args[0].replace("ref_", ""))
            if ref_user_id != user_id:
                if database.update_referral_bonus(ref_user_id, user_id):
                    database.update_balance(ref_user_id, REFERRAL_BONUS, f"Referral bonus")
                    
                    try:
                        referer_balance = database.get_user_balance(ref_user_id)
                        await context.bot.send_message(
                            chat_id=ref_user_id,
                            text=f"🎉 Yangi foydalanuvchi (@{username}) qo‘shildi! +{REFERRAL_BONUS} so‘m. Balans: {referer_balance} so‘m."
                        )
                    except Exception as e:
                        logger.error(f"Referral message error: {e}")
        except Exception as e:
            logger.error(f"Referral error: {e}")

    if not user_data.get("start_bonus_given", 0):
        asyncio.create_task(give_start_bonus(user_id, context))

    text = (
        "🎰 *BetWinner Bukmekeriga xush kelibsiz!* 🎰\n\n"
        "🔥 *Premium bonuslar* va har hafta yangi yutuqlar!\n"
        "📊 *Signal xizmati* va *kunlik kuponlar*\n\n"
        "👇 Quyidagi tugmalar orqali imkoniyatlarni kashf eting:"
    )
    
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

async def give_start_bonus(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    await asyncio.sleep(90)
    
    user_data = await database.get_user(user_id)
    
    if not user_data.get("start_bonus_given", 0):
        database.update_balance(user_id, START_BONUS, "Start bonus")
        
        db_path = database.get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET start_bonus_given = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        try:
            new_balance = database.get_user_balance(user_id)
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎉 Start bonusi: {START_BONUS} so‘m! Balans: {new_balance} so‘m."
            )
        except Exception as e:
            logger.error(f"Bonus message error: {e}")

# ------------------- BOSHQA HANDLERLAR -------------------
async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = "🎰 *BetWinner Bukmekeriga xush kelibsiz!* 🎰\n\n👇 Quyidagi tugmalar orqali imkoniyatlarni kashf eting:"
    await query.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

async def show_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not games_data:
        await query.edit_message_text(
            "Hozircha kunlik stavkalar mavjud emas.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Bosh menyu", callback_data="main_menu")]])
        )
        return
    text = "📊 *Bugungi kun stavkalari:*"
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_game_keyboard())

async def game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game_name = query.data.replace("game_", "")
    game = games_data.get(game_name)
    if not game:
        await query.message.reply_text("Topilmadi.")
        return

    game["views"] = game.get("views", 0) + 1
    save_games(games_data)

    text = game.get("text", "Maʼlumot yo'q")
    photo_id = game.get("photo_id")
    file_id = game.get("file_id")
    button_text = game.get("button_text")
    button_url = game.get("button_url")

    back_button = [[InlineKeyboardButton("◀️ Bosh menyu", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(back_button)
    
    if button_text and button_url:
        keyboard = [[InlineKeyboardButton(button_text, url=button_url)], back_button[0]]
        reply_markup = InlineKeyboardMarkup(keyboard)

    if file_id:
        await query.message.reply_document(document=file_id)

    if photo_id:
        await query.message.reply_photo(photo=photo_id, caption=text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await query.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)

async def earn_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    await database.get_user(user_id, username)

    referral_link = get_referral_link(user_id)
    text = (
        "💰 *Qanday qilib pul ishlash mumkin?*\n\n"
        f"Har bir do‘stingizni taklif qilganingiz uchun *{REFERRAL_BONUS} so‘m* olasiz.\n\n"
        f"Sizning referral havolangiz:\n`{referral_link}`"
    )
    share_url = f"https://t.me/share/url?url={referral_link}"
    keyboard = [
        [InlineKeyboardButton("📤 Ulashish", url=share_url)],
        [InlineKeyboardButton("💸 Pul chiqarish", callback_data="withdraw")],
        [InlineKeyboardButton("◀️ Bosh menyu", callback_data="main_menu")]
    ]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    user_data = await database.get_user(user_id, username)
    
    balance = user_data.get("balance", 0)
    referrals = user_data.get("referrals", 0)
    
    text = (
        f"💵 *Sizning balansingiz:*\n\n"
        f"Balans: *{balance} so‘m*\n"
        f"Takliflar: *{referrals}*\n\n"
        f"Minimal yechish: {MIN_WITHDRAW} so‘m."
    )
    keyboard = [
        [InlineKeyboardButton("💸 Pul chiqarish", callback_data="withdraw")],
        [InlineKeyboardButton("◀️ Bosh menyu", callback_data="main_menu")]
    ]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def withdraw_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    user_data = await database.get_user(user_id, username)
    
    balance = user_data.get("balance", 0)

    if balance < MIN_WITHDRAW:
        await query.edit_message_text(
            f"❌ Minimal balans {MIN_WITHDRAW} so‘m. Sizda {balance} so‘m.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Bosh menyu", callback_data="main_menu")]])
        )
        return

    code = user_data.get("withdraw_code")
    text = (
        f"💸 *Pul chiqarish*\n\n"
        f"Sizning kodingiz: `{code}`\n"
        f"Saytga o‘ting va kodni kiriting."
    )
    keyboard = [
        [InlineKeyboardButton("💳 Saytga o‘tish", url=WITHDRAW_SITE_URL)],
        [InlineKeyboardButton("◀️ Bosh menyu", callback_data="main_menu")]
    ]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# ------------------- ADMIN CALLBACKS -------------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Siz admin emassiz.")
        return
    await update.message.reply_text("👨‍💻 Admin paneli:", reply_markup=get_admin_keyboard())

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("Siz admin emassiz.")
        return

    data = query.data

    if data == "admin_stats":
        if not games_data:
            await query.edit_message_text("Maʼlumot yo‘q.")
            return
        lines = ["📊 Statistika:"]
        total = 0
        for name, game in games_data.items():
            views = game.get("views", 0)
            lines.append(f"• {name}: {views} marta")
            total += views
        lines.append(f"\nJami: {total} marta")
        await query.edit_message_text("\n".join(lines), reply_markup=get_admin_keyboard())
    
    elif data == "admin_users_count":
        stats = database.get_all_users_count()
        stats_text = (
            f"👥 *Foydalanuvchilar*\n\n"
            f"Jami: *{stats['total']}*\n"
            f"Faol: *{stats['active']}*\n"
            f"Referral: *{stats['referred']}*\n"
            f"Umumiy balans: *{stats['total_balance']} so‘m*"
        )
        await query.edit_message_text(stats_text, parse_mode="Markdown", reply_markup=get_admin_keyboard())

    elif data == "admin_close":
        await query.edit_message_text("Panel yopildi.")

    elif data == "admin_back":
        await query.edit_message_text("Admin paneli:", reply_markup=get_admin_keyboard())

# ------------------- BROADCAST -------------------
BROADCAST_MSG = 100

async def admin_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("Siz admin emassiz.")
        return ConversationHandler.END

    await query.edit_message_text(
        "📨 *Barchaga yuboriladigan xabarni kiriting:*\n\n/cancel - bekor qilish",
        parse_mode="Markdown"
    )
    return BROADCAST_MSG

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Siz admin emassiz.")
        return ConversationHandler.END

    message = update.message
    users = database.get_all_users()
    
    success_count = 0
    fail_count = 0
    
    status_msg = await update.message.reply_text(
        f"📨 Xabar yuborilmoqda...\nJami: {len(users)}"
    )

    for (user_id,) in users:
        try:
            if message.text:
                await context.bot.send_message(chat_id=user_id, text=message.text)
            elif message.photo:
                await context.bot.send_photo(chat_id=user_id, photo=message.photo[-1].file_id, caption=message.caption)
            else:
                fail_count += 1
                continue
            
            success_count += 1
            
            if (success_count + fail_count) % 10 == 0:
                await status_msg.edit_text(
                    f"📨 Yuborilmoqda...\n✅ {success_count}\n❌ {fail_count}\nJami: {len(users)}"
                )
                
        except Exception as e:
            fail_count += 1
            logger.error(f"Broadcast error: {e}")

    await status_msg.edit_text(
        f"📨 *Yakunlandi!*\n\n✅ {success_count}\n❌ {fail_count}\n👥 Jami: {len(users)}",
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard()
    )
    
    return ConversationHandler.END

async def broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Bekor qilindi.", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

# ------------------- ADD GAME (qisqartirilgan) -------------------
ADD_NAME, ADD_TEXT, ADD_PHOTO, ADD_FILE, ADD_BUTTON_TEXT, ADD_BUTTON_URL = range(6)

async def admin_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return ConversationHandler.END

    context.user_data.clear()
    context.user_data["add_game"] = {}
    await query.edit_message_text("Yangi kun stavkasi nomini kiriting:")
    return ADD_NAME

async def add_game_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Qayta kiriting:")
        return ADD_NAME
    if name in games_data:
        await update.message.reply_text("Bu nom mavjud. Boshqa nom kiriting:")
        return ADD_NAME
    context.user_data["add_game"]["name"] = name
    await update.message.reply_text("Matnni kiriting (HTML):")
    return ADD_TEXT

# Qolgan ADD GAME funksiyalari shu yerda davom etadi...
# (To'liq versiya uchun avvalgi kodlardan foydalaning)

async def add_game_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Bekor qilindi.", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

# ------------------- ASOSIY -------------------
def main():
    # Database ni ishga tushirish
    database.init_database()
    
    # Eski JSON ma'lumotlarni ko'chirish
    database.migrate_from_json()
    
    # Bot ni ishga tushirish
    app = Application.builder().token(TOKEN).build()

    # Handlerlar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(show_games, pattern="^show_games$"))
    app.add_handler(CallbackQueryHandler(game_callback, pattern="^game_"))
    app.add_handler(CallbackQueryHandler(earn_callback, pattern="^earn$"))
    app.add_handler(CallbackQueryHandler(balance_callback, pattern="^balance$"))
    app.add_handler(CallbackQueryHandler(withdraw_callback, pattern="^withdraw$"))
    app.add_handler(CallbackQueryHandler(back_to_main, pattern="^main_menu$"))
    
    # Admin
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^(admin_stats|admin_users_count|admin_close|admin_back)$"))
    
    # Broadcast
    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_broadcast_callback, pattern="^admin_broadcast$")],
        states={BROADCAST_MSG: [MessageHandler(filters.ALL & ~filters.COMMAND, broadcast_message)]},
        fallbacks=[CommandHandler("cancel", broadcast_cancel)],
    )
    app.add_handler(broadcast_conv)
    
    # Add Game (qisqa)
    add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_callback, pattern="^admin_add$")],
        states={
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_game_name)],
            # ... qolgan state lar
        },
        fallbacks=[CommandHandler("cancel", add_game_cancel)],
    )
    app.add_handler(add_conv)

    logger.info("✅ Bot started!")
    app.run_polling()

if __name__ == "__main__":
    main()
