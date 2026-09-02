# ZO‘R-777 Avto Maktab bot

## Ishga tushirish

Python 3.10 yoki undan yangi versiya kerak.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export BOT_TOKEN="Telegram bot tokeningiz"
python bot.py
```

Windows PowerShell uchun:

```powershell
$env:BOT_TOKEN = "Telegram bot tokeningiz"
python bot.py
```

Tokenni Telegram’dagi BotFather orqali oling va uni ochiq kodga yozmang.

## Vercel'ga deploy qilish

1. Vercel dashboard'da shu GitHub repository'ni import qiling.
2. **Settings → Environment Variables** bo‘limiga quyidagilarni qo‘shing:

```text
BOT_TOKEN=BotFather bergan yangi token
ADMIN_ID=-5189012425
```

3. **Deploy** yoki **Redeploy** tugmasini bosing.
4. Deploy tugagach, webhook'ni bir marta ulang:

```bash
curl "https://api.telegram.org/botYANGI_TOKEN/setWebhook?url=https://SIZNING-LOYIHA.vercel.app/api/webhook"
```

Javobda `"ok":true` chiqsa, bot Vercel orqali ishlayapti. Vercel serverless bo‘lgani
uchun `avtomaktab.db` lokal fayli doimiy saqlanmaydi; production uchun Supabase kabi
doimiy database ishlatish tavsiya etiladi.

## 24/7 serverga joylash

Kompyuter o‘chiq bo‘lsa ham ishlashi uchun loyihani Railway, Render yoki VPS serverga
Docker orqali joylang. `Dockerfile` tayyor.

Hosting panelidagi **Variables/Environment variables** bo‘limiga quyidagilarni qo‘shing:

```text
BOT_TOKEN=BotFather bergan yangi token
ADMIN_ID=-5189012425
```

Deploy komandasi:

```bash
docker build -t zorbot .
docker run -d --restart unless-stopped \
	-e BOT_TOKEN="$BOT_TOKEN" \
	-e ADMIN_ID="$ADMIN_ID" \
	-e DB_PATH=/data/avtomaktab.db \
	-v zorbot-data:/data \
	--name zorbot zorbot
```

Serverda SQLite bazasi saqlanib qolishi uchun persistent volume ulang. Telegram bot
polling ishlatgani sababli hostingda **Worker/Service** turini tanlang, web service emas.