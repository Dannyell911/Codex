from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

from db import DB_PATH, add_transaction, create_category, list_categories

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "deepseek/deepseek-r1-0528:free"


def classify_and_add(text: str, db_path: Path = DB_PATH) -> dict:
    """Use OpenRouter to classify text and record the transaction.

    Returns a dict with keys ``category``, ``amount`` and ``type``.
    """
    categories = [row["name"] for row in list_categories(db_path)]
    prompt = (
        "Определи тип операции (expense или income), сумму и категорию для текста пользователя.\n"
        f"Категории: {', '.join(categories) if categories else 'нет категорий'}.\n"
        "Если подходящей категории нет, предложи новую.\n"
        "Ответь JSON с ключами: type, amount, category."
    )

    headers = {
        "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
        "HTTP-Referer": os.environ.get("OPENROUTER_SITE_URL", "http://localhost"),
        "X-Title": os.environ.get("OPENROUTER_APP", "ExpenseBot"),
    }
    data = {
        "model": MODEL,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "user", "content": prompt + "\n" + text}
        ],
    }
    resp = httpx.post(OPENROUTER_URL, headers=headers, json=data, timeout=30)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    result = json.loads(content)

    category = result["category"]
    amount = float(result["amount"])
    tx_type = result["type"]

    existing = {row["name"]: row["id"] for row in list_categories(db_path)}
    if category not in existing:
        cat_id = create_category(category, db_path)
    else:
        cat_id = existing[category]

    add_transaction(amount, cat_id, tx_type, db_path=db_path)
    return {"category": category, "amount": amount, "type": tx_type}
