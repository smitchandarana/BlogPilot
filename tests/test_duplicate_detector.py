"""Tests for duplicate post detection."""
import pytest
from unittest.mock import MagicMock

from backend.research.duplicate_detector import (
    normalize_text,
    compute_hash,
    check_duplicate,
    register_post,
)
from backend.storage.models import PostContentHash, ScheduledPost


class TestNormalizeText:
    def test_lowercase(self):
        assert normalize_text("HELLO WORLD") == "hello world"

    def test_strip_hashtags(self):
        result = normalize_text("Check this out #analytics #data")
        assert "#" not in result
        assert "analytics" not in result

    def test_strip_urls(self):
        result = normalize_text("Visit https://example.com for more")
        assert "https" not in result
        assert "example" not in result

    def test_collapse_whitespace(self):
        result = normalize_text("too   much    space\n\nnewlines")
        assert "  " not in result

    def test_strip_punctuation(self):
        result = normalize_text("Hello, world! How's it going?")
        assert "," not in result
        assert "!" not in result
        # Apostrophes in contractions are kept
        assert "how's" in result

    def test_empty_string(self):
        assert normalize_text("") == ""
        assert normalize_text(None) == ""

    def test_emoji_removal(self):
        result = normalize_text("Great post! 🎉🔥 Love it")
        assert "🎉" not in result
        assert "🔥" not in result


class TestComputeHash:
    def test_same_content_same_hash(self):
        h1 = compute_hash("Hello world")
        h2 = compute_hash("Hello world")
        assert h1 == h2

    def test_different_content_different_hash(self):
        h1 = compute_hash("Hello world")
        h2 = compute_hash("Goodbye world")
        assert h1 != h2

    def test_case_insensitive(self):
        h1 = compute_hash("HELLO WORLD")
        h2 = compute_hash("hello world")
        assert h1 == h2

    def test_hashtag_insensitive(self):
        h1 = compute_hash("Great insight on data analytics")
        h2 = compute_hash("Great insight on data analytics #analytics #data")
        assert h1 == h2


class TestCheckDuplicate:
    def _mock_db(self, hash_records=None, scheduled_records=None):
        db = MagicMock()

        # Mock hash query
        hash_query = MagicMock()
        hash_query.filter_by.return_value.first.return_value = (
            hash_records[0] if hash_records else None
        )

        # Mock scheduled posts query
        scheduled_query = MagicMock()
        scheduled_query.filter.return_value.all.return_value = scheduled_records or []

        def query_side_effect(model):
            if model == PostContentHash:
                return hash_query
            if model == ScheduledPost:
                return scheduled_query
            return MagicMock()

        db.query.side_effect = query_side_effect
        return db

    def test_no_duplicate(self):
        db = self._mock_db()
        result = check_duplicate("Completely unique content here", db)
        assert result["is_duplicate"] is False
        assert result["similarity"] == 0.0

    def test_exact_hash_match(self):
        record = MagicMock()
        record.post_id = "abc123"
        record.text_preview = "Previously published post..."

        db = self._mock_db(hash_records=[record])
        result = check_duplicate("Some duplicate text", db)
        assert result["is_duplicate"] is True
        assert result["similarity"] == 1.0
        assert result["matching_preview"] == "Previously published post..."


class TestRegisterPost:
    def test_register_new_post(self):
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None

        register_post("Test post content", "post-123", db)

        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_skip_already_registered(self):
        db = MagicMock()
        existing = MagicMock()
        existing.post_id = "old-post"
        db.query.return_value.filter_by.return_value.first.return_value = existing

        register_post("Same content", "new-post", db)

        db.add.assert_not_called()
