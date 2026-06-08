import cv2
import numpy as np
from fastapi import UploadFile, HTTPException
import logging

logger = logging.getLogger("plantguard.quality")

async def run_quality_checks(file: UploadFile) -> bytes:
    """
    DEBUG VERSION: Logs each quality check result.
    Returns processed image bytes if all checks pass.
    """
    # Read file content
    content = await file.read()
    
    # Convert to OpenCV format
    nparr = np.frombuffer(content, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if img is None:
        logger.error("OpenCV failed to decode image")
        raise HTTPException(status_code=422, detail="Photo quality not good enough. Please retake in better lighting.")
    
    h, w = img.shape[:2]
    logger.info(f"Image loaded: {w}x{h}, channels={img.shape[2] if len(img.shape)==3 else 1}")
    
    # Check 1: Resolution
    if h < 224 or w < 224:
        logger.error(f"FAIL: Resolution {w}x{h} < 224x224")
        raise HTTPException(status_code=422, detail="Photo resolution too low. Please retake closer to the leaf.")
    logger.info("PASS: Resolution OK")
    
    # Check 2: Blur (Laplacian variance)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    logger.info(f"Laplacian variance: {laplacian_var:.2f}")
    if laplacian_var < 100:
        logger.error(f"FAIL: Image too blurry (variance {laplacian_var:.2f} < 100)")
        raise HTTPException(status_code=422, detail="Photo is blurry. Please hold steady and retake.")
    logger.info("PASS: Sharpness OK")
    
    # Check 3: Brightness
    mean_brightness = np.mean(gray)
    logger.info(f"Mean brightness: {mean_brightness:.2f}")
    if mean_brightness < 40 or mean_brightness > 220:
        logger.error(f"FAIL: Brightness {mean_brightness:.2f} out of range [40, 220]")
        raise HTTPException(status_code=422, detail="Photo quality not good enough. Please retake in better lighting.")
    logger.info("PASS: Brightness OK")
    
    # Check 4: Green channel ratio
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower_green = np.array([40, 40, 40])
    upper_green = np.array([80, 255, 255])
    mask = cv2.inRange(hsv, lower_green, upper_green)
    green_ratio = np.sum(mask > 0) / mask.size
    logger.info(f"Green channel ratio: {green_ratio:.2f}")
    if green_ratio < 0.1:
        logger.error(f"FAIL: Green ratio {green_ratio:.2f} < 0.1 (not a leaf?)")
        raise HTTPException(status_code=422, detail="No leaf detected. Please ensure the photo shows a plant leaf.")
    logger.info("PASS: Green content OK")
    
    # All checks passed - reset file pointer for downstream use
    await file.seek(0)
    logger.info(" All quality checks passed!")
    
    return content