"""Phase 1: Guarded Application Workflow, Four-Role RBAC, Underwriter Review, and Audit Logging

Revision ID: 003_phase1_workflow_rbac_underwriter_audit
Revises: 002_banking_ai_assistant
Create Date: 2026-09-14

"""
import json
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

revision = '003_phase1_workflow_rbac_underwriter_audit'
down_revision = '002_banking_ai_assistant'
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Expand users.role column if needed
    user_cols = {c['name']: c for c in inspector.get_columns('users')}
    if 'role' in user_cols:
        role_type = str(user_cols['role']['type']).upper()
        if '10' in role_type or 'VARCHAR(10)' in role_type:
            op.alter_column('users', 'role',
                            existing_type=sa.String(length=10),
                            type_=sa.String(length=30),
                            existing_nullable=False,
                            existing_server_default='user')

    # 2. Add workflow and underwriter review columns to loan_applications if not existing
    app_cols = {c['name']: c for c in inspector.get_columns('loan_applications')}
    new_cols = [
        ('status', sa.String(length=30)),
        ('ai_decision', sa.String(length=30)),
        ('ai_probability', sa.Float()),
        ('underwriter_decision', sa.String(length=30)),
        ('underwriter_reason', sa.Text()),
        ('reviewer_comments', sa.Text()),
        ('reviewer_id', sa.Integer()),
        ('reviewer_role', sa.String(length=30)),
        ('reviewed_at', sa.DateTime()),
    ]
    for col_name, col_type in new_cols:
        if col_name not in app_cols:
            op.add_column('loan_applications', sa.Column(col_name, col_type, nullable=True))

    app_indexes = [idx['name'] for idx in inspector.get_indexes('loan_applications')]
    if 'ix_loan_applications_status' not in app_indexes:
        op.create_index('ix_loan_applications_status', 'loan_applications', ['status'])

    app_fks = [fk['name'] for fk in inspector.get_foreign_keys('loan_applications')]
    if 'fk_loan_applications_reviewer_id' not in app_fks:
        op.create_foreign_key(
            'fk_loan_applications_reviewer_id',
            'loan_applications', 'users',
            ['reviewer_id'], ['id'],
            ondelete='SET NULL'
        )

    # 3. Create application_status_history table if not existing
    if 'application_status_history' not in existing_tables:
        op.create_table(
            'application_status_history',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('application_id', sa.Integer(), nullable=False),
            sa.Column('previous_status', sa.String(length=30), nullable=True),
            sa.Column('new_status', sa.String(length=30), nullable=False),
            sa.Column('changed_by', sa.Integer(), nullable=True),
            sa.Column('changed_by_role', sa.String(length=30), nullable=True),
            sa.Column('timestamp', sa.DateTime(), nullable=False),
            sa.Column('reason', sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(['application_id'], ['loan_applications.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['changed_by'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_status_history_application_id', 'application_status_history', ['application_id'])
        op.create_index('ix_status_history_new_status', 'application_status_history', ['new_status'])
        op.create_index('ix_status_history_timestamp', 'application_status_history', ['timestamp'])

    # 4. Create audit_logs table if not existing
    if 'audit_logs' not in existing_tables:
        op.create_table(
            'audit_logs',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('timestamp', sa.DateTime(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('role', sa.String(length=30), nullable=True),
            sa.Column('action', sa.String(length=50), nullable=False),
            sa.Column('resource_type', sa.String(length=50), nullable=True),
            sa.Column('resource_id', sa.String(length=50), nullable=True),
            sa.Column('ip_address', sa.String(length=45), nullable=True),
            sa.Column('metadata', sa.Text(), nullable=True),
            sa.Column('reason', sa.Text(), nullable=True),
            sa.Column('before_value', sa.Text(), nullable=True),
            sa.Column('after_value', sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_audit_logs_timestamp', 'audit_logs', ['timestamp'])
        op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
        op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
        op.create_index('ix_audit_logs_role', 'audit_logs', ['role'])
        op.create_index('ix_audit_logs_resource_type', 'audit_logs', ['resource_type'])

    # 5. Authoritative Data Backfill for existing loan applications
    # A. Update status and ai_decision from approval_status
    conn.execute(text("""
        UPDATE loan_applications
        SET status = CASE
            WHEN approval_status = 'Approved' THEN 'APPROVED'
            WHEN approval_status = 'Rejected' THEN 'REJECTED'
            ELSE 'SUBMITTED'
        END,
        ai_decision = approval_status
        WHERE status IS NULL OR status = ''
    """))

    # B. Extract exact, authoritative AI probability from model_logs (loan_approval)
    log_rows = conn.execute(text("""
        SELECT application_id, prediction
        FROM model_logs
        WHERE model_name = 'loan_approval' AND application_id IS NOT NULL
        ORDER BY application_id ASC, id DESC
    """)).fetchall()

    app_prob_map = {}
    for app_id, pred_raw in log_rows:
        if app_id not in app_prob_map:
            prob = None
            try:
                data = json.loads(pred_raw) if isinstance(pred_raw, str) else pred_raw
                if isinstance(data, dict):
                    prob = data.get('approval_probability')
                    if prob is None:
                        prob = data.get('probability')
            except Exception:
                pass
            if prob is not None:
                app_prob_map[app_id] = float(prob)

    for app_id, prob_val in app_prob_map.items():
        conn.execute(
            text("UPDATE loan_applications SET ai_probability = :prob WHERE id = :app_id AND ai_probability IS NULL"),
            {"prob": prob_val, "app_id": app_id}
        )

    # C. Populate initial status history records for existing applications
    conn.execute(text("""
        INSERT INTO application_status_history (application_id, previous_status, new_status, changed_by, changed_by_role, timestamp, reason)
        SELECT la.id, NULL, la.status, la.user_id, 'CUSTOMER', la.created_at, 'Initial application submission'
        FROM loan_applications la
        WHERE la.id NOT IN (SELECT DISTINCT application_id FROM application_status_history)
    """))

def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'audit_logs' in existing_tables:
        op.drop_table('audit_logs')
    if 'application_status_history' in existing_tables:
        op.drop_table('application_status_history')

    app_fks = [fk['name'] for fk in inspector.get_foreign_keys('loan_applications')]
    if 'fk_loan_applications_reviewer_id' in app_fks:
        op.drop_constraint('fk_loan_applications_reviewer_id', 'loan_applications', type_='foreignkey')

    app_indexes = [idx['name'] for idx in inspector.get_indexes('loan_applications')]
    if 'ix_loan_applications_status' in app_indexes:
        op.drop_index('ix_loan_applications_status', 'loan_applications')

    app_cols = [c['name'] for c in inspector.get_columns('loan_applications')]
    for col_name in ['reviewed_at', 'reviewer_role', 'reviewer_id', 'reviewer_comments',
                     'underwriter_reason', 'underwriter_decision', 'ai_probability',
                     'ai_decision', 'status']:
        if col_name in app_cols:
            op.drop_column('loan_applications', col_name)

    user_cols = {c['name']: c for c in inspector.get_columns('users')}
    if 'role' in user_cols:
        op.alter_column('users', 'role',
                        existing_type=sa.String(length=30),
                        type_=sa.String(length=10),
                        existing_nullable=False,
                        existing_server_default='user')
