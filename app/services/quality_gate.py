import cv2
import numpy as np
from fastapi import UploadFile, HTTPException
import logging

logger = logging.getLogger("plantguard.quality")

async def run_quality_checks(file: UploadFile) -> dict:

    content = await file.read()
    nparr = np.frombuffer(content, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if img is None:
        logger.error("OpenCV failed to decode image")
        raise HTTPException(status_code=422, detail="invalid_input")
    
    h, w = img.shape[:2]
    
    # Check 1: Resolution (Must be >= 224x224 for the AI model)
    if h < 224 or w < 224:
        raise HTTPException(status_code=422, detail="low_resolution")
        
    # Check 2: Blur (Calibrated for mobile cameras)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    if laplacian_var < 60: 
        raise HTTPException(status_code=422, detail="blurry_image")
        
    # Check 3: Brightness (Calibrated for field shade)
    mean_brightness = float(np.mean(gray))
    if mean_brightness < 30:
        raise HTTPException(status_code=422, detail="image_too_dark")
    if mean_brightness > 220:
        raise HTTPException(status_code=422, detail="image_too_bright")
        
    # Check 4: Vegetation Ratio (Calibrated for diseased leaves)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # Green mask
    lower_green = np.array([40, 40, 40])
    upper_green = np.array([80, 255, 255])
    green_mask = cv2.inRange(hsv, lower_green, upper_green)
    
    # Yellow/Brown mask (for diseased leaves)
    lower_yellow = np.array([15, 40, 40])
    upper_yellow = np.array([35, 255, 255])
    yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
    
    # Combine masks
    vegetation_mask = cv2.bitwise_or(green_mask, yellow_mask)
    vegetation_ratio = np.sum(vegetation_mask > 0) / vegetation_mask.size
    
    # If less than 10% of the image is vegetation, it's not a leaf.
    if vegetation_ratio < 0.10:
        raise HTTPException(status_code=422, detail="no_leaf_detected")
        
    await file.seek(0)
    logger.info(" All quality checks passed!")
    
    return {
        "content": content,
        "blur_score": float(laplacian_var),
        "brightness": mean_brightness
    }