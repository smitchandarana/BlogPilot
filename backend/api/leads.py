from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import Response
from pydantic import BaseModel
from backend.utils.logger import get_logger
from backend.storage.database import get_db
import backend.storage.leads_store as leads_store

logger = get_logger(__name__)
router = APIRouter()


@router.get("")
async def list_leads(
    status: Optional[str] = None,
    company: Optional[str] = None,
    search: Optional[str] = None,
):
    filters = {}
    if status:
        filters["email_status"] = status
    if company:
        filters["company"] = company
    if search:
        filters["search"] = search

    with get_db() as db:
        leads = leads_store.get_all(db, filters=filters)
        return [
            {
                "id": l.id,
                "first_name": l.first_name,
                "last_name": l.last_name,
                "title": l.title,
                "company": l.company,
                "linkedin_url": l.linkedin_url,
                "email": l.email,
                "email_status": l.email_status,
                "email_method": l.email_method,
                "source": l.source,
                "created_at": str(l.created_at),
            }
            for l in leads
        ]


@router.get("/export")
async def export_leads():
    with get_db() as db:
        all_leads = leads_store.get_all(db)
        csv_content = leads_store.to_csv(all_leads)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads.csv"},
    )


@router.get("/{lead_id}")
async def get_lead(lead_id: str):
    with get_db() as db:
        lead = leads_store.get_by_id(lead_id, db)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        return {
            "id": lead.id,
            "first_name": lead.first_name,
            "last_name": lead.last_name,
            "title": lead.title,
            "company": lead.company,
            "company_domain": lead.company_domain,
            "linkedin_url": lead.linkedin_url,
            "email": lead.email,
            "email_status": lead.email_status,
            "email_method": lead.email_method,
            "connection_degree": lead.connection_degree,
            "source": lead.source,
        }


@router.post("/{lead_id}/enrich")
async def enrich_lead(lead_id: str, background_tasks: BackgroundTasks):
    with get_db() as db:
        lead = leads_store.get_by_id(lead_id, db)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
    # TODO: trigger actual enrichment in Sprint 6
    logger.info(f"Enrichment requested for lead {lead_id}")
    return {"lead_id": lead_id, "status": "enrichment_queued"}


@router.post("/enrich-all")
async def enrich_all_leads(background_tasks: BackgroundTasks):
    # TODO: trigger bulk enrichment in Sprint 6
    logger.info("Bulk enrichment requested")
    return {"status": "bulk_enrichment_queued"}
