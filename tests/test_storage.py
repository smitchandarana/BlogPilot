import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from backend.utils.config_loader import load_config
from backend.storage.database import init_db, get_db
from backend.storage import post_state, engagement_log, budget_tracker, leads_store


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    # Redirect DB to a temp file for each test
    import backend.storage.database as db_module
    db_module._DB_PATH = str(tmp_path / "test.db")
    db_module._engine = None
    db_module.SessionLocal = None
    load_config()
    init_db()
    yield
    db_module._engine = None
    db_module.SessionLocal = None


def test_init_db():
    with get_db() as db:
        from backend.storage.models import Budget
        budgets = db.query(Budget).all()
        assert len(budgets) > 0


def test_create_and_find_post():
    with get_db() as db:
        url = "https://linkedin.com/posts/test-1234"
        assert not post_state.is_seen(url, db)
        post = post_state.mark_seen(url, db, author_name="Alice")
        assert post.id is not None
        assert post_state.is_seen(url, db)


def test_mark_seen_idempotent():
    with get_db() as db:
        url = "https://linkedin.com/posts/idempotent"
        p1 = post_state.mark_seen(url, db)
        p2 = post_state.mark_seen(url, db)
        assert p1.id == p2.id


def test_update_post_state():
    with get_db() as db:
        url = "https://linkedin.com/posts/state-test"
        post_state.mark_seen(url, db)
        updated = post_state.update_state(url, "ACTED", db, action_taken="LIKE")
        assert updated.state == "ACTED"
        assert updated.action_taken == "LIKE"


def test_budget_check_and_increment():
    with get_db() as db:
        assert budget_tracker.check("likes", db)
        for _ in range(30):
            budget_tracker.increment("likes", db)
        assert not budget_tracker.check("likes", db)


def test_budget_reset():
    with get_db() as db:
        for _ in range(30):
            budget_tracker.increment("likes", db)
        assert not budget_tracker.check("likes", db)
        budget_tracker.reset_all(db)
        assert budget_tracker.check("likes", db)


def test_create_lead():
    with get_db() as db:
        lead = leads_store.create_lead(
            {
                "linkedin_url": "https://linkedin.com/in/john-smith",
                "first_name": "John",
                "last_name": "Smith",
                "company": "Acme Corp",
            },
            db,
        )
        assert lead.id is not None
        assert lead.first_name == "John"


def test_create_lead_upsert():
    with get_db() as db:
        url = "https://linkedin.com/in/upsert-test"
        l1 = leads_store.create_lead({"linkedin_url": url, "company": "OldCo"}, db)
        l2 = leads_store.create_lead({"linkedin_url": url, "company": "NewCo"}, db)
        assert l1.id == l2.id
        assert l2.company == "NewCo"
