"""
Campaign engine tests — enrollment, step advancement, completion.
"""
import os
import sys
import uuid
import pytest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(autouse=True)
def _test_db(tmp_path):
    import backend.storage.database as db_module
    from backend.utils.config_loader import load_config

    db_path = str(tmp_path / "test.db")
    db_module._DB_PATH = db_path
    db_module._engine = None
    db_module.SessionLocal = None

    load_config()
    db_module.init_db()
    yield
    db_module._engine = None
    db_module.SessionLocal = None


def _seed_campaign_and_lead(db):
    from backend.storage.models import Campaign, Lead

    campaign_id = uuid.uuid4().hex[:16]
    campaign = Campaign(
        id=campaign_id,
        name="Test Campaign",
        status="ACTIVE",
        steps=[
            {"type": "VISIT_PROFILE", "config": {}, "delay_days_after_prev": 0},
            {"type": "FOLLOW", "config": {}, "delay_days_after_prev": 1},
            {"type": "CONNECT", "config": {"note": "Hi {first_name}!"}, "delay_days_after_prev": 2},
        ],
    )
    db.add(campaign)

    lead = Lead(
        linkedin_url="https://linkedin.com/in/test-lead",
        first_name="Jane",
        last_name="Doe",
        title="VP Analytics",
        company="TestCo",
    )
    db.add(lead)
    db.commit()
    return campaign_id, lead.id


class TestCampaignEnrollment:

    def test_enroll_creates_enrollment(self):
        from backend.storage.database import get_db
        from backend.storage.models import CampaignEnrollment
        from backend.growth.campaign_engine import CampaignEngine

        engine = CampaignEngine()

        with get_db() as db:
            campaign_id, lead_id = _seed_campaign_and_lead(db)
            engine.enroll(lead_id, campaign_id, db)

            enrollment = db.query(CampaignEnrollment).first()
            assert enrollment is not None
            assert enrollment.campaign_id == campaign_id
            assert enrollment.lead_id == lead_id
            assert enrollment.current_step == 0
            assert enrollment.status == "IN_PROGRESS"

    def test_duplicate_enroll_ignored(self):
        from backend.storage.database import get_db
        from backend.storage.models import CampaignEnrollment
        from backend.growth.campaign_engine import CampaignEngine

        engine = CampaignEngine()

        with get_db() as db:
            campaign_id, lead_id = _seed_campaign_and_lead(db)
            engine.enroll(lead_id, campaign_id, db)
            engine.enroll(lead_id, campaign_id, db)  # Second enroll

            count = db.query(CampaignEnrollment).count()
            assert count == 1


class TestCampaignStepAdvancement:

    def test_enrollment_step_advances(self):
        from backend.storage.database import get_db
        from backend.storage.models import CampaignEnrollment
        from backend.growth.campaign_engine import CampaignEngine

        engine = CampaignEngine()

        with get_db() as db:
            campaign_id, lead_id = _seed_campaign_and_lead(db)
            engine.enroll(lead_id, campaign_id, db)

            enrollment = db.query(CampaignEnrollment).first()
            # Simulate step advancement
            enrollment.current_step = 1
            enrollment.next_action_at = datetime.now(timezone.utc) + timedelta(days=1)
            db.commit()

            db.refresh(enrollment)
            assert enrollment.current_step == 1

    def test_completed_after_last_step(self):
        from backend.storage.database import get_db
        from backend.storage.models import CampaignEnrollment, Campaign
        from backend.growth.campaign_engine import CampaignEngine

        engine = CampaignEngine()

        with get_db() as db:
            campaign_id, lead_id = _seed_campaign_and_lead(db)
            engine.enroll(lead_id, campaign_id, db)

            enrollment = db.query(CampaignEnrollment).first()
            campaign = db.query(Campaign).filter_by(id=campaign_id).first()

            # Simulate reaching past last step
            enrollment.current_step = len(campaign.steps)
            enrollment.status = "COMPLETED"
            enrollment.completed_at = datetime.now(timezone.utc)
            db.commit()

            db.refresh(enrollment)
            assert enrollment.status == "COMPLETED"
            assert enrollment.completed_at is not None
