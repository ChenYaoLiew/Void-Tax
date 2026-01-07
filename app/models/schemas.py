from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ComplianceStatus(str, Enum):
    """Vehicle compliance status."""
    COMPLIANT = "compliant"
    TAX_EXPIRED = "tax_expired"
    INSURANCE_EXPIRED = "insurance_expired"
    BOTH_EXPIRED = "both_expired"


class VehicleStatus(BaseModel):
    """Response from external validation API."""
    plate_number: str
    owner_name: Optional[str] = None
    owner_id: Optional[str] = None
    road_tax_valid: bool = True
    road_tax_expiry: Optional[datetime] = None
    insurance_valid: bool = True
    insurance_expiry: Optional[datetime] = None
    
    @property
    def is_compliant(self) -> bool:
        """Check if vehicle is fully compliant."""
        return self.road_tax_valid and self.insurance_valid
    
    @property
    def compliance_status(self) -> ComplianceStatus:
        """Get detailed compliance status."""
        if self.road_tax_valid and self.insurance_valid:
            return ComplianceStatus.COMPLIANT
        elif not self.road_tax_valid and not self.insurance_valid:
            return ComplianceStatus.BOTH_EXPIRED
        elif not self.road_tax_valid:
            return ComplianceStatus.TAX_EXPIRED
        else:
            return ComplianceStatus.INSURANCE_EXPIRED


class PlateDetection(BaseModel):
    """Single plate detection result."""
    plate_number: str
    confidence: float = Field(ge=0.0, le=1.0)
    bounding_box: Optional[List[List[int]]] = None


class ScanResult(BaseModel):
    """Result of scanning a single plate."""
    plate_number: str
    confidence: float
    cached: bool = False
    vehicle_status: Optional[VehicleStatus] = None
    fine_issued: bool = False
    fine_amount: Optional[float] = None
    error: Optional[str] = None


class ScanFrameResponse(BaseModel):
    """Response from scan-frame endpoint."""
    success: bool
    plates_detected: int = 0
    results: List[ScanResult] = []
    processing_time_ms: float = 0.0


class FineRecord(BaseModel):
    """Fine record schema."""
    id: Optional[int] = None
    plate_number: str
    owner_name: Optional[str] = None
    owner_id: Optional[str] = None
    fine_type: str  # "road_tax", "insurance", or "both"
    fine_amount: float
    issued_at: datetime = Field(default_factory=datetime.now)
    paid: bool = False
    
    class Config:
        from_attributes = True


class CacheStats(BaseModel):
    """Cache statistics."""
    total_entries: int
    active_entries: int
    expired_entries: int
    hit_count: int
    miss_count: int
    hit_rate: float

