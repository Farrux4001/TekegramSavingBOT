import os
import sqlite3
import logging
from datetime import date, datetime, timedelta
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# Configuration
DB_PATH = 'data.db'
DEFAULT_TARGET = 12500000  # so'm (≈ $1000 at 12,500 UZS)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Database helpers ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, target INTEGER, start_date TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS entries (id INTEGER PRIMARY KEY AUTOINCREMENT, day TEXT UNIQUE, amount INTEGER)''')
    cur.execute('SELECT COUNT(*) FROM settings')
    if cur.fetchone()[0] == 0:
        cur.execute('INSERT INTO settings (target, start_date) VALUES (?, ?)', (DEFAULT_TARGET, date.today().isoformat()))
    conn.commit()
    conn.close()

def get_settings():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT target, start_date FROM settings WHERE id = 1')
    row = cur.fetchone()
    conn.close()
    return (row[0], row[1])

def set_target(amount):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('UPDATE settings SET target = ? WHERE id = 1', (amount,))
    conn.commit(); conn.close()

def set_start(start_iso):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('UPDATE settings SET start_date = ? WHERE id = 1', (start_iso,))
    conn.commit(); conn.close()

def add_entry_for(day_iso, amount):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('INSERT OR REPLACE INTO entries (day, amount) VALUES (?, ?)', (day_iso, amount))
    conn.commit(); conn.close()

def inc_entry_for(day_iso, inc_amount):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT amount FROM entries WHERE day = ?', (day_iso,))
    r = cur.fetchone()
    current = int(r[0]) if r else 0
    new = current + inc_amount
    cur.execute('INSERT OR REPLACE INTO entries (day, amount) VALUES (?, ?)', (day_iso, new))
    conn.commit(); conn.close()
    return new

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
    rows = cur.fetchall(); conn.close()
    return rows

# --- Utility ---
def is_sunday(d: date):
    return d.weekday() == 6

def working_days_between(start_iso, end_iso):
    s = date.fromisoformat(start_iso)
    e = date.fromisoformat(end_iso)
    cnt = 0
    while s <= e:
        if not is_sunday(s):
            cnt += 1
        s += timedelta(days=1)
    return cnt

def fetch_usd_rate():
    """Return USD per 1 UZS (i.e. USD = UZS * rate)."""
    try:
        resp = requests.get('https://api.exchangerate.host/latest', params={'base': 'UZS', 'symbols': 'USD'}, timeout=10)
        data = resp.json()
        rate = data.get('rates', {}).get('USD')
        if rate:
            return float(rate)  # USD per UZS (small number)
    except Exception as e:
        logger.warning('fetch_usd_rate failed: %s', e)
    return None

def fmt(n):
    return '{:,}'.format(int(n))

# --- Keyboards ---
def main_keyboard():
    kb = [
        [InlineKeyboardButton("➕ Kunlik summa qo'shish", callback_data='add_daily')],
        [InlineKeyboardButton("💰 Umumiy balans", callback_data='balance'), InlineKeyboardButton("💱 Valyuta kursi", callback_data='rate')],
        [InlineKeyboardButton("📄 Reja (PDF, 1 yil)", callback_data='plan_pdf')]
    ]
    return InlineKeyboardMarkup(kb)

