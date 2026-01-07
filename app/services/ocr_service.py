"""
OCR Service with two-stage detection:
1. OpenCV detects plate regions
2. EasyOCR reads text only from detected regions
"""

import easyocr
import numpy as np
import cv2
import base64
import re
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor
import asyncio
import torch

from app.config import get_settings
from app.models.schemas import PlateDetection
from app.services.plate_detector import plate_detector

settings = get_settings()


def check_gpu_availability():
    """Check if GPU acceleration is available."""
    if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        print("🍎 Apple Silicon MPS detected")
        return True
    if torch.cuda.is_available():
        print("🎮 NVIDIA CUDA detected")
        return True
    print("💻 Using CPU")
    return False


class OCRService:
    """
    Two-stage car plate detection and recognition:
    1. OpenCV detects plate regions (fast)
    2. EasyOCR reads text from detected regions only (accurate)
    """
    
    def __init__(self):
        self._reader: Optional[easyocr.Reader] = None
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._min_confidence = settings.ocr_confidence_min
        self._use_gpu = check_gpu_availability()
        
        # Target size for processing
        self._max_width = 800
        self._max_height = 600
        
        # Plate patterns (Malaysian format)
        self._plate_patterns = [
            r'^[A-Z]{1,3}\s?\d{1,4}[A-Z]?$',
            r'^[A-Z]{1,3}\d{1,4}$',
            r'^\d{1,4}[A-Z]{1,3}$',
            r'^[A-Z]{2}\s?\d{4}\s?[A-Z]{2}$',
        ]
    
    def _get_reader(self) -> easyocr.Reader:
        """Lazy initialization of EasyOCR reader."""
        if self._reader is None:
            print("🔄 Initializing EasyOCR reader...")
            self._reader = easyocr.Reader(['en'], gpu=self._use_gpu and torch.cuda.is_available())
            print("✅ EasyOCR reader initialized")
        return self._reader
    
    def _resize_image(self, image: np.ndarray) -> np.ndarray:
        """Resize image for processing."""
        height, width = image.shape[:2]
        if width <= self._max_width and height <= self._max_height:
            return image
        scale = min(self._max_width / width, self._max_height / height)
        new_width = int(width * scale)
        new_height = int(height * scale)
        return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
    
    def _is_valid_plate(self, text: str) -> bool:
        """Check if detected text matches car plate patterns."""
        cleaned = text.upper().strip()
        cleaned = re.sub(r'[^A-Z0-9\s]', '', cleaned)
        
        if len(cleaned) < 2:
            return False
        
        for pattern in self._plate_patterns:
            if re.match(pattern, cleaned):
                return True
        
        # Lenient: accept any text with letters + numbers, length >= 3
        has_letters = bool(re.search(r'[A-Z]', cleaned))
        has_numbers = bool(re.search(r'\d', cleaned))
        return has_letters and has_numbers and len(cleaned) >= 3
    
    def _clean_plate_text(self, text: str) -> str:
        """Clean and normalize detected plate text."""
        cleaned = re.sub(r'[^A-Z0-9\s]', '', text.upper())
        cleaned = ' '.join(cleaned.split())
        return cleaned
    
    def _detect_plates_sync(self, image: np.ndarray) -> List[PlateDetection]:
        """
        Two-stage plate detection:
        1. Use OpenCV to find plate regions
        2. Run OCR only on those regions
        """
        reader = self._get_reader()
        image = self._resize_image(image)
        results = []
        
        # Stage 1: Detect plate regions using OpenCV
        plate_regions = plate_detector.detect(image)
        
        if plate_regions:
            print(f"🔍 YOLOv8 detected {len(plate_regions)} potential plate region(s)")
            
            # Stage 2: Run OCR on each detected region
            for i, region in enumerate(plate_regions):
                # Preprocess the plate region for better OCR
                preprocessed = plate_detector.preprocess_plate(region.image)
                
                # Run OCR on the cropped plate region
                ocr_results = reader.readtext(region.image)
                
                # Also try on preprocessed version
                if not ocr_results:
                    ocr_results = reader.readtext(preprocessed)
                
                for (bbox, text, confidence) in ocr_results:
                    cleaned_text = self._clean_plate_text(text)
                    is_valid = self._is_valid_plate(cleaned_text)
                    
                    print(f"   📝 Region {i+1}: '{text}' → '{cleaned_text}' (conf: {confidence:.2f}, valid: {is_valid})")
                    
                    if confidence >= self._min_confidence and is_valid:
                        print(f"🚗 PLATE FOUND: {cleaned_text}")
                        results.append(PlateDetection(
                            plate_number=cleaned_text,
                            confidence=confidence,
                            bounding_box=[[region.x, region.y], 
                                         [region.x + region.width, region.y],
                                         [region.x + region.width, region.y + region.height],
                                         [region.x, region.y + region.height]]
                        ))
        else:
            # Fallback: If no plate regions detected, scan whole image
            print("⚠️ No plate regions found, scanning whole image...")
            ocr_results = reader.readtext(image)
            
            if ocr_results:
                print(f"📷 OCR found {len(ocr_results)} text regions in full image:")
                
            for (bbox, text, confidence) in ocr_results:
                cleaned_text = self._clean_plate_text(text)
                is_valid = self._is_valid_plate(cleaned_text)
                status = "✅" if (confidence >= self._min_confidence and is_valid) else "❌"
                print(f"   {status} '{text}' → '{cleaned_text}' (conf: {confidence:.2f})")
                
                if confidence >= self._min_confidence and is_valid:
                    print(f"🚗 PLATE FOUND: {cleaned_text}")
                    results.append(PlateDetection(
                        plate_number=cleaned_text,
                        confidence=confidence,
                        bounding_box=[[int(p[0]), int(p[1])] for p in bbox]
                    ))
        
        return results
    
    async def detect_plates(self, image_data: bytes) -> List[PlateDetection]:
        """Detect and read car plates from image data."""
        nparr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            return []
        
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            self._executor,
            self._detect_plates_sync,
            image
        )
        return results
    
    async def detect_plates_from_base64(self, base64_data: str) -> List[PlateDetection]:
        """Detect plates from base64-encoded image."""
        if ',' in base64_data:
            base64_data = base64_data.split(',')[1]
        image_bytes = base64.b64decode(base64_data)
        return await self.detect_plates(image_bytes)


# Global OCR service instance
ocr_service = OCRService()
