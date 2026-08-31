# -*- coding: utf-8 -*-
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import database as db
import keyboards as kb
from texts import get_text
from utils import fmt_money, esc
from states import UserFlow
from handlers.common import safe_edit, user_is_joined, send_join_prompt

router = Router(name="user")


# ==========================================================
#  شروع
# ==========================================================
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    parts = (message.text or "").split()
    if len(parts) > 1 and parts[1].startswith("ref"):
        ref_raw = parts[1][3:]
        if ref_raw.isdigit() and int(ref_raw) != message.from_user.id and db.get_user(int(ref_raw)):
            db.set_referrer_if_empty(message.from_user.id, int(ref_raw))

    if not await user_is_joined(bot, message.from_user.id):
        await send_join_prompt(message)
        return

    await message.answer(
        get_text("WELCOME", first_name=message.from_user.first_name or ""),
        reply_markup=kb.kb_main_menu(message.from_user.id), parse_mode="HTML"
    )


# ==========================================================
#  خرید اشتراک
# ==========================================================
def _plan_detail_view(plan, discount=None):
    stock = db.get_stock_count(plan["plan_id"])
    price = plan["price"]
    extra = ""
    if discount:
        price = max(0, price - discount["amount"])
        extra = f'\n\n🎟 کد <b>{esc(discount["code"])}</b> اعمال شد!\n💵 قیمت با تخفیف: {fmt_money(price)}'
    text = get_text(
        "PLAN_DETAIL",
        name=esc(plan["name"]),
        description=esc(plan["description"] or ""),
        duration=esc(plan["duration_days"]),
        volume=esc(plan["volume"]),
        price=fmt_money(price),
        stock=(f"{stock} عدد ✅" if stock > 0 else "ناموجود ❌"),
    ) + extra
    markup = kb.kb_plan_detail(plan, stock > 0, has_discount=bool(discount))
    return text, markup, price


@router.callback_query(F.data.in_(["menu_buy", "buy_menu"]))
async def cb_buy_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    plans = db.get_active_plans()
    if not plans:
        await safe_edit(callback, "😔 در حال حاضر پلنی برای فروش موجود نیست.", kb.kb_back())
        await callback.answer()
        return
    await safe_edit(callback, get_text("PLANS_HEADER"), kb.kb_plans_list(plans))
    await callback.answer()


@router.callback_query(F.data.startswith("plan_"))
async def cb_plan_detail(callback: CallbackQuery, state: FSMContext):
    plan_id = int(callback.data.split("_")[1])
    plan = db.get_plan(plan_id)
    if not plan:
        await callback.answer("این پلن دیگر موجود نیست.", show_alert=True)
        return
    data = await state.get_data()
    discount = None
    if data.get("discount_plan_id") == plan_id:
        discount = {"code": data.get("discount_code"), "amount": data.get("discount_amount", 0)}
    text, markup, _ = _plan_detail_view(plan, discount)
    await safe_edit(callback, text, markup)
    await callback.answer()


@router.callback_query(F.data.startswith("buy_wallet_") | F.data.startswith("buy_card_"))
async def cb_buy_confirm(callback: CallbackQuery, state: FSMContext):
    method = "wallet" if callback.data.startswith("buy_wallet_") else "card"
    plan_id = int(callback.data.split("_")[2])
    plan = db.get_plan(plan_id)
    if not plan or db.get_stock_count(plan_id) <= 0:
        await callback.answer("موجودی این پلن تمام شده است.", show_alert=True)
        return
    data = await state.get_data()
    amount = plan["price"]
    if data.get("discount_plan_id") == plan_id:
        amount = max(0, amount - data.get("discount_amount", 0))
    method_label = "💳 کیف پول" if method == "wallet" else "🏦 کارت به کارت"
    text = (f'🧾 <b>تایید سفارش</b>\n\n📦 پلن: {esc(plan["name"])}\n💰 مبلغ: {fmt_money(amount)}\n'
            f'💳 روش پرداخت: {method_label}\n\nآیا تایید می‌کنی؟')
    await safe_edit(callback, text, kb.kb_confirm_order(plan_id, method))
    await callback.answer()


