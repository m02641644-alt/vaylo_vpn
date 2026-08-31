# -*- coding: utf-8 -*-
from aiogram import Router, F, Bot
from aiogram.filters import BaseFilter, StateFilter, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import database as db
import keyboards as kb
from texts import get_text, set_text, TEXT_DEFS
from utils import fmt_money, esc
from states import AdminFlow
from config import is_admin, ADMIN_IDS
from handlers.common import safe_edit

router = Router(name="admin")


class IsAdmin(BaseFilter):
    async def __call__(self, event) -> bool:
        return is_admin(event.from_user.id)


router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# ==========================================================
#  خانه پنل مدیریت
# ==========================================================
@router.callback_query(F.data == "adm_home")
async def cb_admin_home(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit(callback, "⚙️ <b>پنل مدیریت فروشگاه</b>\n\nیکی از گزینه‌ها رو انتخاب کن:", kb.kb_admin_main())
    await callback.answer()


@router.callback_query(F.data == "adm_stats")
async def cb_admin_stats(callback: CallbackQuery):
    s = db.get_stats()
    text = ("📊 <b>آمار فروشگاه</b>\n\n"
            f'👥 تعداد کاربران: {s["users"]}\n'
            f'🧾 تعداد کل سفارش‌ها: {s["orders"]}\n'
            f'⏳ سفارش‌های در انتظار: {s["pending"]}\n'
            f'✅ خریدهای موفق: {s["delivered"]}\n'
            f'💰 مجموع فروش: {fmt_money(s["total_sales"])}\n'
            f'🔥 پرفروش‌ترین پلن: {esc(s["best_plan_name"])} ({s["best_plan_count"]} فروش)\n'
            f'📦 موجودی فعلی مخزن: {s["stock"]} کانفیگ\n'
            f'🎁 موجودی اکانت تست: {s["trial_stock"]} عدد\n'
            f'📋 تعداد محصولات: {s["plans"]}')
    await safe_edit(callback, text, kb.kb_back("adm_home"))
    await callback.answer()


# ==========================================================
#  محصولات (پلن‌ها)
# ==========================================================
@router.callback_query(F.data == "adm_plans")
async def cb_admin_plans(callback: CallbackQuery):
    plans = db.get_all_plans()
    await safe_edit(callback, "🛍 <b>مدیریت محصولات</b>\n\nهر محصول: نام/قیمت برای ویرایش، 🗃 مخزن برای افزودن "
                               "کانفیگ، 🗑 برای حذف.", kb.kb_admin_plans(plans))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_plan_") & ~F.data.startswith("adm_plan_new"))
async def cb_admin_plan_detail(callback: CallbackQuery):
    plan_id = int(callback.data.split("_")[2])
    plan = db.get_plan(plan_id)
    if not plan:
        await callback.answer("محصول یافت نشد.", show_alert=True)
        return
    text = (f'📦 <b>{esc(plan["name"])}</b>\n\n'
            f'💰 قیمت: {fmt_money(plan["price"])}\n⏳ مدت: {esc(plan["duration_days"])} روز\n'
            f'📊 حجم: {esc(plan["volume"])}\n📝 توضیحات: {esc(plan["description"] or "-")}\n'
            f'📦 موجودی: {db.get_stock_count(plan_id)}\n'
            f'🔘 وضعیت: {"فعال ✅" if plan["active"] else "غیرفعال ❌"}')
    await safe_edit(callback, text, kb.kb_admin_plan_detail(plan))
    await callback.answer()


@router.callback_query(F.data == "adm_plan_new")
async def cb_admin_plan_new(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminFlow.np_name)
    await safe_edit(callback, "➕ <b>افزودن محصول جدید</b>\n\nمرحله ۱ از ۵ - نام محصول رو بفرست "
                               "(مثلاً: ۵ گیگ یک ماهه):", kb.kb_cancel())
    await callback.answer()


@router.message(StateFilter(AdminFlow.np_name))
async def msg_np_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AdminFlow.np_price)
    await message.answer("مرحله ۲ از ۵ - قیمت محصول رو به تومان بفرست (فقط عدد):", reply_markup=kb.kb_cancel())


@router.message(StateFilter(AdminFlow.np_price))
async def msg_np_price(message: Message, state: FSMContext):
    raw = "".join(ch for ch in (message.text or "") if ch.isdigit())
    if not raw:
        await message.answer("❌ عدد معتبر بفرست.", reply_markup=kb.kb_cancel())
        return
    await state.update_data(price=int(raw))
    await state.set_state(AdminFlow.np_duration)
    await message.answer("مرحله ۳ از ۵ - مدت زمان به روز رو بفرست (مثلاً 30):", reply_markup=kb.kb_cancel())


