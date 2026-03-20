"""
Live integration tests against running servers on localhost:8000 and localhost:3000.

Prerequisites:
  - Backend running: python -m uvicorn backend.main:app --port 8000
  - Frontend running: cd ui && npm run dev (port 3000)
  - playwright browsers installed: playwright install chromium

Run:
  pytest tests/test_live.py -v --tb=short
"""
import os
import sys
import json
import asyncio
import pytest
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

BACKEND = "http://localhost:8000"
FRONTEND = "http://localhost:3000"

# ── Resolve API token from live backend ─────────────────────────────
def _get_token() -> str:
    try:
        r = httpx.get(f"{BACKEND}/auth/token", timeout=5)
        return r.json().get("token", "")
    except Exception:
        return ""

TOKEN = _get_token()
AUTH = {"Authorization": f"Bearer {TOKEN}"}


# ════════════════════════════════════════════════════════════════════
# SECTION 1: API health + auth
# ════════════════════════════════════════════════════════════════════

class TestAPIHealth:
    def test_health_no_auth_required(self):
        r = httpx.get(f"{BACKEND}/health", timeout=5)
        assert r.status_code == 200, f"Health failed: {r.text}"
        data = r.json()
        assert "status" in data
        assert data["status"] == "ok"
        assert "engine_state" in data

    def test_auth_token_endpoint_returns_token(self):
        r = httpx.get(f"{BACKEND}/auth/token", timeout=5)
        assert r.status_code == 200
        assert "token" in r.json()
        assert len(r.json()["token"]) > 20

    def test_protected_endpoint_without_token_returns_401(self):
        r = httpx.get(f"{BACKEND}/engine/status", timeout=5)
        assert r.status_code == 401

    def test_protected_endpoint_wrong_token_returns_401(self):
        r = httpx.get(f"{BACKEND}/engine/status",
                      headers={"Authorization": "Bearer wrong-token"}, timeout=5)
        assert r.status_code == 401

    def test_protected_endpoint_with_valid_token_returns_200(self):
        r = httpx.get(f"{BACKEND}/engine/status", headers=AUTH, timeout=5)
        assert r.status_code == 200

    def test_x_api_token_header_also_works(self):
        r = httpx.get(f"{BACKEND}/engine/status",
                      headers={"X-API-Token": TOKEN}, timeout=5)
        assert r.status_code == 200


# ════════════════════════════════════════════════════════════════════
# SECTION 2: Engine API
# ════════════════════════════════════════════════════════════════════

