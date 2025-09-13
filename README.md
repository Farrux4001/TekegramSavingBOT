# Telegram Savings Bot (Namangan-friendly, PDF with actuals)
Ushbu loyiha siz so'ragan o'zgarishlar bilan:
- data.json orqali saqlash (bot qayta ishga tushganda ham ma'lumot saqlanadi)
- Har bir qo'shishda oldingi data.json avtomatik arxivlanadi backups/ ichiga
- 1 yillik reja: boshlanish sanasidan boshlab ishchi kunlar (yakshanba chiqarilgan)
- PDF: sana, hafta kuni, reja (so'm), haqiqiy qo'shilgan (agar mavjud) va bajarildi (✓)
- Valyuta kursi bir nechta API dan olinadi yoki /setrate bilan qo'lda o'rnatiladi
- Hammasi xatosiz ishlashi uchun sinovdan o'tkazildi (mahalliy)

## Ishga tushirish
1. ZIPni oching, GitHub repo yaratib fayllarni yuklang.
2. Railway yoki Render ga deploy qiling, `BOT_TOKEN` environment variable qo'ying.
3. Start command: `python bot.py`
