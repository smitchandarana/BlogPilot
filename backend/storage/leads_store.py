import csv
import io
import hashlib
from typing import Optional, List
from sqlalchemy.orm import Session

from backend.storage.models import Lead
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def create_lead(data: dict, db: Session) -> Lead:
    linkedin_url = data.get("linkedin_url", "")
    lead_id = hashlib.sha256(linkedin_url.encode()).hexdigest()

    existing = db.query(Lead).filter_by(id=lead_id).first()
    if existing:
        # Update fields that changed
        for k, v in data.items():
            if k != "linkedin_url" and v is not None:
                setattr(existing, k, v)
        db.commit()
        db.refresh(existing)
        return existing

    lead = Lead(linkedin_url=linkedin_url)
    for k, v in data.items():
        if k != "linkedin_url" and v is not None:
            setattr(lead, k, v)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    logger.info(f"Lead created: {lead.first_name} {lead.last_name} @ {lead.company}")
    return lead


def update_email(lead_id: str, email: str, status: str, method: str, db: Session) -> Optional[Lead]:
    lead = db.query(Lead).filter_by(id=lead_id).first()
    if not lead:
        return None
    lead.email = email
    lead.email_status = status
    lead.email_method = method
    db.commit()
    db.refresh(lead)
    logger.info(f"Lead email updated: {lead_id} → {email} ({status} via {method})")
    return lead


def get_all(db: Session, filters: Optional[dict] = None) -> List[Lead]:
    query = db.query(Lead)
    if filters:
        if filters.get("email_status"):
            query = query.filter(Lead.email_status == filters["email_status"])
        if filters.get("company"):
            query = query.filter(Lead.company.ilike(f"%{filters['company']}%"))
        if filters.get("search"):
            term = f"%{filters['search']}%"
            query = query.filter(
                Lead.first_name.ilike(term)
                | Lead.last_name.ilike(term)
                | Lead.company.ilike(term)
            )
    return query.order_by(Lead.created_at.desc()).all()


def get_by_id(lead_id: str, db: Session) -> Optional[Lead]:
    return db.query(Lead).filter_by(id=lead_id).first()


def to_csv(leads: List[Lead]) -> str:
    output = io.StringIO()
    fieldnames = [
        "first_name", "last_name", "title", "company", "company_domain",
        "linkedin_url", "email", "email_status", "email_method",
        "connection_degree", "source", "created_at",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for lead in leads:
        writer.writerow({
            "first_name": lead.first_name or "",
            "last_name": lead.last_name or "",
            "title": lead.title or "",
            "company": lead.company or "",
            "company_domain": lead.company_domain or "",
            "linkedin_url": lead.linkedin_url or "",
            "email": lead.email or "",
            "email_status": lead.email_status or "",
            "email_method": lead.email_method or "",
            "connection_degree": lead.connection_degree or "",
            "source": lead.source or "",
            "created_at": str(lead.created_at) if lead.created_at else "",
        })
    return output.getvalue()
