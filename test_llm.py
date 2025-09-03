import json

import llm
import db


def test_classify_and_add_creates_category(monkeypatch, tmp_path):
    db_file = tmp_path / "test.db"
    db.init_db(db_file)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    def fake_post(url, headers=None, json=None, timeout=None):
        assert url == llm.OPENROUTER_URL
        class Resp:
            def json(self):
                return {
                    "choices": [
                        {"message": {"content": '{"category": "Еда", "type": "expense", "amount": 100}'}}
                    ]
                }
            def raise_for_status(self):
                pass
        return Resp()

    monkeypatch.setattr(llm.httpx, "post", fake_post)

    result = llm.classify_and_add("купил обед на 100", db_file)
    assert result == {"category": "Еда", "amount": 100.0, "type": "expense"}
    cats = db.list_categories(db_file)
    assert cats[0]["name"] == "Еда"
    assert db.get_balance(db_file) == -100.0
