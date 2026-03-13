"""Tests for the topic research pipeline."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

from backend.research.reddit_scanner import _extract_post_data
from backend.research.rss_scanner import _strip_html
from backend.research.topic_researcher import TopicResearcher


class TestRedditScanner:
    def test_extract_post_data(self):
        raw = {
            "title": "Power BI vs Tableau in 2025",
            "selftext": "I've been comparing these tools...",
            "permalink": "/r/PowerBI/comments/abc123/",
            "ups": 150,
            "num_comments": 42,
            "created_utc": 1700000000,
        }
        result = _extract_post_data(raw, "PowerBI")
        assert result["title"] == "Power BI vs Tableau in 2025"
        assert result["text"] == "I've been comparing these tools..."
        assert result["upvotes"] == 150
        assert result["num_comments"] == 42
        assert result["subreddit"] == "PowerBI"
        assert result["source"] == "REDDIT"
        assert "reddit.com" in result["url"]

    def test_extract_empty_selftext(self):
        raw = {
            "title": "Link post",
            "selftext": None,
            "permalink": "/r/test/",
            "ups": 10,
            "num_comments": 2,
            "created_utc": 0,
        }
        result = _extract_post_data(raw, "test")
        assert result["text"] == ""

    def test_truncate_long_text(self):
        raw = {
            "title": "Long post",
            "selftext": "x" * 5000,
            "permalink": "/r/test/",
            "ups": 1,
            "num_comments": 0,
            "created_utc": 0,
        }
        result = _extract_post_data(raw, "test")
        assert len(result["text"]) <= 2000


class TestRSSScanner:
    def test_strip_html(self):
        html = "<p>Hello <b>world</b></p><br/><a href='#'>link</a>"
        result = _strip_html(html)
        assert "<" not in result
        assert ">" not in result
        assert "Hello" in result
        assert "world" in result

    def test_strip_html_empty(self):
        assert _strip_html("") == ""


class TestTopicResearcher:
    def test_match_snippets_to_topic_exact(self):
        researcher = TopicResearcher()
        snippets = [
            {"title": "Data Analytics trends 2025", "text": "The field of data analytics is evolving"},
            {"title": "Cooking recipes for beginners", "text": "Start with simple pasta"},
            {"title": "Power BI dashboard design", "text": "Best practices for data visualization"},
        ]
        matched = researcher._match_snippets_to_topic("Data Analytics", snippets)
        assert len(matched) >= 1
        assert any("Data Analytics" in s["title"] for s in matched)

    def test_match_snippets_keyword_overlap(self):
        researcher = TopicResearcher()
        snippets = [
            {"title": "How analytics drives business growth", "text": "Using data to make better decisions"},
            {"title": "Weather forecast today", "text": "Sunny with clouds"},
        ]
        matched = researcher._match_snippets_to_topic("Business Analytics", snippets)
        assert len(matched) >= 1

    def test_match_no_snippets(self):
        researcher = TopicResearcher()
        snippets = [
            {"title": "Cooking pasta", "text": "Boil water first"},
        ]
        matched = researcher._match_snippets_to_topic("Data Analytics", snippets)
        assert len(matched) == 0

    def test_match_caps_at_30(self):
        researcher = TopicResearcher()
        snippets = [{"title": f"Analytics article {i}", "text": "analytics content"} for i in range(50)]
        matched = researcher._match_snippets_to_topic("Analytics", snippets)
        assert len(matched) <= 30

    def test_heuristic_score(self):
        researcher = TopicResearcher()
        snippets = [
            {"title": "test", "text": "", "upvotes": 100, "source": "REDDIT"},
            {"title": "test2", "text": "", "upvotes": 200, "source": "REDDIT"},
        ]
        scores = researcher._heuristic_score("Data Analytics", snippets, {})
        assert 0 <= scores["trending_velocity"] <= 10
        assert 0 <= scores["content_gap"] <= 10
        assert scores["relevance"] == 7.0
        assert "suggested_angle" in scores

    def test_heuristic_score_empty_snippets(self):
        researcher = TopicResearcher()
        scores = researcher._heuristic_score("Data Analytics", [], {})
        assert scores["trending_velocity"] == 0

    @pytest.mark.asyncio
    async def test_score_topic_no_ai(self):
        """Without groq_client, should fall back to heuristic scoring."""
        researcher = TopicResearcher(groq_client=None, prompt_loader=None)
        snippets = [
            {"title": "Test", "text": "content", "upvotes": 50, "source": "REDDIT"},
        ]
        scores = await researcher._score_topic("Analytics", snippets, {})
        assert "trending_velocity" in scores
        assert "content_gap" in scores
        assert "relevance" in scores
        assert "suggested_angle" in scores

    @pytest.mark.asyncio
    async def test_score_topic_with_ai(self):
        """With mock groq_client, should use AI scoring."""
        mock_groq = AsyncMock()
        mock_groq.complete.return_value = json.dumps({
            "trending_velocity": 7.5,
            "content_gap": 6.0,
            "relevance": 8.5,
            "suggested_angle": "Focus on ROI metrics for small businesses",
        })

        mock_prompts = MagicMock()
        mock_prompts.format.return_value = "formatted prompt"

        researcher = TopicResearcher(groq_client=mock_groq, prompt_loader=mock_prompts)
        snippets = [
            {"title": "Test", "text": "content", "upvotes": 50, "source": "REDDIT"},
        ]
        scores = await researcher._score_topic("Analytics", snippets, {})
        assert scores["trending_velocity"] == 7.5
        assert scores["content_gap"] == 6.0
        assert scores["relevance"] == 8.5
        assert "ROI" in scores["suggested_angle"]

    @pytest.mark.asyncio
    async def test_score_topic_ai_fallback_on_error(self):
        """If AI scoring fails, should fall back to heuristic."""
        mock_groq = AsyncMock()
        mock_groq.complete.side_effect = Exception("API error")

        mock_prompts = MagicMock()
        mock_prompts.format.return_value = "formatted prompt"

        researcher = TopicResearcher(groq_client=mock_groq, prompt_loader=mock_prompts)
        snippets = [
            {"title": "Test", "text": "content", "upvotes": 50, "source": "REDDIT"},
        ]
        scores = await researcher._score_topic("Analytics", snippets, {})
        # Should return valid scores from heuristic fallback
        assert "trending_velocity" in scores
        assert "relevance" in scores