@router.message(StateFilter(AdminFlow.np_duration))
async def msg_np_duration(message: Message, state: FSMContext):
    raw = "".join(ch for ch in (message.text or "") if ch.isdigit()) or (message.text or "")
    await state.update_data(duration=raw)
    await state.set_state(AdminFlow.np_volume)
    await message.answer('مرحله ۴ از ۵ - حجم رو بفرست (مثلاً "30 گیگابایت" یا "نامحدود"):', reply_markup=kb.kb_cancel())


@router.message(StateFilter(AdminFlow.np_volume))
async def msg_np_volume(message: Message, state: FSMContext):
    await state.update_data(volume=message.text)
    await state.set_state(AdminFlow.np_desc)
    await message.answer('مرحله ۵ از ۵ - توضیحات کوتاه رو بفرست (یا "-" برای رد کردن):', reply_markup=kb.kb_cancel())


@router.message(StateFilter(AdminFlow.np_desc))
async def msg_np_desc(message: Message, state: FSMContext):
    data = await state.get_data()
    desc = "" if message.text.strip() == "-" else message.text
    plan_id = db.insert_plan(data["name"], desc, data["price"], data["duration"], data["volume"])
    await state.clear()
    await message.answer(f'✅ محصول «{esc(data["name"])}» اضافه شد.\n\nحالا کانفیگ‌هاش رو به مخزن اضافه کن:',
                          parse_mode="HTML")
    await state.set_state(AdminFlow.stock_add)
    await state.update_data(plan_id=plan_id)
    await message.answer("➕ کانفیگ‌ها رو ارسال کن (هر کانفیگ در یک خط جدا، هر چند تا که بخوای):",
                          reply_markup=kb.kb_cancel())