@router.callback_query(F.data.startswith("ordconf_wallet_"))
async def cb_order_confirm_wallet(callback: CallbackQuery, state: FSMContext, bot: Bot):
    plan_id = int(callback.data.split("_")[2])
    plan = db.get_plan(plan_id)
    user_id = callback.from_user.id
    if not plan:
        await callback.answer("پلن یافت نشد.", show_alert=True)
        return
    data = await state.get_data()
    discount_code, discount_amount = None, 0
    amount = plan["price"]
    if data.get("discount_plan_id") == plan_id:
        discount_code = data.get("discount_code")
        discount_amount = data.get("discount_amount", 0)
        amount = max(0, amount - discount_amount)

    user = db.get_user(user_id)
    if int(user["balance"]) < amount:
        await safe_edit(callback, f'❌ موجودی کیف پول شما کافی نیست.\nموجودی فعلی: {fmt_money(user["balance"])}\n'
                                   f'مبلغ لازم: {fmt_money(amount)}', kb.kb_back(f"plan_{plan_id}"))
        await callback.answer()
        return

    stock_item = db.allocate_and_sell_stock(plan_id, user_id, None)
    if not stock_item:
        await safe_edit(callback, "❌ متاسفانه موجودی این پلن هم‌اکنون تمام شد.", kb.kb_back("buy_menu"))
        await callback.answer()
        return

    order_id = db.create_order(user_id, plan_id, amount, "purchase", "کیف پول", "delivered",
                                discount_code=discount_code or "", discount_amount=discount_amount)
    db.update_order(order_id, delivered_stock_id=stock_item["stock_id"], processed_date=db.now_str())
    db.change_balance(user_id, -amount, "خرید پلن", plan["name"], order_id)
    if discount_code:
        db.increment_discount_usage(discount_code)
    await state.clear()

    await safe_edit(callback, "✅ خرید شما با موفقیت انجام شد!", None)
    await bot.send_message(user_id, get_text("PURCHASE_DELIVERED", plan_name=esc(plan["name"])),
                            reply_markup=kb.kb_main_menu(user_id), parse_mode="HTML")
    await bot.send_message(user_id, f'<code>{esc(stock_item["config_text"])}</code>', parse_mode="HTML")
    await callback.answer()
    await _handle_referral_reward(bot, user_id, amount)


@router.callback_query(F.data.startswith("ordconf_card_"))
async def cb_order_confirm_card(callback: CallbackQuery, state: FSMContext):
    plan_id = int(callback.data.split("_")[2])
    plan = db.get_plan(plan_id)
    if not plan:
        await callback.answer("پلن یافت نشد.", show_alert=True)
        return
    data = await state.get_data()
    discount_code, discount_amount = None, 0
    if data.get("discount_plan_id") == plan_id:
        discount_code = data.get("discount_code")
        discount_amount = data.get("discount_amount", 0)

    await state.update_data(pending_plan_id=plan_id, pending_discount_code=discount_code or "",
                             pending_discount_amount=discount_amount)
    await state.set_state(UserFlow.waiting_receipt)
    await state.update_data(receipt_type="purchase")

    amount = max(0, plan["price"] - discount_amount)
    card = db.get_setting("CARD_NUMBER", "-")
    holder = db.get_setting("CARD_HOLDER", "-")
    text = get_text("RECEIPT_PROMPT", card_number=esc(card), card_holder=esc(holder), amount=fmt_money(amount))
    await safe_edit(callback, text, kb.kb_cancel())
    await callback.answer()


# -------------------- کد تخفیف --------------------
@router.callback_query(F.data.startswith("disc_apply_"))
async def cb_discount_apply(callback: CallbackQuery, state: FSMContext):
    plan_id = int(callback.data.split("_")[2])
    await state.update_data(discount_target_plan=plan_id)
    await state.set_state(UserFlow.waiting_discount_code)
    await safe_edit(callback, "🎟 کد تخفیف رو بفرست:", kb.kb_cancel())
    await callback.answer()


