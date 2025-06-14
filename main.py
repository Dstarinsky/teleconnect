import os
import re
import logging
import warnings
from dotenv import load_dotenv
from datetime import datetime
from mysql.connector import pooling
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.warnings import PTBUserWarning

warnings.filterwarnings("ignore", category=PTBUserWarning)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    filename="bot.log"
)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")

import os

db_pool = pooling.MySQLConnectionPool(
    pool_name="bot_pool",
    pool_size=5,
    pool_reset_session=True,
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", 3306)),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASS"),
    database=os.getenv("DB_NAME")
)

NAME, PHONE, AREA, CITY, CAPACITY, DATE, EDIT_FIELD, EDIT_VALUE = range(8)

ad_editing = {}

def is_valid_phone(phone):
    return re.fullmatch(r"\d{7,15}", phone) is not None

def is_valid_date(date_str):
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
        return date >= datetime.today().date()
    except ValueError:
        return False

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error(msg="Exception while handling an update:", exc_info=context.error)

    try:
        if hasattr(update, "callback_query") and update.callback_query:
            await update.callback_query.message.reply_text("❌ קרתה שגיאה. נסה שוב מאוחר יותר.")
        elif hasattr(update, "message") and update.message:
            await update.message.reply_text("❌ קרתה שגיאה. נסה שוב מאוחר יותר.")
    except Exception as e:
        logging.error("Failed to send error message: %s", e)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    intro_text = (
        "🏠 *ברוכים הבאים לבוט החיבור בין מארחים לבין מי שביתו נפגע*\n\n"
        "בוט זה נועד לסייע בחיבור בין אנשים שיכולים להציע מקום לינה, לבין אלו שביתם נפגע והם זקוקים לאירוח זמני.\n\n"
        "💡 באמצעות הבוט ניתן:\n"
        "• לפרסם מודעת אירוח\n"
        "• לצפות בכל המודעות או לסנן לפי אזור\n"
        "• לערוך או למחוק מודעות קיימות\n"
        "• לדווח על מודעות שאינן הולמות\n\n"
        "🚨 *אזהרה:* הימנעו משיתוף מידע אישי רגיש. אנו מהווים פלטפורמת תיווך בלבד ואיננו אחראים לתוכן המודעות או להשלכות ההתקשרות בין המשתמשים.\n\n"
        "🙏 תודה על תרומתכם ועזרתכם לקהילה!"
    )

    keyboard = [
        [InlineKeyboardButton("📤 פרסום מודעה", callback_data='post_ad')],
        [InlineKeyboardButton("📋 הצגת המודעות שלי", callback_data='my_ads')],
        [InlineKeyboardButton("🌍 כל המודעות", callback_data='all_ads')],
        [InlineKeyboardButton("🔎 חיפוש לפי אזור", callback_data='search_by_area')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.message.reply_text(intro_text)
        await update.callback_query.message.reply_text("בחר פעולה:", reply_markup=reply_markup)
    else:
        await update.message.reply_text(intro_text)
        await update.message.reply_text("בחר פעולה:", reply_markup=reply_markup)

async def show_all_ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = db_pool.get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, name, phone, area, city, capacity, date_available FROM ads ORDER BY date_available ASC")
        ads = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    target = update.callback_query.message

    if not ads:
        await target.reply_text("📭 אין מודעות להצגה כרגע.")
    else:
        for ad in ads:
            text = (
                f"👤 שם: {ad['name']}\n"
                f"📞 טלפון: {ad['phone']}\n"
                f"📍 אזור: {ad['area']}\n"
                f"🏘️ עיר: {ad['city']}\n"
                f"👥 מספר אורחים: {ad['capacity']}\n"
                f"📅 תאריך: {ad['date_available']}"
            )
            buttons = [[InlineKeyboardButton("🚩 דווח", callback_data=f"report:{ad['id']}")]]
            await target.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    await target.reply_text(
        "⬅️ חזור לתפריט הראשי:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 חזרה לתפריט", callback_data='main_menu')]])
    )

async def start_post_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("📋 בוא ניצור מודעה חדשה. איך קוראים לך?")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text.strip()
    await update.message.reply_text("📞 מה מספר הטלפון שלך?")
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    if not is_valid_phone(phone):
        await update.message.reply_text("❗ מספר טלפון לא חוקי. השתמש רק במספרים (7–15 ספרות).")
        return PHONE
    context.user_data['phone'] = phone
    keyboard = [
        [InlineKeyboardButton("🌍 צפון", callback_data="area:צפון"),
         InlineKeyboardButton("🏙️ מרכז", callback_data="area:מרכז")],
        [InlineKeyboardButton("🏜️ דרום", callback_data="area:דרום"),
         InlineKeyboardButton("🌅 אילת", callback_data="area:אילת")],
        [InlineKeyboardButton("❓ אחר", callback_data="area:אחר")]
    ]
    await update.message.reply_text("📍 בחר אזור:", reply_markup=InlineKeyboardMarkup(keyboard))
    return AREA