@router.callback_query(F.data.startswith("adm_pedit_"))
async def cb_admin_plan_field_edit(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    field, plan_id = parts[2], int(parts[3])
    labels = {"name": "نام", "price": "قیمت (تومان)", "dur": "مدت (روز)", "vol": "حجم", "desc": "توضیحات"}
    await state.set_state(AdminFlow.plan_field_edit)
    await state.update_data(field=field, plan_id=plan_id)
    await safe_edit(callback, f'✏️ مقدار جدید برای «{labels.get(field, field)}» رو بفرست:', kb.kb_cancel())
    await callback.answer()


@router.message(StateFilter(AdminFlow.plan_field_edit))
async def msg_plan_field_edit(message: Message, state: FSMContext):
    data = await state.get_data()
    field, plan_id = data["field"], data["plan_id"]
    plan = db.get_plan(plan_id)
    if not plan:
        await state.clear()
        await message.answer("محصول یافت نشد.", reply_markup=kb.kb_admin_main())
        return
    col_map = {"name": "name", "price": "price", "dur": "duration_days", "vol": "volume", "desc": "description"}
    value = message.text
    if field == "price":
        raw = "".join(ch for ch in value if ch.isdigit())
        value = int(raw) if raw else plan["price"]
    db.update_plan(plan_id, **{col_map[field]: value})
    await state.clear()
    await message.answer("✅ بروزرسانی شد.", reply_markup=kb.kb_admin_main())


@router.callback_query(F.data.startswith("adm_ptoggle_"))
async def cb_admin_plan_toggle(callback: CallbackQuery):
    plan_id = int(callback.data.split("_")[2])
    plan = db.get_plan(plan_id)
    if plan:
        db.update_plan(plan_id, active=0 if plan["active"] else 1)
        plan = db.get_plan(plan_id)
        text = (f'📦 <b>{esc(plan["name"])}</b>\n\n'
                f'💰 قیمت: {fmt_money(plan["price"])}\n⏳ مدت: {esc(plan["duration_days"])} روز\n'
                f'📊 حجم: {esc(plan["volume"])}\n📝 توضیحات: {esc(plan["description"] or "-")}\n'
                f'📦 موجودی: {db.get_stock_count(plan_id)}\n'
                f'🔘 وضعیت: {"فعال ✅" if plan["active"] else "غیرفعال ❌"}')
        await safe_edit(callback, text, kb.kb_admin_plan_detail(plan))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_pdel_"))
async def cb_admin_plan_delete_confirm(callback: CallbackQuery):
    plan_id = int(callback.data.split("_")[2])
    await safe_edit(callback, "⚠️ آیا از حذف این محصول مطمئنی؟ (کانفیگ‌های مخزن هم حذف می‌شن)",
                     kb.kb_confirm_delete(f"adm_pdelyes_{plan_id}", "adm_plans"))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_pdelyes_"))
async def cb_admin_plan_delete(callback: CallbackQuery):
    plan_id = int(callback.data.split("_")[2])
    db.clear_stock(plan_id)
    db.delete_plan(plan_id)
    plans = db.get_all_plans()
    await safe_edit(callback, "🗑 محصول حذف شد.\n\n🛍 <b>مدیریت محصولات</b>", kb.kb_admin_plans(plans))
    await callback.answer()


# -------------------- مخزن --------------------
@router.callback_query(F.data.startswith("adm_stkadd_"))
async def cb_admin_stock_add_start(callback: CallbackQuery, state: FSMContext):
    plan_id = int(callback.data.split("_")[2])
    await state.set_state(AdminFlow.stock_add)
    await state.update_data(plan_id=plan_id)
    await safe_edit(callback, "➕ کانفیگ‌ها رو ارسال کن (هر کانفیگ در یک خط جدا، هر چند تا که بخوای):", kb.kb_cancel())
    await callback.answer()


@router.message(StateFilter(AdminFlow.stock_add))
async def msg_admin_stock_add(message: Message, state: FSMContext):
    data = await state.get_data()
    plan_id = data["plan_id"]
    lines = [l.strip() for l in (message.text or "").split("\n") if l.strip()]
    if not lines:
        await message.answer("❌ متنی دریافت نشد.", reply_markup=kb.kb_cancel())
        return
    db.add_stock_bulk(plan_id, lines)
    await state.clear()
    await message.answer(f"✅ {len(lines)} کانفیگ به مخزن اضافه شد.", reply_markup=kb.kb_admin_main())


@router.callback_query(F.data.startswith("adm_stkclear_"))
async def cb_admin_stock_clear_confirm(callback: CallbackQuery):
    plan_id = int(callback.data.split("_")[2])
    await safe_edit(callback, "⚠️ همه موجودی این محصول حذف بشه؟",
                     kb.kb_confirm_delete(f"adm_stkclearyes_{plan_id}", f"adm_plan_{plan_id}"))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_stkclearyes_"))
async def cb_admin_stock_clear(callback: CallbackQuery):
    plan_id = int(callback.data.split("_")[2])
    n = db.clear_stock(plan_id)
    await safe_edit(callback, f"🗑 {n} کانفیگ حذف شد.", kb.kb_back("adm_plans"))
    await callback.answer()


# ==========================================================
#  اکانت تست رایگان
# ==========================================================
@router.callback_query(F.data == "adm_trial")
async def cb_admin_trial(callback: CallbackQuery):
    count = db.get_trial_stock_count()
    await safe_edit(callback, f"🎁 <b>اکانت‌های تست رایگان</b>\n\nموجودی فعلی: {count} عدد", kb.kb_admin_trial())
    await callback.answer()


@router.callback_query(F.data == "adm_trialadd")
async def cb_admin_trial_add_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminFlow.trial_add)
    await safe_edit(callback, "➕ اکانت‌های تست رو ارسال کن (هر کدوم در یک خط جدا):", kb.kb_cancel())
    await callback.answer()


@router.message(StateFilter(AdminFlow.trial_add))
async def msg_admin_trial_add(message: Message, state: FSMContext):
    lines = [l.strip() for l in (message.text or "").split("\n") if l.strip()]
    if not lines:
        await message.answer("❌ متنی دریافت نشد.", reply_markup=kb.kb_cancel())
        return
    db.add_trial_stock_bulk(lines)
    await state.clear()
    await message.answer(f"✅ {len(lines)} اکانت تست اضافه شد.", reply_markup=kb.kb_admin_main())


@router.callback_query(F.data == "adm_trialclear")
async def cb_admin_trial_clear_confirm(callback: CallbackQuery):
    await safe_edit(callback, "⚠️ همه‌ی اکانت‌های تست موجود حذف بشن؟",
                     kb.kb_confirm_delete("adm_trialclearyes", "adm_trial"))
    await callback.answer()


@router.callback_query(F.data == "adm_trialclearyes")
async def cb_admin_trial_clear(callback: CallbackQuery):
    n = db.clear_trial_stock()
    await safe_edit(callback, f"🗑 {n} اکانت تست حذف شد.", kb.kb_back("adm_home"))
    await callback.answer()


