# -*- coding: utf-8 -*-
"""
لایه دیتابیس (SQLite). همه‌ی داده‌های ربات اینجا نگه‌داری می‌شه.
برای هاست روی Railway حتماً یک Volume به مسیر DB_PATH وصل کن تا داده‌ها
بعد از هر دیپلوی جدید از بین نره (توضیحات کامل در README.md).
"""
import sqlite3
import threading
import datetime
from config import DB_PATH

_lock = threading.Lock()
_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
_conn.row_factory = sqlite3.Row
_conn.execute("PRAGMA journal_mode=WAL;")
_conn.execute("PRAGMA foreign_keys=ON;")


def now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db():
    with _lock:
        cur = _conn.cursor()
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            join_date TEXT,
            balance INTEGER DEFAULT 0,
            referrer_id INTEGER,
            banned INTEGER DEFAULT 0,
            referral_earned INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS plans (
            plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            price INTEGER,
            duration_days INTEGER,
            volume TEXT,
            active INTEGER DEFAULT 1,
            sort_order INTEGER
        );

        CREATE TABLE IF NOT EXISTS stock (
            stock_id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER,
            config_text TEXT,
            status TEXT DEFAULT 'available',
            sold_to INTEGER,
            sold_date TEXT,
            order_id INTEGER
        );

        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            plan_id INTEGER,
            amount INTEGER,
            type TEXT,
            payment_method TEXT,
            status TEXT,
            receipt_file_id TEXT,
            discount_code TEXT,
            discount_amount INTEGER DEFAULT 0,
            created_date TEXT,
            processed_date TEXT,
            admin_note TEXT,
            delivered_stock_id INTEGER
        );

        CREATE TABLE IF NOT EXISTS transactions (
            trans_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            amount INTEGER,
            balance_after INTEGER,
            date TEXT,
            related_order_id INTEGER,
            note TEXT
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS discount_codes (
            code TEXT PRIMARY KEY,
            percent INTEGER DEFAULT 0,
            fixed_amount INTEGER DEFAULT 0,
            max_uses INTEGER DEFAULT 0,
            used_count INTEGER DEFAULT 0,
            plan_id INTEGER,
            active INTEGER DEFAULT 1,
            created_date TEXT
        );

        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            link TEXT
        );

        CREATE TABLE IF NOT EXISTS support_chats (
            user_id INTEGER PRIMARY KEY,
            active INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS admin_reply_map (
            admin_id INTEGER PRIMARY KEY,
            user_id INTEGER
        );

        CREATE TABLE IF NOT EXISTS trial_stock (
            trial_id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_text TEXT,
            status TEXT DEFAULT 'available',
            used_by INTEGER,
            used_date TEXT
        );
        """)
        _conn.commit()

        # مهاجرت ستون trial_used برای دیتابیس‌های قدیمی‌تر
        cols = [r["name"] for r in _conn.execute("PRAGMA table_info(users)").fetchall()]
        if "trial_used" not in cols:
            _conn.execute("ALTER TABLE users ADD COLUMN trial_used INTEGER DEFAULT 0")
            _conn.commit()

        defaults = {
            "CARD_NUMBER": "6037-XXXX-XXXX-XXXX",
            "CARD_HOLDER": "نام و نام‌خانوادگی",
            "JOIN_REQUIRED": "FALSE",
            "TOPUP_MIN": "10000",
            "TOPUP_MAX": "0",
            "REFERRAL_REWARD": "10000",
            "REFERRAL_MIN_PURCHASE": "0",
            "SUPPORT_USERNAME": "@YourSupportId",
            "BOT_USERNAME": "",
        }
        for k, v in defaults.items():
            cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
        _conn.commit()


# -------------------- Settings --------------------
def get_setting(key, default=""):
    row = _conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    with _lock:
        _conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) "
                      "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
        _conn.commit()


# -------------------- Users --------------------
def get_user(user_id):
    row = _conn.execute("SELECT * FROM users WHERE user_id=?", (int(user_id),)).fetchone()
    return dict(row) if row else None


def ensure_user(user_id, username, first_name, referrer_id=None):
    user = get_user(user_id)
    if user:
        with _lock:
            _conn.execute("UPDATE users SET username=?, first_name=? WHERE user_id=?",
                          (username or "", first_name or "", int(user_id)))
            _conn.commit()
        return get_user(user_id)
    with _lock:
        _conn.execute(
            "INSERT INTO users (user_id, username, first_name, join_date, balance, referrer_id, banned, referral_earned) "
            "VALUES (?, ?, ?, ?, 0, ?, 0, 0)",
            (int(user_id), username or "", first_name or "", now_str(), referrer_id)
        )
        _conn.commit()
    return get_user(user_id)


def set_referrer_if_empty(user_id, referrer_id):
    with _lock:
        row = _conn.execute("SELECT referrer_id FROM users WHERE user_id=?", (int(user_id),)).fetchone()
        if row and not row["referrer_id"]:
            _conn.execute("UPDATE users SET referrer_id=? WHERE user_id=?", (int(referrer_id), int(user_id)))
            _conn.commit()


def get_all_users():
    return [dict(r) for r in _conn.execute("SELECT * FROM users").fetchall()]


def search_user(query):
    query = str(query).replace("@", "").strip()
    if query.isdigit():
        row = _conn.execute("SELECT * FROM users WHERE user_id=?", (int(query),)).fetchone()
        if row:
            return dict(row)
    row = _conn.execute("SELECT * FROM users WHERE username=?", (query,)).fetchone()
    return dict(row) if row else None


def toggle_ban(user_id):
    user = get_user(user_id)
    if not user:
        return None
    new_val = 0 if user["banned"] else 1
    with _lock:
        _conn.execute("UPDATE users SET banned=? WHERE user_id=?", (new_val, int(user_id)))
        _conn.commit()
    return new_val


def change_balance(user_id, amount, type_, note="", related_order_id=None):
    with _lock:
        user = get_user(user_id)
        if not user:
            return None
        new_balance = int(user["balance"]) + int(amount)
        _conn.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, int(user_id)))
        _conn.execute(
            "INSERT INTO transactions (user_id, type, amount, balance_after, date, related_order_id, note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (int(user_id), type_, amount, new_balance, now_str(), related_order_id, note)
        )
        _conn.commit()
        return new_balance


def set_referral_earned(user_id):
    with _lock:
        _conn.execute("UPDATE users SET referral_earned=1 WHERE user_id=?", (int(user_id),))
        _conn.commit()


def count_referrals(user_id):
    row = _conn.execute("SELECT COUNT(*) c FROM users WHERE referrer_id=?", (int(user_id),)).fetchone()
    return row["c"] if row else 0


# -------------------- Plans --------------------
def get_active_plans():
    rows = _conn.execute("SELECT * FROM plans WHERE active=1 ORDER BY sort_order ASC, plan_id ASC").fetchall()
    return [dict(r) for r in rows]


def get_all_plans():
    rows = _conn.execute("SELECT * FROM plans ORDER BY sort_order ASC, plan_id ASC").fetchall()
    return [dict(r) for r in rows]


def get_plan(plan_id):
    row = _conn.execute("SELECT * FROM plans WHERE plan_id=?", (int(plan_id),)).fetchone()
    return dict(row) if row else None


def insert_plan(name, description, price, duration_days, volume):
    with _lock:
        cur = _conn.execute(
            "INSERT INTO plans (name, description, price, duration_days, volume, active, sort_order) "
            "VALUES (?, ?, ?, ?, ?, 1, (SELECT IFNULL(MAX(sort_order),0)+1 FROM plans))",
            (name, description, price, duration_days, volume)
        )
        _conn.commit()
        return cur.lastrowid


def update_plan(plan_id, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields.keys())
    vals = list(fields.values()) + [int(plan_id)]
    with _lock:
        _conn.execute(f"UPDATE plans SET {cols} WHERE plan_id=?", vals)
        _conn.commit()


def delete_plan(plan_id):
    with _lock:
        _conn.execute("DELETE FROM plans WHERE plan_id=?", (int(plan_id),))
        _conn.commit()


# -------------------- Stock --------------------
def get_stock_count(plan_id):
    row = _conn.execute("SELECT COUNT(*) c FROM stock WHERE plan_id=? AND status='available'",
                         (int(plan_id),)).fetchone()
    return row["c"] if row else 0


def add_stock_bulk(plan_id, lines):
    with _lock:
        _conn.executemany(
            "INSERT INTO stock (plan_id, config_text, status) VALUES (?, ?, 'available')",
            [(int(plan_id), line) for line in lines]
        )
        _conn.commit()
    return len(lines)


def allocate_and_sell_stock(plan_id, user_id, order_id):
    """یک کانفیگ موجود را به‌صورت اتمیک به کاربر اختصاص می‌ده و به‌عنوان فروخته‌شده علامت می‌زنه."""
    with _lock:
        row = _conn.execute(
            "SELECT * FROM stock WHERE plan_id=? AND status='available' ORDER BY stock_id ASC LIMIT 1",
            (int(plan_id),)
        ).fetchone()
        if not row:
            return None
        _conn.execute(
            "UPDATE stock SET status='sold', sold_to=?, sold_date=?, order_id=? WHERE stock_id=?",
            (int(user_id), now_str(), order_id, row["stock_id"])
        )
        _conn.commit()
        return dict(row)


def clear_stock(plan_id):
    with _lock:
        cur = _conn.execute("DELETE FROM stock WHERE plan_id=? AND status='available'", (int(plan_id),))
        _conn.commit()
        return cur.rowcount


def get_user_stock_items(user_id):
    rows = _conn.execute("SELECT * FROM stock WHERE sold_to=? ORDER BY stock_id DESC", (int(user_id),)).fetchall()
    return [dict(r) for r in rows]


def get_stock_item(stock_id):
    row = _conn.execute("SELECT * FROM stock WHERE stock_id=?", (int(stock_id),)).fetchone()
    return dict(row) if row else None


# -------------------- اکانت تست رایگان --------------------
def get_trial_stock_count():
    row = _conn.execute("SELECT COUNT(*) c FROM trial_stock WHERE status='available'").fetchone()
    return row["c"] if row else 0


def add_trial_stock_bulk(lines):
    with _lock:
        _conn.executemany(
            "INSERT INTO trial_stock (config_text, status) VALUES (?, 'available')",
            [(line,) for line in lines]
        )
        _conn.commit()
    return len(lines)


def clear_trial_stock():
    with _lock:
        cur = _conn.execute("DELETE FROM trial_stock WHERE status='available'")
        _conn.commit()
        return cur.rowcount


def claim_trial(user_id):
    """
    یک اکانت تست به کاربر اختصاص می‌ده (فقط یک‌بار برای هر کاربر).
    خروجی: ('ok', config_text) | ('already_used', None) | ('empty', None)
    """
    with _lock:
        user = _conn.execute("SELECT trial_used FROM users WHERE user_id=?", (int(user_id),)).fetchone()
        if user and user["trial_used"]:
            return "already_used", None
        row = _conn.execute(
            "SELECT * FROM trial_stock WHERE status='available' ORDER BY trial_id ASC LIMIT 1"
        ).fetchone()
        if not row:
            return "empty", None
        _conn.execute(
            "UPDATE trial_stock SET status='used', used_by=?, used_date=? WHERE trial_id=?",
            (int(user_id), now_str(), row["trial_id"])
        )
        _conn.execute("UPDATE users SET trial_used=1 WHERE user_id=?", (int(user_id),))
        _conn.commit()
        return "ok", row["config_text"]


# -------------------- Orders --------------------
def create_order(user_id, plan_id, amount, type_, payment_method, status,
                  receipt_file_id="", discount_code="", discount_amount=0):
    with _lock:
        cur = _conn.execute(
            "INSERT INTO orders (user_id, plan_id, amount, type, payment_method, status, receipt_file_id, "
            "discount_code, discount_amount, created_date, processed_date, admin_note, delivered_stock_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', '', NULL)",
            (int(user_id), plan_id, amount, type_, payment_method, status, receipt_file_id,
             discount_code, discount_amount, now_str())
        )
        _conn.commit()
        return cur.lastrowid


def get_order(order_id):
    row = _conn.execute("SELECT * FROM orders WHERE order_id=?", (int(order_id),)).fetchone()
    return dict(row) if row else None


def update_order(order_id, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields.keys())
    vals = list(fields.values()) + [int(order_id)]
    with _lock:
        _conn.execute(f"UPDATE orders SET {cols} WHERE order_id=?", vals)
        _conn.commit()


def get_pending_orders():
    rows = _conn.execute("SELECT * FROM orders WHERE status='pending' ORDER BY order_id ASC").fetchall()
    return [dict(r) for r in rows]


def get_user_delivered_orders(user_id):
    rows = _conn.execute(
        "SELECT * FROM orders WHERE user_id=? AND type='purchase' AND status='delivered'", (int(user_id),)
    ).fetchall()
    return [dict(r) for r in rows]


# -------------------- Discount Codes --------------------
def create_discount(code, percent=0, fixed_amount=0, max_uses=0, plan_id=None):
    with _lock:
        _conn.execute(
            "INSERT OR REPLACE INTO discount_codes (code, percent, fixed_amount, max_uses, used_count, plan_id, active, created_date) "
            "VALUES (?, ?, ?, ?, 0, ?, 1, ?)",
            (code.upper(), percent, fixed_amount, max_uses, plan_id, now_str())
        )
        _conn.commit()


def get_discount(code):
    row = _conn.execute("SELECT * FROM discount_codes WHERE code=?", (code.upper(),)).fetchone()
    return dict(row) if row else None


def get_all_discounts():
    rows = _conn.execute("SELECT * FROM discount_codes ORDER BY created_date DESC").fetchall()
    return [dict(r) for r in rows]


def delete_discount(code):
    with _lock:
        _conn.execute("DELETE FROM discount_codes WHERE code=?", (code.upper(),))
        _conn.commit()


def increment_discount_usage(code):
    with _lock:
        _conn.execute("UPDATE discount_codes SET used_count = used_count + 1 WHERE code=?", (code.upper(),))
        _conn.commit()


# -------------------- Channels (عضویت اجباری) --------------------
def get_channels():
    rows = _conn.execute("SELECT * FROM channels ORDER BY id ASC").fetchall()
    return [dict(r) for r in rows]


def add_channel(chat_id, link):
    with _lock:
        cur = _conn.execute("INSERT INTO channels (chat_id, link) VALUES (?, ?)", (chat_id, link))
        _conn.commit()
        return cur.lastrowid


def remove_channel(channel_id):
    with _lock:
        _conn.execute("DELETE FROM channels WHERE id=?", (int(channel_id),))
        _conn.commit()


# -------------------- Support (پشتیبانی آنلاین) --------------------
def set_support_active(user_id, active: bool):
    with _lock:
        _conn.execute(
            "INSERT INTO support_chats (user_id, active) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET active=excluded.active",
            (int(user_id), 1 if active else 0)
        )
        _conn.commit()


def is_support_active(user_id):
    row = _conn.execute("SELECT active FROM support_chats WHERE user_id=?", (int(user_id),)).fetchone()
    return bool(row and row["active"])


def set_admin_reply_target(admin_id, user_id):
    with _lock:
        _conn.execute(
            "INSERT INTO admin_reply_map (admin_id, user_id) VALUES (?, ?) "
            "ON CONFLICT(admin_id) DO UPDATE SET user_id=excluded.user_id",
            (int(admin_id), int(user_id))
        )
        _conn.commit()


def get_admin_reply_target(admin_id):
    row = _conn.execute("SELECT user_id FROM admin_reply_map WHERE admin_id=?", (int(admin_id),)).fetchone()
    return row["user_id"] if row else None


def clear_admin_reply_target(admin_id):
    with _lock:
        _conn.execute("DELETE FROM admin_reply_map WHERE admin_id=?", (int(admin_id),))
        _conn.commit()


# -------------------- آمار --------------------
def get_stats():
    users_count = _conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    orders_count = _conn.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"]
    pending_count = _conn.execute("SELECT COUNT(*) c FROM orders WHERE status='pending'").fetchone()["c"]
    delivered = _conn.execute(
        "SELECT COUNT(*) c, IFNULL(SUM(amount),0) s FROM orders WHERE status='delivered' AND type='purchase'"
    ).fetchone()
    stock_count = _conn.execute("SELECT COUNT(*) c FROM stock WHERE status='available'").fetchone()["c"]
    trial_count = _conn.execute("SELECT COUNT(*) c FROM trial_stock WHERE status='available'").fetchone()["c"]
    plans_count = _conn.execute("SELECT COUNT(*) c FROM plans").fetchone()["c"]
    best = _conn.execute(
        "SELECT plan_id, COUNT(*) c FROM orders WHERE status='delivered' AND type='purchase' "
        "GROUP BY plan_id ORDER BY c DESC LIMIT 1"
    ).fetchone()
    best_plan_name, best_plan_count = "-", 0
    if best:
        p = get_plan(best["plan_id"])
        best_plan_name = p["name"] if p else "-"
        best_plan_count = best["c"]
    return {
        "users": users_count,
        "orders": orders_count,
        "pending": pending_count,
        "delivered": delivered["c"],
        "total_sales": delivered["s"],
        "stock": stock_count,
        "trial_stock": trial_count,
        "plans": plans_count,
        "best_plan_name": best_plan_name,
        "best_plan_count": best_plan_count,
    }