async def get_area(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data['area'] = update.callback_query.data.split(":")[1]
    await update.callback_query.message.reply_text("🏘️ מה שם העיר שלך?")
    return CITY

async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['city'] = update.message.text.strip()
    await update.message.reply_text("👥 כמה אנשים אתה יכול לארח? (1–100)")
    return CAPACITY

async def get_capacity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = int(update.message.text.strip())
        if not (1 <= val <= 100):
            raise ValueError
    except ValueError:
        await update.message.reply_text("❗ הזן מספר בין 1 ל-100.")
        return CAPACITY
    context.user_data['capacity'] = val
    await update.message.reply_text("📅 באיזה תאריך אתה זמין? (YYYY-MM-DD)")
    return DATE

async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date_str = update.message.text.strip()
    if not is_valid_date(date_str):
        await update.message.reply_text("❗ תאריך לא חוקי. פורמט: YYYY-MM-DD")
        return DATE

    context.user_data['date'] = date_str
    user = update.effective_user
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO users (user_id, username, first_name, last_name)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE username=VALUES(username), first_name=VALUES(first_name), last_name=VALUES(last_name)
        """, (user.id, user.username, user.first_name, user.last_name))

        cursor.execute("""
            INSERT INTO ads (user_id, name, phone, area, city, capacity, date_available)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (user.id, context.user_data['name'], context.user_data['phone'], context.user_data['area'],
              context.user_data['city'], context.user_data['capacity'], context.user_data['date']))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    await update.message.reply_text("✅ המודעה פורסמה בהצלחה!",
                                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 חזרה לתפריט", callback_data='main_menu')]]))
    return ConversationHandler.END


async def show_my_ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    conn = db_pool.get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, name, phone, area, city, capacity, date_available FROM ads WHERE user_id = %s", (user_id,))
        ads = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    target = (
        update.callback_query.message
        if update.callback_query
        else update.message
    )

    if not ads:
        await target.reply_text("📭 אין לך מודעות כרגע.")
    else:
        for ad in ads:
            text = (
                f"👤 שם: {ad['name']}\n"
                f"📞 טלפון: {ad['phone']}\n"
                f"📍 אזור: {ad['area']}\n"
                f"🏘️ עיר: {ad['city']}\n"
                f"👥 מספר אורחים: {ad['capacity']}\n"
                f"📅 תאריך: {ad['date_available']}"
            )
            buttons = [
                [InlineKeyboardButton("📝 ערוך", callback_data=f"edit:{ad['id']}"),
                 InlineKeyboardButton("🗑️ מחק", callback_data=f"delete:{ad['id']}")]
            ]
            await target.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    await target.reply_text(
        "⬅️ חזור לתפריט הראשי:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 חזרה לתפריט", callback_data='main_menu')]])
    )

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    logging.info(f"[handle_buttons] user clicked: {query.data}")

    if query.data == 'all_ads':
        await show_all_ads(update, context)
    elif query.data == 'search_by_area':
        await show_area_options(update, context)
    elif query.data.startswith("choose_area:"):
        await show_ads_by_area(update, context)
    elif query.data == 'my_ads':
        await show_my_ads(update, context)
    elif query.data.startswith("delete:"):
        ad_id = int(query.data.split(":")[1])
        conn = db_pool.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM ads WHERE id = %s AND user_id = %s", (ad_id, query.from_user.id))
            conn.commit()
        finally:
            cursor.close()
            conn.close()
        await query.message.edit_text("✅ המודעה נמחקה.")
    elif query.data.startswith("edit:"):
        ad_id = int(query.data.split(":")[1])
        ad_editing[query.from_user.id] = ad_id
        keyboard = [
            [InlineKeyboardButton("👤 שם", callback_data="field:name"),
             InlineKeyboardButton("📞 טלפון", callback_data="field:phone")],
            [InlineKeyboardButton("🌍 אזור", callback_data="field:area"),
             InlineKeyboardButton("🏘️ עיר", callback_data="field:city")],
            [InlineKeyboardButton("👥 מספר אורחים", callback_data="field:capacity"),
             InlineKeyboardButton("📅 תאריך", callback_data="field:date")]
        ]
        await query.message.reply_text("🔧 מה ברצונך לערוך?", reply_markup=InlineKeyboardMarkup(keyboard))
        return EDIT_FIELD
    elif query.data.startswith("field:"):
        field = query.data.split(":")[1]
        context.user_data['edit_field'] = field
        if field == "area":
            keyboard = [
                [InlineKeyboardButton("🌍 צפון", callback_data="value:צפון"),
                 InlineKeyboardButton("🏙️ מרכז", callback_data="value:מרכז")],
                [InlineKeyboardButton("🏜️ דרום", callback_data="value:דרום"),
                 InlineKeyboardButton("🌅 אילת", callback_data="value:אילת")],
                [InlineKeyboardButton("❓ אחר", callback_data="value:אחר")]
            ]
            await query.message.reply_text("📍 בחר אזור חדש:", reply_markup=InlineKeyboardMarkup(keyboard))
            return EDIT_VALUE
        else:
            await query.message.reply_text("✏️ הזן ערך חדש:")
            return EDIT_VALUE
    elif query.data.startswith("value:"):
        value = query.data.split(":")[1]
        context.user_data['edit_value'] = value
        return await update_ad_value(update, context)
    elif query.data.startswith("report:"):
        ad_id = int(query.data.split(":")[1])
        user_id = query.from_user.id

        conn = db_pool.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO ad_reports (ad_id, user_id, reported_at)
                VALUES (%s, %s, NOW())
            """, (ad_id, user_id))
            conn.commit()
        finally:
            cursor.close()
            conn.close()

        await query.message.reply_text("✅ תודה! הדיווח התקבל ונבדוק את המודעה בהקדם.")
    elif query.data == 'main_menu':
        await query.message.delete()
        await start(update, context)


async def update_ad_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ad_id = ad_editing.get(user_id)
    target = update.message if update.message else update.callback_query.message

    logging.info(f"[update_ad_value] user_data={context.user_data}, ad_id={ad_id}")

    if not ad_id:
        await target.reply_text("⚠️ שגיאה: לא נמצאה מודעה לעריכה.")
        return ConversationHandler.END

    field = context.user_data.get('edit_field')
    value = context.user_data.get('edit_value') if 'edit_value' in context.user_data else update.message.text.strip()

    logging.info(f"Updating ad_id={ad_id}, field={field}, value={value}, user_id={user_id}")

    if field == 'phone' and not is_valid_phone(value):
        await target.reply_text("❗ מספר טלפון לא חוקי. רק מספרים.")
        return EDIT_VALUE
    if field == 'capacity':
        try:
            value = int(value)
            if not (1 <= value <= 100):
                raise ValueError
        except ValueError:
            await target.reply_text("❗ מספר לא חוקי. טווח 1-100.")
            return EDIT_VALUE
    if field == 'date' and not is_valid_date(value):
        await target.reply_text("❗ תאריך לא חוקי. פורמט: YYYY-MM-DD")
        return EDIT_VALUE

    conn = db_pool.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f"UPDATE ads SET {field} = %s WHERE id = %s AND user_id = %s", (value, ad_id, user_id))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    await target.reply_text(
        "✅ המודעה עודכנה בהצלחה.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 חזרה לתפריט", callback_data='main_menu')]
        ])
    )
    return ConversationHandler.END

async def show_area_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🌍 צפון", callback_data="area_filter:צפון"),
         InlineKeyboardButton("🏙️ מרכז", callback_data="area_filter:מרכז")],
        [InlineKeyboardButton("🏜️ דרום", callback_data="area_filter:דרום"),
         InlineKeyboardButton("🌅 אילת", callback_data="area_filter:אילת")],
        [InlineKeyboardButton("❓ אחר", callback_data="area_filter:אחר")],
        [InlineKeyboardButton("🔙 חזרה לתפריט", callback_data="main_menu")]
    ]
    await update.callback_query.message.reply_text(
        "📍 בחר אזור להצגת מודעות:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_ads_by_area(update: Update, context: ContextTypes.DEFAULT_TYPE):
    area = update.callback_query.data.split(":")[1]
    conn = db_pool.get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT id, name, phone, area, city, capacity, date_available
            FROM ads WHERE area = %s ORDER BY date_available ASC
        """, (area,))
        ads = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    target = update.callback_query.message

    if not ads:
        await target.reply_text(f"📭 אין מודעות זמינות באזור {area}.")
    else:
        for ad in ads:
            text = (
                f"👤 שם: {ad['name']}\n"
                f"📞 טלפון: {ad['phone']}\n"
                f"📍 אזור: {ad['area']}\n"
                f"🏘️ עיר: {ad['city']}\n"
                f"👥 מספר אורחים: {ad['capacity']}\n"
                f"📅 תאריך: {ad['date_available']}"
            )
            buttons = [[InlineKeyboardButton("🚩 דווח", callback_data=f"report:{ad['id']}")]]
            await target.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    await target.reply_text(
        "⬅️ חזור לתפריט הראשי:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 חזרה לתפריט", callback_data='main_menu')]])
    )

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_post_ad, pattern='^post_ad$')],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            AREA: [CallbackQueryHandler(get_area, pattern="^area:.*")],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)],
            CAPACITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_capacity)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
            EDIT_FIELD: [CallbackQueryHandler(handle_buttons, pattern='^field:.*')],
            EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_ad_value), CallbackQueryHandler(handle_buttons, pattern='^value:.*')]
        },
        fallbacks=[]
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(handle_buttons))
    app.add_handler(CommandHandler("start", start))
    app.add_error_handler(error_handler)

    print("🤖 Running Telegram bot...")
    app.run_polling()

if __name__ == '__main__':
    main()
