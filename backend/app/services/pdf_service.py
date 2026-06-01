import fitz
import pytesseract
from PIL import Image
import io
import os
import cloudinary
import cloudinary.uploader
from app.config import settings
from app.utils.logger import setup_logger

logger = setup_logger()

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

cloudinary.config(
    cloud_name=settings.cloudinary_cloud_name,
    api_key=settings.cloudinary_api_key,
    api_secret=settings.cloudinary_api_secret,
)


def extract_text_digital(file_path: str) -> str:
    try:
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        logger.info(f"Digital extraction successful: {len(text)} characters")
        return text.strip()
    except Exception as e:
        logger.error(f"Digital extraction failed: {e}")
        return ""


def extract_text_ocr(file_path: str) -> str:
    try:
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img_data = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_data))
            page_text = pytesseract.image_to_string(image)
            text += page_text
        doc.close()
        logger.info(f"OCR extraction successful: {len(text)} characters")
        return text.strip()
    except Exception as e:
        logger.error(f"OCR extraction failed: {e}")
        return ""


def smart_extract(file_path: str) -> str:
    logger.info(f"Starting smart extraction for: {file_path}")
    digital_text = extract_text_digital(file_path)
    if len(digital_text) > 100:
        logger.info("Using digital extraction")
        return digital_text
    logger.info("Digital text too short, falling back to OCR")
    return extract_text_ocr(file_path)


def upload_to_cloudinary(file_path: str, filename: str) -> str:
    try:
        result = cloudinary.uploader.upload(
            file_path,
            resource_type="raw",
            folder="medical_docs",
            public_id=filename,
        )
        logger.info(f"Uploaded to Cloudinary: {result['secure_url']}")
        return result["secure_url"]
    except Exception as e:
        logger.error(f"Cloudinary upload failed: {e}")
        raise