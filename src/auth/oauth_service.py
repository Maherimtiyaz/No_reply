"""
OAuth service for handling Google OAuth flow and token management.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import uuid
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from config import settings
from src.db.models import User, OAuthAccount, OAuthProvider
from src.auth.crypto import token_encryptor


class OAuthService:
    """Handles OAuth authentication and token management"""
    
    # Google OAuth scopes
    SCOPES = [
        'openid',
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile',
        'https://www.googleapis.com/auth/gmail.readonly',
    ]
    
    def __init__(self):
        """Initialize OAuth service"""
        self.client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
        self.client_secret = getattr(settings, 'GOOGLE_CLIENT_SECRET', '')
        self.redirect_uri = getattr(settings, 'GOOGLE_REDIRECT_URI', 'http://localhost:8000/auth/google/callback')
    
    def get_authorization_url(self, state: Optional[str] = None) -> tuple[str, str]:
        """
        Generate Google OAuth authorization URL
        
        Args:
            state: Optional state parameter for CSRF protection
            
        Returns:
            Tuple of (authorization_url, state)
        """
        if not state:
            state = str(uuid.uuid4())
        
        flow = Flow.from_client_config(
            client_config={
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri],
                }
            },
            scopes=self.SCOPES,
            redirect_uri=self.redirect_uri
        )
        
        authorization_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=state,
            prompt='consent'  # Force consent to get refresh token
        )
        
        return authorization_url, state
    
    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access and refresh tokens
        
        Args:
            code: Authorization code from OAuth callback
            
        Returns:
            Dictionary containing token information
        """
        flow = Flow.from_client_config(
            client_config={
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri],
                }
            },
            scopes=self.SCOPES,
            redirect_uri=self.redirect_uri
        )
        
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        # Get user info
        user_info = self._get_user_info(credentials)
        
        return {
            'access_token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_expiry': credentials.expiry,
            'user_info': user_info
        }
    
    def _get_user_info(self, credentials: Credentials) -> Dict[str, Any]:
        """
        Get user information from Google
        
        Args:
            credentials: Google OAuth credentials
            
        Returns:
            Dictionary containing user information
        """
        service = build('oauth2', 'v2', credentials=credentials)
        user_info = service.userinfo().get().execute()
        
        return {
            'email': user_info.get('email'),
            'name': user_info.get('name'),
            'google_id': user_info.get('id'),
        }
    
    def create_or_update_user(
        self,
        db: Session,
        token_data: Dict[str, Any]
    ) -> tuple[User, OAuthAccount]:
        """
        Create or update user and OAuth account from token data
        
        Args:
            db: Database session
            token_data: Token data from OAuth exchange
            
        Returns:
            Tuple of (User, OAuthAccount)
        """
        user_info = token_data['user_info']
        email = user_info['email']
        google_id = user_info['google_id']
        
        # Find or create user
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email,
                full_name=user_info.get('name')
            )
            db.add(user)
            db.flush()  # Get user.id
        
        # Encrypt tokens
        encrypted_access = token_encryptor.encrypt_token(token_data['access_token'])
        encrypted_refresh = token_encryptor.encrypt_token(token_data['refresh_token']) if token_data.get('refresh_token') else None
        
        # Find or create OAuth account
        oauth_account = db.query(OAuthAccount).filter(
            OAuthAccount.user_id == user.id,
            OAuthAccount.provider == OAuthProvider.GOOGLE
        ).first()
        
        if oauth_account:
            # Update existing account
            oauth_account.provider_account_id = google_id
            oauth_account.access_token = encrypted_access
            oauth_account.refresh_token = encrypted_refresh
            oauth_account.token_expires_at = token_data.get('token_expiry')
        else:
            # Create new OAuth account
            oauth_account = OAuthAccount(
                user_id=user.id,
                provider=OAuthProvider.GOOGLE,
                provider_account_id=google_id,
                access_token=encrypted_access,
                refresh_token=encrypted_refresh,
                token_expires_at=token_data.get('token_expiry')
            )
            db.add(oauth_account)
        
        db.commit()
        db.refresh(user)
        db.refresh(oauth_account)
        
        return user, oauth_account
    
    def refresh_access_token(
        self,
        db: Session,
        oauth_account: OAuthAccount
    ) -> OAuthAccount:
        """
        Refresh an expired access token using refresh token
        
        Args:
            db: Database session
            oauth_account: OAuth account with refresh token
            
        Returns:
            Updated OAuth account with new access token
        """
        if not oauth_account.refresh_token:
            raise ValueError("No refresh token available")
        
        # Decrypt refresh token
        refresh_token = token_encryptor.decrypt_token(oauth_account.refresh_token)
        
        # Create credentials with refresh token
        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret
        )
        
        # Refresh the token
        from google.auth.transport.requests import Request
        credentials.refresh(Request())
        
        # Encrypt and update access token
        encrypted_access = token_encryptor.encrypt_token(credentials.token)
        oauth_account.access_token = encrypted_access
        oauth_account.token_expires_at = credentials.expiry
        
        db.commit()
        db.refresh(oauth_account)
        
        return oauth_account
    
    def is_token_expired(self, oauth_account: OAuthAccount) -> bool:
        """
        Check if access token is expired
        
        Args:
            oauth_account: OAuth account to check
            
        Returns:
            True if token is expired or will expire in next 5 minutes
        """
        if not oauth_account.token_expires_at:
            return True
        
        # Consider token expired if it expires in the next 5 minutes
        buffer = timedelta(minutes=5)
        return datetime.utcnow() + buffer >= oauth_account.token_expires_at
    
    def get_valid_credentials(
        self,
        db: Session,
        oauth_account: OAuthAccount
    ) -> Credentials:
        """
        Get valid credentials, refreshing if necessary
        
        Args:
            db: Database session
            oauth_account: OAuth account
            
        Returns:
            Valid Google OAuth credentials
        """
        # Refresh token if expired
        if self.is_token_expired(oauth_account):
            oauth_account = self.refresh_access_token(db, oauth_account)
        
        # Decrypt access token
        access_token = token_encryptor.decrypt_token(oauth_account.access_token)
        
        # Create credentials object
        credentials = Credentials(
            token=access_token,
            refresh_token=token_encryptor.decrypt_token(oauth_account.refresh_token) if oauth_account.refresh_token else None,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret
        )
        
        return credentials


# Singleton instance
oauth_service = OAuthService()
