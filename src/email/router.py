"""
Email ingestion API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel, Field

from src.db.session import get_db
from src.db.models import User, RawEmail
from src.auth.dependencies import get_current_user
from src.email.gmail_service import GmailService


router = APIRouter(prefix="/emails", tags=["emails"])


# Request/Response Models
class IngestEmailsRequest(BaseModel):
    """Request model for email ingestion"""
    query: str = Field(default="is:unread", description="Gmail search query")
    max_results: int = Field(default=100, ge=1, le=500, description="Maximum number of emails to fetch")
    label_ids: Optional[List[str]] = Field(default=None, description="Optional Gmail label IDs to filter by")


class IngestEmailsResponse(BaseModel):
    """Response model for email ingestion"""
    fetched: int = Field(description="Number of emails fetched from Gmail")
    ingested: int = Field(description="Number of new emails ingested")
    duplicates: int = Field(description="Number of duplicate emails skipped")
    errors: int = Field(description="Number of errors encountered")


class RawEmailResponse(BaseModel):
    """Response model for a single raw email"""
    id: str
    message_id: str
    subject: Optional[str]
    sender: str
    received_at: str
    status: str
    created_at: str
    
    class Config:
        from_attributes = True


class EmailListResponse(BaseModel):
    """Response model for list of emails"""
    total: int
    emails: List[RawEmailResponse]


@router.post("/ingest", response_model=IngestEmailsResponse)
async def ingest_emails(
    request: IngestEmailsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Ingest emails from user's Gmail account.
    
    Fetches emails matching the query and stores them in the database.
    Automatically handles deduplication based on message_id.
    
    Args:
        request: Ingestion parameters (query, max_results, label_ids)
        current_user: Authenticated user
        db: Database session
        
    Returns:
        Statistics about the ingestion process
        
    Raises:
        HTTPException: If Gmail API access fails or user lacks OAuth credentials
    """
    try:
        gmail_service = GmailService(db, current_user)
        
        result = gmail_service.ingest_messages(
            query=request.query,
            max_results=request.max_results,
            label_ids=request.label_ids
        )
        
        return IngestEmailsResponse(**result)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest emails: {str(e)}"
        )


@router.get("/", response_model=EmailListResponse)
async def list_emails(
    skip: int = 0,
    limit: int = 50,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List emails for the current user.
    
    Args:
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
        status_filter: Optional filter by email status
        current_user: Authenticated user
        db: Database session
        
    Returns:
        List of raw emails with total count
    """
    query = db.query(RawEmail).filter(RawEmail.user_id == current_user.id)
    
    if status_filter:
        query = query.filter(RawEmail.status == status_filter)
    
    total = query.count()
    emails = query.order_by(RawEmail.received_at.desc()).offset(skip).limit(limit).all()
    
    return EmailListResponse(
        total=total,
        emails=[
            RawEmailResponse(
                id=str(email.id),
                message_id=email.message_id,
                subject=email.subject,
                sender=email.sender,
                received_at=email.received_at.isoformat(),
                status=email.status.value,
                created_at=email.created_at.isoformat()
            )
            for email in emails
        ]
    )


@router.get("/{email_id}", response_model=RawEmailResponse)
async def get_email(
    email_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific email by ID.
    
    Args:
        email_id: Email UUID
        current_user: Authenticated user
        db: Database session
        
    Returns:
        Raw email details
        
    Raises:
        HTTPException: If email not found or doesn't belong to user
    """
    email_obj = db.query(RawEmail).filter(
        RawEmail.id == email_id,
        RawEmail.user_id == current_user.id
    ).first()
    
    if not email_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found"
        )
    
    return RawEmailResponse(
        id=str(email_obj.id),
        message_id=email_obj.message_id,
        subject=email_obj.subject,
        sender=email_obj.sender,
        received_at=email_obj.received_at.isoformat(),
        status=email_obj.status.value,
        created_at=email_obj.created_at.isoformat()
    )
