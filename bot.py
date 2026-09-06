import os
import re
import asyncio
import sqlite3
import logging
from datetime import datetime, timedelta, timezone

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

# =========================================================
# CONFIG
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")

# Hisobotlar va arizalar yuboriladigan ADMIN GURUHI
ADMIN_ID_RAW = os.getenv("ADMIN_ID")

# Admin USER IDlari
# .env dagi ADMIN_IDS ga bog'liq emas
ADMIN_IDS = {
    6514150973,
    8487314122,
}

DB_PATH = os.getenv(
    "DB_PATH",
    "/tmp/avtomaktab.db" if os.getenv("VERCEL") else "avtomaktab.db"
)

SCHOOL_LATITUDE = 41.329341
SCHOOL_LONGITUDE = 69.238440

if not TOKEN:
    raise RuntimeError(
        "BOT_TOKEN environment variable topilmadi!"
    )

if not ADMIN_ID_RAW:
    raise RuntimeError(
        "ADMIN_ID environment variable topilmadi! "
        "Bu yerga admin GURUH IDsi yoziladi."
    )

try:
    ADMIN_ID = int(ADMIN_ID_RAW)
except ValueError:
    raise RuntimeError(
        "ADMIN_ID raqam bo'lishi kerak!"
    )


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================================================
# STATES
# =========================================================

NAME, PHONE, BIRTHDAY, PASSPORT, MEDICAL, CATEGORY = range(6)


# =========================================================
# DATABASE
# =========================================================

def db_connect():
    return sqlite3.connect(DB_PATH)


def init_db():
    with db_connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                username TEXT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                birthday TEXT NOT NULL,
                category TEXT NOT NULL,
                passport_file_id TEXT,
                medical_file_id TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()


def save_registration(data):
    with db_connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO registrations (
                telegram_id,
                username,
                name,
                phone,
                birthday,
                category,
                passport_file_id,
                medical_file_id,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["telegram_id"],
                data.get("username"),
                data["name"],
                data["phone"],
                data["birthday"],
                data["category"],
                data.get("passport"),
                data.get("medical"),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )

        conn.commit()

        return cursor.lastrowid


def get_registration_count():
    with db_connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM registrations"
        ).fetchone()

        return row[0]


