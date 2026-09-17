from datetime import datetime
import math
from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

class UserRegister(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class UserLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str

class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: EmailStr
    role: str
    created_at: datetime

class UserRoleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["CUSTOMER", "UNDERWRITER", "RISK_ANALYST", "ADMIN", "user", "admin"]
    reason: Optional[str] = None

class LoanApplicationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    applicant_name: str = Field(default="Applicant", min_length=2, max_length=120)
    city: str = Field(default="", max_length=100)
    region: str = Field(default="", max_length=100)
    age: int = Field(ge=18, le=75)
    dependents: int = Field(ge=0, le=5)
    gender: Literal["Male", "Female"]
    marital_status: Literal["Single", "Married", "Divorced"]
    education: Literal["Undergraduate", "Graduate", "Postgraduate"]
    employment_type: Literal["Business", "Contract", "Salaried", "Self-employed"]
    annual_income: float = Field(gt=0, le=50_000_000)
    debt_to_income_ratio: float = Field(ge=0, le=1)
    savings: float = Field(ge=0, le=50_000_000)
    bank_balance: float = Field(ge=0, le=20_000_000)
    assets: float = Field(ge=0, le=100_000_000)
    credit_history: Literal["Good", "Average", "Poor"]
    previous_loans: int = Field(ge=0, le=30)
    previous_defaults: int = Field(ge=0, le=20)
    payment_history: float = Field(ge=0, le=100)
    credit_utilization: float = Field(ge=0, le=1)
    credit_score: float = Field(ge=300, le=850)
    loan_type: Literal["Education", "Business", "Personal", "Home", "Auto"]
    requested_loan_amount: float = Field(gt=0, le=100_000_000)
    loan_term: int = Field(ge=1, le=480)
    collateral_value: float = Field(ge=0, le=500_000_000)
    interest_rate: float = Field(gt=0, le=100)

    @field_validator("*")
    @classmethod
    def finite(cls, value):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Value must be finite")
        return value

class RiskEvaluationRequest(LoanApplicationRequest):
    """Authenticated credit-risk evaluation request."""

class RiskEvaluationResponse(BaseModel):
    credit_score: float = Field(ge=300, le=850)
    risk_level: Literal["Low", "Medium", "High"]
    risk_probabilities: dict[str, float]

class LoanPredictionResponse(BaseModel):
    loan_status: Literal["Approved", "Rejected"]
    approved: bool
    approval_probability: float = Field(ge=0, le=1)
    approved_loan_amount: float = Field(ge=0)
    credit_score: float = Field(ge=300, le=850)
    risk_level: Literal["Low", "Medium", "High"]
    risk_probabilities: dict[str, float]
    # Enterprise explainability fields
    adverse_action_reasons: list[dict] = Field(default_factory=list)
    positive_factors: list[dict] = Field(default_factory=list)
    all_feature_contributions: list[dict] = Field(default_factory=list)
    explanation_metadata: dict = Field(default_factory=dict)
    # Phase 1 workflow status
    status: Optional[str] = None

class CounterfactualRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    applicant_data: LoanApplicationRequest
    requested_loan_amount: Optional[float] = None
    loan_term: Optional[int] = None
    collateral_value: Optional[float] = None
    savings: Optional[float] = None
    debt_to_income_ratio: Optional[float] = None

class CounterfactualResponse(BaseModel):
    original_probability: float
    approval_probability: float
    estimated_decision: Literal["Approved", "Rejected"]
    changes: list[dict]
    feasible: bool
    disclaimer: str

class TaskResponse(BaseModel):
    task_id: str
    application_id: Optional[int] = None
    status: Literal["PENDING", "PROCESSING", "SUCCESS", "FAILED"]
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None

class StatusHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    application_id: int
    previous_status: Optional[str] = None
    new_status: str
    changed_by: Optional[int] = None
    changed_by_role: Optional[str] = None
    timestamp: datetime
    reason: Optional[str] = None

class WorkflowTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_status: str
    reason: Optional[str] = None

class UnderwriterReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["APPROVED", "REJECTED"]
    reason: str = Field(min_length=5, max_length=1000)
    reviewer_comments: Optional[str] = Field(default=None, max_length=2000)

class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    applicant_name: str
    city: str | None
    region: str | None
    loan_amount: float
    approval_status: str | None
    predicted_loan_amount: float | None
    credit_score: Optional[float] = None
    predicted_credit_score: float | None
    risk_level: str | None
    created_at: datetime
    approval_probability: Optional[float] = None
    # Phase 1 Workflow & Underwriting fields
    status: Optional[str] = None
    ai_decision: Optional[str] = None
    ai_probability: Optional[float] = None
    underwriter_decision: Optional[str] = None
    underwriter_reason: Optional[str] = None
    reviewer_comments: Optional[str] = None
    reviewer_id: Optional[int] = None
    reviewer_role: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    status_history: list[StatusHistoryResponse] = Field(default_factory=list)

class ApplicationListResponse(BaseModel):
    items: list[ApplicationResponse]
    total: int
    page: int
    page_size: int

class UnderwriterQueueItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    applicant_name: str
    loan_amount: float
    credit_score: float
    predicted_credit_score: Optional[float] = None
    risk_level: Optional[str] = None
    approval_probability: Optional[float] = None
    ai_decision: Optional[str] = None
    status: str
    created_at: datetime

class UnderwriterQueueListResponse(BaseModel):
    items: list[UnderwriterQueueItemResponse]
    total: int
    page: int
    page_size: int

class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    timestamp: datetime
    user_id: Optional[int] = None
    role: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    ip_address: Optional[str] = None
    metadata_json: Optional[str] = Field(default=None, alias="metadata_json")
    reason: Optional[str] = None
    before_value: Optional[str] = None
    after_value: Optional[str] = None

class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int

class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: EmailStr
    role: str
    created_at: datetime
    application_count: int

class AdminUserListResponse(BaseModel):
    items: list[AdminUserResponse]
    total: int
    page: int
    page_size: int

class FairnessReportResponse(BaseModel):
    group_attribute: str
    groups: dict
    disparate_impact_ratio: float
    favorable_group: str
    protected_group: str
    four_fifths_rule_passed: bool
    status: Optional[str] = None
    disclaimer: str

class ChatMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=2000)
    application_id: Optional[int] = None
    conversation_id: Optional[str] = None

