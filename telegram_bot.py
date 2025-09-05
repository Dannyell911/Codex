import os
import tempfile
from datetime import datetime
from typing import Optional

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot import Bot
from db import (
    DB_PATH,
    add_transaction,
    create_category,
    delete_category,
    get_balance,
    get_transactions_for_month,
    init_db,
    list_categories,
    update_category,
)
from llm import classify_and_add
from speech import transcribe


MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["Добавить доход 💰", "Добавить расход 💸"],
        ["Показать баланс 📊", "Отчёт за месяц 📅"],
        ["Создать категорию ➕", "Переименовать категорию ✏️"],
        ["Удалить категорию 🗑️", "Помощь ❓"],
    ],
    resize_keyboard=True,
)


def create_application(token: Optional[str] = None) -> Application:
    """Create a Telegram application using the provided token or `TELEGRAM_TOKEN` env var."""
    if token is None:
        token = os.environ["TELEGRAM_TOKEN"]
    init_db(DB_PATH)
    application = ApplicationBuilder().token(token).build()
    convo = Bot()

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "Привет! Выбери действие 😊",
            reply_markup=MAIN_KEYBOARD,
        )

    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = update.message.text

        if context.user_data.get("step") == "category":
            categories = {row["name"]: row["id"] for row in list_categories(DB_PATH)}
            cat_id = categories.get(text)
            if cat_id is None:
                keyboard = ReplyKeyboardMarkup([[name] for name in categories], resize_keyboard=True)
                await update.message.reply_text(
                    "Выбери категорию из списка 🗂", reply_markup=keyboard
                )
                return
            context.user_data["category_id"] = cat_id
            context.user_data["step"] = "amount"
            await update.message.reply_text("Сколько? 💵")
            return

        if context.user_data.get("step") == "amount":
            try:
                amount = float(text.replace(",", "."))
            except ValueError:
                await update.message.reply_text("Нужна цифра, попробуй ещё раз 🙂")
                return
            add_transaction(
                amount,
                context.user_data["category_id"],
                context.user_data["type"],
                db_path=DB_PATH,
            )
            context.user_data.clear()
            balance = get_balance(DB_PATH)
            await update.message.reply_text(
                f"Готово! Баланс: {balance:.2f} ₽", reply_markup=MAIN_KEYBOARD
            )
            return

        if context.user_data.get("step") == "report":
            try:
                year, month = map(int, text.split("-"))
            except ValueError:
                await update.message.reply_text(
                    "Выбери месяц из списка 🙏",
                )
                return
            rows = get_transactions_for_month(year, month, DB_PATH)
            if not rows:
                msg = "Транзакций нет 📭"
            else:
                lines = []
                total = 0.0
                for r in rows:
                    sign = -r["amount"] if r["type"] == "expense" else r["amount"]
                    total += sign
                    lines.append(
                        f"{r['timestamp'][:10]} {r['category']}: {sign:+.2f} ₽"
                    )
                lines.append(f"Итог: {total:+.2f} ₽")
                msg = "\n".join(lines)
            context.user_data.clear()
            await update.message.reply_text(msg, reply_markup=MAIN_KEYBOARD)
            return

        if context.user_data.get("step") == "new_category":
            create_category(text, DB_PATH)
            context.user_data.clear()
            await update.message.reply_text(
                f"Категория '{text}' добавлена ✅", reply_markup=MAIN_KEYBOARD
            )
            return

        if context.user_data.get("step") == "rename_select":
            categories = {row["name"]: row["id"] for row in list_categories(DB_PATH)}
            cat_id = categories.get(text)
            if cat_id is None:
                keyboard = ReplyKeyboardMarkup([[name] for name in categories], resize_keyboard=True)
                await update.message.reply_text(
                    "Выбери категорию из списка 🗂", reply_markup=keyboard
                )
                return
            context.user_data["cat_id"] = cat_id
            context.user_data["step"] = "rename_name"
            await update.message.reply_text("Новое имя? ✏️")
            return

        if context.user_data.get("step") == "rename_name":
            update_category(context.user_data["cat_id"], text, DB_PATH)
            context.user_data.clear()
            await update.message.reply_text(
                "Категория обновлена ✅", reply_markup=MAIN_KEYBOARD
            )
            return

        if context.user_data.get("step") == "delete_select":
            categories = {row["name"]: row["id"] for row in list_categories(DB_PATH)}
            cat_id = categories.get(text)
            if cat_id is None:
                keyboard = ReplyKeyboardMarkup([[name] for name in categories], resize_keyboard=True)
                await update.message.reply_text(
                    "Выбери категорию из списка 🗂", reply_markup=keyboard
                )
                return
            delete_category(cat_id, DB_PATH)
            context.user_data.clear()
            await update.message.reply_text(
                "Категория удалена 🗑️", reply_markup=MAIN_KEYBOARD
            )
            return

        if text == "Добавить доход 💰":
            context.user_data["type"] = "income"
            context.user_data["step"] = "category"
            categories = list_categories(DB_PATH)
            if not categories:
                create_category("Общее", DB_PATH)
                categories = list_categories(DB_PATH)
            keyboard = ReplyKeyboardMarkup([[c["name"]] for c in categories], resize_keyboard=True)
            await update.message.reply_text(
                "Выбери категорию дохода 💰", reply_markup=keyboard
            )
            return

        if text == "Добавить расход 💸":
            context.user_data["type"] = "expense"
            context.user_data["step"] = "category"
            categories = list_categories(DB_PATH)
            if not categories:
                create_category("Общее", DB_PATH)
                categories = list_categories(DB_PATH)
            keyboard = ReplyKeyboardMarkup([[c["name"]] for c in categories], resize_keyboard=True)
            await update.message.reply_text(
                "Выбери категорию расхода 💸", reply_markup=keyboard
            )
            return

        if text == "Показать баланс 📊":
            balance = get_balance(DB_PATH)
            await update.message.reply_text(
                f"Сейчас: {balance:.2f} ₽", reply_markup=MAIN_KEYBOARD
            )
            return

        if text == "Отчёт за месяц 📅":
            context.user_data["step"] = "report"
            now = datetime.utcnow()
            options = []
            for i in range(6):
                m = now.month - i
                y = now.year
                while m <= 0:
                    m += 12
                    y -= 1
                options.append(f"{y}-{m:02d}")
            keyboard = ReplyKeyboardMarkup([[o] for o in options], resize_keyboard=True)
            await update.message.reply_text(
                "Выбери месяц 🗓", reply_markup=keyboard
            )
            return

        if text == "Создать категорию ➕":
            context.user_data["step"] = "new_category"
            await update.message.reply_text("Название категории? 📝")
            return

        if text == "Переименовать категорию ✏️":
            categories = list_categories(DB_PATH)
            if not categories:
                await update.message.reply_text(
                    "Категорий нет 👀", reply_markup=MAIN_KEYBOARD
                )
                return
            context.user_data["step"] = "rename_select"
            keyboard = ReplyKeyboardMarkup(
                [[c["name"]] for c in categories], resize_keyboard=True
            )
            await update.message.reply_text(
                "Что переименовать? 🗂", reply_markup=keyboard
            )
            return

        if text == "Удалить категорию 🗑️":
            categories = list_categories(DB_PATH)
            if not categories:
                await update.message.reply_text(
                    "Категорий нет 👀", reply_markup=MAIN_KEYBOARD
                )
                return
            context.user_data["step"] = "delete_select"
            keyboard = ReplyKeyboardMarkup(
                [[c["name"]] for c in categories], resize_keyboard=True
            )
            await update.message.reply_text(
                "Что удалить? 🗂", reply_markup=keyboard
            )
            return

        if text == "Помощь ❓":
            await update.message.reply_text(
                "Нажми нужную кнопку: доход, расход или баланс. 🤝"
            )
            return
        try:
            result = classify_and_add(text, DB_PATH)
        except Exception:
            response = convo.respond(text)
            await update.message.reply_text(response)
        else:
            await update.message.reply_text(
                f"{result['amount']:.2f} ₽ в категории {result['category']} записано ✅",
                reply_markup=MAIN_KEYBOARD,
            )

    async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Transcribe voice message and process like free text."""
        voice = update.message.voice
        file = await voice.get_file()
        with tempfile.NamedTemporaryFile(suffix=".ogg") as tmp:
            await file.download_to_drive(tmp.name)
            text = await transcribe(tmp.name)
        try:
            result = classify_and_add(text, DB_PATH)
        except Exception:
            response = convo.respond(text)
            await update.message.reply_text(response)
        else:
            await update.message.reply_text(
                f"{result['amount']:.2f} ₽ в категории {result['category']} записано ✅",
                reply_markup=MAIN_KEYBOARD,
            )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    return application


def main() -> None:
    app = create_application()
    app.run_polling()


if __name__ == "__main__":
    main()
