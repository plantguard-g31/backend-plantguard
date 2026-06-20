from pydantic import BaseModel, Field, constr
from typing import Optional, List
from datetime import datetime

# ─────────────────────────────────────────────────────────────
# REQUEST SCHEMAS
# ─────────────────────────────────────────────────────────────
class DiagnoseQueryParams(BaseModel):
    """Query parameters for /diagnose endpoint."""
    lang: str = Field(default="en", regex="^(en|ne)$")
    minimal: bool = False

# ─────────────────────────────────────────────────────────────
# RESPONSE SCHEMAS
# ─────────────────────────────────────────────────────────────
class DiagnosisResponse(BaseModel):
    """Full diagnosis response (default mode)."""
    disease: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    severity: str  # mild | moderate | severe
    pesticide: str
    dosage: str
    application: str
    safety_notes: Optional[str]
    source: str
    low_confidence_warning: Optional[str]
    analytics_warning: Optional[str]
    
    class Config:
        json_schema_extra = {
            "example": {
                "disease": "Tomato Early Blight",
                "confidence": 0.88,
                "severity": "moderate",
                "pesticide": "Copper Hydroxide 77% WP",
                "dosage": "3g per 1L water, spray every 5 days",
                "application": "Foliar spray in early morning",
                "safety_notes": "Wear gloves & mask",
                "source": "FAO Plant Protection Manual 2023",
                "low_confidence_warning": None,
                "analytics_warning": None
            }
        }


class MinimalDiagnosisResponse(BaseModel):
    """Stripped response for ?minimal=true (low-bandwidth)."""
    disease: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    severity: str
    pesticide: str


class HistoryItem(BaseModel):
    """Single diagnosis history record."""
    id: str
    disease: str
    crop: str
    confidence: float
    severity: str
    diagnosed_at: datetime


class HistoryResponse(BaseModel):
    total: int
    limit: int
    offset: int
    has_more: bool
    items: List[HistoryItem]