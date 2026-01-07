import cv2
import numpy as np
from typing import Tuple, Optional


def resize_image(
    image: np.ndarray, 
    max_width: int = 1280, 
    max_height: int = 720
) -> np.ndarray:
    """
    Resize image while maintaining aspect ratio.
    """
    height, width = image.shape[:2]
    
    if width <= max_width and height <= max_height:
        return image
    
    # Calculate scaling factor
    scale_w = max_width / width
    scale_h = max_height / height
    scale = min(scale_w, scale_h)
    
    new_width = int(width * scale)
    new_height = int(height * scale)
    
    return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)


def enhance_contrast(image: np.ndarray) -> np.ndarray:
    """
    Enhance image contrast using CLAHE.
    """
    if len(image.shape) == 3:
        # Convert to LAB color space
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # Apply CLAHE to L channel
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        
        # Merge and convert back
        lab = cv2.merge([l, a, b])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    else:
        # Grayscale image
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(image)


def detect_plate_region(image: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Attempt to detect license plate region using edge detection.
    Returns (x, y, width, height) or None if not found.
    """
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    
    # Blur and edge detection
    blur = cv2.bilateralFilter(gray, 11, 17, 17)
    edges = cv2.Canny(blur, 30, 200)
    
    # Find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    # Sort by area, largest first
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:30]
    
    for contour in contours:
        # Approximate contour
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.018 * peri, True)
        
        # Look for rectangular shapes (4 corners)
        if len(approx) == 4:
            x, y, w, h = cv2.boundingRect(approx)
            
            # Check aspect ratio (license plates are typically 2:1 to 5:1)
            aspect_ratio = w / h
            if 2.0 <= aspect_ratio <= 5.0:
                # Check minimum size
                if w >= 60 and h >= 20:
                    return (x, y, w, h)
    
    return None


def crop_plate_region(
    image: np.ndarray, 
    region: Tuple[int, int, int, int],
    padding: int = 10
) -> np.ndarray:
    """
    Crop the detected plate region with optional padding.
    """
    x, y, w, h = region
    height, width = image.shape[:2]
    
    # Add padding while staying within bounds
    x1 = max(0, x - padding)
    y1 = max(0, y - padding)
    x2 = min(width, x + w + padding)
    y2 = min(height, y + h + padding)
    
    return image[y1:y2, x1:x2]


def deskew_image(image: np.ndarray) -> np.ndarray:
    """
    Deskew slightly rotated text in image.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    
    # Threshold
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Find coordinates of non-zero pixels
    coords = np.column_stack(np.where(thresh > 0))
    
    if len(coords) < 100:
        return image
    
    # Get rotation angle
    angle = cv2.minAreaRect(coords)[-1]
    
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    
    # Only deskew if angle is significant but not too large
    if abs(angle) < 0.5 or abs(angle) > 15:
        return image
    
    # Rotate image
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        image, M, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE
    )
    
    return rotated

