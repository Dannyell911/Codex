from datetime import datetime, timedelta
from pathlib import Path

from db import (
    add_transaction,
    create_category,
    delete_category,
    get_transactions_for_month,
    init_db,
    list_categories,
    update_category,
    get_balance,
)


def test_category_crud(tmp_path):
    db_file = tmp_path / "test.db"
    init_db(db_file)

    cat_id = create_category("Food", db_file)
    categories = list_categories(db_file)
    assert len(categories) == 1 and categories[0]["name"] == "Food"

    update_category(cat_id, "Groceries", db_file)
    categories = list_categories(db_file)
    assert categories[0]["name"] == "Groceries"

    delete_category(cat_id, db_file)
    assert list_categories(db_file) == []


def test_transactions_and_purge(tmp_path):
    db_file = tmp_path / "test.db"
    init_db(db_file)

    cat_id = create_category("Bills", db_file)

    old_date = datetime.utcnow() - timedelta(days=200)
    add_transaction(100.0, cat_id, "expense", timestamp=old_date, db_path=db_file)

    add_transaction(50.0, cat_id, "expense", db_path=db_file)

    now = datetime.utcnow()
    rows = get_transactions_for_month(now.year, now.month, db_file)
    assert len(rows) == 1 and rows[0]["amount"] == 50.0 and rows[0]["category"] == "Bills"

    # ensure purge removed old transaction
    rows = get_transactions_for_month(old_date.year, old_date.month, db_file)
    assert rows == []


def test_get_balance(tmp_path):
    db_file = tmp_path / "test.db"
    init_db(db_file)
    cat_id = create_category("Salary", db_file)
    add_transaction(100.0, cat_id, "income", db_path=db_file)
    add_transaction(40.0, cat_id, "expense", db_path=db_file)
    assert get_balance(db_file) == 60.0
