# -*- coding: utf-8 -*-
import html


def fmt_money(n) -> str:
    try:
        n = int(round(float(n)))
    except (ValueError, TypeError):
        n = 0
    return f"{n:,}".replace(",", ",") + " تومان"


def esc(s) -> str:
    if s is None:
        return ""
    return html.escape(str(s))


def to_jalali(g_y, g_m, g_d):
    """تبدیل ساده تاریخ میلادی به شمسی، فقط برای نمایش."""
    g_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    j_days_in_month = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]
    gy = g_y - 1600
    gm = g_m - 1
    gd = g_d - 1
    g_day_no = 365 * gy + (gy + 3) // 4 - (gy + 99) // 100 + (gy + 399) // 400
    for i in range(gm):
        g_day_no += g_days_in_month[i]
    if gm > 1 and ((g_y % 4 == 0 and g_y % 100 != 0) or (g_y % 400 == 0)):
        g_day_no += 1
    g_day_no += gd
    j_day_no = g_day_no - 79
    j_np = j_day_no // 12053
    j_day_no %= 12053
    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461
    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365
    for i in range(11):
        if j_day_no < j_days_in_month[i]:
            jm = i + 1
            jd = j_day_no + 1
            break
        j_day_no -= j_days_in_month[i]
    else:
        jm = 12
        jd = j_day_no + 1
    return f"{jy}/{jm:02d}/{jd:02d}"
