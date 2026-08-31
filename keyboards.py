# -*- coding: utf-8 -*-
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import database as db
from utils import fmt_money
from config import is_admin


def _kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)


def btn(text, cb=None, url=None):
    if url:
        return InlineKeyboardButton(text=text, url=url)
    return InlineKeyboardButton(text=text, callback_data=cb)


# -------------------- منوی اصلی --------------------
def kb_main_menu(user_id):
    rows = [
        [btn("🛒 خرید اشتراک", "menu_buy"), btn("🎁 اکانت تست رایگان", "menu_trial")],
        [btn("👤 حساب کاربری", "menu_account"), btn("📦 سرویس‌های من", "menu_myconfigs")],
        [btn("💳 کیف پول", "menu_wallet"), btn("🎁 دعوت دوستان", "menu_referral")],
        [btn("🛟 پشتیبانی آنلاین", "menu_support"), btn("📋 قوانین", "menu_rules")],
        [btn("ℹ️ درباره ما", "menu_about")],
    ]
    if is_admin(user_id):
        rows.append([btn("⚙️ پنل مدیریت", "adm_home")])
    return _kb(rows)


def kb_back(cb="back_main", label="🔙 بازگشت"):
    return _kb([[btn(label, cb)]])


def kb_cancel():
    return _kb([[btn("❌ انصراف", "cancel_flow")]])


def kb_confirm_delete(cb_yes, cb_no):
    return _kb([[btn("✅ بله، حذف کن", cb_yes), btn("❌ انصراف", cb_no)]])


def kb_join(channels):
    rows = [[btn("📢 عضویت در " + (c["link"] or c["chat_id"]), url=c["link"])] for c in channels if c["link"]]
    rows.append([btn("✅ عضو شدم، بررسی کن", "check_join")])
    return _kb(rows)


# -------------------- خرید --------------------
def kb_plans_list(plans):
    rows = []
    for p in plans:
        stock = db.get_stock_count(p["plan_id"])
        badge = "🟢" if stock > 0 else "🔴"
        rows.append([btn(f'{badge} {p["name"]} | {fmt_money(p["price"])}', f'plan_{p["plan_id"]}')])
    rows.append([btn("🔙 بازگشت", "back_main")])
    return _kb(rows)


def kb_plan_detail(plan, has_stock, has_discount=False):
    rows = []
    if has_stock:
        rows.append([btn("💳 پرداخت از کیف پول", f'buy_wallet_{plan["plan_id"]}')])
        rows.append([btn("🏦 پرداخت کارت به کارت", f'buy_card_{plan["plan_id"]}')])
        code_label = "🎟 اعمال کد تخفیف" if not has_discount else "🎟 تغییر کد تخفیف"
        rows.append([btn(code_label, f'disc_apply_{plan["plan_id"]}')])
    rows.append([btn("🔙 بازگشت به لیست پلن‌ها", "buy_menu")])
    return _kb(rows)


def kb_confirm_order(plan_id, method):
    return _kb([
        [btn("✅ تایید و ثبت سفارش", f'ordconf_{method}_{plan_id}')],
        [btn("❌ انصراف", f'plan_{plan_id}')],
    ])


# -------------------- حساب / کیف پول --------------------
def kb_wallet():
    return _kb([[btn("💰 شارژ کیف پول", "wallet_topup")], [btn("🔙 بازگشت", "back_main")]])


def kb_myconfigs(items):
    rows = []
    for it in items:
        plan = db.get_plan(it["plan_id"])
        name = plan["name"] if plan else "سرویس"
        rows.append([btn(f'📦 {name} - {it["sold_date"]}', f'cfg_{it["stock_id"]}')])
    rows.append([btn("🔙 بازگشت", "back_main")])
    return _kb(rows)


# -------------------- پشتیبانی --------------------
def kb_end_chat():
    return _kb([[btn("🔴 پایان گفتگو", "support_end")]])


def kb_reply_to_user(user_id):
    return _kb([[btn("✍️ پاسخ به کاربر", f'adm_reply_{user_id}')]])


# ==========================================================
#                     پنل مدیریت
# ==========================================================
def kb_admin_main():
    return _kb([
        [btn("📊 آمار فروشگاه", "adm_stats")],
        [btn("🛍 مدیریت محصولات", "adm_plans"), btn("🎁 اکانت‌های تست", "adm_trial")],
        [btn("🧾 سفارش‌های در انتظار", "adm_orders")],
        [btn("👥 مدیریت کاربران", "adm_users"), btn("🎟 کدهای تخفیف", "adm_discounts")],
        [btn("📢 کانال‌های اجباری", "adm_channels")],
        [btn("📝 متن‌های ربات", "adm_texts")],
        [btn("💰 تنظیمات مالی", "adm_financial"), btn("🛠 سایر تنظیمات", "adm_other")],
        [btn("📣 ارسال همگانی", "adm_broadcast")],
    ])


# -------------------- محصولات --------------------
def kb_admin_plans(plans):
    rows = []
    for p in plans:
        status = "🟢" if p["active"] else "⚪️"
        stock = db.get_stock_count(p["plan_id"])
        rows.append([btn(f'{status} {p["name"]} — {fmt_money(p["price"])}', f'adm_plan_{p["plan_id"]}')])
        rows.append([btn(f'🗃 مخزن ({stock})', f'adm_stkadd_{p["plan_id"]}'),
                     btn("🗑 حذف", f'adm_pdel_{p["plan_id"]}')])
    rows.append([btn("➕ افزودن محصول جدید", "adm_plan_new")])
    rows.append([btn("🔙 بازگشت", "adm_home")])
    return _kb(rows)


