import random
import string
from datetime import datetime

def generate_game_row():
    """Random olma qatorini yaratish"""
    apples = []
    positions = random.sample(range(5), 2)
    
    for i in range(5):
        if i == positions[0]:
            apples.append("🍎")  # Butun olma
        elif i == positions[1]:
            apples.append("❓")  # Sirli olma
        else:
            apples.append("🍎")  # Qolganlari butun olma
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
