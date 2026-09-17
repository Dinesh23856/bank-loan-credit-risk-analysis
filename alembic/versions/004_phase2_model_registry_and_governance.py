"""Phase 2: Model Registry, Model Governance, Model Cards, and Artifact Integrity Verification

Revision ID: 004_phase2_model_registry_and_governance
Revises: 003_phase1_workflow_rbac_underwriter_audit
Create Date: 2026-09-14

"""
import json
from datetime import datetime
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

revision = '004_phase2_model_registry_and_governance'
down_revision = '003_phase1_workflow_rbac_underwriter_audit'
branch_labels = None
depends_on = None

MODELS_SEED = [
    {
        "model_name": "loan_approval",
        "model_version": "2.0.0",
        "task": "binary_classification",
        "model_type": "RandomForestClassifier",
        "artifact_path": "models/loan_approval.joblib",
        "artifact_sha256": "b70d0fd7ef583b3492e0ac57acf4cea5b0689844ad6615a3cbd6a46466c02f26",
        "dataset_reference": "data/raw/loan_data.csv",
        "dataset_sha256": "cee57f9c187a4cfd97ccf40030a279d6ab41bdd3c78bb80704c118a2ecf0554a",
        "target_variable": "loan_status",
        "features_json": json.dumps([
            "age", "dependents", "education", "employment_type", "monthly_income", "annual_income",
            "monthly_debt", "debt_to_income_ratio", "savings", "bank_balance", "assets",
            "credit_history", "previous_loans", "previous_defaults", "payment_history",
            "credit_utilization", "credit_score", "loan_type", "requested_loan_amount",
            "loan_term", "collateral_value", "disposable_income", "wealth_to_income",
            "savings_months", "default_rate", "payment_quality", "loan_to_income",
            "loan_to_assets", "credit_strength"
        ]),
        "metrics_json": json.dumps({
            "rows": 12000,
            "accuracy": 0.7733333333333333,
            "f1": 0.3182957393483709,
            "roc_auc": 0.7426283950419577,
            "confusion_matrix": [[1729, 135], [409, 127]]
        }),
        "intended_use": "Automated credit risk assessment and underwriting decision recommendation for retail consumer loan applications.",
        "limitations": "Trained on retail banking synthetic distribution; class imbalance in historical approvals is handled via class weighting (F1 0.3183). Should be subject to manual underwriting review for borderline probabilities (0.40 - 0.60).",
        "known_risks": "Potential demographic bias if unmonitored; ECOA/FCRA protected attributes (Age, Gender, Marital Status) are strictly forbidden as recourse levers.",
        "explainability_method": "TreeSHAP (TreeExplainer) with localized feature attributions and adverse action mapping.",
        "lifecycle_status": "APPROVED",
        "deployment_status": "ACTIVE",
        "integrity_status": "VERIFIED"
    },
    {
        "model_name": "loan_amount",
        "model_version": "2.0.0",
        "task": "regression",
        "model_type": "RandomForestRegressor",
        "artifact_path": "models/loan_amount.joblib",
        "artifact_sha256": "963bff7f4317a6d373fd0aa0e324f698a32cabee2d7a4d12d9fdef5048fcabe6",
        "dataset_reference": "data/raw/loan_data.csv",
        "dataset_sha256": "cee57f9c187a4cfd97ccf40030a279d6ab41bdd3c78bb80704c118a2ecf0554a",
        "target_variable": "approved_loan_amount",
        "features_json": json.dumps([
            "age", "dependents", "education", "employment_type", "monthly_income", "annual_income",
            "monthly_debt", "debt_to_income_ratio", "savings", "bank_balance", "assets",
            "credit_history", "previous_loans", "previous_defaults", "payment_history",
            "credit_utilization", "credit_score", "loan_type", "requested_loan_amount",
            "loan_term", "collateral_value", "disposable_income", "wealth_to_income",
            "savings_months", "default_rate", "payment_quality", "loan_to_income",
            "loan_to_assets", "credit_strength"
        ]),
        "metrics_json": json.dumps({
            "rows": 2682,
            "mae": 30814.57946354833,
            "rmse": 47756.22540987956,
            "r2": 0.9485321797140178
        }),
        "intended_use": "Predicts sanctioned loan amount in INR for approved applications, subject to loan request cap.",
        "limitations": "Trained solely on historically approved loans (2,682 rows). In inference, predicted loan amount is capped at the applicant's requested loan amount.",
        "known_risks": "Over-prediction risk mitigated by mandatory hard-cap logic at inference time.",
        "explainability_method": "Tree feature importance and applicant debt-to-income sensitivity analysis.",
        "lifecycle_status": "APPROVED",
        "deployment_status": "ACTIVE",
        "integrity_status": "VERIFIED"
    },
    {
        "model_name": "credit_score",
        "model_version": "2.0.0",
        "task": "regression",
        "model_type": "GradientBoostingRegressor",
        "artifact_path": "models/credit_score.joblib",
        "artifact_sha256": "897948653b3982012b327746955a79b8487834f2bb0dcefa02dd0b9f3a553f59",
        "dataset_reference": "data/raw/loan_data.csv",
        "dataset_sha256": "cee57f9c187a4cfd97ccf40030a279d6ab41bdd3c78bb80704c118a2ecf0554a",
        "target_variable": "predicted_credit_score",
        "features_json": json.dumps([
            "age", "dependents", "education", "employment_type", "monthly_income", "annual_income",
            "monthly_debt", "debt_to_income_ratio", "savings", "bank_balance", "assets",
            "credit_history", "previous_loans", "previous_defaults", "payment_history",
            "credit_utilization", "disposable_income", "wealth_to_income", "savings_months",
            "default_rate", "payment_quality", "credit_strength"
        ]),
        "metrics_json": json.dumps({
            "rows": 12000,
            "mae": 15.007433330990231,
            "rmse": 19.145374873593788,
            "r2": 0.8620293057359676
        }),
        "intended_use": "Estimates internal credit bureau score (300-850) based on financial profile and repayment history.",
        "limitations": "Excludes observed credit score from features to prevent target leakage; predictions bounded between 300 and 850.",
        "known_risks": "Non-linear drift in macro-economic default rates may impact prediction accuracy over time.",
        "explainability_method": "Gradient boosting feature importances and historical credit trajectory comparison.",
        "lifecycle_status": "APPROVED",
        "deployment_status": "ACTIVE",
        "integrity_status": "VERIFIED"
    },
    {
        "model_name": "credit_risk",
        "model_version": "2.0.0",
        "task": "multiclass_classification",
        "model_type": "RandomForestClassifier",
        "artifact_path": "models/credit_risk.joblib",
        "artifact_sha256": "044aa75d7741d1bb6b448d3795b145350cacc65c8c6e598cff6e6df219d55922",
        "dataset_reference": "data/raw/credit_risk_data.csv",
        "dataset_sha256": "f579fb61724b5abf61e1af563ba3b3e6b71657bb949042ac315d68f3f4d22c2c",
        "target_variable": "risk_level",
        "features_json": json.dumps([
            "age", "dependents", "education", "employment_type", "monthly_income", "annual_income",
            "monthly_debt", "debt_to_income_ratio", "savings", "bank_balance", "assets",
            "credit_history", "previous_loans", "previous_defaults", "payment_history",
            "credit_utilization", "disposable_income", "wealth_to_income", "savings_months",
            "default_rate", "payment_quality"
        ]),
        "metrics_json": json.dumps({
            "rows": 12000,
            "classes": ["High", "Low", "Medium"],
            "accuracy": 0.8179166666666666,
            "f1_macro": 0.5779510627189675,
            "confusion_matrix": [
                [1625, 0, 165],
                [4, 13, 73],
                [186, 9, 325]
            ]
        }),
        "intended_use": "Multi-tier risk grading (High / Medium / Low) for portfolio risk management and provisioning.",
        "limitations": "Leakage-safe model with credit_score and credit_strength excluded. Lower macro-F1 on Low class due to class distribution.",
        "known_risks": "Borderline Medium/High classifications should be corroborated by manual underwriter assessment.",
        "explainability_method": "Multiclass Random Forest feature importances and risk probability distribution.",
        "lifecycle_status": "APPROVED",
        "deployment_status": "ACTIVE",
        "integrity_status": "VERIFIED"
    }
]

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'model_registry' not in existing_tables:
        op.create_table(
            'model_registry',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('model_name', sa.String(length=80), nullable=False),
            sa.Column('model_version', sa.String(length=30), nullable=False, server_default='2.0.0'),
            sa.Column('task', sa.String(length=50), nullable=False),
            sa.Column('model_type', sa.String(length=80), nullable=False),
            sa.Column('artifact_path', sa.String(length=255), nullable=False),
            sa.Column('artifact_sha256', sa.String(length=64), nullable=False),
            sa.Column('dataset_reference', sa.String(length=100), nullable=False),
            sa.Column('dataset_sha256', sa.String(length=64), nullable=False),
            sa.Column('target_variable', sa.String(length=50), nullable=False),
            sa.Column('features_json', sa.Text(), nullable=False),
            sa.Column('metrics_json', sa.Text(), nullable=False),
            sa.Column('intended_use', sa.Text(), nullable=True),
            sa.Column('limitations', sa.Text(), nullable=True),
            sa.Column('known_risks', sa.Text(), nullable=True),
            sa.Column('explainability_method', sa.String(length=100), nullable=True),
            sa.Column('lifecycle_status', sa.String(length=30), nullable=False, server_default='APPROVED'),
            sa.Column('deployment_status', sa.String(length=30), nullable=False, server_default='ACTIVE'),
            sa.Column('integrity_status', sa.String(length=30), nullable=False, server_default='VERIFIED'),
            sa.Column('last_integrity_check', sa.DateTime(), nullable=True),
            sa.Column('registered_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('reviewed_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('reviewed_at', sa.DateTime(), nullable=True),
            sa.Column('review_notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now())
        )
        op.create_index('ix_model_registry_model_name', 'model_registry', ['model_name'], unique=True)

    # Pre-seed the 4 immutable models into model_registry if missing
    for model_meta in MODELS_SEED:
        existing = conn.execute(
            text("SELECT id FROM model_registry WHERE model_name = :m_name"),
            {"m_name": model_meta["model_name"]}
        ).fetchone()
        if not existing:
            conn.execute(
                text("""
                    INSERT INTO model_registry (
                        model_name, model_version, task, model_type,
                        artifact_path, artifact_sha256, dataset_reference, dataset_sha256,
                        target_variable, features_json, metrics_json, intended_use,
                        limitations, known_risks, explainability_method,
                        lifecycle_status, deployment_status, integrity_status,
                        last_integrity_check, created_at, updated_at
                    ) VALUES (
                        :model_name, :model_version, :task, :model_type,
                        :artifact_path, :artifact_sha256, :dataset_reference, :dataset_sha256,
                        :target_variable, :features_json, :metrics_json, :intended_use,
                        :limitations, :known_risks, :explainability_method,
                        :lifecycle_status, :deployment_status, :integrity_status,
                        NOW(), NOW(), NOW()
                    )
                """),
                model_meta
            )

def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    if 'model_registry' in existing_tables:
        op.drop_table('model_registry')
