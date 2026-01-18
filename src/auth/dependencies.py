"""
Authentication dependencies for FastAPI routes
"""
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Optional
import uuid

from src.db.session import get_db
from src.db.models import User


async def get_current_user(
    user_id: Optional[str] = Header(None, alias="X-User-ID"),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from request headers
    
    This is a simplified version for development/testing.
    In production, this would validate a JWT token or session cookie.
    
    Args:
        user_id: User ID from X-User-ID header
        db: Database session
        
    Returns:
        User object
        
    Raises:
        HTTPException: If user is not authenticated or not found
    """
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated. X-User-ID header required."
        )
    
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


async def get_optional_user(
    user_id: Optional[str] = Header(None, alias="X-User-ID"),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get current user if authenticated, None otherwise
    
    Args:
        user_id: User ID from X-User-ID header
        db: Database session
        
    Returns:
        User object or None
    """
    if not user_id:
        return None
    
    try:
        user_uuid = uuid.UUID(user_id)
        user = db.query(User).filter(User.id == user_uuid).first()
        return user
    except (ValueError, Exception):
        return None
