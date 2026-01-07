from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional

from app.models.schemas import FineRecord
from app.services.fine_service import fine_service

router = APIRouter()


@router.get("/fines", response_model=List[FineRecord])
async def get_fines(
    limit: int = Query(default=100, ge=1, le=1000),
    unpaid_only: bool = Query(default=False)
):
    """
    Get list of issued fines.
    
    Args:
        limit: Maximum number of records to return (1-1000)
        unpaid_only: If true, return only unpaid fines
    """
    return await fine_service.get_fines(limit=limit, unpaid_only=unpaid_only)


@router.get("/fines/plate/{plate_number}", response_model=List[FineRecord])
async def get_fines_by_plate(plate_number: str):
    """
    Get all fines for a specific plate number.
    """
    return await fine_service.get_fine_by_plate(plate_number)


@router.post("/fines/{fine_id}/pay")
async def mark_fine_paid(fine_id: int):
    """
    Mark a fine as paid.
    """
    success = await fine_service.mark_fine_paid(fine_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Fine not found")
    
    return {"message": "Fine marked as paid", "fine_id": fine_id}


@router.get("/fines/summary")
async def get_fines_summary():
    """
    Get summary statistics for fines.
    """
    all_fines = await fine_service.get_fines(limit=10000)
    unpaid_fines = [f for f in all_fines if not f.paid]
    
    total_amount = sum(f.fine_amount for f in all_fines)
    unpaid_amount = sum(f.fine_amount for f in unpaid_fines)
    
    # Count by type
    type_counts = {}
    for fine in all_fines:
        type_counts[fine.fine_type] = type_counts.get(fine.fine_type, 0) + 1
    
    return {
        "total_fines": len(all_fines),
        "unpaid_fines": len(unpaid_fines),
        "paid_fines": len(all_fines) - len(unpaid_fines),
        "total_amount": total_amount,
        "unpaid_amount": unpaid_amount,
        "collected_amount": total_amount - unpaid_amount,
        "fines_by_type": type_counts
    }

