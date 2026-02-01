"""
API endpoints for transaction parsing.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

from src.db.session import get_db
from src.db.models import User, RawEmail, Transaction, EmailStatus
from src.auth.dependencies import get_current_user
from .parsing_engine import ParsingEngine
from .llm_service import LLMService, LLMProvider


router = APIRouter(prefix="/parse", tags=["parsing"])


# Request/Response Models
class ParseEmailRequest(BaseModel):
    """Request to parse a specific email"""
    email_id: str = Field(description="UUID of the raw email to parse")
    force_reparse: bool = Field(default=False, description="Force re-parsing even if already parsed")


class ParseBatchRequest(BaseModel):
    """Request to parse multiple emails"""
    email_ids: Optional[List[str]] = Field(default=None, description="List of email UUIDs (or None for all pending)")
    max_emails: int = Field(default=100, ge=1, le=500, description="Maximum emails to parse")
    confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0, description="Minimum confidence threshold")


class TransactionResponse(BaseModel):
    """Response model for a transaction"""
    id: str
    transaction_type: str
    amount: str
    currency: str
    merchant: Optional[str]
    description: Optional[str]
    transaction_date: str
    confidence_score: Optional[float]
    parsing_method: Optional[str]
    created_at: str
    
    class Config:
        from_attributes = True


class ParseEmailResponse(BaseModel):
    """Response from parsing a single email"""
    email_id: str
    status: str
    transaction: Optional[TransactionResponse]
    message: str


class ParseBatchResponse(BaseModel):
    """Response from batch parsing"""
    total: int
    success: int
    failed: int
    ignored: int
    transactions_created: int


class ParsingStatsResponse(BaseModel):
    """Parsing statistics for a user"""
    email_status: dict
    transactions_created: int
    parsing_status: dict


@router.post("/email", response_model=ParseEmailResponse)
async def parse_email(
    request: ParseEmailRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Parse a specific email to extract transaction information.
    
    Uses AI-powered parsing with rule-based fallback to extract
    financial transaction details from the email.
    
    Args:
        request: Parse request with email_id
        current_user: Authenticated user
        db: Database session
        
    Returns:
        Parsing result with transaction if successful
    """
    # Get the email
    email = db.query(RawEmail).filter(
        RawEmail.id == request.email_id,
        RawEmail.user_id == current_user.id
    ).first()
    
    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found"
        )
    
    # Check if already parsed
    if email.status == EmailStatus.PARSED and not request.force_reparse:
        # Return existing transaction
        existing_transaction = db.query(Transaction).filter(
            Transaction.raw_email_id == email.id
        ).first()
        
        if existing_transaction:
            return ParseEmailResponse(
                email_id=str(email.id),
                status=email.status.value,
                transaction=TransactionResponse(
                    id=str(existing_transaction.id),
                    transaction_type=existing_transaction.transaction_type.value,
                    amount=existing_transaction.amount,
                    currency=existing_transaction.currency,
                    merchant=existing_transaction.merchant,
                    description=existing_transaction.description,
                    transaction_date=existing_transaction.transaction_date.isoformat(),
                    confidence_score=existing_transaction.extra_metadata.get("confidence_score") if existing_transaction.extra_metadata else None,
                    parsing_method=existing_transaction.extra_metadata.get("parsing_method") if existing_transaction.extra_metadata else None,
                    created_at=existing_transaction.created_at.isoformat()
                ),
                message="Already parsed (from cache)"
            )
    
    # Initialize parsing engine
    # For now, use mock LLM. In production, configure with real API keys
    llm_service = LLMService(provider=LLMProvider.MOCK)
    engine = ParsingEngine(db, llm_service=llm_service)
    
    # Parse the email
    try:
        transaction = await engine.parse_email(email)
        
        if transaction:
            return ParseEmailResponse(
                email_id=str(email.id),
                status=email.status.value,
                transaction=TransactionResponse(
                    id=str(transaction.id),
                    transaction_type=transaction.transaction_type.value,
                    amount=transaction.amount,
                    currency=transaction.currency,
                    merchant=transaction.merchant,
                    description=transaction.description,
                    transaction_date=transaction.transaction_date.isoformat(),
                    confidence_score=transaction.extra_metadata.get("confidence_score") if transaction.extra_metadata else None,
                    parsing_method=transaction.extra_metadata.get("parsing_method") if transaction.extra_metadata else None,
                    created_at=transaction.created_at.isoformat()
                ),
                message="Successfully parsed"
            )
        else:
            return ParseEmailResponse(
                email_id=str(email.id),
                status=email.status.value,
                transaction=None,
                message="Not a transaction email" if email.status == EmailStatus.IGNORED else "Parsing failed"
            )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Parsing error: {str(e)}"
        )


@router.post("/batch", response_model=ParseBatchResponse)
async def parse_batch(
    request: ParseBatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Parse multiple emails in batch.
    
    Processes pending emails and extracts transactions using AI parsing
    with rule-based fallback.
    
    Args:
        request: Batch parse request
        current_user: Authenticated user
        db: Database session
        
    Returns:
        Batch parsing statistics
    """
    # Get emails to parse
    query = db.query(RawEmail).filter(RawEmail.user_id == current_user.id)
    
    if request.email_ids:
        # Parse specific emails
        query = query.filter(RawEmail.id.in_(request.email_ids))
    else:
        # Parse pending emails
        query = query.filter(RawEmail.status == EmailStatus.PENDING)
    
    emails = query.limit(request.max_emails).all()
    
    if not emails:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No emails found to parse"
        )
    
    # Initialize parsing engine
    llm_service = LLMService(provider=LLMProvider.MOCK)
    engine = ParsingEngine(
        db,
        llm_service=llm_service,
        confidence_threshold=request.confidence_threshold
    )
    
    # Parse batch
    try:
        results = await engine.batch_parse_emails(emails)
        return ParseBatchResponse(**results)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch parsing error: {str(e)}"
        )


@router.get("/stats", response_model=ParsingStatsResponse)
async def get_parsing_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get parsing statistics for the current user.
    
    Returns summary of email processing status, transactions created,
    and parsing success rates.
    """
    llm_service = LLMService(provider=LLMProvider.MOCK)
    engine = ParsingEngine(db, llm_service=llm_service)
    
    stats = engine.get_parsing_statistics(str(current_user.id))
    
    return ParsingStatsResponse(**stats)


@router.get("/transactions", response_model=List[TransactionResponse])
async def list_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all transactions for the current user.
    
    Returns parsed transactions with pagination.
    """
    transactions = db.query(Transaction).filter(
        Transaction.user_id == current_user.id
    ).order_by(
        Transaction.transaction_date.desc()
    ).offset(skip).limit(limit).all()
    
    return [
        TransactionResponse(
            id=str(t.id),
            transaction_type=t.transaction_type.value,
            amount=t.amount,
            currency=t.currency,
            merchant=t.merchant,
            description=t.description,
            transaction_date=t.transaction_date.isoformat(),
            confidence_score=t.extra_metadata.get("confidence_score") if t.extra_metadata else None,
            parsing_method=t.extra_metadata.get("parsing_method") if t.extra_metadata else None,
            created_at=t.created_at.isoformat()
        )
        for t in transactions
    ]
