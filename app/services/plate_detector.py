"""
License Plate Detector using YOLOv8 ONLY
Uses a pre-trained YOLOv8 model for accurate plate detection
"""

import cv2
import numpy as np
from typing import List, Optional, Tuple
from dataclasses import dataclass
import os

from ultralytics import YOLO
import torch


@dataclass
class PlateRegion:
    """Detected plate region."""
    x: int
    y: int
    width: int
    height: int
    image: np.ndarray  # Cropped plate image
    confidence: float = 1.0


class PlateDetector:
    """
    Detects license plate regions using YOLOv8 with GPU acceleration.
    Includes result caching for high FPS operation.
    """
    
    def __init__(self):
        self._yolo_model: Optional[YOLO] = None
        self._device = 'cpu'
        
        # Model path
        self._model_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "models",
            "license_plate_detector.pt"
        )
        
        # Cache for last detection results (avoid double inference)
        self._last_results = None
        self._last_image_hash = None
        
        # Initialize YOLO model
        self._init_yolo()
    
    def _init_yolo(self):
        """Initialize the YOLOv8 model with GPU support."""
        if not os.path.exists(self._model_path):
            raise FileNotFoundError(f"YOLO model not found at {self._model_path}")
        
        print("🔄 Loading YOLOv8 license plate detector...")
        self._yolo_model = YOLO(self._model_path)
        
        # Check for MPS (Apple Silicon GPU) support
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            self._device = 'mps'
            print("🍎 YOLOv8 using Apple MPS GPU acceleration!")
        elif torch.cuda.is_available():
            self._device = 'cuda'
            print("🎮 YOLOv8 using NVIDIA CUDA GPU!")
        else:
            self._device = 'cpu'
            print("💻 YOLOv8 using CPU")
        
        print("✅ YOLOv8 model loaded successfully!")
    
    def _get_image_hash(self, image: np.ndarray) -> int:
        """Get a quick hash of the image for caching."""
        # Use a fast hash based on image shape and a sample of pixels
        return hash((image.shape, image[0, 0, 0].item() if image.size > 0 else 0, 
                     image[-1, -1, 0].item() if image.size > 0 else 0))
    
    def detect(self, image: np.ndarray, use_cache: bool = True) -> List[PlateRegion]:
        """
        Detect license plate regions in an image using YOLOv8.
        
        Args:
            image: BGR image (from cv2.imread or webcam)
            use_cache: If True, return cached results for same image
            
        Returns:
            List of detected plate regions
        """
        if image is None or image.size == 0:
            return []
        
        # Check cache
        if use_cache:
            img_hash = self._get_image_hash(image)
            if img_hash == self._last_image_hash and self._last_results is not None:
                return self._last_results
        
        height, width = image.shape[:2]
        plates = []
        
        try:
            # Run YOLO inference on GPU
            results = self._yolo_model(image, device=self._device, verbose=False)[0]
            
            # Process detections
            for box in results.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                confidence = float(box.conf[0])
                
                # Skip low confidence detections
                if confidence < 0.25:
                    continue
                
                # Ensure coordinates are within image bounds
                x1 = max(0, x1)
                y1 = max(0, y1)
                x2 = min(width, x2)
                y2 = min(height, y2)
                
                # Crop the plate region
                plate_image = image[y1:y2, x1:x2]
                
                if plate_image.size == 0:
                    continue
                
                plates.append(PlateRegion(
                    x=x1,
                    y=y1,
                    width=x2 - x1,
                    height=y2 - y1,
                    image=plate_image,
                    confidence=confidence
                ))
            
            # Cache results
            if use_cache:
                self._last_image_hash = img_hash
                self._last_results = plates
            
            if plates:
                print(f"🎯 YOLOv8 detected {len(plates)} plate(s) on {self._device.upper()}")
            
            return plates
            
        except Exception as e:
            print(f"⚠️ YOLO detection error: {e}")
            return []
    
    def detect_raw(self, image: np.ndarray):
        """
        Get raw YOLOv8 results for visualization.
        
        Returns:
            YOLOv8 Results object
        """
        if image is None or image.size == 0:
            return None
        
        return self._yolo_model(image, device=self._device, verbose=False)[0]
    
    def get_yolo_visualization(self, image: np.ndarray) -> Tuple[np.ndarray, int]:
        """
        Get YOLOv8's native visualization with bounding boxes.
        
        Args:
            image: BGR image
            
        Returns:
            Tuple of (annotated image, number of detections)
        """
        annotated, num_detections, _ = self.get_yolo_visualization_with_info(image)
        return annotated, num_detections
    
    def get_yolo_visualization_with_info(self, image: np.ndarray) -> Tuple[np.ndarray, int, list]:
        """
        Get YOLOv8's visualization with bounding boxes AND plate info in single inference.
        Optimized for high FPS operation.
        
        Args:
            image: BGR image
            
        Returns:
            Tuple of (annotated image, number of detections, list of plate info dicts)
        """
        if image is None or image.size == 0:
            return image, 0, []
        
        try:
            # Run YOLO inference ONCE
            results = self._yolo_model(image, device=self._device, verbose=False)[0]
            
            # Use YOLOv8's built-in plot() method for visualization
            annotated = results.plot(
                conf=True,      # Show confidence
                labels=True,    # Show class labels
                boxes=True,     # Show bounding boxes
                line_width=2    # Box line width
            )
            
            num_detections = len(results.boxes)
            
            # Extract plate info from the same results
            plates = []
            for i, box in enumerate(results.boxes):
                confidence = float(box.conf[0])
                if confidence >= 0.25:
                    plates.append({
                        "label": f"Plate {i+1}",
                        "confidence": confidence
                    })
            
            # Add header with device info
            header = f"YOLOv8 on {self._device.upper()} | {num_detections} detection(s)"
            cv2.rectangle(annotated, (0, 0), (400, 35), (0, 0, 0), -1)
            cv2.putText(annotated, header, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            
            return annotated, num_detections, plates
            
        except Exception as e:
            print(f"⚠️ Visualization error: {e}")
            return image, 0, []
    
    def preprocess_plate(self, plate_image: np.ndarray) -> np.ndarray:
        """
        Preprocess cropped plate image for better OCR.
        """
        target_height = 100
        aspect = plate_image.shape[1] / plate_image.shape[0]
        target_width = int(target_height * aspect)
        resized = cv2.resize(plate_image, (target_width, target_height))
        
        if len(resized.shape) == 3:
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        else:
            gray = resized
        
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        denoised = cv2.fastNlMeansDenoising(enhanced, None, 10, 7, 21)
        _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        return thresh
    
    def draw_detections(self, image: np.ndarray, regions: List[PlateRegion]) -> np.ndarray:
        """
        Use YOLOv8's native visualization.
        """
        annotated, _ = self.get_yolo_visualization(image)
        return annotated
    
    @property
    def detection_method(self) -> str:
        return "YOLOv8"
    
    @property
    def device(self) -> str:
        return self._device


# Global detector instance
plate_detector = PlateDetector()
