"""
Pattern generator — Sprint 6.

Generates candidate email addresses from first name, last name, and company domain.
Patterns are ordered by likelihood (most common corporate formats first).
"""
import unicodedata
import re
from typing import List


def generate(first_name: str, last_name: str, domain: str) -> List[str]:
    """
    Generate candidate email addresses in priority order.

    Names are normalized: lowercased, accents stripped, non-alphanumeric removed,
    truncated to 20 chars max.

    Returns deduplicated list preserving order.
    Returns empty list if any input is missing/empty.
    """
    if not first_name or not last_name or not domain:
        return []

    first = _normalize(first_name)
    last = _normalize(last_name)

    if not first or not last:
        return []

    f = first[0]  # first initial

    patterns = [
        f"{first}.{last}@{domain}",
        f"{f}.{last}@{domain}",
        f"{first}@{domain}",
        f"{f}{last}@{domain}",
        f"{first}{last[0]}@{domain}",
        f"{last}@{domain}",
        f"{first}_{last}@{domain}",
        f"{f}_{last}@{domain}",
    ]

    # Deduplicate preserving order
    seen = set()
    result = []
    for p in patterns:
        if p not in seen:
            seen.add(p)
            result.append(p)

    return result


def _normalize(name: str) -> str:
    """
    Normalize a name for email generation:
    - Lowercase
    - Strip accents (NFD decomposition, remove combining chars)
    - Remove non-alphanumeric except hyphens
    - Truncate to 20 chars
    """
    name = name.strip().lower()

    # Strip accents: decompose → remove combining marks → recompose
    nfkd = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in nfkd if not unicodedata.combining(c))

    # Keep only alphanumeric and hyphens
    name = re.sub(r"[^a-z0-9\-]", "", name)

    return name[:20]
