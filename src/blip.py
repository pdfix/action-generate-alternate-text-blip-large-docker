import re
import warnings
from typing import Any

import torch
from PIL import Image
from transformers import BlipForConditionalGeneration, BlipProcessor
from transformers.utils import logging as transformers_logging

# Hugging Face libraries log and show their own progress bars when loading the model; keep only ours
transformers_logging.disable_progress_bar()
transformers_logging.set_verbosity_error()
# Every caption warns: Using the model-agnostic default `max_length` (=21) to control the generation length
warnings.filterwarnings("ignore", message=".*model-agnostic default `max_length`.*")


class BlipCaptioner:
    """
    Salesforce BLIP (Bootstrapped Language Image Pretraining) large model that describes images.
    The model is loaded once and used for all images.
    """

    def __init__(self, model_path: str) -> None:
        """
        Load the processor and model.

        Args:
            model_path (str): Path to BLIP large model. Default value is "model".
        """
        self.processor: Any = BlipProcessor.from_pretrained(model_path, local_files_only=True)
        self.model: Any = BlipForConditionalGeneration.from_pretrained(model_path, local_files_only=True)

    def describe(self, image_path: str) -> str:
        """
        Generate alt text description of an image.

        Args:
            image_path (str): Path to file containing image.

        Returns:
            Caption of image.
        """
        # Load image data
        image: Image.Image = Image.open(image_path)
        if image.mode != "RGB":
            image = image.convert(mode="RGB")

        # Prepare inputs
        inputs: Any = self.processor(images=image, return_tensors="pt")

        # Generate caption
        with torch.no_grad():
            outputs: Any = self.model.generate(**inputs)

        # Decode caption
        caption: Any = self.processor.decode(outputs[0], skip_special_tokens=True)

        # Return alt text
        return clean_caption(str(caption))


def clean_caption(caption: str) -> str:
    """
    Remove words that BLIP generates but that have no meaning.

    Args:
        caption (str): Caption from BLIP.

    Returns:
        Caption without the artifact word "arafed".
    """
    return re.sub(r"\barafed\b\s*", "", caption).strip()
