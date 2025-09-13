# Telegram Savings Bot (Final Fixed)
# Foydalanuvchiga kunlik jamg‘arma kiritish, balans va qolgan summani ko‘rish,
# hamda valyuta kursini olish imkoniyatini beradi.

import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Umumiy sozlamalar
TARGET_AMOUNT = 1000  # maqsad
SAVED_AMOUNT = 0      # umumiy jamg‘arma

# Start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Kunlik summa qo‘shish", callback_data="add")],
        [InlineKeyboardButton("💰 Umumiy balans", callback_data="balance")],
        [InlineKeyboardButton("💱 Valyuta kursi", callback_data="currency")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    remaining = TARGET_AMOUNT - SAVED_AMOUNT
    await update.message.reply_text(
        f"🎯 Maqsad: {TARGET_AMOUNT}$\n💵 Jamg‘arilgan: {SAVED_AMOUNT}$\n📉 Qolgan: {remaining}$",
        reply_markup=reply_markup
    )

# Callbacklarni boshqarish
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global SAVED_AMOUNT
    query = update.callback_query
    await query.answer()

    if query.data == "add":
        SAVED_AMOUNT += 10  # vaqtincha har safar 10$ qo‘shadi
        remaining = TARGET_AMOUNT - SAVED_AMOUNT
        await query.edit_message_text(
            f"✅ Kunlik summa qo‘shildi!\n\n💵 Jamg‘arilgan: {SAVED_AMOUNT}$\n📉 Qolgan: {remaining}$"
        )
    elif query.data == "balance":
        remaining = TARGET_AMOUNT - SAVED_AMOUNT
        await query.edit_message_text(
            f"💵 Umumiy balans: {SAVED_AMOUNT}$\n📉 Qolgan: {remaining}$"
        )
    elif query.data == "currency":
        rate = get_usd_to_uzs()
        await query.edit_message_text(
            f"💱 1 USD = {rate} UZS"
        )

# Valyuta kursini olish
def get_usd_to_uzs():
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        res = requests.get(url).json()
        return res["rates"]["UZS"]
    except:
        return "Noma’lum"

def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("ERROR: Please set BOT_TOKEN environment variable")
        return
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    print("Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
