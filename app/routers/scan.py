from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from typing import Optional, List
import time
import base64
import cv2
import numpy as np

from app.models.schemas import ScanFrameResponse, ScanResult, CacheStats
from app.services.ocr_service import ocr_service
from app.services.plate_cache import plate_cache
from app.services.validation_api import validation_api
from app.services.fine_service import fine_service
from app.services.plate_detector import plate_detector
from app.config import get_settings

router = APIRouter()
settings = get_settings()


class Base64ImageRequest(BaseModel):
    """Request body for base64 image scan."""
    image: str  # Base64 encoded image


@router.post("/scan-frame", response_model=ScanFrameResponse)
async def scan_frame(file: UploadFile = File(...)):
    """
    Process a single video frame and detect car plates.
    
    This endpoint:
    1. Receives an image frame from the webcam
    2. Runs OCR to detect car plates
    3. Checks cache for recently scanned plates
    4. For new plates, calls external API to validate tax/insurance
    5. Issues fines for non-compliant vehicles
    6. Returns all results to the frontend
    """
    start_time = time.time()
    
    try:
        # Read image data
        image_data = await file.read()
        
        if not image_data:
            return ScanFrameResponse(
                success=False,
                plates_detected=0,
                results=[],
                processing_time_ms=0
            )
        
        # Detect plates using OCR
        plates = await ocr_service.detect_plates(image_data)
        
        if not plates:
            return ScanFrameResponse(
                success=True,
                plates_detected=0,
                results=[],
                processing_time_ms=(time.time() - start_time) * 1000
            )
        
        results = []
        
        for plate in plates:
            result = await _process_plate(plate.plate_number, plate.confidence)
            results.append(result)
        
        return ScanFrameResponse(
            success=True,
            plates_detected=len(plates),
            results=results,
            processing_time_ms=(time.time() - start_time) * 1000
        )
        
    except Exception as e:
        return ScanFrameResponse(
            success=False,
            plates_detected=0,
            results=[],
            processing_time_ms=(time.time() - start_time) * 1000
        )


@router.post("/scan-frame-base64", response_model=ScanFrameResponse)
async def scan_frame_base64(request: Base64ImageRequest):
    """
    Process a base64-encoded video frame and detect car plates.
    Alternative to file upload for webcam frames.
    """
    start_time = time.time()
    
    try:
        # Detect plates from base64 image
        plates = await ocr_service.detect_plates_from_base64(request.image)
        
        if not plates:
            return ScanFrameResponse(
                success=True,
                plates_detected=0,
                results=[],
                processing_time_ms=(time.time() - start_time) * 1000
            )
        
        results = []
        
        for plate in plates:
            result = await _process_plate(plate.plate_number, plate.confidence)
            results.append(result)
        
        return ScanFrameResponse(
            success=True,
            plates_detected=len(plates),
            results=results,
            processing_time_ms=(time.time() - start_time) * 1000
        )
        
    except Exception as e:
        print(f"Error processing frame: {e}")
        return ScanFrameResponse(
            success=False,
            plates_detected=0,
            results=[],
            processing_time_ms=(time.time() - start_time) * 1000
        )


async def _process_plate(plate_number: str, confidence: float) -> ScanResult:
    """
    Process a single detected plate.
    Uses cache-first logic to avoid duplicate API calls.
    Only issues fines for high confidence detections (>0.9).
    """
    # Minimum confidence to issue a fine
    MIN_FINE_CONFIDENCE = 0.9
    
    # Check if plate was recently scanned
    cached_status = plate_cache.get_cached_result(plate_number)
    
    if cached_status is not None:
        # Return cached result without calling API
        return ScanResult(
            plate_number=plate_number,
            confidence=confidence,
            cached=True,
            vehicle_status=cached_status,
            fine_issued=False,  # Fine already issued on first scan
            fine_amount=None
        )
    
    # Not in cache - fetch from external API
    try:
        vehicle_status = await validation_api.check_vehicle(plate_number)
        
        # Add to cache
        plate_cache.add_plate(plate_number, vehicle_status)
        
        # Check if fine needs to be issued
        # Only issue fine if confidence is above threshold
        fine_record = None
        if not vehicle_status.is_compliant and confidence >= MIN_FINE_CONFIDENCE:
            print(f"💰 Issuing fine for {plate_number} (confidence: {confidence:.2f})")
            fine_record = await fine_service.issue_fine(vehicle_status, confidence)
        elif not vehicle_status.is_compliant:
            print(f"⚠️ Low confidence ({confidence:.2f}) - skipping fine for {plate_number}")
            # Log but don't fine
            await fine_service.log_scan(
                plate_number, confidence, vehicle_status, 
                cached=False, fine_issued=False
            )
        else:
            # Log compliant scan
            await fine_service.log_scan(
                plate_number, confidence, vehicle_status, 
                cached=False, fine_issued=False
            )
        
        return ScanResult(
            plate_number=plate_number,
            confidence=confidence,
            cached=False,
            vehicle_status=vehicle_status,
            fine_issued=fine_record is not None,
            fine_amount=fine_record.fine_amount if fine_record else None
        )
        
    except Exception as e:
        print(f"❌ Error processing {plate_number}: {e}")
        return ScanResult(
            plate_number=plate_number,
            confidence=confidence,
            cached=False,
            vehicle_status=None,
            fine_issued=False,
            error=str(e)
        )


