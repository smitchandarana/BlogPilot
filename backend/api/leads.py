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

        # Build profile_data from lead record
        profile_data = {
            "first_name": lead.first_name,
            "last_name": lead.last_name,
            "company_domain": lead.company_domain,
            "connection_degree": lead.connection_degree,
            "linkedin_url": lead.linkedin_url,
        }

    async def _run_enrichment(profile_data: dict):
        try:
            from backend.enrichment.email_enricher import EmailEnricher
            enricher = EmailEnricher(page=None)  # No page — DOM scraper skipped
            result = await enricher.enrich(profile_data)
            logger.info(
                f"Enrichment complete for {lead_id}: "
                f"{result['status']} via {result.get('method')}"
            )
        except Exception as e:
            logger.error(f"Enrichment failed for {lead_id}: {e}")

    background_tasks.add_task(_run_enrichment, profile_data)
    logger.info(f"Enrichment queued for lead {lead_id}")
    return {"lead_id": lead_id, "status": "enrichment_queued"}


@router.post("/enrich-all")
async def enrich_all_leads(background_tasks: BackgroundTasks):
    with get_db() as db:
        # Get all leads with no email found yet
        leads_to_enrich = leads_store.get_all(
            db, filters={"email_status": "NOT_FOUND"}
        )
        # Also include leads with no status set
        leads_no_status = [
            l for l in leads_store.get_all(db)
            if not l.email_status or l.email_status == "NOT_FOUND"
        ]
        # Deduplicate
        seen_ids = set()
        all_leads = []
        for l in leads_to_enrich + leads_no_status:
            if l.id not in seen_ids:
                seen_ids.add(l.id)
                all_leads.append(l)

        profiles = [
            {
                "first_name": l.first_name,
                "last_name": l.last_name,
                "company_domain": l.company_domain,
                "connection_degree": l.connection_degree,
                "linkedin_url": l.linkedin_url,
            }
            for l in all_leads
        ]

    async def _run_bulk(profiles):
        from backend.enrichment.email_enricher import EmailEnricher
        enricher = EmailEnricher(page=None)
        for profile_data in profiles:
            try:
                await enricher.enrich(profile_data)
            except Exception as e:
                logger.warning(f"Bulk enrich error: {e}")

    if profiles:
        background_tasks.add_task(_run_bulk, profiles)

    logger.info(f"Bulk enrichment queued: {len(profiles)} leads")
    return {"status": "bulk_enrichment_queued", "queued": len(profiles)}
