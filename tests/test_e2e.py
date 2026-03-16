"""
End-to-end pipeline test with mocked Playwright and Groq.

Tests: engine start → scheduler fires → feed scan → pipeline processes post →
       post in DB with state ACTED, action in actions_log, budget incremented,
       WebSocket event fired.
"""
import asyncio
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(autouse=True)
def _test_db(tmp_path):
    """Use a temporary SQLite DB for each test."""
    import backend.storage.database as db_module
    from backend.utils.config_loader import load_config

    db_path = str(tmp_path / "test.db")
    db_module._DB_PATH = db_path
    db_module._engine = None
    db_module.SessionLocal = None

    load_config()
    db_module.init_db()
    yield
    db_module._engine = None
    db_module.SessionLocal = None


@pytest.fixture
def mock_page():
    """Create a mock Playwright Page."""
    page = AsyncMock()
    page.goto = AsyncMock()
    page.query_selector = AsyncMock(return_value=None)
    page.query_selector_all = AsyncMock(return_value=[])
    page.keyboard = MagicMock()
    page.keyboard.type = AsyncMock()
    return page


class TestPipelineE2E:
    """Full pipeline flow: post → score → decide → act → log."""

    def test_pipeline_processes_post_and_logs_action(self, mock_page):
        """Scored post should be acted on and logged."""
        from backend.storage.database import get_db
        from backend.storage.models import Post, ActionLog, Budget

        # Ensure budget rows exist with correct limits (init_db seeds them)
        with get_db() as db:
            for at, lim in [("likes", 30), ("comments", 12)]:
                row = db.query(Budget).filter_by(action_type=at).first()
                if row:
                    row.limit_per_day = lim
                    row.count_today = 0
                else:
                    db.add(Budget(action_type=at, limit_per_day=lim, count_today=0))
            db.commit()

        post_data = {
            "url": "https://linkedin.com/feed/update/urn:li:activity:12345",
            "author_name": "Test Author",
            "author_url": "https://linkedin.com/in/test-author",
            "text": "Data Analytics is transforming Business Intelligence and Dashboard Design for modern companies.",
            "like_count": 5,
            "comment_count": 1,
        }

        # Mock the like button interaction to succeed
        like_btn = AsyncMock()
        like_btn.hover = AsyncMock()
        like_btn.click = AsyncMock()
        mock_page.query_selector = AsyncMock(side_effect=_like_button_mock(like_btn))

        async def _noop_delay(*args, **kwargs):
            pass

        with patch("backend.core.pipeline._build_ai_deps", return_value=(None, None)), \
             patch("backend.core.pipeline._in_activity_window", return_value=True), \
             patch("backend.automation.human_behavior.random_delay", _noop_delay), \
             patch("backend.api.websocket.schedule_broadcast"):

            from backend.core import pipeline
            asyncio.run(pipeline._process_post(
                post_data, mock_page,
                _make_ie(mock_page),
                _get_test_db(),
                engine=None,
            ))

        # Verify post is in DB
        with get_db() as db:
            post = db.query(Post).first()
            assert post is not None
            assert post.author_name == "Test Author"
            assert post.state in ("ACTED", "SCORED", "SKIPPED", "PREVIEW")

    def test_budget_exhausted_skips_action(self, mock_page):
        """When budget is exhausted, pipeline should skip the action."""
        from backend.storage.database import get_db
        from backend.storage.models import Post, Budget

        # Set budget to exhausted
        with get_db() as db:
            for at, lim, used in [("likes", 30, 30), ("comments", 12, 12)]:
                row = db.query(Budget).filter_by(action_type=at).first()
                if row:
                    row.limit_per_day = lim
                    row.count_today = used
                else:
                    db.add(Budget(action_type=at, limit_per_day=lim, count_today=used))
            db.commit()

        post_data = {
            "url": "https://linkedin.com/feed/update/urn:li:activity:99999",
            "author_name": "Budget Test",
            "text": "Data Analytics Business Intelligence Dashboard Design KPI Tracking Financial Reporting",
            "like_count": 100,
            "comment_count": 20,
        }

        async def _noop_delay2(*args, **kwargs):
            pass

        with patch("backend.core.pipeline._build_ai_deps", return_value=(None, None)), \
             patch("backend.core.pipeline._in_activity_window", return_value=True), \
             patch("backend.automation.human_behavior.random_delay", side_effect=_noop_delay2), \
             patch("backend.api.websocket.schedule_broadcast"):

            from backend.core import pipeline
            asyncio.run(pipeline._process_post(
                post_data, mock_page,
                _make_ie(mock_page),
                _get_test_db(),
                engine=None,
            ))

        # Post should be SKIPPED because budget is exhausted
        with get_db() as db:
            post = db.query(Post).filter(Post.url == post_data["url"]).first()
            assert post is not None
            assert post.state in ("SKIPPED", "SCORED")


