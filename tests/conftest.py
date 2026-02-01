"""
Shared pytest fixtures for all tests.
"""
import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.db.base import Base
from src.db.models import User, OAuthAccount, OAuthProvider
from src.auth.crypto import token_encryptor


# Test database URL (using SQLite for testing)
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def db_engine():
    """Create a test database engine"""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a test database session"""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def test_user(db_session):
    """Create a test user with OAuth account"""
    user = User(
        email="test@example.com",
        full_name="Test User"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    # Create OAuth account with encrypted tokens
    access_token = token_encryptor.encrypt_token("test_access_token")
    refresh_token = token_encryptor.encrypt_token("test_refresh_token")
    
    oauth_account = OAuthAccount(
        user_id=user.id,
        provider=OAuthProvider.GOOGLE,
        provider_account_id="google_123",
        access_token=access_token,
        refresh_token=refresh_token,
        token_expires_at=datetime(2025, 12, 31)
    )
    db_session.add(oauth_account)
    db_session.commit()
    
    return user
