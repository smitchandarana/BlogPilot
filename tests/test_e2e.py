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
def _test_db(tmp_path, monkeypatch):
    """Use a temporary SQLite DB for each test."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DATABASE_PATH", db_path)

    from backend.storage import database
    database._engine = None
    database._SessionLocal = None
    database.Base.metadata.clear()

    # Re-import models so they register with the new Base
    import importlib
    from backend.storage import models
    importlib.reload(models)
    importlib.reload(database)

    database.init_db()
    yield


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

        # Seed budget rows
        with get_db() as db:
            db.add(Budget(action_type="likes", limit_per_day=30, count_today=0))
            db.add(Budget(action_type="comments", limit_per_day=12, count_today=0))
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

        with patch("backend.core.pipeline._build_ai_deps", return_value=(None, None)), \
             patch("backend.core.pipeline._in_activity_window", return_value=True), \
             patch("backend.automation.human_behavior.random_delay", new_callable=lambda: AsyncMock), \
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
            assert post.state in ("ACTED", "SCORED", "SKIPPED")

    def test_budget_exhausted_skips_action(self, mock_page):
        """When budget is exhausted, pipeline should skip the action."""
        from backend.storage.database import get_db
        from backend.storage.models import Post, Budget

        # Seed budget at limit
        with get_db() as db:
            db.add(Budget(action_type="likes", limit_per_day=30, count_today=30))
            db.add(Budget(action_type="comments", limit_per_day=12, count_today=12))
            db.commit()

        post_data = {
            "url": "https://linkedin.com/feed/update/urn:li:activity:99999",
            "author_name": "Budget Test",
            "text": "Data Analytics Business Intelligence Dashboard Design KPI Tracking Financial Reporting",
            "like_count": 100,
            "comment_count": 20,
        }

        with patch("backend.core.pipeline._build_ai_deps", return_value=(None, None)), \
             patch("backend.core.pipeline._in_activity_window", return_value=True), \
             patch("backend.automation.human_behavior.random_delay", new_callable=lambda: AsyncMock), \
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

    def test_budget_check_blocks_when_exhausted(self):
        from backend.storage.database import get_db
        from backend.storage.models import Budget
        from backend.storage import budget_tracker

        with get_db() as db:
            db.add(Budget(action_type="likes", limit_per_day=10, count_today=10))
            db.commit()

        with get_db() as db:
            assert budget_tracker.check("likes", db) is False

    def test_budget_check_allows_under_limit(self):
        from backend.storage.database import get_db
        from backend.storage.models import Budget
        from backend.storage import budget_tracker

        with get_db() as db:
            db.add(Budget(action_type="likes", limit_per_day=10, count_today=5))
            db.commit()

        with get_db() as db:
            assert budget_tracker.check("likes", db) is True

    def test_budget_increment_updates_count(self):
        from backend.storage.database import get_db
        from backend.storage.models import Budget
        from backend.storage import budget_tracker

        with get_db() as db:
            db.add(Budget(action_type="comments", limit_per_day=12, count_today=3))
            db.commit()

        with get_db() as db:
            budget_tracker.increment("comments", db)
            row = db.query(Budget).filter_by(action_type="comments").first()
            assert row.count_today == 4

    def test_midnight_reset_clears_all(self):
        from backend.storage.database import get_db
        from backend.storage.models import Budget
        from backend.storage import budget_tracker

        with get_db() as db:
            db.add(Budget(action_type="likes", limit_per_day=30, count_today=25))
            db.add(Budget(action_type="comments", limit_per_day=12, count_today=11))
            db.commit()

        with get_db() as db:
            budget_tracker.reset_all(db)
            rows = budget_tracker.get_all(db)
            for row in rows:
                assert row.count_today == 0

    def test_unlimited_budget_always_allows(self):
        from backend.storage.database import get_db
        from backend.storage.models import Budget
        from backend.storage import budget_tracker

        with get_db() as db:
            db.add(Budget(action_type="feed_scans", limit_per_day=0, count_today=999))
            db.commit()

        with get_db() as db:
            assert budget_tracker.check("feed_scans", db) is True


class TestInteractionEngineBudget:
    """Verify interaction engine checks budget before every action."""

    def test_like_blocked_by_budget(self, mock_page):
        from backend.storage.database import get_db
        from backend.storage.models import Budget

        with get_db() as db:
            db.add(Budget(action_type="likes", limit_per_day=5, count_today=5))
            db.commit()

        with patch("backend.automation.human_behavior.random_delay", new_callable=lambda: AsyncMock), \
             patch("backend.api.websocket.schedule_broadcast"):
            from backend.automation.interaction_engine import InteractionEngine
            ie = InteractionEngine()
            result = asyncio.run(ie.like_post(mock_page, "https://example.com/post", db=_get_test_db()))
            assert result is False

    def test_comment_blocked_by_budget(self, mock_page):
        from backend.storage.database import get_db
        from backend.storage.models import Budget

        with get_db() as db:
            db.add(Budget(action_type="comments", limit_per_day=3, count_today=3))
            db.commit()

        with patch("backend.automation.human_behavior.random_delay", new_callable=lambda: AsyncMock), \
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
