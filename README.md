# Telegram Savings Bot (tayyor loyiha)
Bu loyiha sizga $1000 (taxminiy) yig'ish uchun Telegram bot beradi. Bot quyidagilarni qiladi:
- Maqsadni o'rnatish (/settarget)
- Boshlanish sanasini o'rnatish (/setstart)
- Kunlik summani kirish (/add yoki /adddate)
- Jami yig'ilgan / qolgan summa va kunlik tavsiya (/total, /remaining)
- Valyuta kursini olish (/rate)
- Oy hisobotini ko'rish (/report YYYY-MM)

**MUHIM**: Bot tokenni hech qayerga to'g'ridan-to'g'ri joylamang. Quyidagi ko'rsatmalar orqali GitHub Secrets va Railway/Render-da o'rnating.

## Fayllar
- bot.py — asosiy kod
- requirements.txt — kerakli kutubxonalar

## Qanday qilib GitHub-ga yuklash (eng sodda)
1. ZIPni oching va papkani o'zingizning kompyuteringizga saqlang.
2. GitHub.com ga kiring va yangi repository yarating (nom: `TelegramSavingsBot`).
3. Kompyuterda papkaga kirib quyidagilarni bajaring:
   ```bash
   git init
   git branch -M main
   git remote add origin https://github.com/YOURUSERNAME/TelegramSavingsBot.git
   git add .
   git commit -m "Initial commit"
   git push -u origin main
   ```
4. GitHub reponi oching → **Settings → Secrets and variables → Actions → New repository secret** ga kiring.
   - Name: `BOT_TOKEN`
   - Value: (BotFather'dan olgan token, masalan: 498141994:AAH...)
   - Saqlang.

## Railway-ga deploy qilish (eng oson, bepul)
1. https://railway.app ga kiring va akkaunt yarating (yoki Google bilan kiring).
2. New Project → Deploy from GitHub → o'z reponi tanlang.
3. Railway sizga kerakli branch (main) ni so'raydi — tanlang.
4. Environment Variables (Railway UI orqali) ga `BOT_TOKEN` ni qo'shing (value: token).
5. Start command sifatida bo'sh qoldiring yoki `python bot.py` kiriting.
6. Deploy tugmasini bosing. Deploy yakunlangach, bot avtomatik ishga tushadi.
7. Endi Telegramda botga /start yozib tekshiring.

## Agar Railway ishlamasa, Render yoki boshqa PaaS-lardan foydalaning — usul shunga o'xshash.
## Agar yordam kerak bo'lsa — men bosqichma-bosqich qo'llab-quvvatlayman.
