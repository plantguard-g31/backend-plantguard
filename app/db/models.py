import uuid
from datetime import datetime, time
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, Time, ForeignKey, Index, func
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
    is_super_admin = Column(Boolean, nullable=False, default=False)
    language_pref = Column(String(2), nullable=False, default="en")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    profile_picture_url = Column(String, nullable=True)
    refresh_token = Column(String(500), nullable=True)
    refresh_token_expiry = Column(DateTime, nullable=True)
    
    # ✅ NOTIFICATION FEATURE — Firebase Cloud Messaging device token
    # Stored when Flutter app calls POST /notifications/fcm-token
    # Nullable because new users haven't registered their device yet
    fcm_token = Column(String(500), nullable=True)
    
    diagnosis_history = relationship("DiagnosisHistory", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")
    
    # ✅ NOTIFICATION FEATURE — Relationships
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    notification_preferences = relationship(
        "UserNotificationPreference", 
        back_populates="user", 
        uselist=False,  # One-to-one: each user has exactly one preference row
        cascade="all, delete-orphan"
    )

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
    
    # NOTIFICATION FEATURE — Relationship to notifications triggered by this diagnosis
    notifications = relationship("Notification", back_populates="diagnosis")
    
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
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    endpoint = Column(String(100), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    additional_data = Column(JSONB, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    user = relationship("User", back_populates="audit_logs")


# ===== TABLE 6: PASSWORD_RESET_TOKENS =====
class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, index=True)  # Which farmer requested reset
    otp_code = Column(String(6), nullable=False)              # 6-digit code (plain text, short-lived)
    expires_at = Column(DateTime, nullable=False)             # 15 minutes from creation
    is_used = Column(Boolean, nullable=False, default=False)  # Single-use protection
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Index for fast lookup when verifying OTP
    __table_args__ = (
        Index("ix_reset_email_code", "email", "otp_code"),
    )


# ===== TABLE 7: NOTIFICATIONS ✅ NEW =====
class Notification(Base):
    """
    Stores every notification scheduled for a farmer.
    
    Types:
    - treatment_reminder: "Time to spray your tomatoes with Mancozeb"
    - follow_up: "How is your plant recovering? Tap to diagnose again"
    - phi_warning: "Stop spraying — pre-harvest interval reached"
    - crop_recommendation: "Consider growing potato this season"
    
    Flow:
    1. Farmer diagnoses a plant → notification_scheduler creates rows here
    2. APScheduler runs every hour → finds rows where scheduled_at <= now AND sent_at IS NULL
    3. Sends push notification via FCM → sets sent_at
    4. Farmer taps notification → Flutter sets read_at
    """
    __tablename__ = "notifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Who gets this notification
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Which diagnosis triggered this (nullable for crop_recommendation type)
    diagnosis_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("diagnosis_history.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )
    
    # Type of notification — determines the icon, color, and action in Flutter
    notification_type = Column(String(30), nullable=False, index=True)
    # Values: 'treatment_reminder', 'follow_up', 'phi_warning', 'crop_recommendation'
    
    # Bilingual content (always stored in both languages)
    title_en = Column(String(200), nullable=False)
    title_ne = Column(String(200), nullable=False)
    message_en = Column(Text, nullable=False)
    message_ne = Column(Text, nullable=False)
    
    # Scheduling
    scheduled_at = Column(DateTime, nullable=False, index=True)  # When to send
    sent_at = Column(DateTime, nullable=True)                     # When actually sent (null = pending)
    read_at = Column(DateTime, nullable=True)                     # When farmer opened it (null = unread)
    
    # Status
    is_active = Column(Boolean, nullable=False, default=True)    # False = cancelled (e.g., farmer deleted diagnosis)
    is_delivered = Column(Boolean, nullable=False, default=False) # True = FCM confirmed delivery
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="notifications")
    diagnosis = relationship("DiagnosisHistory", back_populates="notifications")
    
    # Index for the scheduler query: find pending notifications due now
    __table_args__ = (
        Index("ix_notification_pending", "scheduled_at", "sent_at", "is_active"),
        Index("ix_notification_user_unread", "user_id", "read_at"),
    )


# ===== TABLE 8: USER NOTIFICATION PREFERENCES ✅ NEW =====
class UserNotificationPreference(Base):
    """
    One-to-one with User. Stores farmer's notification settings.
    
    Created automatically when user registers (default: all enabled, 7 AM).
    Updated via PUT /notifications/preferences endpoint.
    
    Quiet hours: No notifications between quiet_hours_start and quiet_hours_end.
    Example: quiet_hours_start = 20:00 (8 PM), quiet_hours_end = 07:00 (7 AM)
    """
    __tablename__ = "user_notification_preferences"
    
    # Primary key is also FK to users (one-to-one relationship)
    user_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="CASCADE"), 
        primary_key=True
    )
    
    # Which types of notifications the farmer wants
    treatment_reminders_enabled = Column(Boolean, nullable=False, default=True)
    follow_ups_enabled = Column(Boolean, nullable=False, default=True)
    crop_recommendations_enabled = Column(Boolean, nullable=False, default=True)
    
    # Quiet hours (no notifications during this window)
    quiet_hours_start = Column(Time, nullable=True)   # e.g., time(20, 0) = 8 PM
    quiet_hours_end = Column(Time, nullable=True)     # e.g., time(7, 0) = 7 AM
    
    # Preferred hour for treatment reminders (default 7 AM)
    preferred_notification_hour = Column(Integer, nullable=False, default=7)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship back to user
    user = relationship("User", back_populates="notification_preferences")