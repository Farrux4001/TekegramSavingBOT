import os
import json
import logging
from datetime import date, datetime, timedelta
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

DATA_FILE = 'data.json'
BACKUP_DIR = 'backups'
DEFAULT_TARGET = 12500000  # so'm approx $1000 (you can change with /settarget)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --------- Data helpers (JSON persistence) ----------
def ensure_data():
    if not os.path.exists(DATA_FILE):
        data = {
            "settings": {
                "target": DEFAULT_TARGET,
                "start": None,
                "local_rate": None
            },
            "entries": {}  # "YYYY-MM-DD": amount (int)
        }
        save_data(data)
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR, exist_ok=True)

def load_data():
    ensure_data()
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    # archive current before overwrite
    if os.path.exists(DATA_FILE):
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        shutil.copy2(DATA_FILE, os.path.join(BACKUP_DIR, f'data_{ts}.json'))
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------- Currency helpers (try APIs, fallback to local) ----------
def fetch_rate_uzs_per_usd():
    # returns UZS per 1 USD (float) or None
    # try several endpoints
    try:
        r = requests.get('https://api.exchangerate.host/latest', params={'base':'USD','symbols':'UZS'}, timeout=8)
        j = r.json()
        v = j.get('rates', {}).get('UZS')
        if v: return float(v)
    except Exception as e:
        logger.debug('exchangerate.host failed: %s', e)
    try:
        r = requests.get('https://open.er-api.com/v6/latest/USD', timeout=8)
        j = r.json()
        v = j.get('rates', {}).get('UZS')
        if v: return float(v)
    except Exception as e:
        logger.debug('er-api failed: %s', e)
    # fallback to local_rate if set
    data = load_data()
    local = data.get('settings', {}).get('local_rate')
    if local:
        try:
            return float(local)
        except:
            return None
    return None

# ---------- Utility ----------
def fmt(n):
    try:
        return '{:,}'.format(int(n))
    except:
        return str(n)

def is_sunday(d: date):
    return d.weekday() == 6

# ---------- Keyboards ----------
def main_keyboard():
    kb = [
        [InlineKeyboardButton("➕ Kunlik summa qo'shish", callback_data='add_daily')],
        [InlineKeyboardButton("💰 Umumiy balans", callback_data='balance'),
         InlineKeyboardButton("💱 Valyuta kursi", callback_data='rate')],
        [InlineKeyboardButton("📄 Reja (PDF, 1 yil)", callback_data='plan_pdf')],
    ]
    return InlineKeyboardMarkup(kb)

def back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Bosh menyuga qaytish", callback_data='back_main')]])

