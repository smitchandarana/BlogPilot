"""
Tests for backend/automation/feed_scanner.py

Uses mock Playwright page objects so no real browser is required.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Mock page helpers ──────────────────────────────────────────────────────

def make_mock_element(inner_text: str = "", attribute: str = "") -> AsyncMock:
    """Return a mock Playwright element."""
    el = AsyncMock()
    el.inner_text = AsyncMock(return_value=inner_text)
    el.get_attribute = AsyncMock(return_value=attribute)
    el.scroll_into_view_if_needed = AsyncMock()
    return el


def make_mock_page(
    url: str = "https://www.linkedin.com/feed/",
    post_elements: list = None,
) -> AsyncMock:
    """Return a minimal mock Playwright page."""
    page = AsyncMock()
    page.url = url
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.wait_for_timeout = AsyncMock()

    post_elements = post_elements or []
    page.query_selector_all = AsyncMock(return_value=post_elements)
    page.query_selector = AsyncMock(return_value=None)
    return page


# ── Helper function tests ──────────────────────────────────────────────────

def test_clean_text_strips_whitespace():
    from backend.automation.feed_scanner import _clean
    assert _clean("  hello   world  ") == "hello world"
    assert _clean("") == ""
    assert _clean("  \n  ") == ""


def test_parse_count_basic():
    from backend.automation.feed_scanner import _parse_count
    assert _parse_count("42") == 42
    assert _parse_count("1,234") == 1234
    assert _parse_count("1.2K") == 1200
    assert _parse_count("2.5k") == 2500
    assert _parse_count("1M") == 1_000_000
    assert _parse_count("") == 0
    assert _parse_count("abc") == 0


def test_normalise_url_relative():
    from backend.automation.feed_scanner import _normalise_url
    assert _normalise_url("/in/john-doe") == "https://www.linkedin.com/in/john-doe"


def test_normalise_url_absolute_strips_query():
    from backend.automation.feed_scanner import _normalise_url
    assert _normalise_url(
        "https://www.linkedin.com/feed/update/urn:li:activity:123/?trackingId=abc"
    ) == "https://www.linkedin.com/feed/update/urn:li:activity:123/"


def test_normalise_url_empty():
    from backend.automation.feed_scanner import _normalise_url
    assert _normalise_url("") == ""


# ── FeedScanner unit tests ─────────────────────────────────────────────────

class TestFeedScanner:

    @pytest.mark.asyncio
    async def test_scan_returns_empty_when_no_posts(self):
        from backend.automation.feed_scanner import FeedScanner
        page = make_mock_page()
        # query_selector_all returns empty list → no posts
        page.query_selector_all = AsyncMock(return_value=[])

        scanner = FeedScanner()
        with patch("backend.automation.feed_scanner.scroll_down", AsyncMock()):
            with patch("backend.automation.feed_scanner.random_delay", AsyncMock()):
                result = await scanner.scan(page, db=None)

        assert result == []

    @pytest.mark.asyncio
    async def test_scan_navigates_to_feed_if_not_there(self):
        from backend.automation.feed_scanner import FeedScanner
        page = make_mock_page(url="https://www.linkedin.com/in/someone/")
        page.query_selector_all = AsyncMock(return_value=[])

        scanner = FeedScanner()
        with patch("backend.automation.feed_scanner.scroll_down", AsyncMock()):
            with patch("backend.automation.feed_scanner.random_delay", AsyncMock()):
                await scanner.scan(page, db=None)

        page.goto.assert_called_once()
        call_url = page.goto.call_args[0][0]
        assert "linkedin.com/feed" in call_url

    @pytest.mark.asyncio
    async def test_scan_does_not_navigate_if_already_on_feed(self):
        from backend.automation.feed_scanner import FeedScanner
        page = make_mock_page(url="https://www.linkedin.com/feed/")
        page.query_selector_all = AsyncMock(return_value=[])

        scanner = FeedScanner()
        with patch("backend.automation.feed_scanner.scroll_down", AsyncMock()):
            await scanner.scan(page, db=None)

        page.goto.assert_not_called()

    @pytest.mark.asyncio
    async def test_filter_seen_removes_known_posts(self):
        from backend.automation.feed_scanner import FeedScanner

        posts = [
            {"url": "https://www.linkedin.com/feed/update/1/", "text": "Post 1"},
            {"url": "https://www.linkedin.com/feed/update/2/", "text": "Post 2"},
            {"url": "https://www.linkedin.com/feed/update/3/", "text": "Post 3"},
        ]

        mock_db = MagicMock()
        # URL 2 is "already seen"
        with patch("backend.automation.feed_scanner.FeedScanner._filter_seen") as mock_filter:
            mock_filter.return_value = [posts[0], posts[2]]
            scanner = FeedScanner()
            result = scanner._filter_seen(posts, mock_db)
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_extract_url_from_data_urn(self):
        from backend.automation.feed_scanner import FeedScanner

        el = AsyncMock()
        el.get_attribute = AsyncMock(return_value="urn:li:activity:7123456789")
        el.query_selector = AsyncMock(return_value=None)

        scanner = FeedScanner()
        url = await scanner._extract_url(el)

        assert url == "https://www.linkedin.com/feed/update/urn:li:activity:7123456789/"

    @pytest.mark.asyncio
    async def test_extract_url_fallback_to_link(self):
        from backend.automation.feed_scanner import FeedScanner

        link_el = make_mock_element(attribute="/feed/update/urn:li:activity:9999/")

        el = AsyncMock()
        el.get_attribute = AsyncMock(return_value=None)  # No data-urn
        el.query_selector = AsyncMock(return_value=link_el)

        scanner = FeedScanner()
        url = await scanner._extract_url(el)

        assert "9999" in url

    @pytest.mark.asyncio
    async def test_extract_url_returns_none_when_missing(self):
        from backend.automation.feed_scanner import FeedScanner

        el = AsyncMock()
        el.get_attribute = AsyncMock(return_value=None)
        el.query_selector = AsyncMock(return_value=None)

        scanner = FeedScanner()
        url = await scanner._extract_url(el)
        assert url is None

    @pytest.mark.asyncio
    async def test_scan_respects_max_posts_config(self):
        from backend.automation.feed_scanner import FeedScanner

        # Build 50 fake post dicts
        posts = [
            {
                "url": f"https://www.linkedin.com/feed/update/{i}/",
                "author_name": f"Author {i}",
                "author_url": "",
                "text": f"Post text {i}",
                "like_count": 0,
                "comment_count": 0,
                "timestamp_text": "1h",
            }
            for i in range(50)
        ]

        scanner = FeedScanner()

        with patch.object(scanner, "_extract_posts", AsyncMock(return_value=posts)):
            with patch("backend.automation.feed_scanner.scroll_down", AsyncMock()):
                with patch(
                    "backend.automation.feed_scanner.cfg_get",
                    side_effect=lambda key, default=None: 30 if key == "feed_engagement.max_posts_per_scan" else default,
                ):
                    result = await scanner.scan(make_mock_page(), db=None)

        assert len(result) == 30