# ==========================================================
#  سفارش‌ها
# ==========================================================
@router.callback_query(F.data == "adm_orders")
async def cb_admin_orders(callback: CallbackQuery):
    orders = db.get_pending_orders()
    if not orders:
        await safe_edit(callback, "✅ سفارش در انتظاری وجود ندارد.", kb.kb_back("adm_home"))
        await callback.answer()
        return
    await safe_edit(callback, f"🧾 <b>سفارش‌های در انتظار تایید</b> ({len(orders)})", kb.kb_admin_orders(orders))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_ordv_"))
async def cb_admin_order_view(callback: CallbackQuery, bot: Bot):
    order_id = int(callback.data.split("_")[2])
    order = db.get_order(order_id)
    if not order:
        await callback.answer("سفارش یافت نشد.", show_alert=True)
        return
    user = db.get_user(order["user_id"])
    item_name = "شارژ کیف پول"
    if order["type"] == "purchase":
        plan = db.get_plan(order["plan_id"])
        item_name = plan["name"] if plan else "-"
    text = (f'🧾 سفارش #{order["order_id"]}\n'
            f'👤 کاربر: {esc(user["first_name"] if user else "")} - <code>{order["user_id"]}</code>\n'
            f'📦 مورد: {esc(item_name)}\n💰 مبلغ: {fmt_money(order["amount"])}\n'
            f'📅 تاریخ: {esc(order["created_date"])}')
    if order["receipt_file_id"]:
        await bot.send_photo(callback.message.chat.id, order["receipt_file_id"], caption=text, parse_mode="HTML",
                              reply_markup=kb.kb_admin_order_actions(order_id))
    else:
        await safe_edit(callback, text, kb.kb_admin_order_actions(order_id))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_ord_ok_"))
async def cb_admin_order_approve(callback: CallbackQuery, bot: Bot):
    order_id = int(callback.data.split("_")[3])
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    order = db.get_order(order_id)
    if not order or order["status"] != "pending":
        await callback.message.answer("این سفارش قبلاً پردازش شده.")
        await callback.answer()
        return

    if order["type"] == "topup":
        db.change_balance(order["user_id"], order["amount"], "شارژ کیف پول (تایید ادمین)",
                           related_order_id=order_id)
        db.update_order(order_id, status="approved", processed_date=db.now_str())
        await callback.message.answer(f'✅ سفارش شارژ #{order_id} تایید شد.')
        await bot.send_message(order["user_id"], get_text("TOPUP_DELIVERED", amount=fmt_money(order["amount"])))
        await callback.answer()
        return

    plan = db.get_plan(order["plan_id"])
    if not plan:
        await callback.message.answer("❌ محصول این سفارش دیگر وجود ندارد.")
        await callback.answer()
        return
    stock_item = db.allocate_and_sell_stock(order["plan_id"], order["user_id"], order_id)
    if not stock_item:
        await callback.message.answer("❌ موجودی این محصول تمام شده! ابتدا از «مدیریت محصولات» کانفیگ اضافه کن، "
                                       "سپس دوباره تایید بزن.")
        await callback.answer()
        return
    db.update_order(order_id, status="delivered", processed_date=db.now_str(),
                     delivered_stock_id=stock_item["stock_id"])
    if order["discount_code"]:
        db.increment_discount_usage(order["discount_code"])
    await callback.message.answer(f'✅ سفارش #{order_id} تایید و سرویس ارسال شد.')
    await bot.send_message(order["user_id"], get_text("PURCHASE_DELIVERED", plan_name=esc(plan["name"])),
                            parse_mode="HTML")
    await bot.send_message(order["user_id"], f'<code>{esc(stock_item["config_text"])}</code>', parse_mode="HTML")
    await callback.answer()

    from handlers.user import _handle_referral_reward
    await _handle_referral_reward(bot, order["user_id"], order["amount"])


@router.callback_query(F.data.startswith("adm_ord_no_"))
async def cb_admin_order_reject_prompt(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split("_")[3])
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await state.set_state(AdminFlow.reject_reason)
    await state.update_data(order_id=order_id)
    await callback.message.answer(f"✏️ دلیل رد سفارش #{order_id} رو بنویس (یا «-» برای رد بدون دلیل):",
                                   reply_markup=kb.kb_cancel())
    await callback.answer()


