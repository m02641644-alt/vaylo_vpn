# -*- coding: utf-8 -*-
from aiogram.fsm.state import State, StatesGroup


class UserFlow(StatesGroup):
    waiting_topup_amount = State()
    waiting_receipt = State()
    waiting_discount_code = State()


class AdminFlow(StatesGroup):
    # افزودن پلن جدید (مرحله‌ای)
    np_name = State()
    np_price = State()
    np_duration = State()
    np_volume = State()
    np_desc = State()

    # ویرایش یک فیلد پلن
    plan_field_edit = State()

    # افزودن موجودی (مخزن)
    stock_add = State()

    # افزودن اکانت تست
    trial_add = State()

    # سفارش‌ها
    reject_reason = State()

    # کاربران
    user_search = State()
    balance_adjust = State()

    # ارسال همگانی
    broadcast = State()

    # تنظیمات و متن‌ها
    setting_edit = State()
    text_edit = State()

    # کانال‌های اجباری
    channel_add_id = State()
    channel_add_link = State()

    # کدهای تخفیف
    disc_code = State()
    disc_value = State()
    disc_max_uses = State()

    # پاسخ به کاربر (پشتیبانی) - در عمل با admin_reply_map در دیتابیس مدیریت می‌شه
