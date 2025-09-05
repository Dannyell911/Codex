import asyncio
from unittest.mock import AsyncMock, MagicMock

import asyncio
from unittest.mock import AsyncMock, MagicMock

from telegram_bot import MAIN_KEYBOARD, create_application
import telegram_bot
import db


def test_create_application(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "TOKEN123")
    app = create_application()
    assert app.bot.token == "TOKEN123"


def test_start_shows_keyboard(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "TOKEN123")
    app = create_application()
    start_handler = app.handlers[0][0]

    update = MagicMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    asyncio.run(start_handler.callback(update, context))

    update.message.reply_text.assert_called_once()
    kwargs = update.message.reply_text.call_args.kwargs
    assert kwargs["reply_markup"] is MAIN_KEYBOARD


def test_add_income_flow(monkeypatch, tmp_path):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("TELEGRAM_TOKEN", "TOKEN123")
    monkeypatch.setattr(db, "DB_PATH", db_file)
    monkeypatch.setattr(telegram_bot, "DB_PATH", db_file)
    db.init_db(db_file)
    db.create_category("Salary", db_file)

    app = create_application()
    handler = app.handlers[0][1]

    context = MagicMock()
    context.user_data = {}

    async def call(text: str):
        update = MagicMock()
        update.message = MagicMock()
        update.message.text = text
        update.message.reply_text = AsyncMock()
        await handler.callback(update, context)
        return update.message.reply_text

    # Step 1: choose to add income
    reply = asyncio.run(call("Добавить доход 💰"))
    assert context.user_data["step"] == "category"
    keyboard = reply.call_args.kwargs["reply_markup"].keyboard
    assert keyboard[0][0].text == "Salary"

    # Step 2: select category
    reply = asyncio.run(call("Salary"))
    assert context.user_data["step"] == "amount"

    # Step 3: enter amount
    reply = asyncio.run(call("100"))
    assert context.user_data == {}
    assert reply.call_args.kwargs["reply_markup"] is MAIN_KEYBOARD
    assert db.get_balance(db_file) == 100.0


def test_month_report_flow(monkeypatch, tmp_path):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("TELEGRAM_TOKEN", "TOKEN123")
    monkeypatch.setattr(db, "DB_PATH", db_file)
    monkeypatch.setattr(telegram_bot, "DB_PATH", db_file)
    db.init_db(db_file)
    cat_id = db.create_category("Food", db_file)
    db.add_transaction(50.0, cat_id, "expense", db_path=db_file)

    app = create_application()
    handler = app.handlers[0][1]

    context = MagicMock()
    context.user_data = {}

    async def call(text: str):
        update = MagicMock()
        update.message = MagicMock()
        update.message.text = text
        update.message.reply_text = AsyncMock()
        await handler.callback(update, context)
        return update.message.reply_text

    reply = asyncio.run(call("Отчёт за месяц 📅"))
    assert context.user_data["step"] == "report"
    keyboard = reply.call_args.kwargs["reply_markup"].keyboard
    month = keyboard[0][0].text

    reply = asyncio.run(call(month))
    assert context.user_data == {}
    assert reply.call_args.kwargs["reply_markup"] is MAIN_KEYBOARD
    assert "50.00" in reply.call_args.args[0]


def test_voice_message_transcribed(monkeypatch, tmp_path):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("TELEGRAM_TOKEN", "TOKEN123")
    monkeypatch.setattr(db, "DB_PATH", db_file)
    monkeypatch.setattr(telegram_bot, "DB_PATH", db_file)
    db.init_db(db_file)

    # patch transcription and classification
    fake_text = "потратил 20 на еду"
    transcribe = AsyncMock(return_value=fake_text)
    monkeypatch.setattr(telegram_bot, "transcribe", transcribe)
    classify = MagicMock(return_value={"category": "Food", "amount": 20.0, "type": "expense"})
    monkeypatch.setattr(telegram_bot, "classify_and_add", classify)

    app = create_application()
    voice_handler = app.handlers[0][2]

    context = MagicMock()
    context.user_data = {}

    update = MagicMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    voice = MagicMock()
    update.message.voice = voice
    file = MagicMock()
    voice.get_file = AsyncMock(return_value=file)

    async def fake_download(path):
        from pathlib import Path
        Path(path).write_bytes(b"data")

    file.download_to_drive = AsyncMock(side_effect=fake_download)

    asyncio.run(voice_handler.callback(update, context))

    transcribe.assert_called_once()
    classify.assert_called_once_with(fake_text, db_file)
    update.message.reply_text.assert_called_once()
    assert "Food" in update.message.reply_text.call_args.args[0]


def test_category_management_flow(monkeypatch, tmp_path):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("TELEGRAM_TOKEN", "TOKEN123")
    monkeypatch.setattr(db, "DB_PATH", db_file)
    monkeypatch.setattr(telegram_bot, "DB_PATH", db_file)
    db.init_db(db_file)

    app = create_application()
    handler = app.handlers[0][1]

    context = MagicMock()
    context.user_data = {}

    async def call(text: str):
        update = MagicMock()
        update.message = MagicMock()
        update.message.text = text
        update.message.reply_text = AsyncMock()
        await handler.callback(update, context)
        return update.message.reply_text

    # Create category
    asyncio.run(call("Создать категорию ➕"))
    assert context.user_data["step"] == "new_category"
    asyncio.run(call("Food"))
    assert context.user_data == {}
    assert db.list_categories(db_file)[0]["name"] == "Food"

    # Rename category
    asyncio.run(call("Переименовать категорию ✏️"))
    assert context.user_data["step"] == "rename_select"
    asyncio.run(call("Food"))
    assert context.user_data["step"] == "rename_name"
    asyncio.run(call("Groceries"))
    assert context.user_data == {}
    assert db.list_categories(db_file)[0]["name"] == "Groceries"

    # Delete category
    asyncio.run(call("Удалить категорию 🗑️"))
    assert context.user_data["step"] == "delete_select"
    asyncio.run(call("Groceries"))
    assert context.user_data == {}
    assert db.list_categories(db_file) == []