@router.message(StateFilter(UserFlow.waiting_discount_code))
async def msg_discount_code(message: Message, state: FSMContext):
    data = await state.get_data()
    plan_id = data.get("discount_target_plan")
    plan = db.get_plan(plan_id)
    code = (message.text or "").strip().upper()
    disc = db.get_discount(code)

    if not plan:
        await state.clear()
        await message.answer("پلن یافت نشد.", reply_markup=kb.kb_main_menu(message.from_user.id))
        return
    if not disc or not disc["active"]:
        await message.answer("❌ کد تخفیف معتبر نیست.", reply_markup=kb.kb_cancel())
        return
    if disc["max_uses"] and disc["used_count"] >= disc["max_uses"]:
        await message.answer("❌ ظرفیت استفاده از این کد تمام شده.", reply_markup=kb.kb_cancel())
        return
    if disc["plan_id"] and int(disc["plan_id"]) != plan_id:
        await message.answer("❌ این کد برای این پلن معتبر نیست.", reply_markup=kb.kb_cancel())
        return

    if disc["percent"]:
        amount = int(plan["price"] * disc["percent"] / 100)
    else:
        amount = int(disc["fixed_amount"])
    amount = min(amount, plan["price"])

    await state.update_data(discount_plan_id=plan_id, discount_code=code, discount_amount=amount)
    await state.set_state(None)

    text, markup, _ = _plan_detail_view(plan, {"code": code, "amount": amount})
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


# ==========================================================
#  اکانت تست رایگان
# ==========================================================
@router.callback_query(F.data == "menu_trial")
async def cb_trial(callback: CallbackQuery):
    status, config_text = db.claim_trial(callback.from_user.id)
    if status == "already_used":
        await safe_edit(callback, "⚠️ شما قبلاً از اکانت تست رایگان استفاده کرده‌اید.", kb.kb_back())
    elif status == "empty":
        await safe_edit(callback, "😔 اکانت‌های تست رایگان به پایان رسید.", kb.kb_back())
    else:
        await safe_edit(callback, "✅ اکانت تست رایگان شما آماده‌ست 🎉\n\n👇 مشخصات اتصال:", kb.kb_back())
        await callback.message.answer(f"<code>{esc(config_text)}</code>", parse_mode="HTML")
    await callback.answer()