def get_last_registrations(limit=10):
    with db_connect() as conn:
        return conn.execute(
            """
            SELECT id, name, phone, birthday, category, created_at
            FROM registrations
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


# =========================================================
# TEXT / KEYBOARDS
# =========================================================

WELCOME_TEXT = (
    "🚗 <b>ZO‘R-777 AVTO MAKTAB</b>\n\n"
    "Assalomu alaykum! 👋\n"
    "Avtomaktabimizning rasmiy botiga xush kelibsiz.\n\n"
    "Kerakli bo‘limni tanlang:"
)


def main_menu():
    keyboard = [
        ["📝 Ro‘yxatdan o‘tish"],
        ["📚 Darslar", "🧠 Test"],
        ["👨‍🏫 O‘qituvchilar", "📅 Dars jadvali"],
        ["📍 Manzil", "📞 Bog‘lanish"],
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Bo‘limni tanlang...",
    )


def cancel_keyboard():
    return ReplyKeyboardMarkup(
        [["❌ Bekor qilish"]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data.clear()

    await update.message.reply_text(
        WELCOME_TEXT,
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )


# =========================================================
# REGISTRATION
# =========================================================

async def register_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.callback_query:
        await update.callback_query.answer()
        message = update.callback_query.message
    else:
        message = update.message

    context.user_data.clear()

    await message.reply_text(
        "📝 <b>RO‘YXATDAN O‘TISH</b>\n\n"
        "1️⃣ Ism va familiyangizni kiriting:",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_keyboard(),
    )

    return NAME


async def get_name(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    name = update.message.text.strip()

    if len(name) < 3 or name == "❌ Bekor qilish":

        if name == "❌ Bekor qilish":
            return await cancel(update, context)

        await update.message.reply_text(
            "❗ Ism va familiyani to‘liq kiriting.\n"
            "Masalan: <b>Ahmadjon Bahromjonov</b>",
            parse_mode=ParseMode.HTML,
        )

        return NAME

    context.user_data["name"] = name

    keyboard = [
        [
            KeyboardButton(
                "📱 Telefon raqamni yuborish",
                request_contact=True,
            )
        ],
        ["❌ Bekor qilish"],
    ]

    await update.message.reply_text(
        "2️⃣ <b>Telefon raqamingizni yuboring:</b>\n\n"
        "Pastdagi tugma orqali Telegram kontakt sifatida "
        "yuborishingiz yoki raqamni qo‘lda yozishingiz mumkin.",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )

    return PHONE


async def get_phone(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.message.text == "❌ Bekor qilish":
        return await cancel(update, context)

    phone = None

    if update.message.contact:
        phone = update.message.contact.phone_number

    elif update.message.text:
        phone = update.message.text.strip()

    if not phone:
        await update.message.reply_text(
            "❗ Telefon raqamini yuboring."
        )

        return PHONE

    cleaned = re.sub(r"[^\d+]", "", phone)
    digits = re.sub(r"\D", "", cleaned)

    if len(digits) < 9:

        await update.message.reply_text(
            "❗ Telefon raqami noto‘g‘ri.\n"
            "Masalan: <b>+998901234567</b>",
            parse_mode=ParseMode.HTML,
        )

        return PHONE

    context.user_data["phone"] = cleaned

    await update.message.reply_text(
        "3️⃣ 🎂 <b>Tug‘ilgan sanangizni kiriting:</b>\n\n"
        "Format: <code>KK.OO.YYYY</code>\n"
        "Masalan: <code>15.04.2008</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_keyboard(),
    )

    return BIRTHDAY


async def get_birthday(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    birthday = update.message.text.strip()

    if birthday == "❌ Bekor qilish":
        return await cancel(update, context)

    try:

        date = datetime.strptime(
            birthday,
            "%d.%m.%Y"
        )

        if date > datetime.now():
            raise ValueError

    except ValueError:

        await update.message.reply_text(
            "❗ Sana noto‘g‘ri.\n\n"
            "To‘g‘ri format:\n"
            "<code>15.04.2008</code>",
            parse_mode=ParseMode.HTML,
        )

        return BIRTHDAY

    context.user_data["birthday"] = birthday

    await update.message.reply_text(
        "4️⃣ 🪪 <b>Pasportning OLD TOMONINI yuboring.</b>\n\n"
        "📸 Rasm yoki 📄 PDF yuboring.",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_keyboard(),
    )

    return PASSPORT


# =========================================================
# PASSPORT
# =========================================================

async def get_passport(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.message.text == "❌ Bekor qilish":
        return await cancel(update, context)

    # -----------------------------------------------------
    # PASPORT OLD TOMONI
    # -----------------------------------------------------

    if not context.user_data.get(
        "passport_front_message_id"
    ):

        if update.message.photo:

            context.user_data["passport_front"] = (
                update.message.photo[-1].file_id
            )

            context.user_data[
                "passport_front_message_id"
            ] = update.message.message_id

            context.user_data[
                "passport_front_chat_id"
            ] = update.message.chat_id

        elif update.message.document:

            document = update.message.document

            if document.mime_type != "application/pdf":

                await update.message.reply_text(
                    "❗ Pasportni rasm yoki PDF formatida yuboring."
                )

                return PASSPORT

            context.user_data["passport_front"] = (
                document.file_id
            )

            context.user_data[
                "passport_front_message_id"
            ] = update.message.message_id

            context.user_data[
                "passport_front_chat_id"
            ] = update.message.chat_id

        else:

            await update.message.reply_text(
                "❗ Pasportning OLD TOMONINI "
                "rasm yoki PDF ko‘rinishida yuboring."
            )

            return PASSPORT

        await update.message.reply_text(
            "✅ Pasportning OLD TOMONI qabul qilindi.\n\n"
            "➡️ Endi <b>pasportning ORQA TOMONINI</b> yuboring.",
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_keyboard(),
        )

        return PASSPORT

    # -----------------------------------------------------
    # PASPORT ORQA TOMONI
    # -----------------------------------------------------

    if update.message.photo:

        context.user_data["passport_back"] = (
            update.message.photo[-1].file_id
        )

        context.user_data[
            "passport_back_message_id"
        ] = update.message.message_id

        context.user_data[
            "passport_back_chat_id"
        ] = update.message.chat_id

    elif update.message.document:

        document = update.message.document

        if document.mime_type != "application/pdf":

            await update.message.reply_text(
                "❗ Pasportning ORQA TOMONINI "
                "rasm yoki PDF formatida yuboring."
            )

            return PASSPORT

        context.user_data["passport_back"] = (
            document.file_id
        )

        context.user_data[
            "passport_back_message_id"
        ] = update.message.message_id

        context.user_data[
            "passport_back_chat_id"
        ] = update.message.chat_id

    else:

        await update.message.reply_text(
            "❗ Pasportning ORQA TOMONINI "
            "rasm yoki PDF ko‘rinishida yuboring."
        )

        return PASSPORT

    context.user_data["passport"] = (
        context.user_data["passport_front"]
    )

    await update.message.reply_text(
        "✅ Pasportning OLD va ORQA TOMONI qabul qilindi.\n\n"
        "5️⃣ 🩺 <b>083 tibbiy formasini yuboring.</b>\n\n"
        "📸 Rasm yoki 📄 PDF yuboring.",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_keyboard(),
    )

    return MEDICAL


# =========================================================
# MEDICAL
# =========================================================

async def get_medical(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.message.text == "❌ Bekor qilish":
        return await cancel(update, context)

    if update.message.photo:

        context.user_data["medical"] = (
            update.message.photo[-1].file_id
        )

        context.user_data[
            "medical_message_id"
        ] = update.message.message_id

        context.user_data[
            "medical_chat_id"
        ] = update.message.chat_id

    elif update.message.document:

        document = update.message.document

        if document.mime_type != "application/pdf":

            await update.message.reply_text(
                "❗ 083 formasini rasm yoki PDF formatida yuboring."
            )

            return MEDICAL

        context.user_data["medical"] = (
            document.file_id
        )

        context.user_data[
            "medical_message_id"
        ] = update.message.message_id

        context.user_data[
            "medical_chat_id"
        ] = update.message.chat_id

    else:

        await update.message.reply_text(
            "❗ 083 formasini rasm yoki PDF ko‘rinishida yuboring."
        )

        return MEDICAL

    keyboard = [
        [
            InlineKeyboardButton(
                "🚗 B kategoriya",
                callback_data="category_B",
            )
        ]
    ]

    await update.message.reply_text(
        "✅ 083 forma qabul qilindi.\n\n"
        "6️⃣ 🚘 <b>Kategoriyani tanlang:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return CATEGORY


# =========================================================
# CATEGORY
# =========================================================

async def get_category(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    category = query.data.replace(
        "category_",
        ""
    )

    data = {
        "telegram_id": update.effective_user.id,
        "username": update.effective_user.username,
        "name": context.user_data["name"],
        "phone": context.user_data["phone"],
        "birthday": context.user_data["birthday"],
        "category": category,
        "passport": context.user_data.get("passport"),
        "medical": context.user_data.get("medical"),
    }

    registration_id = save_registration(data)

    admin_text = (
        "🚨 <b>YANGI RO‘YXATDAN O‘TISH</b>\n\n"
        f"🆔 Ariza: <code>#{registration_id}</code>\n"
        f"👤 Ism: <b>{data['name']}</b>\n"
        f"📱 Telefon: <b>{data['phone']}</b>\n"
        f"🎂 Tug‘ilgan sana: <b>{data['birthday']}</b>\n"
        f"🚗 Kategoriya: <b>{data['category']}</b>\n"
        f"👤 Telegram ID: <code>{data['telegram_id']}</code>\n"
        f"🔗 Username: @{data['username'] or 'mavjud emas'}\n\n"
        "🪪 Pasport: ✅ qabul qilindi\n"
        "🩺 083 forma: ✅ qabul qilindi"
    )

    try:

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_text,
            parse_mode=ParseMode.HTML,
        )

        # PASPORT OLD

        if context.user_data.get(
            "passport_front_message_id"
        ):

            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"🪪 <b>Pasport OLD TOMONI — "
                    f"ariza #{registration_id}</b>"
                ),
                parse_mode=ParseMode.HTML,
            )

            await context.bot.copy_message(
                chat_id=ADMIN_ID,
                from_chat_id=context.user_data[
                    "passport_front_chat_id"
                ],
                message_id=context.user_data[
                    "passport_front_message_id"
                ],
            )

        # PASPORT ORQA

        if context.user_data.get(
            "passport_back_message_id"
        ):

            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"🪪 <b>Pasport ORQA TOMONI — "
                    f"ariza #{registration_id}</b>"
                ),
                parse_mode=ParseMode.HTML,
            )

            await context.bot.copy_message(
                chat_id=ADMIN_ID,
                from_chat_id=context.user_data[
                    "passport_back_chat_id"
                ],
                message_id=context.user_data[
                    "passport_back_message_id"
                ],
            )

        # 083 FORMA

        if context.user_data.get(
            "medical_message_id"
        ):

            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"🩺 <b>083 forma — "
                    f"ariza #{registration_id}</b>"
                ),
                parse_mode=ParseMode.HTML,
            )

            await context.bot.copy_message(
                chat_id=ADMIN_ID,
                from_chat_id=context.user_data[
                    "medical_chat_id"
                ],
                message_id=context.user_data[
                    "medical_message_id"
                ],
            )

    except Exception:

        logger.exception(
            "Admin'ga ariza yuborishda xatolik"
        )

    await query.message.reply_text(
        "🎉 <b>RO‘YXATDAN O‘TISH MUVAFFAQIYATLI!</b>\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🆔 Ariza: <code>#{registration_id}</code>\n"
        f"👤 Ism: {data['name']}\n"
        f"📱 Telefon: {data['phone']}\n"
        f"🎂 Tug‘ilgan sana: {data['birthday']}\n"
        "🪪 Pasport: ✅ Qabul qilindi\n"
        "🩺 083 forma: ✅ Qabul qilindi\n"
        f"🚗 Kategoriya: {data['category']}\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "📞 Arizangiz qabul qilindi. "
        "Tez orada avtomaktab xodimi siz bilan bog‘lanadi.",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )

    context.user_data.clear()

    return ConversationHandler.END


# =========================================================
# WEEKLY REPORT
# =========================================================

UZ_TZ = timezone(
    timedelta(hours=5)
)


def get_week_stats(start_dt, end_dt):

    start_str = start_dt.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    end_str = end_dt.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    with db_connect() as conn:

        total = conn.execute(
            """
            SELECT COUNT(*)
            FROM registrations
            WHERE created_at >= ?
            AND created_at < ?
            """,
            (
                start_str,
                end_str,
            ),
        ).fetchone()[0]

        categories = conn.execute(
            """
            SELECT category, COUNT(*)
            FROM registrations
            WHERE created_at >= ?
            AND created_at < ?
            GROUP BY category
            ORDER BY COUNT(*) DESC
            """,
            (
                start_str,
                end_str,
            ),
        ).fetchall()

    return total, categories


def build_weekly_report(
    week_offset=0
):

    now = datetime.now(UZ_TZ)

    current_week_start = (
        now - timedelta(days=now.weekday())
    ).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    week_start = (
        current_week_start
        - timedelta(days=7 * week_offset)
    )

    week_end = (
        week_start + timedelta(days=7)
    )

    previous_week_start = (
        week_start - timedelta(days=7)
    )

    if week_offset == 0:
        report_end = (
            now + timedelta(seconds=1)
        )
    else:
        report_end = week_end

    total, categories = get_week_stats(
        week_start,
        report_end,
    )

    previous_total, _ = get_week_stats(
        previous_week_start,
        week_start,
    )

    difference = total - previous_total

    if difference > 0:

        comparison = (
            f"📈 O‘tgan haftaga nisbatan: "
            f"+{difference} ta"
        )

    elif difference < 0:

        comparison = (
            f"📉 O‘tgan haftaga nisbatan: "
            f"{difference} ta"
        )

    else:

        comparison = (
            "➡️ O‘tgan hafta bilan bir xil"
        )

    lines = [
        "📊 <b>HAFTALIK HISOBOT</b>",
        "",
        (
            f"📅 {week_start.strftime('%d.%m.%Y')} — "
            f"{(report_end - timedelta(seconds=1)).strftime('%d.%m.%Y')}"
        ),
        (
            f"👥 Yangi ro‘yxatdan o‘tganlar: "
            f"<b>{total} ta</b>"
        ),
        (
            f"🕐 Hisobot vaqti: "
            f"{now.strftime('%d.%m.%Y %H:%M')}"
        ),
        "",
        comparison,
        (
            f"📋 O‘tgan hafta: "
            f"<b>{previous_total} ta</b>"
        ),
    ]

    if categories:

        lines.extend([
            "",
            "🚗 <b>Kategoriyalar bo‘yicha:</b>",
        ])

        for category, count in categories:

            lines.append(
                f"• {category}: <b>{count} ta</b>"
            )

    else:

        lines.extend([
            "",
            "📭 Bu hafta hali yangi "
            "ro‘yxatdan o‘tganlar yo‘q.",
        ])

    return "\n".join(lines)


# =========================================================
# ADMIN CHECK
# =========================================================

async def is_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    if not user:
        return False

    logger.info(
        "Admin tekshiruvi: user_id=%s username=%s",
        user.id,
        user.username,
    )

    return user.id in ADMIN_IDS


# =========================================================
# MY ID
# =========================================================

async def my_id(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    if not user:
        return

    await update.message.reply_text(
        f"🆔 Sizning Telegram ID: "
        f"<code>{user.id}</code>\n"
        f"👤 Username: "
        f"@{user.username or 'mavjud emas'}",
        parse_mode=ParseMode.HTML,
    )


# =========================================================
# WEEKLY REPORT COMMAND
# =========================================================

async def weekly_report_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await is_admin(update, context):

        await update.message.reply_text(
            "⛔ Sizda admin huquqi yo‘q."
        )

        return

    report = build_weekly_report()

    try:

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=report,
            parse_mode=ParseMode.HTML,
        )

        if (
            update.effective_chat
            and update.effective_chat.id != ADMIN_ID
        ):

            await update.message.reply_text(
                "✅ Haftalik hisobot admin guruhga yuborildi."
            )

    except Exception:

        logger.exception(
            "/hisobot yuborishda xatolik"
        )

        await update.message.reply_text(
            "❌ Hisobotni guruhga yuborib bo‘lmadi.\n\n"
            "ADMIN_ID guruh IDsi ekanini va "
            "bot guruhda ekanini tekshiring."
        )


# =========================================================
# AUTOMATIC WEEKLY REPORT
# =========================================================

async def weekly_report_loop(app):

    while True:

        now = datetime.now(UZ_TZ)

        days_until_monday = (
            7 - now.weekday()
        ) % 7

        next_monday = (
            now + timedelta(
                days=days_until_monday
            )
        ).replace(
            hour=9,
            minute=0,
            second=0,
            microsecond=0,
        )

        if next_monday <= now:

            next_monday += timedelta(
                days=7
            )

        wait_seconds = (
            next_monday - now
        ).total_seconds()

        logger.info(
            "Keyingi haftalik hisobot: %s",
            next_monday.strftime(
                "%Y-%m-%d %H:%M"
            ),
        )

        await asyncio.sleep(
            wait_seconds
        )

        try:

            await app.bot.send_message(
                chat_id=ADMIN_ID,
                text=build_weekly_report(
                    week_offset=1
                ),
                parse_mode=ParseMode.HTML,
            )

            logger.info(
                "Haftalik hisobot yuborildi."
            )

        except Exception:

            logger.exception(
                "Haftalik hisobotni yuborishda xatolik"
            )


async def post_init(app):

    asyncio.create_task(
        weekly_report_loop(app)
    )


# =========================================================
# CANCEL
# =========================================================

async def cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data.clear()

    await update.message.reply_text(
        "❌ <b>Ro‘yxatdan o‘tish bekor qilindi.</b>\n\n"
        "Qayta boshlash uchun tugmani bosing.",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )

    return ConversationHandler.END


# =========================================================
# ADMIN PANEL
# =========================================================

async def admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await is_admin(update, context):

        await update.message.reply_text(
            "⛔ Sizda admin huquqi yo‘q."
        )

        return

    count = get_registration_count()

    keyboard = [
        [
            InlineKeyboardButton(
                "👥 O‘quvchilar",
                callback_data="admin_students",
            )
        ],
        [
            InlineKeyboardButton(
                "📊 Statistika",
                callback_data="admin_stats",
            )
        ],
    ]

    await update.message.reply_text(
        "👨‍💼 <b>ADMIN PANEL</b>\n\n"
        f"👥 Jami arizalar: <b>{count}</b>\n\n"
        "Kerakli bo‘limni tanlang:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
    )


async def admin_buttons(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if not await is_admin(
        update,
        context
    ):

        await query.answer(
            "⛔ Ruxsat yo‘q.",
            show_alert=True,
        )

        return

    await query.answer()

    if query.data == "admin_stats":

        count = get_registration_count()

        await query.message.reply_text(
            "📊 <b>STATISTIKA</b>\n\n"
            f"👥 Jami ro‘yxatdan o‘tganlar: "
            f"<b>{count}</b>",
            parse_mode=ParseMode.HTML,
        )

    elif query.data == "admin_students":

        rows = get_last_registrations(10)

        if not rows:

            await query.message.reply_text(
                "📭 Hozircha arizalar yo‘q."
            )

            return

        text = (
            "👥 <b>SO‘NGGI ARIZALAR</b>\n\n"
        )

        for row in rows:

            (
                reg_id,
                name,
                phone,
                birthday,
                category,
                created,
            ) = row

            text += (
                f"🆔 #{reg_id}\n"
                f"👤 {name}\n"
                f"📱 {phone}\n"
                f"🎂 {birthday}\n"
                f"🚗 {category}\n"
                f"🕒 {created}\n"
                "────────────\n"
            )

        await query.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
        )


# =========================================================
# MENU
# =========================================================

async def menu_buttons(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = update.message.text

    responses = {

        "📚 Darslar": (
            "📚 <b>DARSLAR</b>\n\n"
            "📖 Nazariy mashg‘ulotlar\n"
            "🚗 Amaliy haydash\n"
            "📝 Yo‘l harakati qoidalari"
        ),

        "🧠 Test": (
            "🧠 <b>TEST</b>\n\n"
            "Yo‘l harakati qoidalari bo‘yicha "
            "test tizimi tez orada ishga tushadi."
        ),

        "👨‍🏫 O‘qituvchilar": (
            "👨‍🏫 <b>O‘QITUVCHILAR</b>\n\n"
            "Tajribali instruktorlarimiz haqida "
            "ma’lumot tez orada qo‘shiladi."
        ),

        "📅 Dars jadvali": (
            "📅 <b>DARS JADVALI</b>\n\n"
            "Dars kunlari va vaqtlarini "
            "avtomaktab ma’muriyatidan bilib "
            "olishingiz mumkin."
        ),

        "📍 Manzil": (
            "📍 <b>MANZIL</b>\n\n"
            "ZO‘R-777 AVTO MAKTAB\n"
            "📌 Koordinata: "
            "<code>41.329341, 69.238440</code>"
        ),

        "📞 Bog‘lanish": (
            "📞 <b>BOG‘LANISH</b>\n\n"
            "☎️ Telefon: +998 (90) 807-12-22\n"
            "📍 Manzil: 41.329341, 69.238440"
        ),
    }

    response = responses.get(text)

    if response:

        await update.message.reply_text(
            response,
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )

        if text == "📍 Manzil":

            await update.message.reply_location(
                latitude=SCHOOL_LATITUDE,
                longitude=SCHOOL_LONGITUDE,
            )


# =========================================================
# ERROR
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    logger.error(
        "Exception while handling update:",
        exc_info=context.error,
    )


# =========================================================
# APPLICATION
# =========================================================

def build_application():

    init_db()

    app = (
        Application
        .builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    registration = ConversationHandler(

        entry_points=[

            MessageHandler(
                filters.Regex(
                    r"^📝 Ro‘yxatdan o‘tish$"
                ),
                register_start,
            ),

            CallbackQueryHandler(
                register_start,
                pattern=r"^register$",
            ),
        ],

        states={

            NAME: [

                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    get_name,
                )

            ],

            PHONE: [

                MessageHandler(
                    filters.CONTACT
                    | (
                        filters.TEXT
                        & ~filters.COMMAND
                    ),
                    get_phone,
                )

            ],

            BIRTHDAY: [

                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    get_birthday,
                )

            ],

            PASSPORT: [

                MessageHandler(
                    filters.PHOTO
                    | filters.Document.ALL,
                    get_passport,
                )

            ],

            MEDICAL: [

                MessageHandler(
                    filters.PHOTO
                    | filters.Document.ALL,
                    get_medical,
                )

            ],

            CATEGORY: [

                CallbackQueryHandler(
                    get_category,
                    pattern=r"^category_",
                )

            ],
        },

        fallbacks=[

            CommandHandler(
                "cancel",
                cancel,
            ),

            MessageHandler(
                filters.Regex(
                    r"^❌ Bekor qilish$"
                ),
                cancel,
            ),
        ],

        allow_reentry=True,
    )

    # -----------------------------------------------------
    # COMMANDS
    # -----------------------------------------------------

    app.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    app.add_handler(
        CommandHandler(
            "admin",
            admin,
        )
    )

    app.add_handler(
        CommandHandler(
            "hisobot",
            weekly_report_command,
        )
    )

    app.add_handler(
        CommandHandler(
            "myid",
            my_id,
        )
    )

    # -----------------------------------------------------
    # REGISTRATION
    # -----------------------------------------------------

    app.add_handler(
        registration
    )

    # -----------------------------------------------------
    # ADMIN BUTTONS
    # -----------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            admin_buttons,
            pattern=r"^admin_",
        )
    )

    # -----------------------------------------------------
    # MENU
    # -----------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            menu_buttons,
        )
    )

    app.add_error_handler(
        error_handler
    )

    return app


# =========================================================
# MAIN
# =========================================================

def main():

    app = build_application()

    logger.info(
        "🚗 ZO‘R-777 AVTO MAKTAB bot ishga tushdi!"
    )

    app.run_polling(
        poll_interval=1,
        timeout=30,
        bootstrap_retries=5,
    )


if __name__ == "__main__":
    main()