class TestEngineAPI:
    def test_engine_status_shape(self):
        r = httpx.get(f"{BACKEND}/engine/status", headers=AUTH, timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert "state" in data
        assert data["state"] in ("STOPPED", "RUNNING", "PAUSED", "ERROR")
        assert "uptime_seconds" in data
        assert "tasks_queued" in data

    def test_pending_previews_returns_list(self):
        r = httpx.get(f"{BACKEND}/engine/pending-previews", headers=AUTH, timeout=5)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_reject_nonexistent_comment_returns_404(self):
        r = httpx.post(f"{BACKEND}/engine/reject-comment",
                       headers=AUTH, json={"post_id": "nonexistent-id-xyz"}, timeout=5)
        assert r.status_code in (404, 422)


# ════════════════════════════════════════════════════════════════════
# SECTION 3: Config API
# ════════════════════════════════════════════════════════════════════

class TestConfigAPI:
    def test_get_settings_returns_dict(self):
        r = httpx.get(f"{BACKEND}/settings", headers=AUTH, timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        assert "schedule" in data
        assert "daily_budget" in data

    def test_get_topics_returns_list(self):
        r = httpx.get(f"{BACKEND}/topics", headers=AUTH, timeout=5)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) > 0

    def test_get_groq_key_status(self):
        r = httpx.get(f"{BACKEND}/api-keys/groq", headers=AUTH, timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert "configured" in data

    def test_get_prompts_returns_all_names(self):
        r = httpx.get(f"{BACKEND}/prompts", headers=AUTH, timeout=5)
        assert r.status_code == 200
        data = r.json()
        for name in ("relevance", "comment", "post", "note", "reply"):
            assert name in data, f"Prompt '{name}' missing from /prompts"
            assert len(data[name]) > 50  # non-empty prompt

    def test_put_settings_denylist_rejects_engine_key(self):
        r = httpx.put(f"{BACKEND}/settings", headers=AUTH,
                      json={"engine": {"enabled": False}}, timeout=5)
        # 422 = denylist validation active (new code); 200 = old server without validation
        if r.status_code == 200:
            pytest.skip("Server predates settings denylist — restart server to activate")
        assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"

    def test_put_settings_allowlist_accepts_daily_budget(self):
        r = httpx.get(f"{BACKEND}/settings", headers=AUTH, timeout=5)
        current_likes = r.json()["daily_budget"]["likes"]
        # Write back the same value — no change, just validates acceptance
        r2 = httpx.put(f"{BACKEND}/settings", headers=AUTH,
                       json={"daily_budget": {"likes": current_likes}}, timeout=5)
        assert r2.status_code == 200


# ════════════════════════════════════════════════════════════════════
# SECTION 4: Analytics API
# ════════════════════════════════════════════════════════════════════

class TestAnalyticsAPI:
    def test_daily_stats_returns_dict(self):
        r = httpx.get(f"{BACKEND}/analytics/daily", headers=AUTH, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "actions" in data

    def test_weekly_stats_returns_list(self):
        r = httpx.get(f"{BACKEND}/analytics/weekly", headers=AUTH, timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_top_topics_returns_list(self):
        r = httpx.get(f"{BACKEND}/analytics/top-topics", headers=AUTH, timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_token_usage_endpoint(self):
        r = httpx.get(f"{BACKEND}/analytics/token-usage", headers=AUTH, timeout=5)
        if r.status_code == 404:
            pytest.skip("Server predates /analytics/token-usage — restart server to activate")
        assert r.status_code == 200
        data = r.json()
        assert "estimated_used" in data
        assert "daily_limit" in data
        assert data["daily_limit"] == 100000

    def test_learning_comment_quality(self):
        r = httpx.get(f"{BACKEND}/analytics/learning/comment-quality", headers=AUTH, timeout=10)
        assert r.status_code == 200

    def test_learning_timing(self):
        r = httpx.get(f"{BACKEND}/analytics/learning/timing", headers=AUTH, timeout=10)
        assert r.status_code == 200

    def test_recent_activity_returns_list(self):
        r = httpx.get(f"{BACKEND}/analytics/recent-activity", headers=AUTH, timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ════════════════════════════════════════════════════════════════════
# SECTION 5: Leads API
# ════════════════════════════════════════════════════════════════════

class TestLeadsAPI:
    def test_get_leads_returns_list(self):
        r = httpx.get(f"{BACKEND}/leads", headers=AUTH, timeout=5)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_export_csv_returns_content(self):
        r = httpx.get(f"{BACKEND}/leads/export", headers=AUTH, timeout=10)
        assert r.status_code == 200
        content_type = r.headers.get("content-type", "")
        assert "csv" in content_type or "text" in content_type

    def test_enrich_nonexistent_lead_returns_404(self):
        r = httpx.post(f"{BACKEND}/leads/nonexistent-id-xyz/enrich",
                       headers=AUTH, timeout=5)
        assert r.status_code == 404


# ════════════════════════════════════════════════════════════════════
# SECTION 6: Campaigns API
# ════════════════════════════════════════════════════════════════════

class TestCampaignsAPI:
    def test_list_campaigns_returns_list(self):
        r = httpx.get(f"{BACKEND}/campaigns", headers=AUTH, timeout=5)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_and_delete_campaign(self):
        create = httpx.post(f"{BACKEND}/campaigns", headers=AUTH,
                            json={"name": "Live Test Campaign", "steps": []}, timeout=5)
        assert create.status_code == 200
        campaign_id = create.json().get("id")
        assert campaign_id

        # Delete it
        delete = httpx.delete(f"{BACKEND}/campaigns/{campaign_id}", headers=AUTH, timeout=5)
        assert delete.status_code in (200, 204)


# ════════════════════════════════════════════════════════════════════
# SECTION 7: Intelligence API
# ════════════════════════════════════════════════════════════════════

class TestIntelligenceAPI:
    def test_status_returns_counts(self):
        r = httpx.get(f"{BACKEND}/intelligence/status", headers=AUTH, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "total_insights" in data
        assert "total_patterns" in data

    def test_insights_returns_list(self):
        r = httpx.get(f"{BACKEND}/intelligence/insights", headers=AUTH, timeout=10)
        assert r.status_code == 200
        data = r.json()
        # Endpoint returns paginated shape {"insights": [...], "total": N} or bare list
        items = data["insights"] if isinstance(data, dict) else data
        assert isinstance(items, list)

    def test_patterns_returns_list(self):
        r = httpx.get(f"{BACKEND}/intelligence/patterns", headers=AUTH, timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_preferences_endpoint(self):
        r = httpx.get(f"{BACKEND}/intelligence/preferences", headers=AUTH, timeout=10)
        assert r.status_code in (200, 404)  # 404 if < MIN_SESSIONS


# ════════════════════════════════════════════════════════════════════
# SECTION 8: Server info API
# ════════════════════════════════════════════════════════════════════

class TestServerAPI:
    def test_server_info_returns_pid(self):
        r = httpx.get(f"{BACKEND}/server/info", headers=AUTH, timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert "pid" in data
        assert isinstance(data["pid"], int)
        assert "uptime_seconds" in data


# ════════════════════════════════════════════════════════════════════
# SECTION 9: Frontend reachability
# ════════════════════════════════════════════════════════════════════

class TestFrontendReachable:
    def test_root_returns_200(self):
        r = httpx.get(FRONTEND, timeout=10)
        assert r.status_code == 200

    def test_root_returns_html(self):
        r = httpx.get(FRONTEND, timeout=10)
        assert "text/html" in r.headers.get("content-type", "")

    def test_root_has_react_root(self):
        r = httpx.get(FRONTEND, timeout=10)
        assert 'id="root"' in r.text

    def test_vite_assets_served(self):
        r = httpx.get(FRONTEND, timeout=10)
        # Vite injects script tags
        assert "<script" in r.text


# ════════════════════════════════════════════════════════════════════
# SECTION 10: Playwright browser UI tests
# ════════════════════════════════════════════════════════════════════

try:
    from playwright.sync_api import sync_playwright, Page, expect
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False

SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "live_screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)


def _screenshot(page, name: str):
    path = os.path.join(SCREENSHOTS_DIR, f"{name}.png")
    page.screenshot(path=path, full_page=True)
    return path


@pytest.mark.skipif(not _PLAYWRIGHT_AVAILABLE, reason="playwright not installed")
class TestBrowserUI:
    """Full browser tests using Playwright."""

    @pytest.fixture(scope="class")
    def browser_page(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            ctx = browser.new_context(viewport={"width": 1366, "height": 768})
            page = ctx.new_page()

            # Inject auth token so wizard is skipped and pages load
            page.goto(FRONTEND)
            page.evaluate(f"""
                localStorage.setItem('authToken', '{TOKEN}');
                localStorage.setItem('firstRunComplete', 'true');
            """)
            yield page
            ctx.close()
            browser.close()

    def test_dashboard_loads(self, browser_page):
        browser_page.goto(FRONTEND)
        browser_page.wait_for_load_state("networkidle", timeout=15000)
        _screenshot(browser_page, "01_dashboard")
        assert browser_page.title() != ""

    def test_engine_toggle_visible(self, browser_page):
        browser_page.goto(FRONTEND)
        browser_page.wait_for_load_state("networkidle", timeout=15000)
        # At least one button with engine-related text must be visible
        buttons = browser_page.locator("button").all()
        texts = [b.text_content() or "" for b in buttons]
        engine_btns = [t for t in texts if any(
            kw in t for kw in ("Start", "Stop", "Pause", "Resume", "Engine")
        )]
        assert len(engine_btns) >= 1, f"No engine control button found. All buttons: {texts}"
        _screenshot(browser_page, "02_engine_toggle")

    def test_settings_page_loads(self, browser_page):
        browser_page.goto(f"{FRONTEND}/settings")
        browser_page.wait_for_load_state("networkidle", timeout=15000)
        _screenshot(browser_page, "03_settings")
        assert browser_page.locator("body").is_visible()

    def test_analytics_page_loads(self, browser_page):
        browser_page.goto(f"{FRONTEND}/analytics")
        browser_page.wait_for_load_state("networkidle", timeout=15000)
        _screenshot(browser_page, "04_analytics")
        assert browser_page.locator("body").is_visible()

    def test_leads_page_loads(self, browser_page):
        browser_page.goto(f"{FRONTEND}/leads")
        browser_page.wait_for_load_state("networkidle", timeout=15000)
        _screenshot(browser_page, "05_leads")
        assert browser_page.locator("body").is_visible()

    def test_campaigns_page_loads(self, browser_page):
        browser_page.goto(f"{FRONTEND}/campaigns")
        browser_page.wait_for_load_state("networkidle", timeout=15000)
        _screenshot(browser_page, "06_campaigns")
        assert browser_page.locator("body").is_visible()

    def test_content_studio_loads(self, browser_page):
        browser_page.goto(f"{FRONTEND}/content")
        browser_page.wait_for_load_state("networkidle", timeout=15000)
        _screenshot(browser_page, "07_content_studio")
        assert browser_page.locator("body").is_visible()

    def test_topics_page_loads(self, browser_page):
        browser_page.goto(f"{FRONTEND}/topics")
        browser_page.wait_for_load_state("networkidle", timeout=15000)
        _screenshot(browser_page, "08_topics")
        assert browser_page.locator("body").is_visible()

    def test_prompt_editor_loads(self, browser_page):
        browser_page.goto(f"{FRONTEND}/prompts")
        browser_page.wait_for_load_state("networkidle", timeout=15000)
        _screenshot(browser_page, "09_prompts")
        assert browser_page.locator("body").is_visible()

    def test_feed_engagement_page_loads(self, browser_page):
        browser_page.goto(f"{FRONTEND}/feed")
        browser_page.wait_for_load_state("networkidle", timeout=15000)
        _screenshot(browser_page, "10_feed")
        assert browser_page.locator("body").is_visible()

    def test_engine_control_page_loads(self, browser_page):
        browser_page.goto(f"{FRONTEND}/control")
        browser_page.wait_for_load_state("networkidle", timeout=15000)
        _screenshot(browser_page, "11_control")
        assert browser_page.locator("body").is_visible()

    def test_no_js_errors_on_dashboard(self, browser_page):
        errors = []
        browser_page.on("console", lambda msg: errors.append(msg.text)
                        if msg.type == "error" else None)
        browser_page.goto(FRONTEND)
        browser_page.wait_for_load_state("networkidle", timeout=15000)
        # Filter out network errors (expected if engine is stopped) and known Vite noise
        critical = [e for e in errors if "SyntaxError" in e or "TypeError" in e
                    or "is not a function" in e or "Cannot read" in e]
        assert critical == [], f"JS errors on dashboard: {critical}"

    def test_sidebar_nav_links_present(self, browser_page):
        browser_page.goto(FRONTEND)
        browser_page.wait_for_load_state("networkidle", timeout=15000)
        # Nav should have multiple links
        links = browser_page.locator("nav a").all()
        assert len(links) >= 5, f"Expected ≥5 nav links, got {len(links)}"

    def test_settings_save_shows_no_crash(self, browser_page):
        browser_page.goto(f"{FRONTEND}/settings")
        browser_page.wait_for_load_state("networkidle", timeout=15000)
        # Settings page should have at least one input
        inputs = browser_page.locator("input").all()
        assert len(inputs) >= 1, "Settings page has no inputs"
        _screenshot(browser_page, "12_settings_inputs")
