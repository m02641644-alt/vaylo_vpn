# -*- coding: utf-8 -*-
"""
تنظیمات کلی ربات - همه از متغیرهای محیطی (Environment Variables) خونده می‌شن.
در Railway از تب Variables پروژه‌ت این مقادیر رو ست کن.
"""
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise RuntimeError("❌ متغیر محیطی BOT_TOKEN تنظیم نشده است. آن را در Railway Variables اضافه کنید.")

_admin_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = set()
for part in _admin_raw.split(","):
    part = part.strip()
    if part.isdigit():
        ADMIN_IDS.add(int(part))

DB_PATH = os.getenv("DB_PATH", "data/bot.db")

# اطمینان از وجود پوشه دیتابیس
_db_dir = os.path.dirname(DB_PATH)
if _db_dir and not os.path.exists(_db_dir):
    os.makedirs(_db_dir, exist_ok=True)


def is_admin(user_id: int) -> bool:
    return int(user_id) in ADMIN_IDS