def kb_admin_plan_detail(plan):
    toggle_text = "⏸ غیرفعال کردن" if plan["active"] else "▶️ فعال کردن"
    pid = plan["plan_id"]
    return _kb([
        [btn("✏️ نام", f'adm_pedit_name_{pid}'), btn("✏️ قیمت", f'adm_pedit_price_{pid}')],
        [btn("✏️ مدت", f'adm_pedit_dur_{pid}'), btn("✏️ حجم", f'adm_pedit_vol_{pid}')],
        [btn("✏️ توضیحات", f'adm_pedit_desc_{pid}')],
        [btn("🗃 افزودن به مخزن", f'adm_stkadd_{pid}'), btn("🗑 خالی‌کردن مخزن", f'adm_stkclear_{pid}')],
        [btn(toggle_text, f'adm_ptoggle_{pid}')],
        [btn("🗑 حذف محصول", f'adm_pdel_{pid}')],
        [btn("🔙 بازگشت به لیست", "adm_plans")],
    ])


# -------------------- اکانت تست --------------------
def kb_admin_trial():
    return _kb([
        [btn("➕ افزودن اکانت تست (چندتایی)", "adm_trialadd")],
        [btn("🗑 حذف همه موجودی تست", "adm_trialclear")],
        [btn("🔙 بازگشت", "adm_home")],
    ])


# -------------------- سفارش‌ها --------------------
def kb_admin_orders(orders):
    rows = []
    for o in orders[:25]:
        label = f'#{o["order_id"]} - {o["type"]} - {fmt_money(o["amount"])}'
        rows.append([btn(label, f'adm_ordv_{o["order_id"]}')])
    rows.append([btn("🔙 بازگشت", "adm_home")])
    return _kb(rows)


def kb_admin_order_actions(order_id):
    return _kb([[btn("✅ تایید", f'adm_ord_ok_{order_id}'), btn("❌ رد", f'adm_ord_no_{order_id}')]])


# -------------------- کاربران --------------------
def kb_admin_user_actions(user_id, banned):
    ban_text = "✅ رفع مسدودیت" if banned else "🚫 مسدود کردن"
    return _kb([
        [btn("➕ افزایش موجودی", f'adm_uadd_{user_id}'), btn("➖ کاهش موجودی", f'adm_usub_{user_id}')],
        [btn(ban_text, f'adm_uban_{user_id}')],
        [btn("🔙 بازگشت", "adm_users")],
    ])


def kb_admin_users_home():
    return _kb([[btn("🔎 جستجوی کاربر", "adm_usearch")], [btn("🔙 بازگشت", "adm_home")]])


# -------------------- کدهای تخفیف --------------------
def kb_admin_discounts(discounts):
    rows = []
    for d in discounts:
        val = f'{d["percent"]}%' if d["percent"] else fmt_money(d["fixed_amount"])
        rows.append([btn(f'🎟 {d["code"]} — {val} ({d["used_count"]}/{d["max_uses"] or "∞"})',
                          f'adm_discview_{d["code"]}')])
    rows.append([btn("➕ کد تخفیف جدید", "adm_disc_new")])
    rows.append([btn("🔙 بازگشت", "adm_home")])
    return _kb(rows)


def kb_admin_discount_detail(code):
    return _kb([[btn("🗑 حذف این کد", f'adm_discdel_{code}')], [btn("🔙 بازگشت", "adm_discounts")]])


def kb_discount_type():
    return _kb([
        [btn("٪ درصدی", "disctype_percent"), btn("💰 مبلغ ثابت", "disctype_fixed")],
        [btn("❌ انصراف", "cancel_flow")],
    ])


def kb_discount_plan_scope(plans):
    rows = [[btn("🌐 همه‌ی پلن‌ها", "discscope_all")]]
    for p in plans:
        rows.append([btn(p["name"], f'discscope_{p["plan_id"]}')])
    return _kb(rows)


# -------------------- کانال‌های اجباری --------------------
def kb_admin_channels(channels, join_required):
    rows = []
    for c in channels:
        rows.append([btn(f'❌ حذف — {c["chat_id"]}', f'adm_chdel_{c["id"]}')])
    rows.append([btn("➕ افزودن کانال", "adm_chadd")])
    toggle_text = "🟢 عضویت اجباری: فعال" if join_required else "⚪️ عضویت اجباری: غیرفعال"
    rows.append([btn(toggle_text, "adm_ch_toggle")])
    rows.append([btn("🔙 بازگشت", "adm_home")])
    return _kb(rows)


# -------------------- متن‌ها --------------------
def kb_admin_texts(text_defs):
    rows = [[btn(v["label"], f'adm_txt_{k}')] for k, v in text_defs.items()]
    rows.append([btn("🔙 بازگشت", "adm_home")])
    return _kb(rows)


# -------------------- تنظیمات مالی و سایر --------------------
def kb_admin_financial():
    return _kb([
        [btn("💳 شماره کارت", "adm_set_CARD_NUMBER"), btn("👤 نام صاحب کارت", "adm_set_CARD_HOLDER")],
        [btn("⬇️ حداقل شارژ", "adm_set_TOPUP_MIN"), btn("⬆️ حداکثر شارژ", "adm_set_TOPUP_MAX")],
        [btn("🎁 مبلغ پاداش رفرال", "adm_set_REFERRAL_REWARD")],
        [btn("🎯 حداقل خرید برای رفرال", "adm_set_REFERRAL_MIN_PURCHASE")],
        [btn("🔙 بازگشت", "adm_home")],
    ])


def kb_admin_other():
    return _kb([
        [btn("💬 آیدی پشتیبانی", "adm_set_SUPPORT_USERNAME")],
        [btn("🔙 بازگشت", "adm_home")],
    ])