class ChatMessageResponse(BaseModel):
    message: str
    conversation_id: str
    sources: list[str] = []
    degraded: bool = False

class ChatMessageItem(BaseModel):
    id: int
    role: str
    content: str
    sources: Optional[list[str]] = None
    created_at: datetime

class ChatConversationResponse(BaseModel):
    id: str
    title: Optional[str] = None
    application_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

class ChatConversationDetailResponse(BaseModel):
    id: str
    title: Optional[str] = None
    application_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageItem]

class ModelRegistryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    model_name: str
    model_version: str
    task: str
    model_type: str
    artifact_path: str
    artifact_sha256: str
    dataset_reference: str
    dataset_sha256: str
    target_variable: str
    features_json: str
    metrics_json: str
    intended_use: Optional[str] = None
    limitations: Optional[str] = None
    known_risks: Optional[str] = None
    explainability_method: Optional[str] = None
    lifecycle_status: str
    deployment_status: str
    integrity_status: str
    last_integrity_check: Optional[datetime] = None
    registered_by: Optional[int] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class ModelRegistryListResponse(BaseModel):
    items: list[ModelRegistryResponse]
    total: int

class ModelStatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lifecycle_status: Optional[str] = None
    deployment_status: Optional[str] = None
    reason: Optional[str] = None

class ModelReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(pattern="^(APPROVED|REJECTED)$")
    review_notes: Optional[str] = Field(default=None, max_length=2000)

class ModelIntegrityCheckResponse(BaseModel):
    model_name: str
    status: str
    message: str
    expected_hash: str
    actual_hash: Optional[str] = None
    verified_at: datetime

class ModelCardResponse(BaseModel):
    model_name: str
    model_version: str
    task: str
    model_type: str
    purpose: Optional[str] = None
    intended_use: Optional[str] = None
    out_of_scope_use: Optional[str] = None
    input_features: list[str] = []
    feature_count: int
    target_variable: str
    dataset: dict
    evaluation_metrics: dict
    explainability: dict
    limitations: Optional[str] = None
    known_risks: Optional[str] = None
    artifact: dict
    governance: dict
    regulatory_disclaimer: str

# Phase 3: Financial Calculation & Academic KFS Schemas

class EMICalculatorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal: float = Field(gt=0, le=100_000_000, description="Loan principal amount in INR")
    annual_interest_rate: float = Field(ge=0, le=100, description="Annual interest rate percentage (e.g. 10.5)")
    loan_term_months: int = Field(ge=1, le=480, description="Tenure in months (1 to 480)")

    @field_validator("principal", "annual_interest_rate")
    @classmethod
    def check_finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("Value must be finite (not NaN or Infinity)")
        return v

