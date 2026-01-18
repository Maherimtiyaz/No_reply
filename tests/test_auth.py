"""
Tests for authentication and OAuth functionality
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from src.auth.crypto import TokenEncryption, token_encryptor
from src.auth.oauth_service import OAuthService, oauth_service
from src.db.models import User, OAuthAccount, OAuthProvider


class TestTokenEncryption:
    """Test token encryption and decryption"""
    
    def test_encrypt_decrypt_token(self):
        """Test that tokens can be encrypted and decrypted"""
        encryptor = TokenEncryption()
        original_token = "test-access-token-123456"
        
        # Encrypt
        encrypted = encryptor.encrypt_token(original_token)
        assert encrypted != original_token
        assert len(encrypted) > 0
        
        # Decrypt
        decrypted = encryptor.decrypt_token(encrypted)
        assert decrypted == original_token
    
    def test_encrypt_empty_string(self):
        """Test encrypting empty string"""
        encryptor = TokenEncryption()
        encrypted = encryptor.encrypt_token("")
        assert encrypted == ""
        
        decrypted = encryptor.decrypt_token("")
        assert decrypted == ""
    
    def test_decrypt_invalid_token_raises_error(self):
        """Test that decrypting invalid token raises error"""
        encryptor = TokenEncryption()
        
        with pytest.raises(ValueError, match="Failed to decrypt token"):
            encryptor.decrypt_token("invalid-encrypted-token")
    
    def test_singleton_instance_works(self):
        """Test that singleton token_encryptor works"""
        original_token = "singleton-test-token"
        
        encrypted = token_encryptor.encrypt_token(original_token)
        decrypted = token_encryptor.decrypt_token(encrypted)
        
        assert decrypted == original_token


class TestOAuthService:
    """Test OAuth service functionality"""
    
    def test_get_authorization_url(self):
        """Test generating Google OAuth authorization URL"""
        service = OAuthService()
        
        auth_url, state = service.get_authorization_url()
        
        assert "https://accounts.google.com/o/oauth2" in auth_url
        assert "client_id" in auth_url
        assert "redirect_uri" in auth_url
        assert "scope" in auth_url
        assert len(state) > 0
    
    def test_get_authorization_url_with_custom_state(self):
        """Test authorization URL with custom state"""
        service = OAuthService()
        custom_state = "my-custom-state-123"
        
        auth_url, state = service.get_authorization_url(custom_state)
        
        assert state == custom_state
        assert custom_state in auth_url
    
    @patch('src.auth.oauth_service.Flow')
    def test_exchange_code_for_tokens(self, mock_flow_class):
        """Test exchanging authorization code for tokens"""
        service = OAuthService()
        
        # Mock credentials
        mock_credentials = Mock()
        mock_credentials.token = "access-token-123"
        mock_credentials.refresh_token = "refresh-token-456"
        mock_credentials.expiry = datetime.utcnow() + timedelta(hours=1)
        
        # Mock flow
        mock_flow = Mock()
        mock_flow.credentials = mock_credentials
        mock_flow_class.from_client_config.return_value = mock_flow
        
        # Mock user info service
        with patch('src.auth.oauth_service.build') as mock_build:
            mock_service = Mock()
            mock_userinfo = Mock()
            mock_userinfo.get.return_value.execute.return_value = {
                'email': 'test@example.com',
                'name': 'Test User',
                'id': 'google-id-123'
            }
            mock_service.userinfo.return_value = mock_userinfo
            mock_build.return_value = mock_service
            
            # Exchange code
            result = service.exchange_code_for_tokens("auth-code-123")
            
            assert result['access_token'] == "access-token-123"
            assert result['refresh_token'] == "refresh-token-456"
            assert result['user_info']['email'] == 'test@example.com'
            assert result['user_info']['google_id'] == 'google-id-123'
    
    def test_create_or_update_user_new_user(self, db_session):
        """Test creating a new user from OAuth data"""
        service = OAuthService()
        
        token_data = {
            'access_token': 'access-token-123',
            'refresh_token': 'refresh-token-456',
            'token_expiry': datetime.utcnow() + timedelta(hours=1),
            'user_info': {
                'email': 'newuser@example.com',
                'name': 'New User',
                'google_id': 'google-123'
            }
        }
        
        user, oauth_account = service.create_or_update_user(db_session, token_data)
        
        # Check user
        assert user.email == 'newuser@example.com'
        assert user.full_name == 'New User'
        
        # Check OAuth account
        assert oauth_account.user_id == user.id
        assert oauth_account.provider == OAuthProvider.GOOGLE
        assert oauth_account.provider_account_id == 'google-123'
        assert oauth_account.access_token is not None
        assert oauth_account.refresh_token is not None
        
        # Verify tokens are encrypted (not plain text)
        assert oauth_account.access_token != 'access-token-123'
        assert oauth_account.refresh_token != 'refresh-token-456'
    
    def test_create_or_update_user_existing_user(self, db_session):
        """Test updating an existing user's OAuth account"""
        service = OAuthService()
        
        # Create existing user
        existing_user = User(email='existing@example.com', full_name='Existing User')
        db_session.add(existing_user)
        db_session.commit()
        
        token_data = {
            'access_token': 'new-access-token',
            'refresh_token': 'new-refresh-token',
            'token_expiry': datetime.utcnow() + timedelta(hours=1),
            'user_info': {
                'email': 'existing@example.com',
                'name': 'Existing User Updated',
                'google_id': 'google-456'
            }
        }
        
        user, oauth_account = service.create_or_update_user(db_session, token_data)
        
        # Should return existing user
        assert user.id == existing_user.id
        assert user.email == 'existing@example.com'
        
        # Should create OAuth account
        assert oauth_account.user_id == user.id
        assert oauth_account.provider_account_id == 'google-456'
    
    @patch('google.auth.transport.requests.Request')
    @patch('src.auth.oauth_service.Credentials')
    def test_refresh_access_token(self, mock_credentials_class, mock_request, db_session):
        """Test refreshing an expired access token"""
        service = OAuthService()
        
        # Create user and OAuth account
        user = User(email='user@example.com', full_name='Test User')
        db_session.add(user)
        db_session.flush()
        
        # Encrypt tokens
        encrypted_access = token_encryptor.encrypt_token('old-access-token')
        encrypted_refresh = token_encryptor.encrypt_token('refresh-token-123')
        
        oauth_account = OAuthAccount(
            user_id=user.id,
            provider=OAuthProvider.GOOGLE,
            provider_account_id='google-789',
            access_token=encrypted_access,
            refresh_token=encrypted_refresh,
            token_expires_at=datetime.utcnow() - timedelta(minutes=10)  # Expired
        )
        db_session.add(oauth_account)
        db_session.commit()
        
        # Mock credentials refresh
        mock_credentials = Mock()
        mock_credentials.token = 'new-access-token'
        mock_credentials.expiry = datetime.utcnow() + timedelta(hours=1)
        mock_credentials.refresh_token = 'refresh-token-123'
        mock_credentials.refresh = Mock()  # Mock the refresh method
        mock_credentials_class.return_value = mock_credentials
        
        # Refresh token
        updated_account = service.refresh_access_token(db_session, oauth_account)
        
        # Verify token was updated
        assert updated_account.access_token != encrypted_access
        decrypted_new_token = token_encryptor.decrypt_token(updated_account.access_token)
        assert decrypted_new_token == 'new-access-token'
        assert updated_account.token_expires_at > datetime.utcnow()
    
    def test_refresh_access_token_no_refresh_token(self, db_session):
        """Test that refresh fails without refresh token"""
        service = OAuthService()
        
        # Create user and OAuth account without refresh token
        user = User(email='user@example.com')
        db_session.add(user)
        db_session.flush()
        
        oauth_account = OAuthAccount(
            user_id=user.id,
            provider=OAuthProvider.GOOGLE,
            provider_account_id='google-999',
            access_token=token_encryptor.encrypt_token('access-token'),
            refresh_token=None
        )
        db_session.add(oauth_account)
        db_session.commit()
        
        with pytest.raises(ValueError, match="No refresh token available"):
            service.refresh_access_token(db_session, oauth_account)
    
    def test_is_token_expired_expired(self, db_session):
        """Test checking if token is expired"""
        service = OAuthService()
        
        user = User(email='user@example.com')
        db_session.add(user)
        db_session.flush()
        
        # Create expired OAuth account
        oauth_account = OAuthAccount(
            user_id=user.id,
            provider=OAuthProvider.GOOGLE,
            provider_account_id='google-exp',
            access_token='token',
            token_expires_at=datetime.utcnow() - timedelta(minutes=10)
        )
        
        assert service.is_token_expired(oauth_account) is True
    
    def test_is_token_expired_valid(self, db_session):
        """Test checking if token is still valid"""
        service = OAuthService()
        
        user = User(email='user@example.com')
        db_session.add(user)
        db_session.flush()
        
        # Create valid OAuth account (expires in 1 hour)
        oauth_account = OAuthAccount(
            user_id=user.id,
            provider=OAuthProvider.GOOGLE,
            provider_account_id='google-valid',
            access_token='token',
            token_expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        
        assert service.is_token_expired(oauth_account) is False
    
    def test_is_token_expired_no_expiry(self, db_session):
        """Test token with no expiry is considered expired"""
        service = OAuthService()
        
        user = User(email='user@example.com')
        db_session.add(user)
        db_session.flush()
        
        oauth_account = OAuthAccount(
            user_id=user.id,
            provider=OAuthProvider.GOOGLE,
            provider_account_id='google-noexp',
            access_token='token',
            token_expires_at=None
        )
        
        assert service.is_token_expired(oauth_account) is True


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from src.db.base import Base
    
    # Create in-memory database
    engine = create_engine('sqlite:///:memory:', echo=False)
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()
