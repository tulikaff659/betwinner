from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

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
