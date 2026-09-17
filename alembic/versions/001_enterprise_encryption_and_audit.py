"""enterprise encryption and audit

Revision ID: 001_enterprise_upgrade
Revises: 
Create Date: 2026-09-13

"""
from alembic import op
import sqlalchemy as sa
from backend.db.encrypted_type import EncryptedString, EncryptedFloat, _get_multifernet, _deterministic_encrypt

revision = '001_enterprise_upgrade'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Alter loan_applications columns to VARCHAR(255) to accommodate encrypted ciphertexts
    with op.batch_alter_table("loan_applications") as batch_op:
        batch_op.alter_column("applicant_name", existing_type=sa.String(120), type_=sa.String(255), nullable=False)
        batch_op.alter_column("annual_income", existing_type=sa.Float(), type_=sa.String(255), nullable=False)
        batch_op.alter_column("savings", existing_type=sa.Float(), type_=sa.String(255), nullable=False)
        batch_op.alter_column("bank_balance", existing_type=sa.Float(), type_=sa.String(255), nullable=False)
        batch_op.alter_column("predicted_credit_score", existing_type=sa.Float(), type_=sa.String(255), nullable=True)

    # 2. Add audit logging columns to model_logs
    with op.batch_alter_table("model_logs") as batch_op:
        batch_op.add_column(sa.Column("model_version", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("decision", sa.String(30), nullable=True))
        batch_op.add_column(sa.Column("status", sa.String(20), server_default="SUCCESS", nullable=False))
        batch_op.add_column(sa.Column("explanation_generated", sa.Integer(), server_default="1", nullable=False))
        batch_op.add_column(sa.Column("processing_duration_ms", sa.Float(), nullable=True))

    # 3. Data migration: safely encrypt existing records
    conn = op.get_bind()
    mf = _get_multifernet()
    primary_fernet = mf._fernets[0]

    # Encrypt users.email if plaintext
    users = conn.execute(sa.text("SELECT id, email FROM users")).fetchall()
    for u in users:
        email = str(u[1])
        if not email.startswith("gAAAAA"):
            enc = _deterministic_encrypt(email.strip().lower().encode("utf-8"), primary_fernet)
            conn.execute(sa.text("UPDATE users SET email = :enc WHERE id = :uid"), {"enc": enc, "uid": u[0]})

    # Encrypt loan_applications fields if plaintext
    apps = conn.execute(sa.text(
        "SELECT id, applicant_name, annual_income, savings, bank_balance, predicted_credit_score FROM loan_applications"
    )).fetchall()
    for a in apps:
        app_id = a[0]
        name = str(a[1]) if a[1] is not None else ""
        income = str(a[2]) if a[2] is not None else ""
        savings = str(a[3]) if a[3] is not None else ""
        balance = str(a[4]) if a[4] is not None else ""
        score = str(a[5]) if a[5] is not None else ""

        params = {"id": app_id}
        updates = []
        if name and not name.startswith("gAAAAA"):
            params["name"] = mf.encrypt(name.encode("utf-8")).decode("utf-8")
            updates.append("applicant_name = :name")
        if income and not income.startswith("gAAAAA"):
            params["income"] = mf.encrypt(income.encode("utf-8")).decode("utf-8")
            updates.append("annual_income = :income")
        if savings and not savings.startswith("gAAAAA"):
            params["savings"] = mf.encrypt(savings.encode("utf-8")).decode("utf-8")
            updates.append("savings = :savings")
        if balance and not balance.startswith("gAAAAA"):
            params["balance"] = mf.encrypt(balance.encode("utf-8")).decode("utf-8")
            updates.append("bank_balance = :balance")
        if score and not score.startswith("gAAAAA"):
            params["score"] = mf.encrypt(score.encode("utf-8")).decode("utf-8")
            updates.append("predicted_credit_score = :score")

        if updates:
            stmt = f"UPDATE loan_applications SET {', '.join(updates)} WHERE id = :id"
            conn.execute(sa.text(stmt), params)

def downgrade() -> None:
    # Decrypt records before reverting types
    conn = op.get_bind()
    mf = _get_multifernet()

    users = conn.execute(sa.text("SELECT id, email FROM users")).fetchall()
    for u in users:
        email = str(u[1])
        if email.startswith("gAAAAA"):
            try:
                dec = mf.decrypt(email.encode("utf-8")).decode("utf-8")
                conn.execute(sa.text("UPDATE users SET email = :dec WHERE id = :uid"), {"dec": dec, "uid": u[0]})
            except Exception:
                pass

    with op.batch_alter_table("model_logs") as batch_op:
        batch_op.drop_column("processing_duration_ms")
        batch_op.drop_column("explanation_generated")
        batch_op.drop_column("status")
        batch_op.drop_column("decision")
        batch_op.drop_column("model_version")

    with op.batch_alter_table("loan_applications") as batch_op:
        batch_op.alter_column("applicant_name", existing_type=sa.String(255), type_=sa.String(120), nullable=False)
        batch_op.alter_column("annual_income", existing_type=sa.String(255), type_=sa.Float(), nullable=False)
        batch_op.alter_column("savings", existing_type=sa.String(255), type_=sa.Float(), nullable=False)
        batch_op.alter_column("bank_balance", existing_type=sa.String(255), type_=sa.Float(), nullable=False)
        batch_op.alter_column("predicted_credit_score", existing_type=sa.String(255), type_=sa.Float(), nullable=True)
