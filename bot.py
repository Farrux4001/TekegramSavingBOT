import os
import sqlite3
import logging
from datetime import datetime, date, timedelta
import requests
from telegram import Update, ForceReply
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# --- Configuration ---
DB_PATH = 'data.db'
DEFAULT_TARGET = 12500000  # so'm (approx $1000 at 12,500 UZS)
# ----------------------

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY,
                    target INTEGER,
                    start_date TEXT
                )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    day TEXT UNIQUE,
                    amount INTEGER
                )''')
    # ensure one settings row exists
    cur.execute('SELECT COUNT(*) FROM settings')
    if cur.fetchone()[0] == 0:
        cur.execute('INSERT INTO settings (target, start_date) VALUES (?, ?)', (DEFAULT_TARGET, date.today().isoformat()))
    conn.commit()
    conn.close()

def set_target_in_db(amount: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('UPDATE settings SET target = ? WHERE id = 1', (amount,))
    conn.commit()
    conn.close()

def set_start_in_db(start_iso: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('UPDATE settings SET start_date = ? WHERE id = 1', (start_iso,))
    conn.commit()
    conn.close()

def get_settings():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT target, start_date FROM settings WHERE id = 1')
    row = cur.fetchone()
    conn.close()
    return row[0], row[1]

def add_entry(day_iso: str, amount: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('INSERT OR REPLACE INTO entries (day, amount) VALUES (?, ?)', (day_iso, amount))
    conn.commit()
    conn.close()

def get_total():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT SUM(amount) FROM entries')
    s = cur.fetchone()[0] or 0
    conn.close()
    return int(s)

def get_entries_between(start_iso, end_iso):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT day, amount FROM entries WHERE day BETWEEN ? AND ? ORDER BY day', (start_iso, end_iso))
    rows = cur.fetchall()
    conn.close()
    return rows

def is_sunday(d: date):
    return d.weekday() == 6

def working_days_count(start_iso, end_iso):
    s = date.fromisoformat(start_iso)
    e = date.fromisoformat(end_iso)
    cnt = 0
    while s <= e:
        if not is_sunday(s):
            cnt += 1
        s += timedelta(days=1)
    return cnt

def fetch_usd_rate():
    try:
        # Use exchangerate.host as free API
        res = requests.get('https://api.exchangerate.host/latest', params={'base': 'UZS', 'symbols': 'USD'}, timeout=10)
        data = res.json()
        rate = data.get('rates', {}).get('USD')
        return float(rate) if rate else None
    except Exception as e:
        logger.error('Rate fetch failed: %s', e)
        return None

# --- Helpers ---
def format_num(n):
    return '{:,}'.format(n)

# --- Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    target, start_iso = get_settings()
    total = get_total()
    rem = max(0, target - total)
    rate = fetch_usd_rate()
    usd_rem = (rem * (1.0 / rate)) if rate else None
    today_iso = date.today().isoformat()
    today_saved = 0
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT amount FROM entries WHERE day = ?', (today_iso,))
    r = cur.fetchone()
    if r:
        today_saved = int(r[0])
    conn.close()

    msg = f'Assalomu alaykum!\nMaqsad: {format_num(target)} so\'m\nJami yig\'ilgan: {format_num(total)} so\'m\nQolgan: {format_num(rem)} so\'m'
    if usd_rem:
        msg += f' (~{usd_rem:,.2f} USD)'
    msg += f'\nBugungi yig\'im: {format_num(today_saved)} so\'m\n\nBuyruqlar:\n/settarget <so\'m>\n/setstart YYYY-MM-DD\n/add <summa> - bugungi yig\'ilgan summani kiriting\n/adddate YYYY-MM-DD <summa> - belgilangan kunga summani kiriting\n/total\n/remaining\n/rate\n/report YYYY-MM'
    await update.message.reply_text(msg)

async def settarget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    if not context.args:
        await update.message.reply_text('Iltimos: /settarget 12500000 tarzida maqsadni kiriting (so\'m).')
        return
    try:
        v = int(context.args[0])
        set_target_in_db(v)
        await update.message.reply_text(f'Maqsad yangilandi: {format_num(v)} so\'m')
    except Exception as e:
        await update.message.reply_text('Noto\'g\'ri format. Faqat raqam kiriting.')

async def setstart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    if not context.args:
        await update.message.reply_text('Iltimos: /setstart YYYY-MM-DD tarzida sanani kiriting.')
        return
    try:
        d = date.fromisoformat(context.args[0])
        set_start_in_db(d.isoformat())
        await update.message.reply_text(f'Boshlanish sanasi o\'rnatildi: {d.isoformat()}')
    except Exception as e:
        await update.message.reply_text('Noto\'g\'ri sana format. YYYY-MM-DD ko\'rinishda kiriting.')

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    if not context.args:
        await update.message.reply_text('Iltimos: /add 40000 tarzida bugungi summa kiriting.')
        return
    try:
        amt = int(context.args[0])
        today = date.today().isoformat()
        # get current value for today (if exists) and add to it
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('SELECT amount FROM entries WHERE day = ?', (today,))
        r = cur.fetchone()
        current = int(r[0]) if r else 0
        new_amount = current + amt
        cur.execute('INSERT OR REPLACE INTO entries (day, amount) VALUES (?, ?)', (today, new_amount))
        conn.commit()
        conn.close()

        # compute totals and remaining after this addition
        target, start_iso = get_settings()
        total = get_total()
        rem = max(0, target - total)
        rate = fetch_usd_rate()
        usd_rem = (rem * (1.0 / rate)) if rate else None

        msg = f'Bugungi ({today}) uchun +{format_num(amt)} so\'m qo\'shildi.\nBugungi jami: {format_num(new_amount)} so\'m\nJami yig\'ilgan: {format_num(total)} so\'m\nMaqsaddan qolgan: {format_num(rem)} so\'m'
        if usd_rem:
            msg += f' (~{usd_rem:,.2f} USD)'
        await update.message.reply_text(msg)
    except Exception as e:
        logger.exception('Add failed: %s', e)
        await update.message.reply_text('Noto\'g\'ri format. Faqat raqam kiriting.')

async def adddate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    if len(context.args) < 2:
        await update.message.reply_text('Iltimos: /adddate YYYY-MM-DD 40000 tarzida kiriting.')
        return
    try:
        d = date.fromisoformat(context.args[0])
        amt = int(context.args[1])
        add_entry(d.isoformat(), amt)

        # compute totals and remaining after this addition
        target, start_iso = get_settings()
        total = get_total()
        rem = max(0, target - total)
        rate = fetch_usd_rate()
        usd_rem = (rem * (1.0 / rate)) if rate else None

        msg = f'{d.isoformat()} uchun {format_num(amt)} so\'m saqlandi.\nJami yig\'ilgan: {format_num(total)} so\'m\nMaqsaddan qolgan: {format_num(rem)} so\'m'
        if usd_rem:
            msg += f' (~{usd_rem:,.2f} USD)'
        await update.message.reply_text(msg)
    except Exception as e:
        logger.exception('AddDate failed: %s', e)
        await update.message.reply_text('Noto\'g\'ri format. /adddate YYYY-MM-DD summa')

async def total(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    s = get_total()
    rate = fetch_usd_rate()
    usd = (s * (1.0 / rate)) if rate else None
    msg = f'Jami yig\'ilgan: {format_num(s)} so\'m'
    if usd:
        msg += f' (~{usd:,.2f} USD)'
    await update.message.reply_text(msg)

async def remaining(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    target, start_iso = get_settings()
    tot = get_total()
    rem = max(0, target - tot)
    today = date.today()
    end_date = date.fromisoformat(start_iso) + timedelta(days=365)
    days = 0
    d = today
    while d <= end_date:
        if not is_sunday(d):
            days += 1
        d += timedelta(days=1)
    per_day = (rem // days) if days>0 else rem
    rate = fetch_usd_rate()
    usd_equiv = (rem * (1.0 / rate)) if rate else None
    msg = f'Maqsaddan qolgan: {format_num(rem)} so\'m\nQolgan ishchi kunlar (yakshanba chiqarilgan): {days}\nTavsiya: kuniga {format_num(per_day)} so\'m'
    if rate:
        msg += f'\nValyuta kursi (UZS->USD): 1 UZS = {rate:.8f} USD\nQolgan (USD): {usd_equiv:,.2f} USD'
    await update.message.reply_text(msg)

async def rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    r = fetch_usd_rate()
    if r:
        await update.message.reply_text(f'Valyuta kursi (UZS->USD): 1 UZS = {r:.8f} USD\n1 USD ≈ { (1/r):.2f } UZS')
    else:
        await update.message.reply_text('Kursni olishda xatolik yuz berdi.')

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    if not context.args:
        await update.message.reply_text('Iltimos: /report YYYY-MM ko\'rinishda oyni kiriting (masalan: /report 2025-10)')
        return
    try:
        ym = context.args[0]
        y,m = ym.split('-')
        start_iso = f'{int(y):04d}-{int(m):02d}-01'
        # last day of month
        if int(m)==12:
            end_iso = f'{int(y)+1:04d}-01-01'
        else:
            end_iso = f'{int(y):04d}-{int(m)+1:02d}-01'
        # subtract one day
        e = datetime.fromisoformat(end_iso).date() - timedelta(days=1)
        rows = get_entries_between(start_iso, e.isoformat())
        if not rows:
            await update.message.reply_text('Ushbu oy uchun yozuv topilmadi.')
            return
        text = f'Hisobot — {ym}\n'
        total = 0
        for day, amt in rows:
            text += f'{day}: {format_num(int(amt))} so\'m\n'
            total += int(amt)
        text += f'Jami: {format_num(total)} so\'m'
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text('Noto\'g\'ri format. /report YYYY-MM')

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Buyruqlar: /settarget /setstart /add /adddate /total /remaining /rate /report')

def main():
    init_db()
    token = os.environ.get('BOT_TOKEN')
    if not token:
        print('ERROR: Please set BOT_TOKEN environment variable.')
        return
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('settarget', settarget))
    app.add_handler(CommandHandler('setstart', setstart))
    app.add_handler(CommandHandler('add', add))
    app.add_handler(CommandHandler('adddate', adddate))
    app.add_handler(CommandHandler('total', total))
    app.add_handler(CommandHandler('remaining', remaining))
    app.add_handler(CommandHandler('rate', rate))
    app.add_handler(CommandHandler('report', report))
    app.add_handler(CommandHandler('help', help_cmd))

    print('Bot ishga tushmoqda...')
    app.run_polling()

if __name__ == '__main__':
    main()
