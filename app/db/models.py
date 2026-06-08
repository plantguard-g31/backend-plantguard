from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey, Index, Boolean, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship
import uuid
from datetime import datetime

class Base(DeclarativeBase):
    pass


# ===== TABLE 1: USERS (Farmer accounts) =====
class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, default="Farmer")  
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="farmer")  # farmer | admin
    language_pref = Column(String(2), default="en")  # en | ne
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    diagnoses = relationship("DiagnosisHistory", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")


# ===== TABLE 2: DIAGNOSIS_HISTORY (Every past diagnosis) =====
class DiagnosisHistory(Base):
    __tablename__ = "diagnosis_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    treatment_id = Column(UUID(as_uuid=True), ForeignKey("treatment_records.id", ondelete="SET NULL"), nullable=True, index=True)  # ✅ CHANGED: nullable=True + SET NULL
    confidence_score = Column(Float, nullable=False)  # 0.0 to 1.0
    severity_level = Column(String(20))  # mild | moderate | severe
    is_confidence_flag = Column(Boolean, default=False)  # Tracks low-confidence cases (<60%)
    image_hash = Column(String(64), nullable=True)  # SHA-256 for deduplication
    diagnosed_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship("User", back_populates="diagnoses")
    
    # REMOVED: disease_name & crop_type (now derived via FK join for normalization)
    
    # Composite index for analytics queries (user + time)
    __table_args__ = (
        Index("ix_user_diagnosed_at", user_id, diagnosed_at),
    )


# ===== TABLE 3: TREATMENT_RECORDS (Expert-verified treatments) =====
# UPDATED: Single row per disease, with severity-specific dosage columns
class TreatmentRecord(Base):
    __tablename__ = "treatment_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    disease_name = Column(String(100), nullable=False, index=True)
    crop_type = Column(String(50), nullable=False)  # tomato | potato | bell_pepper
    pesticide_name = Column(String(100), nullable=False)
    
    # Severity-specific dosage columns (matches ER Diagram)
    dosage_mild = Column(String(200), nullable=False)
    dosage_moderate = Column(String(200), nullable=False)
    dosage_severe = Column(String(200), nullable=False)
    
    application_method = Column(String(100), nullable=False)
    safety_warning = Column(Text, nullable=False)
    source = Column(String(255), nullable=False)  
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    translations = relationship("TreatmentTranslation", back_populates="treatment", cascade="all, delete-orphan")
    
    # Composite unique key: One treatment per (disease + crop)
    __table_args__ = (
        Index("ix_disease_crop", disease_name, crop_type, unique=True),
    )


# ===== TABLE 4: TREATMENT_TRANSLATIONS (Multi-language support) =====
class TreatmentTranslation(Base):
    __tablename__ = "treatment_translations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    treatment_id = Column(UUID(as_uuid=True), ForeignKey("treatment_records.id", ondelete="CASCADE"), nullable=False)
    language_code = Column(String(2), nullable=False)  # en | ne
    field_name = Column(String(50), nullable=False)  # pesticide_name | dosage | safety_warning | application_method
    translated_text = Column(Text, nullable=False)
    
    # Relationships
    treatment = relationship("TreatmentRecord", back_populates="translations")
    
    # Ensure one translation per field per language
    __table_args__ = (
        Index("ix_treatment_lang_field", treatment_id, language_code, field_name, unique=True),
    )


# ===== TABLE 5: AUDIT_LOGS =====
class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(50), nullable=False, index=True)  # login | upload | reject | rate_limit
    endpoint = Column(String(100), nullable=True)
    http_status_code = Column(Integer, nullable=True)  
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(String(255), nullable=True)
    details = Column(Text, nullable=True)  # JSON string with extra context
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")

    