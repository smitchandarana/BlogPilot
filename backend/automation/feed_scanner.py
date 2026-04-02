"""
Feed scanner — Sprint 4 (updated March 2026 for new LinkedIn DOM).

Navigates to the LinkedIn feed, scrolls to load posts, extracts post data
from the DOM, and filters out posts already seen in the database.

LinkedIn moved to CSS modules with hashed class names in ~March 2026.
Old selectors (data-urn, feed-shared-update-v2, etc.) no longer work.
New approach uses:
  - div[data-testid="mainFeed"] as the feed container
  - div[data-display-contents="true"] as potential post wrappers
  - button[aria-label*="control menu for post by"] as post identification
  - div[data-testid="expandable-text-box"] for post text
  - a[href*="/in/"] and a[href*="/company/"] for author profile links
  - a[href*="/feed/update/"] and a[href*="/posts/"] for post URLs
"""
import os
import re
from datetime import datetime
from typing import List, Optional

from playwright.async_api import Page

from backend.automation.human_behavior import scroll_down, random_delay
from backend.utils.config_loader import get as cfg_get
from backend.utils.logger import get_logger

logger = get_logger(__name__)

LINKEDIN_FEED_URL = "https://www.linkedin.com/feed/"


class FeedScanner:
    """
    Scans the LinkedIn feed and returns new, unseen posts.
    """

    def __init__(self, post_state=None):
        self._post_state = post_state

    async def scan(self, page: Page, db=None) -> List[dict]:
        """
        Navigate to feed, scroll, extract posts, and deduplicate.
        Returns list of post dicts (new posts only, capped at max_posts_per_scan).
        """
        logger.info("Feed scan starting")

        # Navigate to feed if not already there
        if "linkedin.com/feed" not in page.url:
            logger.info(f"Navigating to feed (current URL: {page.url})")
            await page.goto(LINKEDIN_FEED_URL, wait_until="domcontentloaded", timeout=30000)
            await random_delay(2.0, 4.0)
        else:
            # Force a reload to get fresh content — avoids stale cached DOM
            logger.info(f"Already on feed — reloading for fresh content (URL: {page.url})")
            await page.reload(wait_until="domcontentloaded", timeout=30000)
            await random_delay(2.0, 4.0)

        # Scroll to load posts
        scroll_passes = int(cfg_get("feed_engagement.scroll_passes", 3))
        await scroll_down(page, scroll_passes)

        # Extract all posts from DOM
        posts = await self._extract_posts(page)
        logger.info(f"Extracted {len(posts)} posts from DOM")

        # Deduplicate against DB
        if db is not None:
            posts = self._filter_seen(posts, db)
            logger.info(f"After deduplication: {len(posts)} new posts")

        max_posts = int(cfg_get("feed_engagement.max_posts_per_scan", 30))
        result = posts[:max_posts]
        logger.info(f"Feed scan complete — returning {len(result)} posts")
        return result

    async def _extract_posts(self, page: Page) -> List[dict]:
        """Parse the LinkedIn feed DOM and return raw post dicts."""
        posts = []

        # Strategy: use JavaScript to extract all posts in one evaluate() call.
        # This is faster and more reliable than multiple query_selector calls,
        # and avoids issues with stale element handles after DOM mutations.
        raw_posts = await page.evaluate("""() => {
            const results = [];

            // Find the main feed container (new LinkedIn DOM: data-testid="mainFeed")
            const mainFeed = document.querySelector('[data-testid="mainFeed"]');
            if (!mainFeed) {
                // Legacy fallback selectors
                const legacy = document.querySelector(
                    'div.scaffold-finite-scroll__content, ' +
                    'div.feed-shared-update-v2'
                );
                if (!legacy) return results;
            }

            const searchRoot = mainFeed || document;

            // Find post containers: elements with "control menu for post by" button
            // These are inside data-display-contents wrappers in the new DOM
            const postMenuBtns = searchRoot.querySelectorAll(
                'button[aria-label*="control menu for post by"]'
            );

            for (const btn of postMenuBtns) {
                try {
                    // Walk up to find the post container — the closest
                    // data-display-contents wrapper, or a reasonable ancestor
                    let container = btn.closest('[data-display-contents="true"]');
                    if (!container) {
                        // Fallback: walk up to find a div that contains both
                        // the menu button and text content
                        container = btn.parentElement;
                        for (let i = 0; i < 8 && container; i++) {
                            const textBox = container.querySelector('[data-testid="expandable-text-box"]');
                            if (textBox) break;
                            container = container.parentElement;
                        }
                    }
                    if (!container) continue;

                    // Author name from button aria-label
                    const ariaLabel = btn.getAttribute('aria-label') || '';
                    const authorMatch = ariaLabel.match(/post by (.+)/);
                    const authorName = authorMatch ? authorMatch[1].trim() : 'Unknown';

                    // Post text from expandable-text-box
                    const textBox = container.querySelector('[data-testid="expandable-text-box"]');
                    const text = textBox ? textBox.innerText.trim() : '';
                    if (!text || text.length < 10) continue; // Skip empty/trivial posts

                    // Author profile URL — first /in/ or /company/ link
                    let authorUrl = '';
                    const profileLink = container.querySelector(
                        'a[href*="/in/"], a[href*="/company/"]'
                    );
                    if (profileLink) {
                        authorUrl = profileLink.getAttribute('href') || '';
                        // Clean URL
                        if (authorUrl.startsWith('/')) authorUrl = 'https://www.linkedin.com' + authorUrl;
                        authorUrl = authorUrl.split('?')[0];
                    }

                    // Post URL — look for feed/update or /posts/ links
                    let postUrl = '';
                    const postLink = container.querySelector(
                        'a[href*="/feed/update/"], a[href*="/posts/"]'
                    );
                    if (postLink) {
                        postUrl = postLink.getAttribute('href') || '';
                        if (postUrl.startsWith('/')) postUrl = 'https://www.linkedin.com' + postUrl;
                        postUrl = postUrl.split('?')[0];
                    }

                    // If no direct post URL, try to extract from the comment list data-testid
                    // which contains encoded post URNs
                    if (!postUrl) {
                        const commentList = container.querySelector('[data-testid*="commentList"]');
                        if (commentList) {
                            const testId = commentList.getAttribute('data-testid') || '';
                            // testid format: <base64urn>-commentList<hash>FeedType_...
                            // Use the testid as a unique identifier
                            postUrl = 'urn:testid:' + testId.split('-commentList')[0];
                        }
                    }

                    // If still no URL, generate one from author + text hash
                    if (!postUrl) {
                        const hash = text.substring(0, 80).replace(/[^a-zA-Z0-9]/g, '').substring(0, 40);
                        postUrl = 'urn:li:feedpost:' + hash;
                    }

                    // Like / reaction count
                    let likeCount = 0;
                    const spans = container.querySelectorAll('span');
                    for (const sp of spans) {
                        const t = (sp.innerText || '').trim();
                        if (/^[\\d,]+[KMkm]?$/.test(t) && t.length < 10 && t.length > 0) {
                            // Check if this span is near a reaction-related element
                            const parent = sp.parentElement;
                            const nearReaction = parent?.querySelector('img[aria-label*="reaction"]') ||
                                                parent?.closest('[class]')?.querySelector('img[aria-label]');
                            if (nearReaction || !likeCount) {
                                likeCount = parseCount(t);
                            }
                        }
                    }

                    // Comment count (approximate — count comment-related buttons)
                    let commentCount = 0;
                    const commentBtns = container.querySelectorAll('button[aria-label*="comment"]');
                    for (const cb of commentBtns) {
                        const label = cb.getAttribute('aria-label') || '';
                        const match = label.match(/(\\d+)\\s*comment/i);
                        if (match) {
                            commentCount = parseInt(match[1], 10);
                            break;
                        }
                    }

                    // Timestamp
                    let timestampText = '';
                    const timeEl = container.querySelector('time');
                    if (timeEl) {
                        timestampText = timeEl.innerText?.trim() || timeEl.getAttribute('datetime') || '';
                    }

                    results.push({
                        url: postUrl,
                        author_name: authorName,
                        author_url: authorUrl,
                        text: text,
                        like_count: likeCount,
                        comment_count: commentCount,
                        timestamp_text: timestampText,
                    });
                } catch (e) {
                    // Skip this post on error, continue to next
                    continue;
                }
            }

            function parseCount(text) {
                if (!text) return 0;
                text = text.trim().replace(/,/g, '');
                const upper = text.toUpperCase();
                if (upper.includes('K')) return Math.round(parseFloat(upper.replace('K', '')) * 1000);
                if (upper.includes('M')) return Math.round(parseFloat(upper.replace('M', '')) * 1000000);
                return parseInt(text, 10) || 0;
            }

            return results;
        }""")

        logger.info(f"JS extraction found {len(raw_posts)} posts")

        # Deduplicate by URL (JS may find same post at multiple nesting levels)
        seen_urls = set()
        for post_data in raw_posts:
            url = post_data.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            # Clean the text
            text = _clean(post_data.get("text", ""))
            if not text:
                continue

            posts.append({
                "url": url,
                "author_name": _clean(post_data.get("author_name", "Unknown")),
                "author_url": post_data.get("author_url", ""),
                "text": text,
                "like_count": post_data.get("like_count", 0),
                "comment_count": post_data.get("comment_count", 0),
                "timestamp_text": post_data.get("timestamp_text", ""),
            })

        # If new selectors found nothing, fall back to legacy selectors
        if not posts:
            logger.warning("New selectors found 0 posts — trying legacy selectors")
            posts = await self._extract_posts_legacy(page)

        # If still nothing, dump diagnostics
        if not posts:
            await self._dump_diagnostics(page)

        return posts

    async def _extract_posts_legacy(self, page: Page) -> List[dict]:
        """Legacy extraction using old LinkedIn DOM selectors (pre-March 2026)."""
        posts = []

        # Try old-style selectors
        for selector in [
            "div[data-urn*='activity'], div[data-urn*='ugcPost'], div[data-urn*='share']",
            "div[data-id*='urn:li:activity'], div[data-id*='urn:li:ugcPost']",
            "div.feed-shared-update-v2, div.occludable-update",
        ]:
            post_elements = await page.query_selector_all(selector)
            if post_elements:
                logger.info(f"Legacy selector matched: {len(post_elements)} elements")
                for el in post_elements:
                    try:
                        post = await self._parse_post_legacy(el)
                        if post:
                            posts.append(post)
                    except Exception as e:
                        logger.debug(f"Legacy post parse error: {e}")
                break

        return posts

    async def _parse_post_legacy(self, el) -> Optional[dict]:
        """Extract data from a post container using old-style selectors."""
        # URL
        urn = await el.get_attribute("data-urn") or ""
        url = ""
        if "activity:" in urn:
            activity_id = urn.split("activity:")[-1].split(",")[0]
            url = f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/"
        if not url:
            link_el = await el.query_selector("a[href*='/feed/update/'], a[href*='/posts/']")
            if link_el:
                href = await link_el.get_attribute("href") or ""
                url = _normalise_url(href)
        if not url:
            return None

        # Author
        author_name = "Unknown"
        for sel in [
            "span.update-components-actor__name span[aria-hidden='true']",
            "span.update-components-actor__name",
            "a[href*='/in/'] span[aria-hidden='true']",
        ]:
            author_el = await el.query_selector(sel)
            if author_el:
                name = _clean(await author_el.inner_text())
                if name and len(name) < 100:
                    author_name = name
                    break

        # Text
        text_el = await el.query_selector(
            "div.feed-shared-update-v2__description, "
            "div.update-components-text, "
            "span.break-words"
        )
        text = _clean(await text_el.inner_text()) if text_el else ""
        if not text:
            return None

        # Author URL
        author_link = await el.query_selector("a[href*='/in/'], a[href*='/company/']")
        author_url = ""
        if author_link:
            author_url = _normalise_url(await author_link.get_attribute("href") or "")

        return {
            "url": url,
            "author_name": author_name,
            "author_url": author_url,
            "text": text,
            "like_count": 0,
            "comment_count": 0,
            "timestamp_text": "",
        }

    async def _dump_diagnostics(self, page: Page):
        """Save screenshot + DOM summary when feed extraction finds 0 posts."""
        try:
            diag_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs", "diagnostics")
            os.makedirs(diag_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Screenshot
            ss_path = os.path.join(diag_dir, f"feed_{ts}.png")
            await page.screenshot(path=ss_path, full_page=False)
            logger.warning(f"Diagnostic screenshot saved: {ss_path}")
            logger.warning(f"Diagnostic: page URL = {page.url}")

            # Quick DOM summary
            dom_info = await page.evaluate("""() => {
                const r = [];
                const mainFeed = document.querySelector('[data-testid="mainFeed"]');
                r.push('mainFeed: ' + (mainFeed ? 'FOUND' : 'MISSING'));
                const postBtns = document.querySelectorAll('button[aria-label*="control menu for post"]');
                r.push('post menu buttons: ' + postBtns.length);
                const textBoxes = document.querySelectorAll('[data-testid="expandable-text-box"]');
                r.push('expandable-text-box: ' + textBoxes.length);
                const main = document.querySelector('main');
                r.push('main: ' + (main ? 'FOUND' : 'MISSING'));
                r.push('page title: ' + document.title);
                r.push('URL: ' + location.href);
                // Top-level data-testid values
                const testIds = {};
                document.querySelectorAll('[data-testid]').forEach(el => {
                    const tid = el.getAttribute('data-testid');
                    if (tid.length < 30) testIds[tid] = (testIds[tid] || 0) + 1;
                });
                r.push('data-testid: ' + JSON.stringify(testIds));
                return r.join('\\n');
            }""")

            dump_path = os.path.join(diag_dir, f"dom_{ts}.txt")
            with open(dump_path, "w", encoding="utf-8") as f:
                f.write(dom_info)
            logger.warning(f"Diagnostic DOM dump:\n{dom_info}")

        except Exception as e:
            logger.error(f"Diagnostic dump failed: {e}")

    def _filter_seen(self, posts: List[dict], db) -> List[dict]:
        """Return only posts not already in the database."""
        if self._post_state is None:
            logger.warning("FeedScanner: no post_state injected — deduplication disabled, all posts will be processed")
            return posts
        return [p for p in posts if not self._post_state.is_seen(p["url"], db)]

    async def _extract_url(self, el) -> Optional[str]:
        """Extract a post URL from a Playwright element handle.

        Priority:
        1. data-urn attribute  → https://www.linkedin.com/feed/update/{urn}/
        2. <a href> link       → normalised absolute URL
        3. None                → could not determine URL
        """
        urn = await el.get_attribute("data-urn")
        if urn:
            return f"https://www.linkedin.com/feed/update/{urn}/"
        link = await el.query_selector('a[href*="/feed/update/"], a[href*="/posts/"]')
        if link:
            href = await link.get_attribute("href")
            return _normalise_url(href) if href else None
        return None


# ── Helpers ────────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    """Strip HTML artefacts and normalise whitespace."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _normalise_url(href: str) -> str:
    """Return an absolute LinkedIn URL, stripping query params."""
    if not href:
        return ""
    if href.startswith("http"):
        return href.split("?")[0]
    return f"https://www.linkedin.com{href.split('?')[0]}"


def _parse_count(text: str) -> int:
    """Parse LinkedIn engagement counts: '1.2K' → 1200, '34' → 34."""
    if not text:
        return 0
    text = text.strip().replace(",", "")
    upper = text.upper()
    try:
        if "K" in upper:
            return int(float(upper.replace("K", "")) * 1000)
        if "M" in upper:
            return int(float(upper.replace("M", "")) * 1_000_000)
        return int(text)
    except ValueError:
        return 0
