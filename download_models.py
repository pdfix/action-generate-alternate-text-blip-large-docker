from typing import Any

from transformers import BlipForConditionalGeneration, BlipProcessor

model_name: str = "Salesforce/blip-image-captioning-large"
cache_dir: str = "./models"

processor: Any = BlipProcessor.from_pretrained(model_name, cache_dir=cache_dir)
model: Any = BlipForConditionalGeneration.from_pretrained(model_name, cache_dir=cache_dir)

# now model data is downloaded in "./models/models--Salesforce--blip-image-captioning-large/snapshots/<hash>/"
