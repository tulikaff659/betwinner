import os

# ------------------- SOZLAMALAR -------------------
# Railway environment variables orqali olinadi
TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "6935090105"))
DATA_FILE = "games.json"
DB_FILE = "bot_database.db"

REFERRAL_BONUS = 2500
START_BONUS = 15000
MIN_WITHDRAW = 25000
BOT_USERNAME = os.environ.get("BOT_USERNAME", "Winwin_premium_bonusbot")
WITHDRAW_SITE_URL = os.environ.get("WITHDRAW_SITE_URL", "https://futbolinsidepulyechish.netlify.app/")
