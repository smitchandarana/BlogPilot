"""
SMTP verifier — Sprint 6.

Verifies an email address via MX lookup + SMTP RCPT TO handshake.
Never sends actual email. Never raises — always returns bool.
"""
import asyncio
import smtplib
import socket
from typing import Optional

import dns.resolver

from backend.utils.config_loader import get as cfg_get
from backend.utils.logger import get_logger

logger = get_logger(__name__)


async def verify(email: str) -> bool:
    """
    Verify an email address using MX lookup + SMTP handshake.

    Steps:
      1. Resolve MX records for the domain
      2. Connect to the preferred MX host on port 25
      3. EHLO → MAIL FROM → RCPT TO handshake
      4. 250 on RCPT TO = valid, 550/551/553 = invalid

    Never sends email. Never raises. Always returns bool.
    """
    try:
        domain = email.split("@", 1)[1] if "@" in email else ""
        if not domain:
            return False

        # Step 1: MX lookup
        mx_host = await _resolve_mx(domain)
        if not mx_host:
            logger.debug(f"SMTP verify: no MX records for {domain}")
            return False

        # Step 2+3: SMTP handshake (blocking I/O → run in thread)
        timeout = int(cfg_get("email_enrichment.smtp_timeout_seconds", 10))
        result = await asyncio.get_event_loop().run_in_executor(
            None, _smtp_check, mx_host, email, timeout
        )
        return result

    except Exception as e:
        logger.debug(f"SMTP verify: unexpected error for {email} — {e}")
        return False


async def _resolve_mx(domain: str) -> Optional[str]:
    """Resolve MX records, return the preferred (lowest priority) host."""
    try:
        loop = asyncio.get_event_loop()
        answers = await loop.run_in_executor(
            None, lambda: dns.resolver.resolve(domain, "MX")
        )
        # Sort by priority (lowest = most preferred)
        records = sorted(answers, key=lambda r: r.preference)
        if records:
            # MX exchange is a dns.name.Name — convert to string, strip trailing dot
            return str(records[0].exchange).rstrip(".")
        return None
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
        return None
    except Exception as e:
        logger.debug(f"MX lookup failed for {domain}: {e}")
        return None


def _smtp_check(mx_host: str, email: str, timeout: int) -> bool:
    """
    Synchronous SMTP handshake. Runs in a thread executor.
    Returns True if the server accepts RCPT TO with a 250 response.
    """
    smtp = smtplib.SMTP(timeout=timeout)
    try:
        smtp.connect(mx_host, 25)
        smtp.ehlo("linkedin-ai-engine.local")
        smtp.mail("verify@linkedin-ai-engine.local")
        code, _ = smtp.rcpt(email)
        smtp.quit()

        if code == 250:
            logger.info(f"SMTP verify: {email} accepted (250)")
            return True
        else:
            logger.debug(f"SMTP verify: {email} rejected (code={code})")
            return False

    except smtplib.SMTPServerDisconnected:
        logger.debug(f"SMTP verify: server disconnected for {email}")
        return False
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        logger.debug(f"SMTP verify: connection error for {email} — {e}")
        return False
    except Exception as e:
        logger.debug(f"SMTP verify: error for {email} — {e}")
        return False
    finally:
        try:
            smtp.close()
        except Exception:
            pass
