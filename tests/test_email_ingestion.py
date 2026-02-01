"""
Tests for email ingestion functionality including deduplication and persistence.
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
import base64
import email
from email.mime.text import MIMEText

from src.db.models import User, OAuthAccount, RawEmail, OAuthProvider, EmailStatus
from src.email.gmail_service import GmailService
from src.auth.crypto import token_encryptor


def create_mock_gmail_message(message_id: str, subject: str, sender: str, body: str) -> dict:
    """
    Create a mock Gmail API message in the expected format.
    
    Args:
        message_id: Unique message identifier
        subject: Email subject
        sender: Email sender
        body: Email body content
        
    Returns:
        Dictionary in Gmail API format with raw email
    """
    # Create a proper email message
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = 'recipient@example.com'
    msg['Date'] = 'Mon, 1 Jan 2024 12:00:00 +0000'
    msg['Message-ID'] = message_id
    
    # Encode as base64 (Gmail API format)
    raw_email = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
    
    return {
        'id': 'gmail_' + message_id.replace('<', '').replace('>', ''),
        'raw': raw_email
    }


class TestGmailService:
    """Test cases for GmailService"""
    
    def test_gmail_service_initialization(self, db_session: Session, test_user: User):
        """Test that GmailService initializes correctly"""
        service = GmailService(db_session, test_user)
        assert service.db == db_session
        assert service.user == test_user
        assert service._gmail_client is None
    
    def test_get_credentials_success(self, db_session: Session, test_user: User):
        """Test retrieving OAuth credentials for a user"""
        service = GmailService(db_session, test_user)
        credentials = service._get_credentials()
        
        assert credentials is not None
        assert credentials.token == "test_access_token"
        assert credentials.refresh_token == "test_refresh_token"
    
    def test_get_credentials_no_oauth_account(self, db_session: Session):
        """Test that None is returned when user has no OAuth account"""
        user = User(email="noauth@example.com", full_name="No Auth User")
        db_session.add(user)
        db_session.commit()
        
        service = GmailService(db_session, user)
        credentials = service._get_credentials()
        
        assert credentials is None
    
    @patch('src.email.gmail_service.build')
    def test_get_gmail_client_success(self, mock_build, db_session: Session, test_user: User):
        """Test Gmail client creation"""
        mock_gmail = Mock()
        mock_build.return_value = mock_gmail
        
        service = GmailService(db_session, test_user)
        client = service._get_gmail_client()
        
        assert client == mock_gmail
        mock_build.assert_called_once_with('gmail', 'v1', credentials=Mock)
    
    def test_get_gmail_client_no_credentials(self, db_session: Session):
        """Test that ValueError is raised when user has no credentials"""
        user = User(email="noauth@example.com", full_name="No Auth User")
        db_session.add(user)
        db_session.commit()
        
        service = GmailService(db_session, user)
        
        with pytest.raises(ValueError, match="does not have valid Google OAuth credentials"):
            service._get_gmail_client()
    
    def test_parse_raw_email(self, db_session: Session, test_user: User):
        """Test parsing raw Gmail message into structured format"""
        service = GmailService(db_session, test_user)
        
        mock_message = create_mock_gmail_message(
            message_id="<test123@example.com>",
            subject="Test Subject",
            sender="sender@example.com",
            body="This is a test email body."
        )
        
        parsed = service._parse_raw_email(mock_message)
        
        assert parsed['message_id'] == "<test123@example.com>"
        assert parsed['subject'] == "Test Subject"
        assert parsed['sender'] == "sender@example.com"
        assert "This is a test email body" in parsed['raw_body']
        assert isinstance(parsed['received_at'], datetime)
    
    @patch('src.email.gmail_service.build')
    def test_ingest_email_new(self, mock_build, db_session: Session, test_user: User):
        """Test ingesting a new email (not duplicate)"""
        mock_gmail = Mock()
        mock_build.return_value = mock_gmail
        
        service = GmailService(db_session, test_user)
        
        mock_message = create_mock_gmail_message(
            message_id="<unique123@example.com>",
            subject="New Email",
            sender="sender@example.com",
            body="This is a new email."
        )
        
        result = service.ingest_email(mock_message)
        
        assert result is not None
        assert isinstance(result, RawEmail)
        assert result.message_id == "<unique123@example.com>"
        assert result.subject == "New Email"
        assert result.sender == "sender@example.com"
        assert result.user_id == test_user.id
        assert result.status == EmailStatus.PENDING
        
        # Verify it's persisted in the database
        db_email = db_session.query(RawEmail).filter(
            RawEmail.message_id == "<unique123@example.com>"
        ).first()
        assert db_email is not None
        assert db_email.id == result.id
    
    @patch('src.email.gmail_service.build')
    def test_ingest_email_duplicate(self, mock_build, db_session: Session, test_user: User):
        """Test that duplicate emails are rejected"""
        mock_gmail = Mock()
        mock_build.return_value = mock_gmail
        
        service = GmailService(db_session, test_user)
        
        mock_message = create_mock_gmail_message(
            message_id="<duplicate123@example.com>",
            subject="Duplicate Email",
            sender="sender@example.com",
            body="This email will be duplicated."
        )
        
        # Ingest the email first time
        result1 = service.ingest_email(mock_message)
        assert result1 is not None
        
        # Try to ingest the same email again
        result2 = service.ingest_email(mock_message)
        assert result2 is None  # Should return None for duplicate
        
        # Verify only one email exists in database
        count = db_session.query(RawEmail).filter(
            RawEmail.message_id == "<duplicate123@example.com>"
        ).count()
        assert count == 1
    
    @patch('src.email.gmail_service.build')
    def test_ingest_multiple_emails_persistence(self, mock_build, db_session: Session, test_user: User):
        """Test that multiple different emails are all persisted correctly"""
        mock_gmail = Mock()
        mock_build.return_value = mock_gmail
        
        service = GmailService(db_session, test_user)
        
        # Create multiple different emails
        messages = [
            create_mock_gmail_message(f"<email{i}@example.com>", f"Subject {i}", 
                                     f"sender{i}@example.com", f"Body {i}")
            for i in range(5)
        ]
        
        # Ingest all emails
        results = []
        for msg in messages:
            result = service.ingest_email(msg)
            results.append(result)
        
        # Verify all were created
        assert all(r is not None for r in results)
        assert len(results) == 5
        
        # Verify all are in database
        db_count = db_session.query(RawEmail).filter(
            RawEmail.user_id == test_user.id
        ).count()
        assert db_count == 5
        
        # Verify each has unique message_id
        message_ids = [r.message_id for r in results]
        assert len(message_ids) == len(set(message_ids))  # All unique
    
    @patch('src.email.gmail_service.build')
    def test_fetch_messages(self, mock_build, db_session: Session, test_user: User):
        """Test fetching messages from Gmail API"""
        # Mock Gmail API responses
        mock_gmail = Mock()
        mock_users = Mock()
        mock_messages = Mock()
        mock_list = Mock()
        mock_get = Mock()
        
        mock_gmail.users.return_value = mock_users
        mock_users.messages.return_value = mock_messages
        mock_messages.list.return_value = mock_list
        mock_messages.get.return_value = mock_get
        
        # Mock list response
        mock_list.execute.return_value = {
            'messages': [
                {'id': 'msg1'},
                {'id': 'msg2'}
            ]
        }
        
        # Mock get responses
        mock_get.execute.side_effect = [
            create_mock_gmail_message("<msg1@example.com>", "Subject 1", "sender1@example.com", "Body 1"),
            create_mock_gmail_message("<msg2@example.com>", "Subject 2", "sender2@example.com", "Body 2")
        ]
        
        mock_build.return_value = mock_gmail
        
        service = GmailService(db_session, test_user)
        messages = service.fetch_messages(query="is:unread", max_results=10)
        
        assert len(messages) == 2
        assert messages[0]['id'] == 'gmail_msg1@example.com'
        assert messages[1]['id'] == 'gmail_msg2@example.com'
    
    @patch('src.email.gmail_service.build')
    def test_ingest_messages_with_statistics(self, mock_build, db_session: Session, test_user: User):
        """Test ingesting messages with proper statistics tracking"""
        # Mock Gmail API
        mock_gmail = Mock()
        mock_users = Mock()
        mock_messages = Mock()
        mock_list = Mock()
        mock_get = Mock()
        
        mock_gmail.users.return_value = mock_users
        mock_users.messages.return_value = mock_messages
        mock_messages.list.return_value = mock_list
        mock_messages.get.return_value = mock_get
        
        # Create 3 messages: 2 unique, 1 duplicate
        msg1 = create_mock_gmail_message("<unique1@example.com>", "Subject 1", "sender@example.com", "Body 1")
        msg2 = create_mock_gmail_message("<unique2@example.com>", "Subject 2", "sender@example.com", "Body 2")
        msg3 = create_mock_gmail_message("<unique1@example.com>", "Subject 1 Dup", "sender@example.com", "Body 1")
        
        mock_list.execute.return_value = {
            'messages': [
                {'id': 'msg1'},
                {'id': 'msg2'},
                {'id': 'msg3'}
            ]
        }
        
        mock_get.execute.side_effect = [msg1, msg2, msg3]
        mock_build.return_value = mock_gmail
        
        service = GmailService(db_session, test_user)
        stats = service.ingest_messages(query="is:unread", max_results=10)
        
        assert stats['fetched'] == 3
        assert stats['ingested'] == 2  # Only 2 unique emails
        assert stats['duplicates'] == 1  # 1 duplicate
        assert stats['errors'] == 0


class TestEmailIngestionAPI:
    """Test cases for email ingestion API endpoints"""
    
    @pytest.mark.asyncio
    async def test_ingest_emails_endpoint(self, client, test_user: User, db_session: Session):
        """Test the /emails/ingest endpoint"""
        # This would require mocking the Gmail API and authentication
        # Placeholder for integration test
        pass
    
    @pytest.mark.asyncio
    async def test_list_emails_endpoint(self, client, test_user: User, db_session: Session):
        """Test the /emails/ endpoint for listing emails"""
        # Placeholder for integration test
        pass
