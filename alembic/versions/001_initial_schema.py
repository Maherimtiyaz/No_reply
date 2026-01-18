"""initial schema

Revision ID: 001
Revises: 
Create Date: 2026-01-18 11:09:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
    )
    op.create_index('ix_users_email', 'users', ['email'])
    
    # Create oauth_accounts table
    op.create_table(
        'oauth_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider', sa.Enum('google', 'microsoft', name='oauthprovider'), nullable=False),
        sa.Column('provider_account_id', sa.String(255), nullable=False),
        sa.Column('access_token', sa.Text(), nullable=True),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )
    op.create_index('ix_oauth_accounts_user_id', 'oauth_accounts', ['user_id'])
    
    # Create raw_emails table
    op.create_table(
        'raw_emails',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('message_id', sa.String(255), nullable=False, unique=True),
        sa.Column('subject', sa.String(500), nullable=True),
        sa.Column('sender', sa.String(255), nullable=False),
        sa.Column('received_at', sa.DateTime(), nullable=False),
        sa.Column('raw_body', sa.Text(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'parsed', 'failed', 'ignored', name='emailstatus'), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )
    op.create_index('ix_raw_emails_user_id', 'raw_emails', ['user_id'])
    op.create_index('ix_raw_emails_message_id', 'raw_emails', ['message_id'])
    op.create_index('ix_raw_emails_sender', 'raw_emails', ['sender'])
    op.create_index('ix_raw_emails_received_at', 'raw_emails', ['received_at'])
    op.create_index('ix_raw_emails_status', 'raw_emails', ['status'])
    
    # Create transactions table
    op.create_table(
        'transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('raw_email_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('transaction_type', sa.Enum('debit', 'credit', name='transactiontype'), nullable=False),
        sa.Column('amount', sa.String(50), nullable=False),
        sa.Column('currency', sa.String(10), nullable=False, server_default='USD'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('merchant', sa.String(255), nullable=True),
        sa.Column('transaction_date', sa.DateTime(), nullable=False),
        sa.Column('extra_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['raw_email_id'], ['raw_emails.id'], ),
    )
    op.create_index('ix_transactions_user_id', 'transactions', ['user_id'])
    op.create_index('ix_transactions_raw_email_id', 'transactions', ['raw_email_id'])
    op.create_index('ix_transactions_transaction_type', 'transactions', ['transaction_type'])
    op.create_index('ix_transactions_merchant', 'transactions', ['merchant'])
    op.create_index('ix_transactions_transaction_date', 'transactions', ['transaction_date'])
    
    # Create parsing_logs table
    op.create_table(
        'parsing_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('raw_email_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.Enum('success', 'failed', 'partial', name='parsingstatus'), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('parsed_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['raw_email_id'], ['raw_emails.id'], ),
    )
    op.create_index('ix_parsing_logs_raw_email_id', 'parsing_logs', ['raw_email_id'])
    op.create_index('ix_parsing_logs_status', 'parsing_logs', ['status'])


def downgrade() -> None:
    op.drop_table('parsing_logs')
    op.drop_table('transactions')
    op.drop_table('raw_emails')
    op.drop_table('oauth_accounts')
    op.drop_table('users')
    
    # Drop enums
    sa.Enum(name='parsingstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='transactiontype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='emailstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='oauthprovider').drop(op.get_bind(), checkfirst=True)