@router.message(StateFilter(AdminFlow.reject_reason))
async def msg_admin_reject_reason(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    order_id = data["order_id"]
    await state.clear()
    order = db.get_order(order_id)
    if not order or order["status"] != "pending":
        await message.answer("سفارش یافت نشد یا قبلاً پردازش شده.", reply_markup=kb.kb_admin_main())
        return
    reason = "" if message.text.strip() == "-" else message.text
    db.update_order(order_id, status="rejected", processed_date=db.now_str(), admin_note=reason)
    await message.answer(f"❌ سفارش #{order_id} رد شد.", reply_markup=kb.kb_admin_main())
    reason_line = f"📝 دلیل: {esc(reason)}" if reason else ""
    await bot.send_message(order["user_id"], get_text("ORDER_REJECTED", order_id=order_id, reason=reason_line))


# ==========================================================
#  کاربران
# ==========================================================
@router.callback_query(F.data == "adm_users")
async def cb_admin_users(callback: CallbackQuery):
    await safe_edit(callback, "👥 <b>مدیریت کاربران</b>", kb.kb_admin_users_home())
    await callback.answer()


@router.callback_query(F.data == "adm_usearch")
async def cb_admin_user_search_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminFlow.user_search)
    await safe_edit(callback, "🔎 آیدی عددی یا یوزرنیم کاربر رو بفرست:", kb.kb_cancel())
    await callback.answer()


async def _render_user_detail(user_id):
    user = db.get_user(user_id)
    orders = db.get_user_delivered_orders(user_id)
    username_part = f' (@{esc(user["username"])})' if user["username"] else ""
    ban_status = "مسدود" if user["banned"] else "عادی"
    text = (f'👤 <b>{esc(user["first_name"])}</b>{username_part}\n\n'
            f'🆔 آیدی: <code>{user["user_id"]}</code>\n📅 عضویت: {esc(user["join_date"])}\n'
            f'💳 موجودی: {fmt_money(user["balance"])}\n📦 تعداد خرید: {len(orders)}\n'
            f'🚫 وضعیت: {ban_status}')
    return text, kb.kb_admin_user_actions(user["user_id"], user["banned"])


@router.message(StateFilter(AdminFlow.user_search))
async def msg_admin_user_search(message: Message, state: FSMContext):
    await state.clear()
    user = db.search_user(message.text)
    if not user:
        await message.answer("❌ کاربری با این مشخصات پیدا نشد.", reply_markup=kb.kb_admin_main())
        return
    text, markup = await _render_user_detail(user["user_id"])
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data.startswith("adm_uadd_") | F.data.startswith("adm_usub_"))
async def cb_admin_balance_adjust_start(callback: CallbackQuery, state: FSMContext):
    mode = "add" if callback.data.startswith("adm_uadd_") else "sub"
    target_id = int(callback.data.split("_")[2])
    await state.set_state(AdminFlow.balance_adjust)
    await state.update_data(target_id=target_id, mode=mode)
    await safe_edit(callback, "✏️ مبلغ مورد نظر (تومان) رو بفرست:", kb.kb_cancel())
    await callback.answer()


