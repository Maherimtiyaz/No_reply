"""
Gmail service for fetching and ingesting emails from Gmail API.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import base64
import email
from email.utils import parsedate_to_datetime

from src.db.models import User, OAuthAccount, RawEmail, OAuthProvider, EmailStatus
from src.auth.crypto import token_encryptor


class GmailService:
    """Service for interacting with Gmail API and ingesting emails"""
    
    def __init__(self, db: Session, user: User):
        """
        Initialize Gmail service for a specific user.
        
        Args:
            db: Database session
            user: User object
        """
        self.db = db
        self.user = user
        self._gmail_client = None
    
    def _get_credentials(self) -> Optional[Credentials]:
        """
        Get Google OAuth credentials for the user.
        
        Returns:
            Google Credentials object or None if not found
        """
        oauth_account = (
            self.db.query(OAuthAccount)
            .filter(
                OAuthAccount.user_id == self.user.id,
                OAuthAccount.provider == OAuthProvider.GOOGLE
            )
            .first()
        )
        
        if not oauth_account or not oauth_account.access_token:
            return None
        
        # Decrypt tokens
        access_token = token_encryptor.decrypt(oauth_account.access_token)
        refresh_token = None
        if oauth_account.refresh_token:
            refresh_token = token_encryptor.decrypt(oauth_account.refresh_token)
        
        # Create credentials object
        credentials = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=None,  # Not needed for API calls
            client_secret=None,
            scopes=['https://www.googleapis.com/auth/gmail.readonly']
        )
        
        return credentials
    
    def _get_gmail_client(self):
        """
        Get or create Gmail API client.
        
        Returns:
            Gmail API service object
            
        Raises:
            ValueError: If user doesn't have valid OAuth credentials
        """
        if self._gmail_client is None:
            credentials = self._get_credentials()
            if not credentials:
                raise ValueError("User does not have valid Google OAuth credentials")
            
            self._gmail_client = build('gmail', 'v1', credentials=credentials)
        
        return self._gmail_client
    
    def fetch_messages(
        self,
        query: str = "is:unread",
        max_results: int = 100,
        label_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch messages from Gmail matching the query.
        
        Args:
            query: Gmail search query (default: unread emails)
            max_results: Maximum number of messages to fetch
            label_ids: Optional list of label IDs to filter by
            
        Returns:
            List of message dictionaries with full details
            
        Raises:
            HttpError: If Gmail API request fails
        """
        try:
            gmail = self._get_gmail_client()
            
            # List messages matching query
            list_params = {
                'userId': 'me',
                'q': query,
                'maxResults': max_results
            }
            if label_ids:
                list_params['labelIds'] = label_ids
            
            results = gmail.users().messages().list(**list_params).execute()
            messages = results.get('messages', [])
            
            # Fetch full details for each message
            full_messages = []
            for msg in messages:
                msg_detail = gmail.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='raw'  # Get raw email content
                ).execute()
                full_messages.append(msg_detail)
            
            return full_messages
            
        except HttpError as error:
            print(f"An error occurred fetching messages: {error}")
            raise
    
    def _parse_raw_email(self, raw_message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse raw Gmail message into structured format.
        
        Args:
            raw_message: Raw message from Gmail API
            
        Returns:
            Dictionary with parsed email fields
        """
        # Decode the raw email
        raw_email = base64.urlsafe_b64decode(raw_message['raw'])
        email_message = email.message_from_bytes(raw_email)
        
        # Extract headers
        message_id = email_message.get('Message-ID', raw_message['id'])
        subject = email_message.get('Subject', '')
        sender = email_message.get('From', '')
        date_str = email_message.get('Date', '')
        
        # Parse date
        try:
            received_at = parsedate_to_datetime(date_str)
        except (TypeError, ValueError):
            received_at = datetime.utcnow()
        
        # Extract body
        body = ""
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    break
                elif part.get_content_type() == "text/html" and not body:
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
        else:
            body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
        
        return {
            'message_id': message_id,
            'subject': subject,
            'sender': sender,
            'received_at': received_at,
            'raw_body': body or str(email_message)
        }
    
    def ingest_email(self, raw_message: Dict[str, Any]) -> Optional[RawEmail]:
        """
        Ingest a single email into the database with deduplication.
        
        Args:
            raw_message: Raw message from Gmail API
            
        Returns:
            RawEmail object if created, None if duplicate
        """
        # Parse the message
        parsed = self._parse_raw_email(raw_message)
        
        # Check for duplicates using message_id
        existing = self.db.query(RawEmail).filter(
            RawEmail.message_id == parsed['message_id']
        ).first()
        
        if existing:
            print(f"Email with message_id {parsed['message_id']} already exists. Skipping.")
            return None
        
        # Create new RawEmail record
        raw_email = RawEmail(
            user_id=self.user.id,
            message_id=parsed['message_id'],
            subject=parsed['subject'],
            sender=parsed['sender'],
            received_at=parsed['received_at'],
            raw_body=parsed['raw_body'],
            status=EmailStatus.PENDING
        )
        
        self.db.add(raw_email)
        self.db.commit()
        self.db.refresh(raw_email)
        
        return raw_email
    
    def ingest_messages(
        self,
        query: str = "is:unread",
        max_results: int = 100,
        label_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Fetch and ingest multiple messages from Gmail.
        
        Args:
            query: Gmail search query
            max_results: Maximum number of messages to fetch
            label_ids: Optional list of label IDs to filter by
            
        Returns:
            Dictionary with ingestion statistics
        """
        messages = self.fetch_messages(query, max_results, label_ids)
        
        ingested_count = 0
        duplicate_count = 0
        error_count = 0
        
        for message in messages:
            try:
                result = self.ingest_email(message)
                if result:
                    ingested_count += 1
                else:
                    duplicate_count += 1
            except Exception as e:
                print(f"Error ingesting message: {e}")
                error_count += 1
        
        return {
            'fetched': len(messages),
            'ingested': ingested_count,
            'duplicates': duplicate_count,
            'errors': error_count
        }
