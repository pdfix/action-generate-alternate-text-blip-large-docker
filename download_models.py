from transformers import BlipForConditionalGeneration, BlipProcessor

cache_dir = "./models"
model_name = "Salesforce/blip-image-captioning-large"

processor = BlipProcessor.from_pretrained(model_name, cache_dir=cache_dir)
model = BlipForConditionalGeneration.from_pretrained(model_name, cache_dir=cache_dir)

# now model data is downloaded in "./models/models--Salesforce--blip-image-captioning-large/snapshots/<hash>/"
