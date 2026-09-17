"""banking ai assistant tables

Revision ID: 002_banking_ai_assistant
Revises: 001_enterprise_upgrade
Create Date: 2026-09-13

"""
from alembic import op
import sqlalchemy as sa

revision = '002_banking_ai_assistant'
down_revision = '001_enterprise_upgrade'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Create chat_conversations
    op.create_table(
        'chat_conversations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('application_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['application_id'], ['loan_applications.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chat_conversations_user_id', 'chat_conversations', ['user_id'])
    op.create_index('ix_chat_conversations_application_id', 'chat_conversations', ['application_id'])

    # 2. Create chat_messages
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('conversation_id', sa.String(length=36), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('sources', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['chat_conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chat_messages_conversation_id', 'chat_messages', ['conversation_id'])
    op.create_index('ix_chat_messages_created_at', 'chat_messages', ['created_at'])

    # 3. Create chat_usage_logs
    op.create_table(
        'chat_usage_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.String(length=36), nullable=True),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model', sa.String(length=80), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('latency_ms', sa.Float(), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), nullable=True),
        sa.Column('completion_tokens', sa.Integer(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('error_category', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chat_usage_logs_user_id', 'chat_usage_logs', ['user_id'])
    op.create_index('ix_chat_usage_logs_conversation_id', 'chat_usage_logs', ['conversation_id'])
    op.create_index('ix_chat_usage_logs_created_at', 'chat_usage_logs', ['created_at'])

def downgrade() -> None:
    op.drop_index('ix_chat_usage_logs_created_at', table_name='chat_usage_logs')
    op.drop_index('ix_chat_usage_logs_conversation_id', table_name='chat_usage_logs')
    op.drop_index('ix_chat_usage_logs_user_id', table_name='chat_usage_logs')
    op.drop_table('chat_usage_logs')

    op.drop_index('ix_chat_messages_created_at', table_name='chat_messages')
    op.drop_index('ix_chat_messages_conversation_id', table_name='chat_messages')
    op.drop_table('chat_messages')

    op.drop_index('ix_chat_conversations_application_id', table_name='chat_conversations')
    op.drop_index('ix_chat_conversations_user_id', table_name='chat_conversations')
    op.drop_table('chat_conversations')