@router.message(StateFilter(AdminFlow.balance_adjust))
async def msg_admin_balance_adjust(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target_id, mode = data["target_id"], data["mode"]
    await state.clear()
    raw = "".join(ch for ch in (message.text or "") if ch.isdigit())
    if not raw:
        await message.answer("❌ عدد معتبر نبود.", reply_markup=kb.kb_admin_main())
        return
    amount = int(raw)
    delta = amount if mode == "add" else -amount
    db.change_balance(target_id, delta, "افزایش دستی توسط ادمین" if mode == "add" else "کاهش دستی توسط ادمین")
    await message.answer("✅ موجودی کاربر بروزرسانی شد.", reply_markup=kb.kb_admin_main())
    try:
        if mode == "add":
            await bot.send_message(target_id, f"💳 مبلغ {fmt_money(amount)} توسط پشتیبانی به کیف پول شما اضافه شد.")
        else:
            await bot.send_message(target_id, f"💳 مبلغ {fmt_money(amount)} از کیف پول شما کسر شد.")
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_uban_"))
async def cb_admin_toggle_ban(callback: CallbackQuery, bot: Bot):
    target_id = int(callback.data.split("_")[2])
    new_val = db.toggle_ban(target_id)
    text, markup = await _render_user_detail(target_id)
    await safe_edit(callback, text, markup)
    await callback.answer()
    try:
        if new_val:
            await bot.send_message(target_id, get_text("BANNED_MSG"))
        else:
            await bot.send_message(target_id, "✅ دسترسی شما به ربات مجدداً فعال شد.")
    except Exception:
        pass


# ==========================================================
#  کدهای تخفیف
# ==========================================================
@router.callback_query(F.data == "adm_discounts")
async def cb_admin_discounts(callback: CallbackQuery):
    discounts = db.get_all_discounts()
    await safe_edit(callback, "🎟 <b>کدهای تخفیف</b>", kb.kb_admin_discounts(discounts))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_discview_"))
async def cb_admin_discount_view(callback: CallbackQuery):
    code = callback.data.split("_", 2)[2]
    d = db.get_discount(code)
    if not d:
        await callback.answer("یافت نشد.", show_alert=True)
        return
    scope = "همه‌ی محصولات"
    if d["plan_id"]:
        p = db.get_plan(d["plan_id"])
        scope = p["name"] if p else "-"
    val = f'{d["percent"]}٪' if d["percent"] else fmt_money(d["fixed_amount"])
    text = (f'🎟 <b>{esc(d["code"])}</b>\n\n💵 مقدار تخفیف: {val}\n📦 قابل استفاده برای: {esc(scope)}\n'
            f'🔢 استفاده‌شده: {d["used_count"]} از {d["max_uses"] or "نامحدود"}')
    await safe_edit(callback, text, kb.kb_admin_discount_detail(code))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_discdel_"))
async def cb_admin_discount_delete(callback: CallbackQuery):
    code = callback.data.split("_", 2)[2]
    db.delete_discount(code)
    discounts = db.get_all_discounts()
    await safe_edit(callback, "🗑 کد تخفیف حذف شد.\n\n🎟 <b>کدهای تخفیف</b>", kb.kb_admin_discounts(discounts))
    await callback.answer()


@router.callback_query(F.data == "adm_disc_new")
async def cb_admin_discount_new(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminFlow.disc_code)
    await safe_edit(callback, "🎟 کد تخفیف رو بفرست (فقط حروف/عدد انگلیسی، مثل OFF20):", kb.kb_cancel())
    await callback.answer()


@router.message(StateFilter(AdminFlow.disc_code))
async def msg_admin_discount_code(message: Message, state: FSMContext):
    code = (message.text or "").strip().upper().replace(" ", "")
    if not code or not code.isalnum():
        await message.answer("❌ کد نامعتبره، فقط حروف و عدد انگلیسی بفرست.", reply_markup=kb.kb_cancel())
        return
    await state.update_data(code=code)
    await message.answer("نوع تخفیف رو انتخاب کن:", reply_markup=kb.kb_discount_type())


@router.callback_query(F.data.in_(["disctype_percent", "disctype_fixed"]), StateFilter(AdminFlow.disc_code))
async def cb_admin_discount_type(callback: CallbackQuery, state: FSMContext):
    disc_type = "percent" if callback.data == "disctype_percent" else "fixed"
    await state.update_data(disc_type=disc_type)
    await state.set_state(AdminFlow.disc_value)
    label = "درصد تخفیف رو بفرست (بین ۱ تا ۱۰۰):" if disc_type == "percent" else "مبلغ تخفیف رو به تومان بفرست:"
    await safe_edit(callback, label, kb.kb_cancel())
    await callback.answer()


@router.message(StateFilter(AdminFlow.disc_value))
async def msg_admin_discount_value(message: Message, state: FSMContext):
    raw = "".join(ch for ch in (message.text or "") if ch.isdigit())
    if not raw:
        await message.answer("❌ عدد معتبر بفرست.", reply_markup=kb.kb_cancel())
        return
    await state.update_data(disc_value=int(raw))
    await state.set_state(AdminFlow.disc_max_uses)
    await message.answer("حداکثر تعداد استفاده از این کد چقدره؟ (0 = نامحدود)", reply_markup=kb.kb_cancel())


@router.message(StateFilter(AdminFlow.disc_max_uses))
async def msg_admin_discount_maxuses(message: Message, state: FSMContext):
    raw = "".join(ch for ch in (message.text or "") if ch.isdigit())
    max_uses = int(raw) if raw else 0
    await state.update_data(max_uses=max_uses)
    plans = db.get_active_plans()
    await message.answer("این کد برای کدوم محصول(ها) معتبر باشه؟", reply_markup=kb.kb_discount_plan_scope(plans))


@router.callback_query(F.data.startswith("discscope_"))
async def cb_admin_discount_scope(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    scope = callback.data.split("_", 1)[1]
    plan_id = None if scope == "all" else int(scope)
    percent = data["disc_value"] if data["disc_type"] == "percent" else 0
    fixed = data["disc_value"] if data["disc_type"] == "fixed" else 0
    db.create_discount(data["code"], percent=percent, fixed_amount=fixed, max_uses=data["max_uses"], plan_id=plan_id)
    await state.clear()
    await safe_edit(callback, f'✅ کد تخفیف «{esc(data["code"])}» ساخته شد.', kb.kb_back("adm_discounts"))
    await callback.answer()


# ==========================================================
#  کانال‌های عضویت اجباری
# ==========================================================
@router.callback_query(F.data == "adm_channels")
async def cb_admin_channels(callback: CallbackQuery):
    channels = db.get_channels()
    join_required = db.get_setting("JOIN_REQUIRED", "FALSE") == "TRUE"
    await safe_edit(callback, "📢 <b>کانال‌های عضویت اجباری</b>\n\n⚠️ ربات باید ادمین کانال باشه.",
                     kb.kb_admin_channels(channels, join_required))
    await callback.answer()


@router.callback_query(F.data == "adm_ch_toggle")
async def cb_admin_channel_toggle(callback: CallbackQuery):
    cur = db.get_setting("JOIN_REQUIRED", "FALSE")
    db.set_setting("JOIN_REQUIRED", "FALSE" if cur == "TRUE" else "TRUE")
    channels = db.get_channels()
    join_required = db.get_setting("JOIN_REQUIRED", "FALSE") == "TRUE"
    await safe_edit(callback, "📢 <b>کانال‌های عضویت اجباری</b>\n\n⚠️ ربات باید ادمین کانال باشه.",
                     kb.kb_admin_channels(channels, join_required))
    await callback.answer()


@router.callback_query(F.data == "adm_chadd")
async def cb_admin_channel_add_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminFlow.channel_add_id)
    await safe_edit(callback, "آیدی کانال رو بفرست (مثل @mychannel یا -1001234567890):", kb.kb_cancel())
    await callback.answer()


@router.message(StateFilter(AdminFlow.channel_add_id))
async def msg_admin_channel_id(message: Message, state: FSMContext):
    await state.update_data(chat_id=message.text.strip())
    await state.set_state(AdminFlow.channel_add_link)
    await message.answer("لینک عضویت/دعوت کانال رو بفرست:", reply_markup=kb.kb_cancel())


@router.message(StateFilter(AdminFlow.channel_add_link))
async def msg_admin_channel_link(message: Message, state: FSMContext):
    data = await state.get_data()
    db.add_channel(data["chat_id"], message.text.strip())
    await state.clear()
    await message.answer("✅ کانال اضافه شد.", reply_markup=kb.kb_admin_main())


@router.callback_query(F.data.startswith("adm_chdel_"))
async def cb_admin_channel_del(callback: CallbackQuery):
    ch_id = int(callback.data.split("_")[2])
    db.remove_channel(ch_id)
    channels = db.get_channels()
    join_required = db.get_setting("JOIN_REQUIRED", "FALSE") == "TRUE"
    await safe_edit(callback, "🗑 کانال حذف شد.", kb.kb_admin_channels(channels, join_required))
    await callback.answer()


# ==========================================================
#  متن‌های ربات
# ==========================================================
@router.callback_query(F.data == "adm_texts")
async def cb_admin_texts(callback: CallbackQuery):
    await safe_edit(callback, "📝 <b>متن‌های ربات</b>\n\nهر متن رو انتخاب کن تا ویرایشش کنی.", kb.kb_admin_texts(TEXT_DEFS))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_txt_"))
async def cb_admin_text_edit_start(callback: CallbackQuery, state: FSMContext):
    key = callback.data[len("adm_txt_"):]
    d = TEXT_DEFS.get(key)
    if not d:
        await callback.answer("یافت نشد.", show_alert=True)
        return
    await state.set_state(AdminFlow.text_edit)
    await state.update_data(key=key)
    vars_hint = ("متغیرهای قابل‌استفاده: " + " ".join("{" + v + "}" for v in d["vars"])) if d["vars"] else \
        "این متن متغیر ندارد."
    current = get_text(key)
    await safe_edit(callback, f'✏️ مقدار جدید برای «{d["label"]}» رو بفرست.\n\n{vars_hint}\n\n📄 مقدار فعلی:\n{esc(current)}',
                     kb.kb_cancel())
    await callback.answer()


@router.message(StateFilter(AdminFlow.text_edit))
async def msg_admin_text_edit(message: Message, state: FSMContext):
    data = await state.get_data()
    set_text(data["key"], message.text)
    await state.clear()
    await message.answer("✅ متن بروزرسانی شد.", reply_markup=kb.kb_admin_main())


# ==========================================================
#  تنظیمات مالی و سایر
# ==========================================================
@router.callback_query(F.data == "adm_financial")
async def cb_admin_financial(callback: CallbackQuery):
    await safe_edit(callback, "💰 <b>تنظیمات مالی</b>", kb.kb_admin_financial())
    await callback.answer()


@router.callback_query(F.data == "adm_other")
async def cb_admin_other(callback: CallbackQuery):
    await safe_edit(callback, "🛠 <b>سایر تنظیمات</b>", kb.kb_admin_other())
    await callback.answer()


_SETTING_LABELS = {
    "CARD_NUMBER": "شماره کارت", "CARD_HOLDER": "نام صاحب کارت", "TOPUP_MIN": "حداقل مبلغ شارژ (تومان)",
    "TOPUP_MAX": "حداکثر مبلغ شارژ (تومان، 0 = بدون سقف)", "REFERRAL_REWARD": "مبلغ پاداش رفرال (تومان)",
    "REFERRAL_MIN_PURCHASE": "حداقل مبلغ خرید برای فعال‌شدن پاداش رفرال",
    "SUPPORT_USERNAME": "آیدی پشتیبانی",
}


@router.callback_query(F.data.startswith("adm_set_"))
async def cb_admin_setting_edit_start(callback: CallbackQuery, state: FSMContext):
    key = callback.data[len("adm_set_"):]
    label = _SETTING_LABELS.get(key, key)
    await state.set_state(AdminFlow.setting_edit)
    await state.update_data(key=key)
    current = db.get_setting(key, "-")
    await safe_edit(callback, f'✏️ مقدار جدید برای «{label}» رو بفرست.\n\nمقدار فعلی: {esc(current)}', kb.kb_cancel())
    await callback.answer()


@router.message(StateFilter(AdminFlow.setting_edit))
async def msg_admin_setting_edit(message: Message, state: FSMContext):
    data = await state.get_data()
    db.set_setting(data["key"], message.text.strip())
    await state.clear()
    await message.answer("✅ تنظیمات بروزرسانی شد.", reply_markup=kb.kb_admin_main())


# ==========================================================
#  ارسال همگانی
# ==========================================================
@router.callback_query(F.data == "adm_broadcast")
async def cb_admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminFlow.broadcast)
    await safe_edit(callback, "📣 پیام همگانی رو بفرست (متن یا عکس با کپشن). برای همه‌ی کاربران ارسال می‌شه.",
                     kb.kb_cancel())
    await callback.answer()


