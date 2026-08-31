# -*- coding: utf-8 -*-
"""
نقطه ورود ربات. برای اجرا: python bot.py
روی Railway به‌صورت خودکار همین فایل اجرا می‌شه (به Procfile نگاه کن).
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
import database as db
from middlewares import GuardMiddleware
from handlers import common, admin, user

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("bot")


async def main():
    db.init_db()
    log.info("✅ دیتابیس آماده شد.")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.outer_middleware(GuardMiddleware())
    dp.callback_query.outer_middleware(GuardMiddleware())

    # ترتیب مهمه: ادمین قبل از کاربر (تا هندلرهای عمومی fallback جلوی ادمین رو نگیرن)
    dp.include_router(common.router)
    dp.include_router(admin.router)
    dp.include_router(user.router)

    me = await bot.get_me()
    if not db.get_setting("BOT_USERNAME", ""):
        db.set_setting("BOT_USERNAME", me.username)
    log.info(f"🤖 ربات با یوزرنیم @{me.username} شروع به کار کرد.")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("ربات متوقف شد.")