# ---------- Handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_data()
    data = load_data()
    target = data['settings'].get('target', DEFAULT_TARGET)
    start_iso = data['settings'].get('start')
    entries = data.get('entries', {})
    total = sum(int(v) for v in entries.values()) if entries else 0
    rem = max(0, target - total)
    rate = fetch_rate_uzs_per_usd()
    usd_rem = (rem / rate) if rate else None
    today = date.today().isoformat()
    today_saved = int(entries.get(today, 0))
    msg = f"🎯 Maqsad (so'm): {fmt(target)}\n💵 Jami yig'ilgan: {fmt(total)} so'm\n📉 Qolgan: {fmt(rem)} so'm"
    if usd_rem is not None:
        msg += f" (~{usd_rem:,.2f} USD; 1 USD ≈ {fmt(rate)} UZS)"
    if start_iso:
        msg += f"\nBoshlanish sanasi: {start_iso}"
    msg += f"\n\nBugungi yig'im: {fmt(today_saved)} so'm\n\nQuyidagi bo'limlardan birini tanlang:"
    await update.message.reply_text(msg, reply_markup=main_keyboard())

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == 'add_daily':
        context.user_data['awaiting_amount'] = True
        await query.message.reply_text("Iltimos bugungi yig'ilgan summani so'mda raqam sifatida yuboring (masalan: 40000). /cancel bilan bekor qilishingiz mumkin.", reply_markup=back_keyboard())
        return
    if data == 'balance':
        d = load_data()
        target = d['settings'].get('target', DEFAULT_TARGET)
        entries = d.get('entries', {})
        total = sum(int(v) for v in entries.values()) if entries else 0
        rem = max(0, target - total)
        rate = fetch_rate_uzs_per_usd()
        usd_rem = (rem / rate) if rate else None
        msg = f"💰 Umumiy balans:\nJami yig'ilgan: {fmt(total)} so'm\nQolgan: {fmt(rem)} so'm"
        if usd_rem is not None:
            msg += f"\n(~{usd_rem:,.2f} USD)"
        await query.message.reply_text(msg, reply_markup=back_keyboard())
        return
    if data == 'rate':
        r = fetch_rate_uzs_per_usd()
        if r is not None:
            await query.message.reply_text(f"💱 Valyuta kursi:\n1 USD ≈ {fmt(r)} UZS", reply_markup=back_keyboard())
        else:
            await query.message.reply_text("Kursni olishda xatolik yuz berdi. /setrate orqali mahalliy kurs qo'ying.", reply_markup=back_keyboard())
        return
    if data == 'back_main':
        await query.message.reply_text("Bosh menyu:", reply_markup=main_keyboard())
        return
    if data == 'plan_pdf':
        await query.message.reply_text("PDF reja yaratilmoqda, biroz kuting...")
        pdf_path = generate_plan_pdf()
        if pdf_path:
            await query.message.reply_document(document=InputFile(pdf_path), filename=os.path.basename(pdf_path))
        else:
            await query.message.reply_text("PDF yaratishda xatolik yuz berdi.")
        await query.message.reply_text("Bosh menyu:", reply_markup=main_keyboard())
        return

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt.lower() == '/cancel':
        context.user_data['awaiting_amount'] = False
        await update.message.reply_text("Amal bekor qilindi.", reply_markup=main_keyboard())
        return
    # setrate manual override
    if txt.startswith('/setrate'):
        parts = txt.split()
        if len(parts) == 2:
            try:
                val = float(parts[1])
                d = load_data()
                d['settings']['local_rate'] = val
                save_data(d)
                await update.message.reply_text(f"Mahalliy kurs o'rnatildi: 1 USD ≈ {fmt(val)} UZS", reply_markup=main_keyboard())
            except:
                await update.message.reply_text("Xato format. Masalan: /setrate 12500", reply_markup=main_keyboard())
        else:
            await update.message.reply_text("Iltimos: /setrate 12500 ko'rinishida bering", reply_markup=main_keyboard())
        return

    if context.user_data.get('awaiting_amount'):
        cleaned = txt.replace(',', '').strip()
        if not cleaned.isdigit():
            await update.message.reply_text("Iltimos faqat raqam yozing (masalan: 40000).", reply_markup=back_keyboard())
            return
        amt = int(cleaned)
        today = date.today().isoformat()
        d = load_data()
        # if first ever deposit and start not set, set start to today
        if d['settings'].get('start') is None:
            d['settings']['start'] = today
        # increment today's entry
        prev = int(d['entries'].get(today, 0))
        d['entries'][today] = prev + amt
        save_data(d)  # this will archive previous copy automatically
        total = sum(int(v) for v in d['entries'].values())
        rem = max(0, d['settings'].get('target', DEFAULT_TARGET) - total)
        rate = fetch_rate_uzs_per_usd()
        usd_rem = (rem / rate) if rate else None
        msg = f"✅ +{fmt(amt)} so'm qo'shildi.\nBugungi jami: {fmt(d['entries'][today])} so'm\nJami yig'ilgan: {fmt(total)} so'm\nMaqsaddan qolgan: {fmt(rem)} so'm"
        if usd_rem is not None:
            msg += f"\n(~{usd_rem:,.2f} USD)"
        context.user_data['awaiting_amount'] = False
        # return to main menu automatically
        await update.message.reply_text(msg, reply_markup=main_keyboard())
        return

    await update.message.reply_text("Bosh menyu:", reply_markup=main_keyboard())

