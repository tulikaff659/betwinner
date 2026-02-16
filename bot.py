import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from database import Database
from handlers import setup_handlers

logging.basicConfig(level=logging.INFO)

# Bot va dispatcher
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())
db = Database()

async def on_startup():
    """Bot ishga tushganda"""
    logging.info("🍎 Apple of Fortune Signal Bot ishga tushdi!")
    
    # Adminlarga xabar yuborish
    from config import ADMIN_IDS
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, "✅ Bot ishga tushdi!")
        except:
            pass

async def on_shutdown():
    """Bot to'xtaganda"""
    logging.info("Bot to'xtatilmoqda...")
    db.close()
    await bot.session.close()

async def main():
    # Handlerlarni ulash
    setup_handlers(dp, db, bot)
    
    # Startup va shutdown eventlarini ulash
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Botni ishga tushirish
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
