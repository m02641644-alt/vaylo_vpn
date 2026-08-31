# -*- coding: utf-8 -*-
"""
همه‌ی متن‌های ربات اینجا با یک کلید، لیست متغیرهای مجاز و مقدار پیش‌فرض تعریف شدن.
ادمین از پنل می‌تونه هر کدوم رو با متغیرهاش ویرایش کنه. مقدار ویرایش‌شده در جدول settings
با کلید TXT_<name> ذخیره می‌شه.
"""
import database as db

TEXT_DEFS = {
    "WELCOME": {
        "label": "👋 پیام خوش‌آمدگویی",
        "vars": ["first_name"],
        "default": "🌟 سلام {first_name} عزیز، به فروشگاه اشتراک خوش اومدی!\n\nاز منوی زیر یکی از گزینه‌ها رو انتخاب کن 👇",
    },
    "ABOUT": {
        "label": "ℹ️ درباره ما",
        "vars": [],
        "default": "🤖 این ربات کاملاً خودکار فعالیت می‌کنه و سرویس شما بلافاصله بعد از پرداخت ارسال می‌شه.",
    },
    "RULES": {
        "label": "📋 قوانین و مقررات",
        "vars": [],
        "default": "📋 <b>قوانین و مقررات</b>\n\n"
                   "۱. مسئولیت استفاده از سرویس بر عهده‌ی خود کاربر است.\n"
                   "۲. هرگونه سو‌استفاده از سرویس منجر به مسدودسازی می‌شود.\n"
                   "۳. وجه پرداختی بابت سرویس‌های فعال‌شده قابل بازگشت نیست.\n"
                   "۴. برای مشکلات فنی از بخش پشتیبانی اقدام کنید.",
    },
    "PLANS_HEADER": {
        "label": "🛒 سرتیتر لیست پلن‌ها",
        "vars": [],
        "default": "🛒 <b>لیست پلن‌های اشتراک</b>\n\nیکی از پلن‌های زیر رو انتخاب کن:\n🟢 موجود  |  🔴 ناموجود",
    },
    "PLAN_DETAIL": {
        "label": "📦 نمایش جزئیات پلن",
        "vars": ["name", "description", "duration", "volume", "price", "stock"],
        "default": "📦 <b>{name}</b>\n\n{description}\n\n⏳ مدت: {duration} روز\n📊 حجم: {volume}\n💰 قیمت: {price}\n📦 موجودی: {stock}",
    },
    "ACCOUNT": {
        "label": "👤 حساب کاربری",
        "vars": ["user_id", "join_date", "balance", "orders_count"],
        "default": "👤 <b>حساب کاربری</b>\n\n🆔 آیدی عددی: {user_id}\n📅 تاریخ عضویت: {join_date}\n💳 موجودی کیف پول: {balance}\n📦 تعداد خریدها: {orders_count}",
    },
    "WALLET": {
        "label": "💳 صفحه کیف پول",
        "vars": ["balance"],
        "default": "💳 <b>کیف پول شما</b>\n\nموجودی فعلی: {balance}\n\nبرای شارژ روی دکمه زیر بزن 👇",
    },
    "REFERRAL": {
        "label": "🎁 صفحه دعوت دوستان",
        "vars": ["reward", "link", "count"],
        "default": "🎁 <b>دعوت از دوستان</b>\n\nبا دعوت هر دوست و اولین خریدش، {reward} به کیف پولت اضافه می‌شه!\n\n🔗 لینک اختصاصی شما:\n<code>{link}</code>\n\n👥 تعداد افراد دعوت‌شده: {count}",
    },
    "SUPPORT_PROMPT": {
        "label": "🛟 پیام شروع پشتیبانی آنلاین",
        "vars": [],
        "default": "🛟 <b>پشتیبانی آنلاین</b>\n\nهمین الان با پشتیبان در ارتباطی! پیامت رو بنویس (متن یا عکس).\nبرای پایان گفتگو دکمه زیر رو بزن.",
    },
    "RECEIPT_PROMPT": {
        "label": "🏦 راهنمای پرداخت کارت‌به‌کارت",
        "vars": ["card_number", "card_holder", "amount"],
        "default": "🏦 <b>پرداخت کارت به کارت</b>\n\n💳 شماره کارت: <code>{card_number}</code>\n👤 به نام: {card_holder}\n💰 مبلغ: {amount}\n\n✅ مبلغ رو واریز کن و بعد عکس رسید رو همینجا بفرست.",
    },
    "PURCHASE_DELIVERED": {
        "label": "✅ پیام تحویل موفق سفارش",
        "vars": ["plan_name"],
        "default": "✅ پرداخت شما تایید شد! 🎉\n\n📦 پلن: {plan_name}\n\n👇 کانفیگ شما:",
    },
    "TOPUP_DELIVERED": {
        "label": "✅ پیام تایید شارژ کیف پول",
        "vars": ["amount"],
        "default": "✅ کیف پول شما به مبلغ {amount} شارژ شد. 🎉",
    },
    "ORDER_REJECTED": {
        "label": "❌ پیام رد سفارش",
        "vars": ["order_id", "reason"],
        "default": "❌ متاسفانه سفارش شما (#{order_id}) رد شد.\n{reason}\n\nدر صورت وجود سوال با پشتیبانی در ارتباط باش.",
    },
    "JOIN_PROMPT": {
        "label": "📢 پیام درخواست عضویت در کانال",
        "vars": [],
        "default": "⚠️ برای استفاده از ربات ابتدا باید عضو کانال(های) زیر بشی، بعد دکمه «بررسی مجدد» رو بزن.",
    },
    "BANNED_MSG": {
        "label": "🚫 پیام کاربر مسدود",
        "vars": [],
        "default": "🚫 دسترسی شما به این ربات مسدود شده است.",
    },
}


def get_text(key, **vars_):
    d = TEXT_DEFS.get(key, {})
    raw = db.get_setting(f"TXT_{key}", "") or d.get("default", "")
    for k, v in vars_.items():
        raw = raw.replace("{" + k + "}", str(v))
    return raw


def set_text(key, value):
    db.set_setting(f"TXT_{key}", value)
