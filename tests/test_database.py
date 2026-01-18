import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.db.base import Base
from src.db.models import (
    User, OAuthAccount, RawEmail, Transaction, ParsingLog,
    OAuthProvider, EmailStatus, TransactionType, ParsingStatus
)


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


class TestUserModel:
    """Test User model CRUD operations"""
    
    def test_create_user(self, db_session):
        """Test creating a user"""
        user = User(
            email="test@example.com",
            full_name="Test User"
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.created_at is not None
        assert user.updated_at is not None
        assert user.is_deleted is False
        assert user.deleted_at is None
    
    def test_read_user(self, db_session):
        """Test reading a user"""
        user = User(email="read@example.com", full_name="Read User")
        db_session.add(user)
        db_session.commit()
        
        fetched_user = db_session.query(User).filter(User.email == "read@example.com").first()
        assert fetched_user is not None
        assert fetched_user.email == "read@example.com"
    
    def test_update_user(self, db_session):
        """Test updating a user"""
        user = User(email="update@example.com", full_name="Old Name")
        db_session.add(user)
        db_session.commit()
        
        user.full_name = "New Name"
        db_session.commit()
        db_session.refresh(user)
        
        assert user.full_name == "New Name"
    
    def test_soft_delete_user(self, db_session):
        """Test soft deleting a user"""
        user = User(email="delete@example.com", full_name="Delete User")
        db_session.add(user)
        db_session.commit()
        
        user.is_deleted = True
        user.deleted_at = datetime.utcnow()
        db_session.commit()
        
        assert user.is_deleted is True
        assert user.deleted_at is not None


class TestOAuthAccountModel:
    """Test OAuthAccount model"""
    
    def test_create_oauth_account(self, db_session):
        """Test creating an OAuth account"""
        user = User(email="oauth@example.com", full_name="OAuth User")
        db_session.add(user)
        db_session.commit()
        
        oauth_account = OAuthAccount(
            user_id=user.id,
            provider=OAuthProvider.GOOGLE,
            provider_account_id="google_12345",
            access_token="access_token_value",
            refresh_token="refresh_token_value"
        )
        db_session.add(oauth_account)
        db_session.commit()
        db_session.refresh(oauth_account)
        
        assert oauth_account.id is not None
        assert oauth_account.user_id == user.id
        assert oauth_account.provider == OAuthProvider.GOOGLE
        assert oauth_account.provider_account_id == "google_12345"
    
    def test_oauth_user_relationship(self, db_session):
        """Test OAuth account to user relationship"""
        user = User(email="relation@example.com", full_name="Relation User")
        db_session.add(user)
        db_session.commit()
        
        oauth_account = OAuthAccount(
            user_id=user.id,
            provider=OAuthProvider.MICROSOFT,
            provider_account_id="ms_67890"
        )
        db_session.add(oauth_account)
        db_session.commit()
        
        # Test relationship
        fetched_oauth = db_session.query(OAuthAccount).filter(
            OAuthAccount.provider_account_id == "ms_67890"
        ).first()
        assert fetched_oauth.user.email == "relation@example.com"


class TestRawEmailModel:
    """Test RawEmail model"""
    
    def test_create_raw_email(self, db_session):
        """Test creating a raw email"""
        user = User(email="email@example.com", full_name="Email User")
        db_session.add(user)
        db_session.commit()
        
        raw_email = RawEmail(
            user_id=user.id,
            message_id="msg_12345",
            subject="Test Email",
            sender="sender@example.com",
            received_at=datetime.utcnow(),
            raw_body="This is the email body",
            status=EmailStatus.PENDING
        )
        db_session.add(raw_email)
        db_session.commit()
        db_session.refresh(raw_email)
        
        assert raw_email.id is not None
        assert raw_email.message_id == "msg_12345"
        assert raw_email.status == EmailStatus.PENDING
    
    def test_email_status_update(self, db_session):
        """Test updating email status"""
        user = User(email="status@example.com")
        db_session.add(user)
        db_session.commit()
        
        raw_email = RawEmail(
            user_id=user.id,
            message_id="msg_status",
            sender="sender@test.com",
            received_at=datetime.utcnow(),
            raw_body="Body",
            status=EmailStatus.PENDING
        )
        db_session.add(raw_email)
        db_session.commit()
        
        raw_email.status = EmailStatus.PARSED
        db_session.commit()
        
        fetched = db_session.query(RawEmail).filter(RawEmail.message_id == "msg_status").first()
        assert fetched.status == EmailStatus.PARSED


class TestTransactionModel:
    """Test Transaction model"""
    
    def test_create_transaction(self, db_session):
        """Test creating a transaction"""
        user = User(email="trans@example.com")
        db_session.add(user)
        db_session.commit()
        
        raw_email = RawEmail(
            user_id=user.id,
            message_id="msg_trans",
            sender="bank@example.com",
            received_at=datetime.utcnow(),
            raw_body="Transaction email"
        )
        db_session.add(raw_email)
        db_session.commit()
        
        transaction = Transaction(
            user_id=user.id,
            raw_email_id=raw_email.id,
            transaction_type=TransactionType.DEBIT,
            amount="100.50",
            currency="USD",
            description="Purchase at Store",
            merchant="Test Store",
            transaction_date=datetime.utcnow(),
            extra_metadata={"category": "shopping"}
        )
        db_session.add(transaction)
        db_session.commit()
        db_session.refresh(transaction)
        
        assert transaction.id is not None
        assert transaction.amount == "100.50"
        assert transaction.transaction_type == TransactionType.DEBIT
        assert transaction.extra_metadata == {"category": "shopping"}
    
    def test_transaction_relationships(self, db_session):
        """Test transaction relationships"""
        user = User(email="rel@example.com")
        db_session.add(user)
        db_session.commit()
        
        raw_email = RawEmail(
            user_id=user.id,
            message_id="msg_rel",
            sender="bank@example.com",
            received_at=datetime.utcnow(),
            raw_body="Email"
        )
        db_session.add(raw_email)
        db_session.commit()
        
        transaction = Transaction(
            user_id=user.id,
            raw_email_id=raw_email.id,
            transaction_type=TransactionType.CREDIT,
            amount="50.00",
            transaction_date=datetime.utcnow()
        )
        db_session.add(transaction)
        db_session.commit()
        
        # Test relationships
        fetched_trans = db_session.query(Transaction).first()
        assert fetched_trans.user.email == "rel@example.com"
        assert fetched_trans.raw_email.message_id == "msg_rel"


class TestParsingLogModel:
    """Test ParsingLog model"""
    
    def test_create_parsing_log(self, db_session):
        """Test creating a parsing log"""
        user = User(email="log@example.com")
        db_session.add(user)
        db_session.commit()
        
        raw_email = RawEmail(
            user_id=user.id,
            message_id="msg_log",
            sender="sender@example.com",
            received_at=datetime.utcnow(),
            raw_body="Body"
        )
        db_session.add(raw_email)
        db_session.commit()
        
        parsing_log = ParsingLog(
            raw_email_id=raw_email.id,
            status=ParsingStatus.SUCCESS,
            parsed_data={"amount": "100", "merchant": "Store"}
        )
        db_session.add(parsing_log)
        db_session.commit()
        db_session.refresh(parsing_log)
        
        assert parsing_log.id is not None
        assert parsing_log.status == ParsingStatus.SUCCESS
        assert parsing_log.parsed_data["amount"] == "100"
    
    def test_parsing_log_with_error(self, db_session):
        """Test parsing log with error"""
        user = User(email="error@example.com")
        db_session.add(user)
        db_session.commit()
        
        raw_email = RawEmail(
            user_id=user.id,
            message_id="msg_error",
            sender="sender@example.com",
            received_at=datetime.utcnow(),
            raw_body="Body"
        )
        db_session.add(raw_email)
        db_session.commit()
        
        parsing_log = ParsingLog(
            raw_email_id=raw_email.id,
            status=ParsingStatus.FAILED,
            error_message="Unable to parse amount"
        )
        db_session.add(parsing_log)
        db_session.commit()
        
        fetched = db_session.query(ParsingLog).first()
        assert fetched.status == ParsingStatus.FAILED
        assert "Unable to parse amount" in fetched.error_message


class TestDatabaseSchema:
    """Test database schema constraints"""
    
    def test_user_email_unique(self, db_session):
        """Test that user email must be unique"""
        user1 = User(email="unique@example.com", full_name="User 1")
        db_session.add(user1)
        db_session.commit()
        
        user2 = User(email="unique@example.com", full_name="User 2")
        db_session.add(user2)
        
        with pytest.raises(Exception):  # SQLAlchemy will raise IntegrityError
            db_session.commit()
    
    def test_message_id_unique(self, db_session):
        """Test that message_id must be unique"""
        user = User(email="msgid@example.com")
        db_session.add(user)
        db_session.commit()
        
        email1 = RawEmail(
            user_id=user.id,
            message_id="unique_msg_id",
            sender="sender1@example.com",
            received_at=datetime.utcnow(),
            raw_body="Body 1"
        )
        db_session.add(email1)
        db_session.commit()
        
        email2 = RawEmail(
            user_id=user.id,
            message_id="unique_msg_id",
            sender="sender2@example.com",
            received_at=datetime.utcnow(),
            raw_body="Body 2"
        )
        db_session.add(email2)
        
        with pytest.raises(Exception):
            db_session.commit()
