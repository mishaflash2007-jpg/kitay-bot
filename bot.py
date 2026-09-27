import os
import sqlite3
from decimal import Decimal, ROUND_HALF_UP

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")
DB_FILE = "kitay_bot.db"

PEOPLE = {
    "Миршод": "mirshod",
    "Отабек": "otabek",
    "Ойбек": "oybek",
}


def db_connect():
    return sqlite3.connect(DB_FILE)


def init_db():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person TEXT NOT NULL,
            reason TEXT NOT NULL,
            amount REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["➕ Xarajat qo‘shish", "📋 Xarajatlar"],
            ["📊 Hisobot", "❌ Bekor qilish"],
        ],
        resize_keyboard=True
    )


def people_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["Миршод", "Отабек"],
            ["Ойбек"],
            ["❌ Bekor qilish"],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "🇨🇳 <b>Kitay safar xarajatlar botiga xush kelibsiz!</b>\n\n"
        "👤 Миршод\n"
        "👤 Отабек\n"
        "👤 Ойбек\n\n"
        "💴 Barcha summalar yuan (¥) da.",
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )


async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["state"] = "choose_person"

    await update.message.reply_text(
        "👤 <b>Kim xarajatni to‘lagan?</b>",
        parse_mode="HTML",
        reply_markup=people_keyboard()
    )


async def handle_person(update: Update, context: ContextTypes.DEFAULT_TYPE):
    person = update.message.text

    if person not in PEOPLE:
        return

    context.user_data["person"] = person
    context.user_data["state"] = "reason"

    await update.message.reply_text(
        f"👤 To‘lovchi: <b>{person}</b>\n\n"
        "📝 Xarajat nima uchun bo‘lgan?\n"
        "Masalan: Taksi, restoran, mehmonxona...",
        parse_mode="HTML"
    )


async def handle_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()

    if not reason:
        await update.message.reply_text("📝 Xarajat nomini yozing.")
        return

    context.user_data["reason"] = reason
    context.user_data["state"] = "amount"

    await update.message.reply_text(
        "💴 Summani yuan bilan kiriting.\n\n"
        "Masalan: 150 yoki 125.50"
    )


async def handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(",", ".")

    try:
        amount = Decimal(text)
    except:
        await update.message.reply_text("❗ Masalan: 150 yoki 125.50")
        return

    if amount <= 0:
        await update.message.reply_text("❗ Summa 0 dan katta bo‘lishi kerak.")
        return

    amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    person = context.user_data["person"]
    reason = context.user_data["reason"]

    conn = db_connect()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO expenses (person, reason, amount) VALUES (?, ?, ?)",
        (person, reason, float(amount))
    )

    conn.commit()
    conn.close()
    context.user_data.clear()

    await update.message.reply_text(
        "✅ <b>Xarajat saqlandi!</b>\n\n"
        f"👤 To‘lagan: <b>{person}</b>\n"
        f"📝 Sabab: <b>{reason}</b>\n"
        f"💴 Summa: <b>¥{amount:.2f}</b>",
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )


async def show_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = db_connect()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, person, reason, amount FROM expenses ORDER BY id ASC"
    )

    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text(
            "📋 Hozircha xarajat yo‘q.",
            reply_markup=main_keyboard()
        )
        return

    text = "📋 <b>BARCHA XARAJATLAR</b>\n\n"
    total = Decimal("0")

    for i, person, reason, amount in rows:
        amount_d = Decimal(str(amount))
        total += amount_d

        text += (
            f"{i}. 👤 <b>{person}</b>\n"
            f"   📝 {reason}\n"
            f"   💴 ¥{amount_d:.2f}\n\n"
        )

    text += f"━━━━━━━━━━━━\n💰 <b>Jami: ¥{total:.2f}</b>"

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )


async def show_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = db_connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT person, COALESCE(SUM(amount), 0)
        FROM expenses
        GROUP BY person
    """)

    rows = cur.fetchall()
    conn.close()

    paid = {
        "Миршод": Decimal("0"),
        "Отабек": Decimal("0"),
        "Ойбек": Decimal("0"),
    }

    for person, amount in rows:
        paid[person] = Decimal(str(amount))

    total = sum(paid.values())
    share = total / Decimal("3")

    text = (
        "📊 <b>SAFAR HISOBOTI</b>\n\n"
        f"💰 Umumiy xarajat: <b>¥{total:.2f}</b>\n"
        f"➗ Har bir kishiga: <b>¥{share:.2f}</b>\n\n"
        "💳 <b>Kim qancha to‘lagan:</b>\n"
    )

    for person in PEOPLE:
        text += f"• {person}: ¥{paid[person]:.2f}\n"

    balances = {}

    for person in PEOPLE:
        balances[person] = paid[person] - share

    text += "\n━━━━━━━━━━━━\n"
    text += "💸 <b>KIM KIMGA BERADI:</b>\n\n"

    creditors = []
    debtors = []

    for person, balance in balances.items():
        if balance > Decimal("0.005"):
            creditors.append([person, balance])
        elif balance < Decimal("-0.005"):
            debtors.append([person, -balance])

    i = 0
    j = 0

    while i < len(debtors) and j < len(creditors):
        debtor = debtors[i]
        creditor = creditors[j]

        amount = min(debtor[1], creditor[1])
        amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        text += (
            f"➡️ <b>{debtor[0]}</b> → "
            f"<b>{creditor[0]}</b>: "
            f"<b>¥{amount:.2f}</b>\n"
        )

        debtor[1] -= amount
        creditor[1] -= amount

        if debtor[1] <= Decimal("0.005"):
            i += 1

        if creditor[1] <= Decimal("0.005"):
            j += 1

    if not debtors and not creditors:
        text += "✅ Hamma hisob-kitob teng!\n"

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "❌ Amal bekor qilindi.",
        reply_markup=main_keyboard()
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    state = context.user_data.get("state")

    if text == "➕ Xarajat qo‘shish":
        await add_expense(update, context)
    elif text == "📋 Xarajatlar":
        await show_expenses(update, context)
    elif text == "📊 Hisobot":
        await show_report(update, context)
    elif text == "❌ Bekor qilish":
        await cancel(update, context)
    elif state == "choose_person":
        await handle_person(update, context)
    elif state == "reason":
        await handle_reason(update, context)
    elif state == "amount":
        await handle_amount(update, context)
    else:
        await update.message.reply_text(
            "Menyudan kerakli bo‘limni tanlang 👇",
            reply_markup=main_keyboard()
        )


def main():
    init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    print("🇨🇳 Kitay safar xarajatlar boti ishga tushdi...")

    app.run_polling()


if __name__ == "__main__":
    main()