async def settarget_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Iltimos: /settarget <so'm> ko'rinishida yozing.")
        return
    try:
        v = int(context.args[0])
        d = load_data()
        d['settings']['target'] = v
        save_data(d)
        await update.message.reply_text(f"Maqsad o'zgartirildi: {fmt(v)} so'm", reply_markup=main_keyboard())
    except:
        await update.message.reply_text("Xato format. Raqam kiriting.")

async def setstart_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Iltimos: /setstart YYYY-MM-DD formatda yozing.")
        return
    try:
        dval = date.fromisoformat(context.args[0]).isoformat()
        d = load_data()
        d['settings']['start'] = dval
        save_data(d)
        await update.message.reply_text(f"Boshlanish sanasi o'rnatildi: {dval}", reply_markup=main_keyboard())
    except:
        await update.message.reply_text("Noto'g'ri sana format. YYYY-MM-DD.")

def generate_plan_pdf():
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet

        ensure_data()
        data = load_data()
        target = data['settings'].get('target', DEFAULT_TARGET)
        start_iso = data['settings'].get('start')
        entries = data.get('entries', {})

        if not start_iso:
            # nothing deposited yet; cannot build plan
            return None

        start = date.fromisoformat(start_iso)
        end = start + timedelta(days=365)
        days = []
        d = start
        while d <= end:
            if not is_sunday(d):
                days.append(d)
            d += timedelta(days=1)

        total = sum(int(v) for v in entries.values())
        rem = max(0, target - total)
        per_day = rem // len(days) if len(days) > 0 else rem

        pdf_path = 'saving_plan_1year_detailed.pdf'
        doc = SimpleDocTemplate(pdf_path, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        story.append(Paragraph("1 Yillik Reja (kunma-kun, yakshanba chiqariladi)", styles['Title']))
        story.append(Spacer(1,12))
        story.append(Paragraph(f"Maqsad: {fmt(target)} so'm", styles['Normal']))
        story.append(Paragraph(f"Jami yig'ilgan (hozir): {fmt(total)} so'm", styles['Normal']))
        story.append(Paragraph(f"Qolgan: {fmt(rem)} so'm", styles['Normal']))
        story.append(Paragraph(f"Har ishchi kunga tavsiya: {fmt(per_day)} so'm", styles['Normal']))
        story.append(Spacer(1,12))

        rows = [['Sana', 'Hafta kuni', 'Reja (so\'m)', 'Haqiqiy (so\'m)', 'Bajarildi']]
        for d in days:
            d_iso = d.isoformat()
            planned = per_day
            actual = int(entries.get(d_iso, 0))
            done = '✓' if actual > 0 else ''
            rows.append([d_iso, d.strftime('%a'), fmt(planned), fmt(actual) if actual>0 else '', done])

        table = Table(rows, colWidths=[90,70,80,80,50])
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.lightgrey),('GRID',(0,0),(-1,-1),0.4,colors.black),
                                   ('ALIGN',(2,1),(-1,-1),'RIGHT')]))
        story.append(table)
        doc.build(story)
        return pdf_path
    except Exception as e:
        logger.exception('PDF creation failed: %s', e)
        return None

def main():
    ensure_data()
    token = os.environ.get('BOT_TOKEN')
    if not token:
        print('ERROR: Please set BOT_TOKEN environment variable')
        return
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_handler))
    app.add_handler(CommandHandler('settarget', settarget_cmd))
    app.add_handler(CommandHandler('setstart', setstart_cmd))
    print('Bot ishga tushdi...')
    app.run_polling()

if __name__ == '__main__':
    main()
