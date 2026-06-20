import torch
import logging
from PIL import Image
from torchvision import transforms
from io import BytesIO
from typing import Optional, Dict, Any
import asyncio
import timm
from huggingface_hub import hf_hub_download

logger = logging.getLogger("plantguard.ai")

USE_MOCK = False  # Set to True for MOCK Use
MODEL_REPO = "Precious466/plantguard-resnet50-teacher"
MODEL_FILE = "deit_tiny_student.pth"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# 15 classes matching exact training order
LABEL_MAP = {
    0:  "Tomato Bacterial Spot", 1:  "Tomato Early Blight", 2:  "Tomato Late Blight",
    3:  "Tomato Leaf Mold", 4:  "Tomato Septoria Leaf Spot", 5:  "Tomato Spider Mites",
    6:  "Tomato Target Spot", 7:  "Tomato Yellow Leaf Curl Virus", 8:  "Tomato Mosaic Virus",
    9:  "Tomato Healthy", 10: "Potato Early Blight", 11: "Potato Late Blight",
    12: "Potato Healthy", 13: "Bell Pepper Bacterial Spot", 14: "Bell Pepper Healthy",
}

_model = None
_preprocess = None

def _load_model():
    global _model, _preprocess
    try:
        logger.info(f"Loading DeiT-Tiny from {MODEL_REPO}")
        model_path = hf_hub_download(repo_id=MODEL_REPO, filename=MODEL_FILE, cache_dir="./models_cache")
        
        _model = timm.create_model("deit_tiny_patch16_224", pretrained=False, num_classes=15)
        checkpoint = torch.load(model_path, map_location=DEVICE)
        
        # Handle different checkpoint key names just in case
        state_dict = checkpoint.get("model_state", checkpoint.get("state_dict", checkpoint))
        _model.load_state_dict(state_dict)
        _model.to(DEVICE)
        _model.eval()

        _preprocess = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
        logger.info(f"DeiT-Tiny loaded successfully on {DEVICE}")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        _model = None

async def predict_disease(image_bytes: bytes, filename: str = "leaf.jpg") -> Optional[Dict[str, Any]]:
    if USE_MOCK:
        logger.warning("Using MOCK prediction")
        await asyncio.sleep(0.5)
        return {
            "disease": "Tomato Early Blight", "confidence": 0.88, "is_healthy": False,
            "low_confidence": False, "warning": None,
            "top3": [
                {"rank": 1, "disease": "Tomato Early Blight", "confidence": 0.88},
                {"rank": 2, "disease": "Tomato Late Blight",  "confidence": 0.08},
                {"rank": 3, "disease": "Tomato Healthy",      "confidence": 0.04},
            ]
        }

    try:
        if _model is None:
            _load_model()
        if _model is None:
            return None

        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        input_tensor = _preprocess(image).unsqueeze(0).to(DEVICE)

        loop = asyncio.get_event_loop()
        with torch.no_grad():
            logits = await loop.run_in_executor(None, lambda: _model(input_tensor))

        probs = torch.softmax(logits, dim=1)[0]
        top3_scores, top3_indices = probs.topk(3)

        top1_class = LABEL_MAP.get(top3_indices[0].item(), "Unknown")
        top1_conf  = top3_scores[0].item()

        low_confidence = top1_conf < 0.60
        warning = "Confidence below 60%. Result may be inaccurate. Consult an expert." if low_confidence else None
        is_healthy = "Healthy" in top1_class

        top3 = [
            {"rank": i + 1, "disease": LABEL_MAP.get(top3_indices[i].item(), "Unknown"), "confidence": round(top3_scores[i].item(), 4)}
            for i in range(3)
        ]

        return {
            "disease": top1_class, "confidence": round(top1_conf, 4), "is_healthy": is_healthy,
            "low_confidence": low_confidence, "warning": warning, "top3": top3,
        }
    except Exception as e:
        logger.error(f"Inference failed: {e}")
        return None