@router.message(StateFilter(AdminFlow.broadcast))
async def msg_admin_broadcast(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    users = db.get_all_users()
    await message.answer(f"⏳ در حال ارسال به {len(users)} کاربر...")
    success, fail = 0, 0
    for u in users:
        try:
            await bot.copy_message(u["user_id"], from_chat_id=message.chat.id, message_id=message.message_id)
            success += 1
        except Exception:
            fail += 1
    await message.answer(f"✅ ارسال همگانی تمام شد.\n📤 موفق: {success}\n❌ ناموفق: {fail}",
                          reply_markup=kb.kb_admin_main())


# ==========================================================
#  پاسخ به پیام پشتیبانی (چت زنده)
# ==========================================================
@router.callback_query(F.data.startswith("adm_reply_"))
async def cb_admin_reply_start(callback: CallbackQuery, state: FSMContext):
    target_id = int(callback.data.split("_")[2])
    await state.clear()
    db.set_admin_reply_target(callback.from_user.id, target_id)
    await callback.message.answer(f"✍️ حالا هر پیامی بفرستی مستقیم برای کاربر <code>{target_id}</code> ارسال "
                                   f"می‌شه.\nبرای پایان چت دستور /done رو بفرست.", parse_mode="HTML")
    await callback.answer()


@router.message(Command("done"))
async def cmd_admin_done(message: Message):
    db.clear_admin_reply_target(message.from_user.id)
    await message.answer("🔴 چت با کاربر پایان یافت.", reply_markup=kb.kb_admin_main())


async def _has_reply_target(message: Message) -> bool:
    return db.get_admin_reply_target(message.from_user.id) is not None


@router.message(StateFilter(None), _has_reply_target)
async def msg_admin_reply_relay(message: Message, bot: Bot):
    target = db.get_admin_reply_target(message.from_user.id)
    if not target:
        return
    try:
        await bot.send_message(target, "🛟 <b>پاسخ پشتیبانی:</b>", parse_mode="HTML")
        await bot.copy_message(target, from_chat_id=message.chat.id, message_id=message.message_id)
        await message.answer("✅ پیام ارسال شد. (برای پایان چت: /done)")
    except Exception as e:
        await message.answer(f"❌ ارسال پیام ناموفق بود: {e}")
