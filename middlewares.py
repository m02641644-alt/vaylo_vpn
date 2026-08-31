# -*- coding: utf-8 -*-
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable

import database as db
from texts import get_text


class GuardMiddleware(BaseMiddleware):
    """
    این میان‌افزار روی همه‌ی پیام‌ها و کالبک‌ها اجرا می‌شه:
    ۱) کاربر رو در دیتابیس ثبت/بروزرسانی می‌کنه (در صورت نبود)
    ۲) اگه کاربر مسدود باشه، جلوی اجرای هندلر رو می‌گیره
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = event.from_user
        if user is None or user.is_bot:
            return await handler(event, data)

        db.ensure_user(user.id, user.username, user.first_name)
        u = db.get_user(user.id)

        if u and u["banned"]:
            text = get_text("BANNED_MSG")
            if isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
            else:
                await event.answer(text)
            return  # جلوگیری از رسیدن به هندلر اصلی

        return await handler(event, data)
