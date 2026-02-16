import os
from dotenv import load_dotenv

load_dotenv()

# Bot token
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Adminlar ro'yxati (vergul bilan ajratilgan)
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "123456789").split(",")]

# Ma'lumotlar bazasi fayli
DATABASE_FILE = os.getenv("DATABASE_FILE", "apple_fortune.db")

# APK yuklash havolasi
APK_URL = os.getenv("APK_URL", "https://example.com/app.apk")
