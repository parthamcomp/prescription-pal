import io

import pytesseract
from PIL import Image


def extract_text_from_image(image_bytes: bytes) -> str:
    """Run Tesseract OCR on raw image bytes. Imported by the worker only."""
    image = Image.open(io.BytesIO(image_bytes))
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    text = pytesseract.image_to_string(image)
    return text.strip()