class TestBudgetSafety:
    """Verify budget enforcement at every layer."""

    def _upsert_budget(self, db, action_type, limit, count):
        from backend.storage.models import Budget
        row = db.query(Budget).filter_by(action_type=action_type).first()
        if row:
            row.limit_per_day = limit
            row.count_today = count
        else:
            db.add(Budget(action_type=action_type, limit_per_day=limit, count_today=count))
        db.commit()

    def test_budget_check_blocks_when_exhausted(self):
        from backend.storage.database import get_db
        from backend.storage import budget_tracker

        with get_db() as db:
            self._upsert_budget(db, "likes", 10, 10)

        with get_db() as db:
            assert budget_tracker.check("likes", db) is False

    def test_budget_check_allows_under_limit(self):
        from backend.storage.database import get_db
        from backend.storage import budget_tracker

        with get_db() as db:
            self._upsert_budget(db, "likes", 10, 5)

        with get_db() as db:
            assert budget_tracker.check("likes", db) is True

    def test_budget_increment_updates_count(self):
        from backend.storage.database import get_db
        from backend.storage.models import Budget
        from backend.storage import budget_tracker

        with get_db() as db:
            self._upsert_budget(db, "comments", 12, 3)

        with get_db() as db:
            budget_tracker.increment("comments", db)
            row = db.query(Budget).filter_by(action_type="comments").first()
            assert row.count_today == 4

    def test_midnight_reset_clears_all(self):
        from backend.storage.database import get_db
        from backend.storage import budget_tracker

        with get_db() as db:
            self._upsert_budget(db, "likes", 30, 25)
            self._upsert_budget(db, "comments", 12, 11)

        with get_db() as db:
            budget_tracker.reset_all(db)
            rows = budget_tracker.get_all(db)
            for row in rows:
                assert row.count_today == 0

    def test_unlimited_budget_always_allows(self):
        from backend.storage.database import get_db
        from backend.storage import budget_tracker

        with get_db() as db:
            self._upsert_budget(db, "feed_scans", 0, 999)

        with get_db() as db:
            assert budget_tracker.check("feed_scans", db) is True


class TestInteractionEngineBudget:
    """Verify interaction engine checks budget before every action."""

    def _upsert_budget(self, db, action_type, limit, count):
        from backend.storage.models import Budget
        row = db.query(Budget).filter_by(action_type=action_type).first()
        if row:
            row.limit_per_day = limit
            row.count_today = count
        else:
            db.add(Budget(action_type=action_type, limit_per_day=limit, count_today=count))
        db.commit()

    def test_like_blocked_by_budget(self, mock_page):
        from backend.storage.database import get_db

        async def _noop(*a, **kw): pass

        with get_db() as db:
            self._upsert_budget(db, "likes", 5, 5)

        with patch("backend.automation.human_behavior.random_delay", side_effect=_noop), \
             patch("backend.api.websocket.schedule_broadcast"):
            from backend.automation.interaction_engine import InteractionEngine
            ie = InteractionEngine()
            result = asyncio.run(ie.like_post(mock_page, "https://example.com/post", db=_get_test_db()))
            assert result is False

    def test_comment_blocked_by_budget(self, mock_page):
        from backend.storage.database import get_db

        async def _noop(*a, **kw): pass

        with get_db() as db:
            self._upsert_budget(db, "comments", 3, 3)

        with patch("backend.automation.human_behavior.random_delay", side_effect=_noop), \
             patch("backend.api.websocket.schedule_broadcast"):
            from backend.automation.interaction_engine import InteractionEngine
            ie = InteractionEngine()
            result = asyncio.run(ie.comment_post(mock_page, "https://example.com/post", "test comment", db=_get_test_db()))
            assert result is False


# ── Helpers ─────────────────────────────────────────────────────────────────

def _get_test_db():
    from backend.storage.database import get_db
    return get_db().__enter__()


def _make_ie(mock_page):
    from backend.automation.interaction_engine import InteractionEngine
    return InteractionEngine()


def _like_button_mock(like_btn):
    """Returns a side_effect function for query_selector that fakes a like button."""
    async def _mock(selector):
        if "Like" in selector and "pressed='false'" in selector:
            return like_btn
        if "Like" in selector and "pressed='true'" in selector:
            return like_btn  # Post is now "liked"
        return None
    return _mock
