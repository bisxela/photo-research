#!/usr/bin/env python3
"""
Download Chinese CLIP model and save to local directory.
"""
import os
import sys
from pathlib import Path
from transformers import AutoModel, AutoProcessor

MODEL_NAME = "OFA-Sys/chinese-clip-vit-base-patch16"
# Default path inside container
DEFAULT_MODEL_PATH = "/app/models/chinese-clip-vit-base-patch16"

def main():
    # Determine output directory
    model_path = os.getenv("CLIP_MODEL_PATH", DEFAULT_MODEL_PATH)
    output_dir = Path(model_path)
    
    print(f"Downloading model '{MODEL_NAME}' to {output_dir}")
    
    # Create directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Download model and processor
        print("Loading model...")
        model = AutoModel.from_pretrained(MODEL_NAME)
        print("Loading processor...")
        processor = AutoProcessor.from_pretrained(MODEL_NAME)
        
        # Save locally
        print(f"Saving to {output_dir}")
        model.save_pretrained(output_dir)
        processor.save_pretrained(output_dir)
        
        print("Download completed successfully.")
        
        # Verify files
        files = list(output_dir.glob("*"))
        print(f"Saved files: {[f.name for f in files]}")
        
    except Exception as e:
        print(f"Error downloading model: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()