class EMICalculatorResponse(BaseModel):
    principal: float
    annual_interest_rate: float
    monthly_interest_rate: float
    loan_term_months: int
    emi: float
    total_payment: float
    total_interest: float

class AmortizationRowResponse(BaseModel):
    month: int
    opening_balance: float
    emi: float
    principal_component: float
    interest_component: float
    closing_balance: float

class AmortizationResponse(BaseModel):
    application_id: Optional[int] = None
    principal: float
    annual_interest_rate: float
    monthly_interest_rate: float
    loan_term_months: int
    emi: float
    total_payment: float
    total_interest: float
    schedule: list[AmortizationRowResponse]

class FinancialSummaryResponse(BaseModel):
    application_id: int
    loan_amount: float
    requested_amount: float
    approved_amount: Optional[float] = None
    interest_rate: float
    loan_term_months: int
    emi: float
    total_interest: float
    total_payment: float
    loan_status: str
    approval_status: str
    is_approved_offer: bool

class KFSResponse(BaseModel):
    document_type: str
    document_title: str
    disclaimer_header: str
    disclaimer_text: str
    application_id: int
    reference_number: str
    applicant_name: str
    city: str
    region: str
    loan_type: str
    loan_amount: float
    requested_amount: float
    interest_rate: float
    interest_type: str
    loan_term_months: int
    repayment_frequency: str
    emi: float
    total_interest: float
    total_repayment: float
    loan_status: str
    approval_status: str
    reviewed_at: Optional[str] = None
    reviewer_role: Optional[str] = None
    generated_at: str
    first_year_schedule: list[AmortizationRowResponse] = []

# Phase 4: Risk Analyst & Executive Analytics Schemas

class PortfolioOverviewResponse(BaseModel):
    total_applications: int
    approved_applications: int
    rejected_applications: int
    approval_rate: float
    average_requested_loan_amount: float
    average_approved_loan_amount: float
    average_predicted_credit_score: float
    high_risk_applicant_count: int
    medium_risk_applicant_count: int
    low_risk_applicant_count: int

class WorkflowStatusItem(BaseModel):
    status: str
    count: int
    percentage: float

class WorkflowStatusBreakdownResponse(BaseModel):
    total_applications: int
    breakdown: list[WorkflowStatusItem]

class SubgroupRateItem(BaseModel):
    total: int
    approved: int
    rejected: int
    approval_rate: float
    rejection_rate: float

class ApprovalRejectionAnalysisResponse(BaseModel):
    overall: SubgroupRateItem
    by_risk_level: dict[str, SubgroupRateItem]
    by_credit_score: dict[str, SubgroupRateItem]
    by_loan_amount: dict[str, SubgroupRateItem]
    by_employment_type: dict[str, SubgroupRateItem]

class CreditScoreStatsItem(BaseModel):
    count: int
    mean: float
    min: float
    max: float
    median: float

class CreditScoreBandItem(BaseModel):
    band: str
    label: str
    count: int
    percentage: float

class CreditScoreComponentResponse(BaseModel):
    label: str
    stats: CreditScoreStatsItem
    distribution: list[CreditScoreBandItem]

class CreditScoreAnalysisResponse(BaseModel):
    predicted_credit_score: CreditScoreComponentResponse
    bureau_credit_score: CreditScoreComponentResponse

class LoanAmountStatsItem(BaseModel):
    count: int
    mean: float
    min: float
    max: float
    total: float

class LoanAmountTierItem(BaseModel):
    tier: str
    label: str
    count: int
    percentage: float

class RiskAmountRelationItem(BaseModel):
    risk_level: str
    count: int
    avg_requested: float
    avg_approved: float

class LoanAmountAnalysisResponse(BaseModel):
    requested_amount_stats: LoanAmountStatsItem
    approved_amount_stats: LoanAmountStatsItem
    distribution_tiers: list[LoanAmountTierItem]
    risk_relationship: list[RiskAmountRelationItem]

class RiskDistributionItem(BaseModel):
    risk_level: str
    count: int
    percentage: float
    approved: int
    rejected: int
    approval_rate: float

class RiskDistributionResponse(BaseModel):
    total_applications: int
    distribution: list[RiskDistributionItem]

class TimeTrendPoint(BaseModel):
    date: str
    applications: int
    approved: int
    rejected: int
    high_risk: int
    medium_risk: int
    low_risk: int

class TimeTrendsResponse(BaseModel):
    interval: str
    days: int
    points: list[TimeTrendPoint]


