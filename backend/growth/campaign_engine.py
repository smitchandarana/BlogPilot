"""
Campaign Engine — Sprint 7.

Executes multi-step outreach sequences (campaigns) against enrolled leads.

Step types:
  VISIT_PROFILE | FOLLOW | CONNECT | MESSAGE | INMAIL | ENDORSE | WAIT

Each enrollment has a current_step index and a next_action_at timestamp.
process_due_enrollments() is called on a recurring schedule (every 30 min)
via APScheduler → worker pool.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Step type constants
STEP_VISIT = "VISIT_PROFILE"
STEP_FOLLOW = "FOLLOW"
STEP_CONNECT = "CONNECT"
STEP_MESSAGE = "MESSAGE"
STEP_INMAIL = "INMAIL"
STEP_ENDORSE = "ENDORSE"
STEP_WAIT = "WAIT"


class CampaignEngine:
    """
    Orchestrates campaign step execution for all enrolled leads.

    Dependencies are injected so the engine is testable without live Playwright.
    """

    def __init__(self, interaction_engine=None, note_writer=None, groq_client=None, prompt_loader=None):
        """
        Args:
            interaction_engine: InteractionEngine instance (or None for dry-run).
            note_writer:        NoteWriter module for auto-generating connect notes.
            groq_client:        GroqClient instance (needed by note_writer).
            prompt_loader:      PromptLoader instance (needed by note_writer).
        """
        self._ie = interaction_engine
        self._note_writer = note_writer
        self._groq = groq_client
        self._prompt_loader = prompt_loader

    # ── Public API ────────────────────────────────────────────────────────────

    def enroll(self, lead_id: str, campaign_id: str, db) -> None:
        """
        Enroll a lead in a campaign.

        Creates a CampaignEnrollment row (upsert — skip if already enrolled).
        Sets current_step=0, status=IN_PROGRESS, next_action_at=now.
        """
        from backend.storage.models import CampaignEnrollment, Campaign, Lead

        campaign = db.query(Campaign).filter_by(id=campaign_id).first()
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        lead = db.query(Lead).filter_by(id=lead_id).first()
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")

        existing = db.query(CampaignEnrollment).filter_by(
            campaign_id=campaign_id, lead_id=lead_id
        ).first()

        if existing:
            logger.debug(
                f"CampaignEngine: lead {lead_id} already enrolled in {campaign_id}"
            )
            return

        enrollment = CampaignEnrollment(
            campaign_id=campaign_id,
            lead_id=lead_id,
            status="IN_PROGRESS",
            current_step=0,
            next_action_at=datetime.now(timezone.utc),
        )
        db.add(enrollment)
        db.commit()
        logger.info(
            f"CampaignEngine: enrolled lead {lead_id} in campaign '{campaign.name}'"
        )

    async def process_due_enrollments(self, page) -> int:
        """
        Find all IN_PROGRESS enrollments whose next_action_at is due,
        and execute the next step for each.

        Returns the number of enrollments processed.
        """
        from backend.storage.database import get_db
        from backend.storage.models import CampaignEnrollment, Campaign

        now = datetime.now(timezone.utc)
        processed = 0

        with get_db() as db:
            due: List[CampaignEnrollment] = (
                db.query(CampaignEnrollment)
                .filter(
                    CampaignEnrollment.status == "IN_PROGRESS",
                    CampaignEnrollment.next_action_at <= now,
                )
                .all()
            )

            if not due:
                logger.debug("CampaignEngine: no due enrollments")
                return 0

            logger.info(f"CampaignEngine: {len(due)} enrollment(s) due for execution")

            for enrollment in due:
                try:
                    campaign = db.query(Campaign).filter_by(id=enrollment.campaign_id).first()
                    if not campaign or campaign.status != "ACTIVE":
                        continue

                    await self._execute_step(enrollment, campaign, page, db)
                    processed += 1

                except Exception as e:
                    logger.error(
                        f"CampaignEngine: error processing enrollment {enrollment.id} — {e}",
                        exc_info=True,
                    )
                    enrollment.status = "FAILED"
                    db.commit()

        return processed

    # ── Step execution ────────────────────────────────────────────────────────

    async def _execute_step(self, enrollment, campaign, page, db) -> None:
        """
        Execute the current step for an enrollment, then advance.
        """
        from backend.storage.models import Lead

        steps: List[dict] = campaign.steps or []

        if enrollment.current_step >= len(steps):
            # No more steps — mark complete
            enrollment.status = "COMPLETED"
            enrollment.completed_at = datetime.now(timezone.utc)
            db.commit()
            logger.info(
                f"CampaignEngine: enrollment {enrollment.id} completed (all steps done)"
            )
            return

        step = steps[enrollment.current_step]
        step_type: str = step.get("type", "").upper()
        step_config: dict = step.get("config", {})

        lead = db.query(Lead).filter_by(id=enrollment.lead_id).first()
        if not lead:
            enrollment.status = "FAILED"
            db.commit()
            return

        logger.info(
            f"CampaignEngine: enrollment {enrollment.id} — "
            f"step {enrollment.current_step} ({step_type}) for lead {lead.linkedin_url}"
        )

        if step_type == STEP_WAIT:
            # WAIT steps just advance the clock — no LinkedIn action
            success = True
        else:
            success = await self._execute_step_type(step_type, lead, step_config, page, db)

        # Advance to next step
        next_index = enrollment.current_step + 1
        delay_days = float(step_config.get("delay_days_after_prev", 1))

        if next_index >= len(steps):
            # Last step completed
            enrollment.status = "COMPLETED"
            enrollment.completed_at = datetime.now(timezone.utc)
            logger.info(f"CampaignEngine: enrollment {enrollment.id} completed")
        else:
            enrollment.current_step = next_index
            enrollment.next_action_at = datetime.now(timezone.utc) + timedelta(days=delay_days)
            if not success:
                logger.warning(
                    f"CampaignEngine: step {enrollment.current_step - 1} failed for "
                    f"enrollment {enrollment.id} — continuing to next step"
                )

        db.commit()

    async def _execute_step_type(
        self, step_type: str, lead, config: dict, page, db
    ) -> bool:
        """
        Dispatch to the correct interaction_engine method based on step type.
        Returns True on success, False on failure.
        """
        if self._ie is None:
            logger.debug(f"CampaignEngine: no interaction_engine — dry-running {step_type}")
            return True

        profile_url: str = lead.linkedin_url or ""

        try:
            if step_type == STEP_VISIT:
                from backend.automation.profile_scraper import ProfileScraper
                scraper = ProfileScraper()
                await scraper.scrape(page, profile_url, db=db)
                return True

            if step_type == STEP_FOLLOW:
                return await self._ie.follow(page, profile_url, db=db)

            if step_type == STEP_CONNECT:
                note = config.get("note_text") or await self._generate_note(lead)
                return await self._ie.connect_with(page, profile_url, note=note, db=db)

            if step_type == STEP_MESSAGE:
                message = config.get("message_text") or await self._generate_note(lead)
                return await self._ie.send_message(page, profile_url, message, db=db)

            if step_type == STEP_INMAIL:
                message = config.get("message_text") or await self._generate_note(lead)
                return await self._ie.send_message(page, profile_url, message, db=db)

            if step_type == STEP_ENDORSE:
                return await self._ie.endorse_skills(page, profile_url, db=db)

            logger.warning(f"CampaignEngine: unknown step type '{step_type}'")
            return False

        except Exception as e:
            logger.error(f"CampaignEngine: step {step_type} failed — {e}")
            return False

    async def _generate_note(self, lead) -> Optional[str]:
        """
        Use note_writer to auto-generate a personalised connection note.
        Falls back to None if AI is unavailable.
        """
        if not (self._note_writer and self._groq and self._prompt_loader):
            return None

        try:
            from backend.utils.config_loader import get as cfg_get
            topics = cfg_get("topics", [])
            if isinstance(topics, list):
                topics_str = ", ".join(str(t) for t in topics[:5])
            else:
                topics_str = str(topics)

            note = await self._note_writer.generate(
                first_name=lead.first_name or "",
                title=lead.title or "",
                company=lead.company or "",
                shared_context="LinkedIn engagement",
                topics=topics_str,
                groq_client=self._groq,
                prompt_loader=self._prompt_loader,
            )
            return note
        except Exception as e:
            logger.warning(f"CampaignEngine: note generation failed — {e}")
            return None


# ── Sync entry point for worker pool ─────────────────────────────────────────

def run_campaign_processing():
    """
    Sync entry point registered as PROCESS_CAMPAIGNS handler in worker_pool.
    Opens a browser session and calls process_due_enrollments().
    """
    logger.info("CampaignEngine: run_campaign_processing triggered")
    try:
        asyncio.run(_async_campaign_run())
    except Exception as e:
        logger.error(f"CampaignEngine: run failed — {e}", exc_info=True)


async def _async_campaign_run():
    """Async implementation: open browser, build engine, run due enrollments."""
    from backend.automation.browser import BrowserManager
    from backend.automation.linkedin_login import LinkedInLogin
    from backend.automation.interaction_engine import InteractionEngine
    from backend.core.engine import get_engine

    engine = get_engine()
    if engine:
        from backend.core.state_manager import EngineState
        if engine.state_manager.get() != EngineState.RUNNING:
            logger.info("CampaignEngine: engine not RUNNING — skipping")
            return

    cb = engine.circuit_breaker if engine else None
    ie = InteractionEngine(circuit_breaker=cb)

    campaign_engine = CampaignEngine(interaction_engine=ie)

    browser = BrowserManager()
    try:
        await browser.launch()
        page = await browser.get_page()

        login = LinkedInLogin()
        if not await login.is_logged_in(page):
            ok = await login.login(page)
            if not ok:
                logger.error("CampaignEngine: login failed — aborting")
                return

        count = await campaign_engine.process_due_enrollments(page)
        logger.info(f"CampaignEngine: processed {count} enrollment(s)")
    finally:
        await browser.close()
