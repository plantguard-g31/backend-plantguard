# test_model_load.py
import torch
from huggingface_hub import hf_hub_download
import timm

MODEL_REPO = "Precious466/plantguard-resnet50-teacher"
MODEL_FILE = "deit_tiny_mixed.pth"

try:
    print("Downloading model from HuggingFace...")
    model_path = hf_hub_download(repo_id=MODEL_REPO, filename=MODEL_FILE)
    print(f"✅ Model downloaded to: {model_path}")
    
    print("Loading checkpoint...")
    checkpoint = torch.load(model_path, map_location="cpu")
    print(f"✅ Checkpoint type: {type(checkpoint)}")
    
    if isinstance(checkpoint, dict):
        print(f"✅ Checkpoint keys: {list(checkpoint.keys())}")
        
        # Try to extract state_dict
        if "model_state" in checkpoint:
            state_dict = checkpoint["model_state"]
            print("✅ Found 'model_state' key")
        elif "state_dict" in checkpoint:
            state_dict = checkpoint["state_dict"]
            print("✅ Found 'state_dict' key")
        else:
            state_dict = checkpoint
            print("⚠️ No standard keys found, assuming checkpoint is state_dict")
    else:
        state_dict = checkpoint
        print("⚠️ Checkpoint is not a dict, assuming it's state_dict")
    
    print(f"✅ State dict has {len(state_dict)} layers")
    
    print("Creating model...")
    model = timm.create_model("deit_tiny_patch16_224", pretrained=False, num_classes=15)
    
    print("Loading state dict...")
    model.load_state_dict(state_dict)
    print("✅ Model loaded successfully!")
    
    # Test with a dummy input
    print("Testing inference...")
    dummy_input = torch.randn(1, 3, 224, 224)
    with torch.no_grad():
        output = model(dummy_input)
    print(f"✅ Inference successful! Output shape: {output.shape}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()