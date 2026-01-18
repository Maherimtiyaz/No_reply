from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from .base import BaseModel


class User(BaseModel):
    """User accounts table"""
    __tablename__ = "users"
    
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    
    # Relationships
    oauth_accounts = relationship("OAuthAccount", back_populates="user")
    raw_emails = relationship("RawEmail", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")


class OAuthProvider(str, enum.Enum):
    """Supported OAuth providers"""
    GOOGLE = "google"
    MICROSOFT = "microsoft"


class OAuthAccount(BaseModel):
    """OAuth accounts linked to users"""
    __tablename__ = "oauth_accounts"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(SQLEnum(OAuthProvider), nullable=False)
    provider_account_id = Column(String(255), nullable=False)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="oauth_accounts")


class EmailStatus(str, enum.Enum):
    """Email processing status"""
    PENDING = "pending"
    PARSED = "parsed"
    FAILED = "failed"
    IGNORED = "ignored"


class RawEmail(BaseModel):
    """Raw emails fetched from user's mailbox"""
    __tablename__ = "raw_emails"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    message_id = Column(String(255), unique=True, nullable=False, index=True)
    subject = Column(String(500), nullable=True)
    sender = Column(String(255), nullable=False, index=True)
    received_at = Column(DateTime, nullable=False, index=True)
    raw_body = Column(Text, nullable=False)
    status = Column(SQLEnum(EmailStatus), default=EmailStatus.PENDING, nullable=False, index=True)
    
    # Relationships
    user = relationship("User", back_populates="raw_emails")
    transactions = relationship("Transaction", back_populates="raw_email")
    parsing_logs = relationship("ParsingLog", back_populates="raw_email")


class TransactionType(str, enum.Enum):
    """Transaction types"""
    DEBIT = "debit"
    CREDIT = "credit"


class Transaction(BaseModel):
    """Parsed financial transactions"""
    __tablename__ = "transactions"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    raw_email_id = Column(UUID(as_uuid=True), ForeignKey("raw_emails.id"), nullable=False, index=True)
    
    transaction_type = Column(SQLEnum(TransactionType), nullable=False, index=True)
    amount = Column(String(50), nullable=False)  # Store as string to avoid float precision issues
    currency = Column(String(10), default="USD", nullable=False)
    description = Column(Text, nullable=True)
    merchant = Column(String(255), nullable=True, index=True)
    transaction_date = Column(DateTime, nullable=False, index=True)
    
    extra_metadata = Column(JSON, nullable=True)  # Additional parsed fields
    
    # Relationships
    user = relationship("User", back_populates="transactions")
    raw_email = relationship("RawEmail", back_populates="transactions")


class ParsingStatus(str, enum.Enum):
    """Parsing attempt status"""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class ParsingLog(BaseModel):
    """Logs of parsing attempts"""
    __tablename__ = "parsing_logs"
    
    raw_email_id = Column(UUID(as_uuid=True), ForeignKey("raw_emails.id"), nullable=False, index=True)
    status = Column(SQLEnum(ParsingStatus), nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    parsed_data = Column(JSON, nullable=True)
    
    # Relationships
    raw_email = relationship("RawEmail", back_populates="parsing_logs")
