# Telegram Savings Bot (FinalV2)
Bu loyiha Telegram bot bo'lib, quyidagilarni qiladi:
- /start — bosh menyu: Maqsad, jami yig'ilgan, qolgan summa, bugungi yig'im va menyu
- Menyuda: Kunlik summa qo'shish, Umumiy balans, Valyuta kursi, Reja (PDF 1 yil)
- Kunlik summa so'mda qo'shiladi va jami, qolgan miqdor avtomatik yangilanadi
- Valyuta kursi onlayn olinadi (exchangerate.host)
- Reja (PDF) tugmasi 1 yillik ishchi kunlarga (yakshanba chiqarilgan) tavsiya qilingan kunlik summa bilan jadval yaratadi

## Ishga tushirish
1. GitHub ga yuklang va Railway yoki boshqa PaaS ga deploy qiling.
2. Rekpozitoriyada **Settings → Secrets and variables → Actions** ga `BOT_TOKEN` nomli secret qo'shing yoki Railway/Render da environment variable sifatida `BOT_TOKEN` qo'ying.
3. Start command: `python bot.py`

