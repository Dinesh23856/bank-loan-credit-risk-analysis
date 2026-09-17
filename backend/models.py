from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from .database import Base
from .db.encrypted_type import EncryptedString, EncryptedFloat

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    email = Column(EncryptedString(255, deterministic=True), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(30), nullable=False, default="CUSTOMER")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    applications = relationship("LoanApplication", back_populates="user", foreign_keys="LoanApplication.user_id", cascade="all, delete-orphan")

class LoanApplication(Base):
    __tablename__ = "loan_applications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    applicant_name = Column(EncryptedString(255), nullable=False)
    age = Column(Integer, nullable=False)
    city = Column(String(100))
    region = Column(String(100))
    annual_income = Column(EncryptedFloat(255), nullable=False)
    loan_amount = Column(Float, nullable=False)
    loan_term_months = Column(Integer, nullable=False)
    interest_rate = Column(Float, nullable=False)
    credit_score = Column(Float, nullable=False)
    debt_to_income_ratio = Column(Float, nullable=False)
    employment_type = Column(String(50), nullable=False)
    education = Column(String(50), nullable=False)
    marital_status = Column(String(30), nullable=False)
    dependents = Column(Integer, nullable=False)
    savings = Column(EncryptedFloat(255), nullable=False)
    bank_balance = Column(EncryptedFloat(255), nullable=False)
    assets = Column(Float, nullable=False)
    previous_loans = Column(Integer, nullable=False)
    previous_defaults = Column(Integer, nullable=False)
    payment_history = Column(Float, nullable=False)
    credit_utilization = Column(Float, nullable=False)
    gender = Column(String(30), nullable=False)
    credit_history = Column(String(50), nullable=False)
    loan_type = Column(String(50), nullable=False)
    collateral_value = Column(Float, nullable=False)
    approval_status = Column(String(30))
    predicted_loan_amount = Column(Float)
    predicted_credit_score = Column(EncryptedFloat(255))
    risk_level = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Phase 1: Workflow and Underwriter Review columns
    status = Column(String(30), nullable=True, index=True)
    ai_decision = Column(String(30), nullable=True)
    ai_probability = Column(Float, nullable=True)
    underwriter_decision = Column(String(30), nullable=True)
    underwriter_reason = Column(Text, nullable=True)
    reviewer_comments = Column(Text, nullable=True)
    reviewer_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    reviewer_role = Column(String(30), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="applications", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    logs = relationship("ModelLog", back_populates="application", cascade="all, delete-orphan")
    status_history = relationship(
        "ApplicationStatusHistory",
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="ApplicationStatusHistory.timestamp.asc()"
    )

    __table_args__ = (
        Index("ix_app_user_created", "user_id", "created_at"),
        Index("ix_app_status_created", "approval_status", "created_at"),
        Index("ix_app_region_created", "region", "created_at")
    )

class ApplicationStatusHistory(Base):
    __tablename__ = "application_status_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("loan_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_status = Column(String(30), nullable=True)
    new_status = Column(String(30), nullable=False, index=True)
    changed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    changed_by_role = Column(String(30), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    reason = Column(Text, nullable=True)

    application = relationship("LoanApplication", back_populates="status_history")
    user = relationship("User", foreign_keys=[changed_by])

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    role = Column(String(30), nullable=True, index=True)
    action = Column(String(50), nullable=False, index=True)
    resource_type = Column(String(50), nullable=True, index=True)
    resource_id = Column(String(50), nullable=True, index=True)
    ip_address = Column(String(45), nullable=True)
    metadata_json = Column("metadata", Text, nullable=True)
    reason = Column(Text, nullable=True)
    before_value = Column(Text, nullable=True)
    after_value = Column(Text, nullable=True)

    user = relationship("User", foreign_keys=[user_id])

class ModelLog(Base):
    __tablename__ = "model_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = Column(Integer, ForeignKey("loan_applications.id", ondelete="CASCADE"), nullable=True, index=True)
    model_name = Column(String(80), nullable=False)
    model_version = Column(String(64), nullable=True)
    decision = Column(String(30), nullable=True)
    status = Column(String(20), default="SUCCESS", nullable=False)
    explanation_generated = Column(Integer, default=1, nullable=False)
    prediction = Column(Text, nullable=False)
    inference_time_ms = Column(Float, nullable=False)
    processing_duration_ms = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    application = relationship("LoanApplication", back_populates="logs")

class ModelRegistry(Base):
    __tablename__ = "model_registry"
    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(80), nullable=False, unique=True, index=True)
    model_version = Column(String(30), nullable=False, default="2.0.0")
    task = Column(String(50), nullable=False)
    model_type = Column(String(80), nullable=False)
    artifact_path = Column(String(255), nullable=False)
    artifact_sha256 = Column(String(64), nullable=False)
    dataset_reference = Column(String(100), nullable=False)
    dataset_sha256 = Column(String(64), nullable=False)
    target_variable = Column(String(50), nullable=False)
    features_json = Column(Text, nullable=False)
    metrics_json = Column(Text, nullable=False)
    intended_use = Column(Text, nullable=True)
    limitations = Column(Text, nullable=True)
    known_risks = Column(Text, nullable=True)
    explainability_method = Column(String(100), nullable=True)
    lifecycle_status = Column(String(30), nullable=False, default="APPROVED")
    deployment_status = Column(String(30), nullable=False, default="ACTIVE")
    integrity_status = Column(String(30), nullable=False, default="VERIFIED")
    last_integrity_check = Column(DateTime, nullable=True)
    registered_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    registered_by_user = relationship("User", foreign_keys=[registered_by])
    reviewed_by_user = relationship("User", foreign_keys=[reviewed_by])

class ChatConversation(Base):
    __tablename__ = "chat_conversations"
    id = Column(String(36), primary_key=True)  # UUID4 string
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=True, default="New Conversation")
    application_id = Column(Integer, ForeignKey("loan_applications.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", backref="chat_conversations")
    application = relationship("LoanApplication", backref="chat_conversations")
    messages = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="ChatMessage.created_at")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(36), ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # "user", "assistant", "system"
    content = Column(Text, nullable=False)
    sources = Column(Text, nullable=True)  # JSON-encoded array of safe source labels
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    conversation = relationship("ChatConversation", back_populates="messages")

class ChatUsageLog(Base):
    __tablename__ = "chat_usage_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(String(36), nullable=True, index=True)
    provider = Column(String(50), nullable=False, default="gemini")
    model = Column(String(80), nullable=False, default="gemini-3.5-flash-lite")
    status = Column(String(20), nullable=False, default="SUCCESS")  # SUCCESS, DEGRADED, ERROR, RATE_LIMITED
    latency_ms = Column(Float, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    error_category = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
