# -*- coding: utf-8 -*-
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

import database as db
import keyboards as kb
from texts import get_text

router = Router(name="common")


async def safe_edit(callback: CallbackQuery, text: str, markup=None):
    """پیام رو ادیت می‌کنه؛ اگه ادیت ممکن نبود (مثلاً پیام عکس بود) پیام جدید می‌فرسته."""
    try:
        await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML",
                                          disable_web_page_preview=True)
    except TelegramBadRequest:
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            pass
        await callback.message.answer(text, reply_markup=markup, parse_mode="HTML",
                                       disable_web_page_preview=True)


def check_join(bot_channels_status_map) -> bool:
    return all(bot_channels_status_map)


async def user_is_joined(bot, user_id) -> bool:
    if db.get_setting("JOIN_REQUIRED", "FALSE") != "TRUE":
        return True
    channels = db.get_channels()
    if not channels:
        return True
    for c in channels:
        try:
            member = await bot.get_chat_member(c["chat_id"], user_id)
            if member.status not in ("member", "administrator", "creator"):
                return False
        except Exception:
            continue  # اگه ربات ادمین کانال نبود یا خطا خورد، مانع کاربر نشو
    return True


async def send_join_prompt(callback_or_message):
    channels = db.get_channels()
    text = get_text("JOIN_PROMPT")
    markup = kb.kb_join(channels)
    if isinstance(callback_or_message, CallbackQuery):
        await safe_edit(callback_or_message, text, markup)
    else:
        await callback_or_message.answer(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data == "back_main")
async def cb_back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit(callback, "🏠 منوی اصلی", kb.kb_main_menu(callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data == "cancel_flow")
async def cb_cancel_flow(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit(callback, "❌ لغو شد.\n\n🏠 منوی اصلی", kb.kb_main_menu(callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data == "check_join")
async def cb_check_join(callback: CallbackQuery, bot):
    if await user_is_joined(bot, callback.from_user.id):
        await safe_edit(callback, get_text("WELCOME", first_name=callback.from_user.first_name or ""),
                         kb.kb_main_menu(callback.from_user.id))
        await callback.answer()
    else:
        await callback.answer("❌ هنوز عضو همه‌ی کانال‌ها نشدی!", show_alert=True)