def back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Bosh menyuga qaytish", callback_data='back_main')]])

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    target, start_iso = get_settings()
    total = get_total()
    rem = max(0, target - total)
    rate = fetch_usd_rate()
    usd_rem = rem * rate if rate else None
    usd_per_usd = (1 / rate) if rate else None
    today = date.today().isoformat()
    # today's saved
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute('SELECT amount FROM entries WHERE day = ?', (today,))
    r = cur.fetchone(); conn.close()
    today_saved = int(r[0]) if r else 0

    msg = f"🎯 Maqsad (so'm): {fmt(target)}\n💵 Jami yig'ilgan: {fmt(total)} so'm\n📉 Qolgan: {fmt(rem)} so'm"
    if usd_rem is not None:
        msg += f" (~{usd_rem:,.2f} USD; 1 USD ≈ {fmt(usd_per_usd)} UZS)"
    msg += f"\n\nBugungi yig'im: {fmt(today_saved)} so'm\n\nQuyidagi bo'limlardan birini tanlang:"
    await update.message.reply_text(msg, reply_markup=main_keyboard())

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'add_daily':
        context.user_data['awaiting_amount'] = True
        await query.message.reply_text("Iltimos bugungi yig'ilgan summani so'mda raqam sifatida yuboring (masalan: 40000). /cancel bilan bekor qilish mumkin.", reply_markup=back_keyboard())
        return
    if data == 'balance':
        total = get_total()
        target, _ = get_settings()
        rem = max(0, target - total)
        rate = fetch_usd_rate()
        usd_rem = rem * rate if rate else None
        msg = f"💰 Umumiy balans:\nJami yig'ilgan: {fmt(total)} so'm\nQolgan: {fmt(rem)} so'm"
        if usd_rem is not None:
            msg += f"\n(~{usd_rem:,.2f} USD)"
        await query.message.reply_text(msg, reply_markup=back_keyboard())
        return
    if data == 'rate':
        r = fetch_usd_rate()
        if r is not None:
            await query.message.reply_text(f"💱 Valyuta kursi:\n1 UZS = {r:.8f} USD\n1 USD ≈ {fmt(1/r)} UZS", reply_markup=back_keyboard())
        else:
            await query.message.reply_text("Kursni olishda xatolik yuz berdi.", reply_markup=back_keyboard())
        return
    if data == 'back_main':
        await query.message.reply_text("Bosh menyu:", reply_markup=main_keyboard())
        return
    if data == 'plan_pdf':
        # generate 1-year plan PDF and send
        await query.message.reply_text("PDF reja yaratilmoqda, biroz kuting...")
        pdf_path = generate_plan_pdf()
        if pdf_path:
            await query.message.reply_document(document=InputFile(pdf_path), filename=os.path.basename(pdf_path))
        else:
            await query.message.reply_text("PDF yaratishda xatolik yuz berdi.")
        await query.message.reply_text("Bosh menyu:", reply_markup=main_keyboard())
        return

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # cancel handling
    txt = update.message.text.strip()
    if txt.lower() == '/cancel':
        context.user_data['awaiting_amount'] = False
        await update.message.reply_text("Amal bekor qilindi.", reply_markup=main_keyboard())
        return

    if context.user_data.get('awaiting_amount'):
        cleaned = txt.replace(',', '').strip()
        if not cleaned.isdigit():
            await update.message.reply_text("Iltimos faqat raqam yozing (masalan: 40000).", reply_markup=back_keyboard())
            return
        amt = int(cleaned)
        today = date.today().isoformat()
        new_total_today = inc_entry_for(today, amt)
        total = get_total()
        target, _ = get_settings()
        rem = max(0, target - total)
        rate = fetch_usd_rate()
        usd_rem = rem * rate if rate else None
        msg = f"✅ +{fmt(amt)} so'm qo'shildi.\nBugungi jami: {fmt(new_total_today)} so'm\nJami yig'ilgan: {fmt(total)} so'm\nMaqsaddan qolgan: {fmt(rem)} so'm"
        if usd_rem is not None:
            msg += f"\n(~{usd_rem:,.2f} USD)"
        context.user_data['awaiting_amount'] = False
        # after adding, automatically return to main menu
        await update.message.reply_text(msg, reply_markup=main_keyboard())
        return

    # if not awaiting, show help
    await update.message.reply_text("Bosh menyu:", reply_markup=main_keyboard())

async def settarget_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Iltimos: /settarget <so'm> ko'rinishida yozing.")
        return
    try:
        v = int(context.args[0])
        set_target(v)
        await update.message.reply_text(f"Maqsad o'zgartirildi: {fmt(v)} so'm", reply_markup=main_keyboard())
    except:
        await update.message.reply_text("Xato format. Raqam kiriting.")

async def setstart_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Iltimos: /setstart YYYY-MM-DD formatda yozing.")
        return
    try:
        d = date.fromisoformat(context.args[0])
        set_start(d.isoformat())
        await update.message.reply_text(f"Boshlanish sanasi o'rnatildi: {d.isoformat()}", reply_markup=main_keyboard())
    except:
        await update.message.reply_text("Noto'g'ri sana format. YYYY-MM-DD.")

def generate_plan_pdf():
    try:
        # create a simple PDF plan using reportlab
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet

        pdf_path = 'saving_plan_1year.pdf'
        init_db()
        target, start_iso = get_settings()
        total = get_total()
        rem = max(0, target - total)
        start = date.fromisoformat(start_iso)
        end = start + timedelta(days=365)
        # collect working days (exclude Sundays)
        days = []
        d = start
        while d <= end:
            if not is_sunday(d):
                days.append(d)
            d += timedelta(days=1)
        per_day = rem // len(days) if len(days)>0 else rem
        # build PDF
        doc = SimpleDocTemplate(pdf_path, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        story.append(Paragraph("1 Yillik Yig'im Rejasi", styles['Title']))
        story.append(Spacer(1,12))
        story.append(Paragraph(f"Maqsad: {fmt(target)} so'm", styles['Normal']))
        story.append(Paragraph(f"Jami yig'ilgan hozir: {fmt(total)} so'm", styles['Normal']))
        story.append(Paragraph(f"Qolgan: {fmt(rem)} so'm", styles['Normal']))
        story.append(Paragraph(f"Har ishchi kunga tavsiya: {fmt(per_day)} so'm", styles['Normal']))
        story.append(Spacer(1,12))
        # table header
        rows = [['Sana','Hafta kuni','Tavsiya (so\'m)']]
        for d in days:
            rows.append([d.isoformat(), d.strftime('%A'), fmt(per_day)])
        table = Table(rows, colWidths=[120,120,120])
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.lightgrey),('GRID',(0,0),(-1,-1),0.5,colors.black)]))
        story.append(table)
        doc.build(story)
        return pdf_path
    except Exception as e:
        logger.exception("PDF yaratishda xato: %s", e)
        return None

def main():
    init_db()
    token = os.environ.get('BOT_TOKEN')
    if not token:
        print("ERROR: Please set BOT_TOKEN environment variable")
        return
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_handler))
    app.add_handler(CommandHandler('settarget', settarget_cmd))
    app.add_handler(CommandHandler('setstart', setstart_cmd))
    print("Bot ishga tushdi...")
    app.run_polling()

if __name__ == '__main__':
    main()