@router.get("/cache/stats", response_model=CacheStats)
async def get_cache_stats():
    """Get cache statistics."""
    return plate_cache.get_stats()


@router.post("/cache/clear")
async def clear_cache():
    """Clear the plate cache."""
    plate_cache.clear()
    return {"message": "Cache cleared successfully"}


@router.post("/cache/cleanup")
async def cleanup_cache():
    """Remove expired entries from cache."""
    removed = plate_cache.cleanup_expired()
    return {"message": f"Removed {removed} expired entries"}


class DebugImageRequest(BaseModel):
    """Request body for debug image."""
    image: str  # Base64 encoded image


class DebugResponse(BaseModel):
    """Response with debug image and detection info."""
    debug_image: str  # Base64 encoded image with boxes drawn
    regions_detected: int
    regions: List[dict]


@router.post("/debug-detection", response_model=DebugResponse)
async def debug_detection(request: DebugImageRequest):
    """
    Debug endpoint: Returns YOLOv8's native detection visualization.
    Shows exactly what YOLOv8 sees with bounding boxes and confidence scores.
    """
    try:
        # Decode base64 image
        image_data = request.image
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        image_bytes = base64.b64decode(image_data)
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            return DebugResponse(
                debug_image=request.image,
                regions_detected=0,
                regions=[]
            )
        
        # Resize for processing
        max_width, max_height = 800, 600
        height, width = image.shape[:2]
        if width > max_width or height > max_height:
            scale = min(max_width / width, max_height / height)
            image = cv2.resize(image, (int(width * scale), int(height * scale)))
        
        # Get YOLOv8's native visualization
        debug_image, num_detections = plate_detector.get_yolo_visualization(image)
        
        # Also get regions for info display
        regions = plate_detector.detect(image)
        
        # Convert back to base64
        _, buffer = cv2.imencode('.jpg', debug_image)
        debug_base64 = base64.b64encode(buffer).decode('utf-8')
        
        # Format region info
        region_info = [
            {
                "id": i + 1,
                "x": r.x,
                "y": r.y,
                "width": r.width,
                "height": r.height,
                "confidence": r.confidence
            }
            for i, r in enumerate(regions)
        ]
        
        return DebugResponse(
            debug_image=f"data:image/jpeg;base64,{debug_base64}",
            regions_detected=num_detections,
            regions=region_info
        )
        
    except Exception as e:
        print(f"Debug error: {e}")
        import traceback
        traceback.print_exc()
        return DebugResponse(
            debug_image=request.image,
            regions_detected=0,
            regions=[]
        )


@router.post("/test-fine")
async def test_fine():
    """
    Test endpoint: Create a mock fine for UI testing.
    """
    from app.models.schemas import VehicleStatus
    from datetime import datetime
    
    # Create a mock vehicle status
    mock_vehicle = VehicleStatus(
        plate_number="TEST123",
        owner_name="Test Owner",
        owner_id="123456789",
        road_tax_valid=False,
        insurance_valid=False
    )
    
    # Issue a fine
    fine_record = await fine_service.issue_fine(mock_vehicle, confidence=0.95)
    
    if fine_record:
        print(f"💰 TEST FINE ISSUED: {fine_record.plate_number} - RM {fine_record.fine_amount}")
        return {
            "success": True,
            "fine": {
                "plate_number": fine_record.plate_number,
                "fine_amount": fine_record.fine_amount,
                "fine_type": fine_record.fine_type,
                "owner_name": fine_record.owner_name,
                "issued_at": fine_record.issued_at.isoformat()
            }
        }
    
    return {"success": False, "message": "Failed to issue test fine"}

