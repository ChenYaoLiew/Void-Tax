from datetime import datetime
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.database import Fine, ScanLog, AsyncSessionLocal
from app.models.schemas import VehicleStatus, FineRecord, ComplianceStatus
from app.services.validation_api import validation_api

settings = get_settings()


class FineService:
    """
    Service for issuing and managing fines.
    """
    
    def __init__(self):
        self._road_tax_fine = settings.road_tax_fine_amount
        self._insurance_fine = settings.insurance_fine_amount
    
    def calculate_fine(self, vehicle_status: VehicleStatus) -> tuple[float, str]:
        """
        Calculate fine amount based on vehicle status.
        
        Returns:
            Tuple of (fine_amount, fine_type)
        """
        status = vehicle_status.compliance_status
        
        if status == ComplianceStatus.BOTH_EXPIRED:
            return self._road_tax_fine + self._insurance_fine, "both"
        elif status == ComplianceStatus.TAX_EXPIRED:
            return self._road_tax_fine, "road_tax"
        elif status == ComplianceStatus.INSURANCE_EXPIRED:
            return self._insurance_fine, "insurance"
        else:
            return 0.0, "none"
    
    async def issue_fine(
        self, 
        vehicle_status: VehicleStatus,
        confidence: float = 1.0
    ) -> Optional[FineRecord]:
        """
        Issue a fine for a non-compliant vehicle.
        
        Args:
            vehicle_status: The vehicle's validation status
            confidence: OCR confidence score
            
        Returns:
            FineRecord if fine was issued, None otherwise
        """
        if vehicle_status.is_compliant:
            return None
        
        fine_amount, fine_type = self.calculate_fine(vehicle_status)
        
        if fine_amount == 0:
            return None
        
        async with AsyncSessionLocal() as session:
            # Create fine record
            fine = Fine(
                plate_number=vehicle_status.plate_number,
                owner_name=vehicle_status.owner_name,
                owner_id=vehicle_status.owner_id,
                fine_type=fine_type,
                fine_amount=fine_amount,
                issued_at=datetime.now()
            )
            session.add(fine)
            
            # Create scan log
            scan_log = ScanLog(
                plate_number=vehicle_status.plate_number,
                scanned_at=datetime.now(),
                confidence=confidence,
                road_tax_valid=vehicle_status.road_tax_valid,
                insurance_valid=vehicle_status.insurance_valid,
                fine_issued=True,
                cached_result=False
            )
            session.add(scan_log)
            
            await session.commit()
            await session.refresh(fine)
            
            # Notify external API (non-blocking)
            await validation_api.notify_fine(
                vehicle_status.plate_number, 
                fine_amount, 
                fine_type
            )
            
            return FineRecord(
                id=fine.id,
                plate_number=fine.plate_number,
                owner_name=fine.owner_name,
                owner_id=fine.owner_id,
                fine_type=fine.fine_type,
                fine_amount=fine.fine_amount,
                issued_at=fine.issued_at,
                paid=fine.paid
            )
    
    async def log_scan(
        self,
        plate_number: str,
        confidence: float,
        vehicle_status: Optional[VehicleStatus],
        cached: bool = False,
        fine_issued: bool = False
    ) -> None:
        """Log a scan event."""
        async with AsyncSessionLocal() as session:
            scan_log = ScanLog(
                plate_number=plate_number,
                scanned_at=datetime.now(),
                confidence=confidence,
                road_tax_valid=vehicle_status.road_tax_valid if vehicle_status else None,
                insurance_valid=vehicle_status.insurance_valid if vehicle_status else None,
                fine_issued=fine_issued,
                cached_result=cached
            )
            session.add(scan_log)
            await session.commit()
    
    async def get_fines(
        self, 
        limit: int = 100, 
        unpaid_only: bool = False
    ) -> List[FineRecord]:
        """
        Get list of fines.
        
        Args:
            limit: Maximum number of records to return
            unpaid_only: If True, return only unpaid fines
            
        Returns:
            List of FineRecord objects
        """
        async with AsyncSessionLocal() as session:
            query = select(Fine).order_by(Fine.issued_at.desc()).limit(limit)
            
            if unpaid_only:
                query = query.where(Fine.paid == False)
            
            result = await session.execute(query)
            fines = result.scalars().all()
            
            return [
                FineRecord(
                    id=f.id,
                    plate_number=f.plate_number,
                    owner_name=f.owner_name,
                    owner_id=f.owner_id,
                    fine_type=f.fine_type,
                    fine_amount=f.fine_amount,
                    issued_at=f.issued_at,
                    paid=f.paid
                )
                for f in fines
            ]
    
    async def get_fine_by_plate(self, plate_number: str) -> List[FineRecord]:
        """Get all fines for a specific plate number."""
        normalized = plate_number.upper().replace(" ", "").replace("-", "")
        
        async with AsyncSessionLocal() as session:
            query = select(Fine).where(
                Fine.plate_number == normalized
            ).order_by(Fine.issued_at.desc())
            
            result = await session.execute(query)
            fines = result.scalars().all()
            
            return [
                FineRecord(
                    id=f.id,
                    plate_number=f.plate_number,
                    owner_name=f.owner_name,
                    owner_id=f.owner_id,
                    fine_type=f.fine_type,
                    fine_amount=f.fine_amount,
                    issued_at=f.issued_at,
                    paid=f.paid
                )
                for f in fines
            ]
    
    async def mark_fine_paid(self, fine_id: int) -> bool:
        """Mark a fine as paid."""
        async with AsyncSessionLocal() as session:
            query = select(Fine).where(Fine.id == fine_id)
            result = await session.execute(query)
            fine = result.scalar_one_or_none()
            
            if fine:
                fine.paid = True
                fine.paid_at = datetime.now()
                await session.commit()
                return True
            return False


# Global fine service instance
fine_service = FineService()

