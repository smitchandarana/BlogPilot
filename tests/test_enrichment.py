"""
Tests for Sprint 6 — Email Enrichment Layer.

Covers: pattern_generator, smtp_verifier (mocked), email_enricher orchestration.
"""
import asyncio
import smtplib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.enrichment.pattern_generator import generate
from backend.enrichment.smtp_verifier import verify, _smtp_check


# ── Pattern Generator ────────────────────────────────────────────────────────

class TestPatternGenerator:
    def test_basic_patterns(self):
        result = generate("John", "Smith", "tcs.com")
        assert result[0] == "john.smith@tcs.com"
        assert len(result) == 8
        expected = [
            "john.smith@tcs.com",
            "j.smith@tcs.com",
            "john@tcs.com",
            "jsmith@tcs.com",
            "johns@tcs.com",
            "smith@tcs.com",
            "john_smith@tcs.com",
            "j_smith@tcs.com",
        ]
        assert result == expected

    def test_no_duplicates(self):
        result = generate("John", "Smith", "tcs.com")
        assert len(result) == len(set(result))

    def test_accent_stripping(self):
        result = generate("José", "García", "company.com")
        assert result[0] == "jose.garcia@company.com"
        # Verify all accents stripped
        for email in result:
            local = email.split("@")[0]
            assert local.isascii(), f"Non-ASCII in {email}"

    def test_empty_inputs(self):
        assert generate("", "Smith", "tcs.com") == []
        assert generate("John", "", "tcs.com") == []
        assert generate("John", "Smith", "") == []
        assert generate(None, "Smith", "tcs.com") == []

    def test_special_characters_removed(self):
        result = generate("Mary-Jane", "O'Brien", "acme.com")
        # Hyphens kept, apostrophes removed
        assert "mary-jane.obrien@acme.com" in result

    def test_long_names_truncated(self):
        long_first = "A" * 30
        result = generate(long_first, "Doe", "x.com")
        for email in result:
            local = email.split("@")[0]
            assert len(local) <= 42  # 20 char name + separators + 20 char name max


# ── SMTP Verifier ────────────────────────────────────────────────────────────

class TestSmtpVerifier:
    def test_smtp_accepts_250(self):
        """Mock RCPT TO returning 250 → verify returns True."""
        mock_smtp = MagicMock(spec=smtplib.SMTP)
        mock_smtp.connect.return_value = (220, b"OK")
        mock_smtp.ehlo.return_value = (250, b"OK")
        mock_smtp.mail.return_value = (250, b"OK")
        mock_smtp.rcpt.return_value = (250, b"OK")

        with patch("backend.enrichment.smtp_verifier.smtplib.SMTP", return_value=mock_smtp):
            result = _smtp_check("mx.example.com", "test@example.com", 10)

        assert result is True
        mock_smtp.quit.assert_called_once()

    def test_smtp_rejects_550(self):
        """Mock RCPT TO returning 550 → verify returns False."""
        mock_smtp = MagicMock(spec=smtplib.SMTP)
        mock_smtp.connect.return_value = (220, b"OK")
        mock_smtp.ehlo.return_value = (250, b"OK")
        mock_smtp.mail.return_value = (250, b"OK")
        mock_smtp.rcpt.return_value = (550, b"User unknown")

        with patch("backend.enrichment.smtp_verifier.smtplib.SMTP", return_value=mock_smtp):
            result = _smtp_check("mx.example.com", "bad@example.com", 10)

        assert result is False

    def test_connection_timeout(self):
        """Connection timeout → returns False, no exception raised."""
        with patch(
            "backend.enrichment.smtp_verifier.smtplib.SMTP",
            side_effect=TimeoutError("connection timed out"),
        ):
            result = _smtp_check("mx.example.com", "test@example.com", 5)

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_no_mx(self):
        """No MX records → verify returns False."""
        with patch(
            "backend.enrichment.smtp_verifier._resolve_mx",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await verify("test@nonexistent.invalid")
        assert result is False


# ── Email Enricher Orchestration ─────────────────────────────────────────────

class TestEmailEnricher:
    @pytest.mark.asyncio
    async def test_pattern_smtp_fallthrough(self):
        """
        DOM scraper returns None, Hunter returns None,
        SMTP verifies first pattern → result is VERIFIED via PATTERN_SMTP.
        """
        from backend.enrichment.email_enricher import EmailEnricher

        profile = {
            "first_name": "John",
            "last_name": "Doe",
            "company_domain": "acme.com",
            "connection_degree": 2,  # Not 1st degree → DOM skipped
            "linkedin_url": "https://linkedin.com/in/johndoe",
        }

        with patch(
            "backend.enrichment.hunter_client.find",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "backend.enrichment.smtp_verifier.verify",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_verify, patch(
            "backend.enrichment.email_enricher.EmailEnricher._finalize",
            new_callable=AsyncMock,
        ) as mock_finalize:
            enricher = EmailEnricher(page=None)
            result = await enricher.enrich(profile)

        assert result["status"] == "VERIFIED"
        assert result["method"] == "PATTERN_SMTP"
        assert result["email"] == "john.doe@acme.com"
        mock_finalize.assert_called_once()

    @pytest.mark.asyncio
    async def test_dom_short_circuit(self):
        """
        DOM scraper finds email → Hunter and SMTP are never called.
        """
        from backend.enrichment.email_enricher import EmailEnricher

        profile = {
            "first_name": "Jane",
            "last_name": "Smith",
            "company_domain": "corp.com",
            "connection_degree": 1,
            "linkedin_url": "https://linkedin.com/in/janesmith",
        }

        mock_page = AsyncMock()

        with patch(
            "backend.enrichment.dom_email_scraper.scrape",
            new_callable=AsyncMock,
            return_value="found@email.com",
        ), patch(
            "backend.enrichment.hunter_client.find",
            new_callable=AsyncMock,
        ) as mock_hunter, patch(
            "backend.enrichment.smtp_verifier.verify",
            new_callable=AsyncMock,
        ) as mock_smtp, patch(
            "backend.enrichment.email_enricher.EmailEnricher._finalize",
            new_callable=AsyncMock,
        ):
            enricher = EmailEnricher(page=mock_page)
            result = await enricher.enrich(profile)

        assert result["email"] == "found@email.com"
        assert result["status"] == "FOUND"
        assert result["method"] == "DOM"
        mock_hunter.assert_not_called()
        mock_smtp.assert_not_called()

    @pytest.mark.asyncio
    async def test_all_methods_fail(self):
        """All methods return nothing → NOT_FOUND."""
        from backend.enrichment.email_enricher import EmailEnricher

        profile = {
            "first_name": "Ghost",
            "last_name": "User",
            "company_domain": "nowhere.com",
            "connection_degree": 2,
            "linkedin_url": "https://linkedin.com/in/ghost",
        }

        with patch(
            "backend.enrichment.smtp_verifier.verify",
            new_callable=AsyncMock,
            return_value=False,
        ), patch(
            "backend.enrichment.email_enricher.EmailEnricher._finalize",
            new_callable=AsyncMock,
        ):
            enricher = EmailEnricher(page=None)
            result = await enricher.enrich(profile)

        assert result["status"] == "NOT_FOUND"
        assert result["email"] is None
        assert result["method"] is None
