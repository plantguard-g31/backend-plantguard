import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship

# 1. Define Base locally to prevent circular import errors
class Base(DeclarativeBase):
    pass

# ===== TABLE 1: USERS =====
class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, default="Farmer")
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(10), nullable=False, default="farmer")
    language_pref = Column(String(2), nullable=False, default="en")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    profile_picture_url = Column(String, nullable=True)
    
    diagnosis_history = relationship("DiagnosisHistory", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")

# ===== TABLE 2: TREATMENT_RECORDS =====
class TreatmentRecord(Base):
    __tablename__ = "treatment_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    disease_name = Column(String(100), nullable=False, index=True)
    crop_type = Column(String(20), nullable=False)
    severity_level = Column(String(10), nullable=False) # ADDED per SRS v3.1
    pesticide_name = Column(String(100), nullable=False)
    dosage_mild = Column(String(100), nullable=False)
    dosage_moderate = Column(String(100), nullable=False)
    dosage_severe = Column(String(100), nullable=False)
    application_timing = Column(Text, nullable=False) # RENAMED from application_method
    safety_instructions = Column(Text, nullable=False) # RENAMED from safety_warning
    pre_harvest_interval_days = Column(Integer, nullable=False) # ADDED per SRS v3.1
    source_reference = Column(String(200), nullable=False) # RENAMED from source
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Composite unique key: One treatment per (disease + crop + severity) per SRS v3.1
    __table_args__ = (
        Index("ix_disease_crop_severity", "disease_name", "crop_type", "severity_level", unique=True),
    )
    
    # Relationships
    diagnosis_histories = relationship("DiagnosisHistory", back_populates="treatment")
    translations = relationship("TreatmentTranslation", back_populates="treatment", cascade="all, delete-orphan")

# ===== TABLE 3: DIAGNOSIS_HISTORY =====
class DiagnosisHistory(Base):
    __tablename__ = "diagnosis_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    disease_label = Column(String(100), nullable=False, index=True)
    crop_type = Column(String(20), nullable=False)
    confidence = Column(Float, nullable=False) # RENAMED from confidence_score
    severity = Column(String(10), nullable=True) # RENAMED from severity_level
    treatment_id = Column(UUID(as_uuid=True), ForeignKey("treatment_records.id", ondelete="SET NULL"), nullable=True, index=True)
    image_blur_score = Column(Float, nullable=False) # CHANGED to nullable=False per SRS
    image_brightness = Column(Float, nullable=False) # CHANGED to nullable=False per SRS
    quality_passed = Column(Boolean, nullable=False, default=True) # CHANGED to nullable=False per SRS
    low_confidence_warning = Column(Boolean, nullable=False, default=False) # CHANGED to nullable=False per SRS
    diagnosed_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    user = relationship("User", back_populates="diagnosis_history")
    treatment = relationship("TreatmentRecord", back_populates="diagnosis_histories")
    
    # Composite index for analytics query speed per SRS v3.1
    __table_args__ = (
        Index("ix_user_diagnosed_at", "user_id", "diagnosed_at"),
    )

# ===== TABLE 4: TREATMENT_TRANSLATIONS =====
class TreatmentTranslation(Base):
    __tablename__ = "treatment_translations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    treatment_record_id = Column(UUID(as_uuid=True), ForeignKey("treatment_records.id", ondelete="CASCADE"), nullable=False, index=True) # RENAMED per SRS
    language_code = Column(String(2), nullable=False)
    disease_name_translated = Column(String(200), nullable=False) # ADDED per SRS
    treatment_instructions_translated = Column(Text, nullable=False) # ADDED per SRS
    safety_warnings_translated = Column(Text, nullable=False) # ADDED per SRS
    
    treatment = relationship("TreatmentRecord", back_populates="translations")
    
    # One translation per language per record per SRS v3.1
    __table_args__ = (
        Index("ix_treatment_lang", "treatment_record_id", "language_code", unique=True),
    )

# ===== TABLE 5: AUDIT_LOGS =====
class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String(50), nullable=False, index=True)
    endpoint = Column(String(100), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    additional_data = Column(JSONB, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    user = relationship("User", back_populates="audit_logs")