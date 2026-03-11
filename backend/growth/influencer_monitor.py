"""
Influencer Monitor — Sprint 7.

Polls profiles on the influencer watchlist for new posts and submits
them as HIGH priority SCAN_POST tasks to the worker queue.

Called on a recurring schedule via APScheduler (wired in engine.py / scheduler.py).
"""
from typing import List

from backend.utils.config_loader import get as cfg_get
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class InfluencerMonitor:
    """
    Monitors a list of LinkedIn profiles and discovers new posts
    that haven't been seen yet.
    """

    def __init__(self, worker_pool=None):
        """
        Args:
            worker_pool: Optional WorkerPool reference used to submit
                         SCAN_POST tasks.  Pass None for standalone testing.
        """
        self._pool = worker_pool

    async def check_all(self, page) -> List[dict]:
        """
        Visit every profile on the watchlist, retrieve the most recent post
        URL, and submit HIGH-priority SCAN_POST tasks for any new ones.

        Returns list of newly discovered post dicts.
        """
        watchlist: List[str] = self._get_watchlist()
        if not watchlist:
            logger.debug("InfluencerMonitor: watchlist is empty — nothing to check")
            return []

        from backend.storage.database import get_db
        from backend.storage import post_state

        new_posts: List[dict] = []

        for profile_url in watchlist:
            try:
                post = await self._get_latest_post(page, profile_url)
                if not post:
                    continue

                with get_db() as db:
                    if post_state.is_seen(post["url"], db):
                        logger.debug(
                            f"InfluencerMonitor: already seen post from {profile_url}"
                        )
                        continue

                logger.info(
                    f"InfluencerMonitor: new post from watchlist profile {profile_url}"
                )
                new_posts.append(post)
                self._submit_task(post)

            except Exception as e:
                logger.warning(
                    f"InfluencerMonitor: failed to check {profile_url} — {e}"
                )

        logger.info(
            f"InfluencerMonitor: found {len(new_posts)} new post(s) from {len(watchlist)} profiles"
        )
        return new_posts

    async def _get_latest_post(self, page, profile_url: str) -> dict | None:
        """
        Navigate to the profile's activity feed and return the first post URL
        and metadata.
        """
        activity_url = profile_url.rstrip("/") + "/recent-activity/shares/"
        try:
            await page.goto(activity_url, wait_until="domcontentloaded", timeout=20_000)
            await page.wait_for_timeout(2_000)

            # Try to grab the first post link in the activity feed
            post_link = await page.query_selector(
                "a[href*='/feed/update/'], a[href*='/posts/']"
            )
            if not post_link:
                return None

            href = await post_link.get_attribute("href")
            if not href:
                return None

            # Normalise to absolute URL
            if href.startswith("/"):
                href = "https://www.linkedin.com" + href

            # Try to grab author name from the page title or heading
            author_name = ""
            try:
                heading = await page.query_selector("h1")
                if heading:
                    author_name = (await heading.inner_text()).strip()
            except Exception:
                pass

            return {
                "url": href,
                "author_url": profile_url,
                "author_name": author_name,
                "text": "",
                "like_count": 0,
                "comment_count": 0,
                "timestamp": None,
                "source": "influencer_monitor",
            }
        except Exception as e:
            logger.warning(
                f"InfluencerMonitor: error navigating to {activity_url} — {e}"
            )
            return None

    def _submit_task(self, post: dict) -> None:
        """Submit the post as a HIGH-priority SCAN_POST task."""
        if self._pool is None:
            return
        try:
            from backend.growth.viral_detector import PRIORITY_HIGH
            self._pool.submit("SCAN_POST", payload=post, priority=PRIORITY_HIGH)
        except Exception as e:
            logger.warning(f"InfluencerMonitor: failed to submit task — {e}")

    @staticmethod
    def _get_watchlist() -> List[str]:
        """
        Return the influencer watchlist from config.
        Expected config key: influencer_watchlist (list of LinkedIn URLs).
        Falls back to empty list if not configured.
        """
        watchlist = cfg_get("influencer_watchlist", [])
        if isinstance(watchlist, list):
            return [url.strip() for url in watchlist if url and url.strip()]
        return []
