"""
OAuth authentication routes
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from config import settings
from src.db.session import get_db
from src.auth.oauth_service import oauth_service
from src.auth.dependencies import get_current_user
from src.db.models import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/google/login")
async def google_login():
    """
    Initiate Google OAuth flow
    
    Returns redirect URL to Google's OAuth consent page
    """
    try:
        authorization_url, state = oauth_service.get_authorization_url()
        
        # In production, store state in session/redis for CSRF validation
        # For now, we'll include it in the URL
        return {
            "authorization_url": authorization_url,
            "state": state,
            "message": "Redirect user to authorization_url"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate authorization URL: {str(e)}")


@router.get("/google/callback")
async def google_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: Optional[str] = Query(None, description="State parameter for CSRF protection"),
    error: Optional[str] = Query(None, description="Error from OAuth provider"),
    db: Session = Depends(get_db)
):
    """
    Handle Google OAuth callback
    
    Exchange authorization code for tokens and create/update user
    """
    # Handle OAuth errors
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error: {error}")
    
    try:
        # Exchange code for tokens
        token_data = oauth_service.exchange_code_for_tokens(code)
        
        # Create or update user and OAuth account
        user, oauth_account = oauth_service.create_or_update_user(db, token_data)
        
        # In production, create a session token here
        # For now, return user info and redirect to frontend
        
        # Redirect to frontend with success
        redirect_url = f"{settings.FRONTEND_URL}/auth/success?user_id={user.id}&email={user.email}"
        return RedirectResponse(url=redirect_url)
        
    except Exception as e:
        # Log error and redirect to frontend with error
        error_url = f"{settings.FRONTEND_URL}/auth/error?message={str(e)}"
        return RedirectResponse(url=error_url)


@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user information
    
    This endpoint demonstrates authentication requirement.
    In production, this would be protected by session/JWT token.
    """
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None
    }


@router.post("/refresh-token")
async def refresh_token_endpoint(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    Refresh an expired OAuth access token
    
    Args:
        user_id: User ID to refresh token for
        
    Returns:
        Success message
    """
    from src.db.models import OAuthProvider, OAuthAccount
    import uuid
    
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    # Get user's OAuth account
    oauth_account = db.query(OAuthAccount).filter(
        OAuthAccount.user_id == user_uuid,
        OAuthAccount.provider == OAuthProvider.GOOGLE
    ).first()
    
    if not oauth_account:
        raise HTTPException(status_code=404, detail="OAuth account not found")
    
    try:
        # Refresh the access token
        updated_account = oauth_service.refresh_access_token(db, oauth_account)
        
        return {
            "message": "Token refreshed successfully",
            "expires_at": updated_account.token_expires_at.isoformat() if updated_account.token_expires_at else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh token: {str(e)}")


@router.get("/status")
async def auth_status():
    """
    Check authentication service status
    """
    google_client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
    google_client_secret = getattr(settings, 'GOOGLE_CLIENT_SECRET', '')
    has_credentials = bool(google_client_id and google_client_secret)
    
    return {
        "service": "authentication",
        "status": "configured" if has_credentials else "not_configured",
        "provider": "google",
        "has_credentials": has_credentials
    }