# ==========================================================
#  حساب کاربری / سرویس‌های من
# ==========================================================
@router.callback_query(F.data == "menu_account")
async def cb_account(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    orders = db.get_user_delivered_orders(callback.from_user.id)
    text = get_text("ACCOUNT", user_id=user["user_id"], join_date=esc(user["join_date"]),
                     balance=fmt_money(user["balance"]), orders_count=len(orders))
    await safe_edit(callback, text, kb.kb_back())
    await callback.answer()


@router.callback_query(F.data == "menu_myconfigs")
async def cb_myconfigs(callback: CallbackQuery):
    items = db.get_user_stock_items(callback.from_user.id)
    if not items:
        await safe_edit(callback, "📭 هنوز هیچ سرویسی خریداری نکردی.", kb.kb_back())
        await callback.answer()
        return
    await safe_edit(callback, f"📦 <b>سرویس‌های خریداری‌شده شما</b> ({len(items)} مورد)", kb.kb_myconfigs(items))
    await callback.answer()


@router.callback_query(F.data.startswith("cfg_"))
async def cb_view_config(callback: CallbackQuery):
    stock_id = int(callback.data.split("_")[1])
    item = db.get_stock_item(stock_id)
    if not item or item["sold_to"] != callback.from_user.id:
        await callback.answer("یافت نشد.", show_alert=True)
        return
    plan = db.get_plan(item["plan_id"])
    text = f'📦 {esc(plan["name"] if plan else "")}\n📅 تاریخ خرید: {esc(item["sold_date"])}\n\n<code>{esc(item["config_text"])}</code>'
    await safe_edit(callback, text, kb.kb_back("menu_myconfigs"))
    await callback.answer()


# ==========================================================
#  کیف پول
# ==========================================================
@router.callback_query(F.data == "menu_wallet")
async def cb_wallet(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    await safe_edit(callback, get_text("WALLET", balance=fmt_money(user["balance"])), kb.kb_wallet())
    await callback.answer()


@router.callback_query(F.data == "wallet_topup")
async def cb_wallet_topup(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserFlow.waiting_topup_amount)
    tmin = int(db.get_setting("TOPUP_MIN", "0") or 0)
    tmax = int(db.get_setting("TOPUP_MAX", "0") or 0)
    hint = f"حداقل {fmt_money(tmin)}"
    if tmax > 0:
        hint += f" و حداکثر {fmt_money(tmax)}"
    await safe_edit(callback, f"💰 مبلغ شارژ رو به تومان بفرست.\n({hint})", kb.kb_cancel())
    await callback.answer()


@router.message(StateFilter(UserFlow.waiting_topup_amount))
async def msg_topup_amount(message: Message, state: FSMContext):
    raw = "".join(ch for ch in (message.text or "") if ch.isdigit())
    if not raw:
        await message.answer("❌ لطفاً یک مبلغ معتبر بفرست.", reply_markup=kb.kb_cancel())
        return
    amount = int(raw)
    tmin = int(db.get_setting("TOPUP_MIN", "0") or 0)
    tmax = int(db.get_setting("TOPUP_MAX", "0") or 0)
    if tmin and amount < tmin:
        await message.answer(f"❌ حداقل مبلغ شارژ {fmt_money(tmin)} است.", reply_markup=kb.kb_cancel())
        return
    if tmax and amount > tmax:
        await message.answer(f"❌ حداکثر مبلغ شارژ {fmt_money(tmax)} است.", reply_markup=kb.kb_cancel())
        return

    await state.update_data(receipt_type="topup", pending_amount=amount)
    await state.set_state(UserFlow.waiting_receipt)
    card = db.get_setting("CARD_NUMBER", "-")
    holder = db.get_setting("CARD_HOLDER", "-")
    text = get_text("RECEIPT_PROMPT", card_number=esc(card), card_holder=esc(holder), amount=fmt_money(amount))
    await message.answer(text, reply_markup=kb.kb_cancel(), parse_mode="HTML")


# -------------------- دریافت رسید (خرید یا شارژ) --------------------
@router.message(StateFilter(UserFlow.waiting_receipt), F.photo)
async def msg_receipt_photo(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    rtype = data.get("receipt_type")
    file_id = message.photo[-1].file_id
    user = message.from_user

    if rtype == "purchase":
        plan_id = data.get("pending_plan_id")
        plan = db.get_plan(plan_id)
        if not plan:
            await state.clear()
            await message.answer("❌ این پلن دیگر موجود نیست.", reply_markup=kb.kb_main_menu(user.id))
            return
        discount_code = data.get("pending_discount_code") or ""
        discount_amount = data.get("pending_discount_amount") or 0
        amount = max(0, plan["price"] - discount_amount)
        order_id = db.create_order(user.id, plan_id, amount, "purchase", "کارت به کارت", "pending",
                                    receipt_file_id=file_id, discount_code=discount_code,
                                    discount_amount=discount_amount)
        await state.clear()
        await message.answer("✅ رسید شما ثبت شد و در انتظار تایید ادمین است.\nبعد از تایید، سرویس به‌صورت "
                              "خودکار براتون ارسال می‌شه. 🙏", reply_markup=kb.kb_main_menu(user.id))
        await _notify_admins_new_order(bot, order_id, user, plan["name"])
    elif rtype == "topup":
        amount = data.get("pending_amount")
        order_id = db.create_order(user.id, None, amount, "topup", "کارت به کارت", "pending", receipt_file_id=file_id)
        await state.clear()
        await message.answer("✅ درخواست شارژ کیف پول شما ثبت شد و در انتظار تایید ادمین است.",
                              reply_markup=kb.kb_main_menu(user.id))
        await _notify_admins_new_order(bot, order_id, user, "شارژ کیف پول")
    else:
        await state.clear()
        await message.answer("خطایی رخ داد، دوباره تلاش کن.", reply_markup=kb.kb_main_menu(user.id))


@router.message(StateFilter(UserFlow.waiting_receipt))
async def msg_receipt_not_photo(message: Message):
    await message.answer("📷 لطفاً عکس رسید پرداخت رو ارسال کن (نه متن).", reply_markup=kb.kb_cancel())


async def _notify_admins_new_order(bot: Bot, order_id, user, item_name):
    from config import ADMIN_IDS
    order = db.get_order(order_id)
    text = (f'🔔 <b>سفارش جدید</b>\n\n👤 کاربر: {esc(user.first_name)}'
            f'{f" (@{esc(user.username)})" if user.username else ""}\n'
            f'🆔 آیدی: <code>{user.id}</code>\n📦 مورد: {esc(item_name)}\n💰 مبلغ: {fmt_money(order["amount"])}\n'
            f'🧾 شماره سفارش: #{order_id}')
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(admin_id, order["receipt_file_id"], caption=text, parse_mode="HTML",
                                  reply_markup=kb.kb_admin_order_actions(order_id))
        except Exception:
            pass


# ==========================================================
#  رفرال
# ==========================================================
@router.callback_query(F.data == "menu_referral")
async def cb_referral(callback: CallbackQuery, bot: Bot):
    bot_username = db.get_setting("BOT_USERNAME", "")
    if not bot_username:
        me = await bot.get_me()
        bot_username = me.username
        db.set_setting("BOT_USERNAME", bot_username)
    reward = db.get_setting("REFERRAL_REWARD", "0")
    count = db.count_referrals(callback.from_user.id)
    link = f"https://t.me/{bot_username}?start=ref{callback.from_user.id}"
    text = get_text("REFERRAL", reward=fmt_money(reward), link=link, count=count)
    await safe_edit(callback, text, kb.kb_back())
    await callback.answer()


async def _handle_referral_reward(bot: Bot, user_id, purchase_amount):
    user = db.get_user(user_id)
    if not user or not user["referrer_id"] or user["referral_earned"]:
        return
    min_purchase = int(db.get_setting("REFERRAL_MIN_PURCHASE", "0") or 0)
    if purchase_amount < min_purchase:
        return
    reward = int(db.get_setting("REFERRAL_REWARD", "0") or 0)
    if reward <= 0:
        return
    referrer = db.get_user(user["referrer_id"])
    if not referrer:
        return
    db.change_balance(referrer["user_id"], reward, "پاداش رفرال", f"دعوت کاربر {user_id}")
    db.set_referral_earned(user_id)
    try:
        await bot.send_message(referrer["user_id"],
                                f"🎉 تبریک! یکی از دوستانی که دعوت کردی خرید انجام داد و مبلغ "
                                f"{fmt_money(reward)} به کیف پولت اضافه شد.")
    except Exception:
        pass


# ==========================================================
#  پشتیبانی آنلاین
# ==========================================================
@router.callback_query(F.data == "menu_support")
async def cb_support_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    db.set_support_active(callback.from_user.id, True)
    await safe_edit(callback, get_text("SUPPORT_PROMPT"), kb.kb_end_chat())
    await callback.answer()


@router.callback_query(F.data == "support_end")
async def cb_support_end(callback: CallbackQuery):
    db.set_support_active(callback.from_user.id, False)
    await safe_edit(callback, "🔴 چت پشتیبانی پایان یافت.\n\n🏠 منوی اصلی", kb.kb_main_menu(callback.from_user.id))
    await callback.answer()


async def _is_support_msg(message: Message) -> bool:
    return db.is_support_active(message.from_user.id)


@router.message(StateFilter(None), _is_support_msg)
async def msg_support_relay(message: Message, bot: Bot):
    from config import ADMIN_IDS
    user = message.from_user
    header = (f'🛟 <b>پیام پشتیبانی آنلاین</b>\n👤 {esc(user.first_name)}'
              f'{f" (@{esc(user.username)})" if user.username else ""}\n🆔 <code>{user.id}</code>')
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, header, parse_mode="HTML", reply_markup=kb.kb_reply_to_user(user.id))
            await bot.copy_message(admin_id, from_chat_id=message.chat.id, message_id=message.message_id)
        except Exception:
            pass


# ==========================================================
#  قوانین / درباره ما
# ==========================================================
@router.callback_query(F.data == "menu_rules")
async def cb_rules(callback: CallbackQuery):
    await safe_edit(callback, get_text("RULES"), kb.kb_back())
    await callback.answer()


@router.callback_query(F.data == "menu_about")
async def cb_about(callback: CallbackQuery):
    await safe_edit(callback, get_text("ABOUT"), kb.kb_back())
    await callback.answer()


# ==========================================================
#  پیش‌فرض (پیام‌های بدون‌حالت که به هیچ‌کدام از موارد بالا نخوردند)
# ==========================================================
@router.message(StateFilter(None))
async def msg_fallback(message: Message):
    await message.answer("از دکمه‌های منو استفاده کن 👇", reply_markup=kb.kb_main_menu(message.from_user.id))
