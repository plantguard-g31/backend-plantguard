import torch
import logging
from PIL import Image
from torchvision import transforms
from io import BytesIO
from typing import Optional, Dict, Any
import asyncio
import tempfile
import os

logger = logging.getLogger("plantguard.ai")

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────
USE_MOCK = True  # SET TO FALSE when ready to use real model
MODEL_NAME = "Precious466/plantguard-resnet50-teacher"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# IMPORTANT: This MUST match the order used during training
LABEL_MAP = {
    0: "Tomato Early Blight",
    1: "Tomato Late Blight", 
    2: "Tomato Septoria Leaf Spot",
    3: "Tomato Target Spot",
    4: "Tomato Bacterial Spot",
    5: "Tomato Healthy",
    6: "Potato Early Blight",
    7: "Potato Late Blight",
    8: "Potato Healthy",
    9: "Bell Pepper Bacterial Spot",
    10: "Bell Pepper Healthy",
}

_model = None
_preprocess = None

def _load_model():
    """Loads ResNet-50 teacher model trained with Torchvision transforms."""
    global _model, _preprocess
    
    if _model is None and not USE_MOCK:
        try:
            logger.info(f"Loading REAL AI model: {MODEL_NAME} on {DEVICE}")
            
            # Download model from Hugging Face
            from huggingface_hub import hf_hub_download
            
            # Download the .pth file
            model_path = hf_hub_download(
                repo_id=MODEL_NAME,
                filename="resnet50_teacher.pth",
                cache_dir="./models_cache"
            )
            
            # Load model state dict
            checkpoint = torch.load(model_path, map_location=DEVICE)
            
            # Create ResNet-50 model architecture
            from torchvision import models
            _model = models.resnet50(weights=None)
            
            # Handle different checkpoint formats
            if isinstance(checkpoint, dict) and 'state_dict' in checkpoint:
                state_dict = checkpoint['state_dict']
                # Remove 'module.' prefix if present (from DataParallel)
                state_dict = {k.replace('module.', ''): v for k, v in state_dict.items()}
            elif isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
                state_dict = checkpoint['model_state_dict']
            else:
                state_dict = checkpoint
            
            # Load state dict
            _model.load_state_dict(state_dict, strict=False)
            _model.to(DEVICE)
            _model.eval()
            
            # Define preprocessing transforms (MUST match training)
            _preprocess = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],  # ImageNet normalization
                    std=[0.229, 0.224, 0.225]
                )
            ])
            
            logger.info("REAL AI model loaded successfully.")
            logger.info(f"Model architecture: {_model.__class__.__name__}")
            logger.info(f"Preprocessing: {_preprocess}")
            
        except Exception as e:
            logger.error(f"Failed to load model: {type(e).__name__}: {e}")
            logger.warning("Falling back to MOCK predictions")
            _model = None

async def predict_disease(image_bytes: bytes, filename: str = "leaf.jpg") -> Optional[Dict[str, Any]]:
    """
    Runs disease prediction.
    
    If USE_MOCK = True: Returns mock prediction for testing
    If USE_MOCK = False: Calls real trained model
    """
    
    # ─────────────────────────────────────────────────────────────
    # MOCK MODE (For Testing)
    # ─────────────────────────────────────────────────────────────
    if USE_MOCK:
        logger.warning("Using MOCK prediction (real model disabled)")
        logger.info(f"Processing image: {filename}")
        
        # Simulate inference delay (0.5 seconds)
        await asyncio.sleep(0.5)
        
        # Return Top-3 predictions as required by SRS v3.1 FR-13
        return {
            "disease": "Tomato Early Blight",
            "confidence": 0.88,
            "top3": [
                {"label": "Tomato Early Blight", "confidence": 0.88},
                {"label": "Tomato Late Blight", "confidence": 0.07},
                {"label": "Tomato Septoria Leaf Spot", "confidence": 0.03}
            ]
        }
    

    '''
    # ─────────────────────────────────────────────────────────────
    # REAL MODEL MODE (When Ready)
    # ─────────────────────────────────────────────────────────────
    try:
        # Load model if not already loaded
        if _model is None:
            _load_model()
        
        if _model is None:
            logger.error("Model not loaded. Check USE_MOCK flag.")
            return None
        
        # Convert bytes to PIL Image
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        
        # Preprocess image using torchvision transforms
        input_tensor = _preprocess(image).unsqueeze(0).to(DEVICE)
        
        # Run inference in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        with torch.no_grad():
            outputs = await loop.run_in_executor(
                None, 
                lambda: _model(input_tensor)
            )
        
        # Get predictions
        logits = outputs
        probs = torch.softmax(logits, dim=-1)
        predicted_idx = logits.argmax(-1).item()
        confidence = probs[0][predicted_idx].item()
        
        # Map to disease name
        disease = LABEL_MAP.get(predicted_idx, f"Unknown Class {predicted_idx}")
        
        logger.info(f"AI Prediction: {disease} (confidence: {confidence:.2f}, class: {predicted_idx})")
        
        return {
            "disease": disease, 
            "confidence": confidence, 
            "class_id": predicted_idx
        }
        
    except Exception as e:
        logger.error(f"AI inference failed: {type(e).__name__}: {e}")
        logger.warning("Falling back to MOCK prediction")
        return None
    '''