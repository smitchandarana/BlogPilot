import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.utils.logger import get_logger
from backend.storage.database import get_db
from backend.storage.models import Campaign, CampaignEnrollment

logger = get_logger(__name__)
router = APIRouter()


class CampaignCreate(BaseModel):
    name: str
    steps: List[dict] = []


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    steps: Optional[List[dict]] = None


class EnrollRequest(BaseModel):
    lead_ids: List[str]


@router.get("")
async def list_campaigns():
    with get_db() as db:
        campaigns = db.query(Campaign).order_by(Campaign.created_at.desc()).all()
        return [
            {
                "id": c.id,
                "name": c.name,
                "status": c.status,
                "steps": c.steps,
                "created_at": str(c.created_at),
            }
            for c in campaigns
        ]


@router.post("")
async def create_campaign(body: CampaignCreate):
    with get_db() as db:
        campaign = Campaign(
            id=str(uuid.uuid4()),
            name=body.name,
            steps=body.steps,
            status="ACTIVE",
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        return {"id": campaign.id, "name": campaign.name, "status": campaign.status}


@router.get("/{campaign_id}")
async def get_campaign(campaign_id: str):
    with get_db() as db:
        campaign = db.query(Campaign).filter_by(id=campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        return {"id": campaign.id, "name": campaign.name, "status": campaign.status, "steps": campaign.steps}


@router.put("/{campaign_id}")
async def update_campaign(campaign_id: str, body: CampaignUpdate):
    with get_db() as db:
        campaign = db.query(Campaign).filter_by(id=campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if body.name is not None:
            campaign.name = body.name
        if body.status is not None:
            campaign.status = body.status
        if body.steps is not None:
            campaign.steps = body.steps
        db.commit()
        return {"id": campaign.id, "name": campaign.name, "status": campaign.status}


@router.delete("/{campaign_id}")
async def delete_campaign(campaign_id: str):
    with get_db() as db:
        campaign = db.query(Campaign).filter_by(id=campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        db.delete(campaign)
        db.commit()
        return {"deleted": campaign_id}


@router.post("/{campaign_id}/enroll")
async def enroll_leads(campaign_id: str, body: EnrollRequest):
    with get_db() as db:
        campaign = db.query(Campaign).filter_by(id=campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        enrolled = []
        for lead_id in body.lead_ids:
            existing = db.query(CampaignEnrollment).filter_by(
                campaign_id=campaign_id, lead_id=lead_id
            ).first()
            if not existing:
                enrollment = CampaignEnrollment(
                    campaign_id=campaign_id, lead_id=lead_id
                )
                db.add(enrollment)
                enrolled.append(lead_id)
        db.commit()
        return {"enrolled": len(enrolled), "lead_ids": enrolled}


@router.get("/{campaign_id}/stats")
async def campaign_stats(campaign_id: str):
    with get_db() as db:
        total = db.query(CampaignEnrollment).filter_by(campaign_id=campaign_id).count()
        in_progress = db.query(CampaignEnrollment).filter_by(
            campaign_id=campaign_id, status="IN_PROGRESS"
        ).count()
        completed = db.query(CampaignEnrollment).filter_by(
            campaign_id=campaign_id, status="COMPLETED"
        ).count()
        return {
            "enrolled": total,
            "in_progress": in_progress,
            "completed": completed,
            "reply_rate": 0.0,
        }
