import io
import shutil

import fitz
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.services import pdf_service
from app.services.pdf_service import PAGE_SEPARATOR, ExtractionError
from tests.conftest import make_pdf

LONG = "Hemoglobin 13.5 g/dL (reference 12.0-15.5). Fasting glucose 92 mg/dL. " * 3


def write(tmp_path, data: bytes, name="doc.pdf"):
    path = tmp_path / name
    path.write_bytes(data)
    return str(path)


def scanned_pdf(text: str) -> bytes:
    """A PDF whose only page is an image of text (no text layer), like a scan."""
    img = Image.new("RGB", (1700, 400), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 48)
    except OSError:
        font = ImageFont.load_default()
    draw.text((40, 150), text, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    doc = fitz.open()
    page = doc.new_page(width=850, height=200)
    page.insert_image(page.rect, stream=buf.getvalue())
    data = doc.tobytes()
    doc.close()
    return data


def test_digital_extraction_keeps_page_boundaries(tmp_path):
    path = write(tmp_path, make_pdf([LONG, "Page two: Vitamin D 18 ng/mL (low)."]))
    text = pdf_service.smart_extract(path)
    pages = text.split(PAGE_SEPARATOR)
    assert len(pages) == 2
    assert "Hemoglobin" in pages[0] and "Vitamin D" in pages[1]


@pytest.mark.skipif(not shutil.which("tesseract"), reason="tesseract not installed")
def test_scanned_pdf_falls_back_to_real_ocr(tmp_path):
    path = write(tmp_path, scanned_pdf("CHOLESTEROL 182 mg/dL"))
    text = pdf_service.smart_extract(path)
    assert "CHOLESTEROL" in text.upper()


def test_scanned_pdf_without_tesseract_fails_loudly_instead_of_empty_success(tmp_path, monkeypatch):
    monkeypatch.setattr(pdf_service, "find_tesseract", lambda: None)
    path = write(tmp_path, scanned_pdf("CHOLESTEROL 182"))
    with pytest.raises(ExtractionError, match="OCR"):
        pdf_service.smart_extract(path)


def test_tesseract_path_comes_from_settings_then_path(monkeypatch):
    monkeypatch.setattr(pdf_service.settings, "tesseract_cmd", "/opt/custom/tesseract")
    assert pdf_service.find_tesseract() == "/opt/custom/tesseract"
    monkeypatch.setattr(pdf_service.settings, "tesseract_cmd", "")
    assert pdf_service.find_tesseract() == shutil.which("tesseract")


def test_corrupt_pdf_gives_a_readable_error(tmp_path):
    path = write(tmp_path, b"%PDF-1.7 this is not really a pdf")
    with pytest.raises(ExtractionError, match="could not be read"):
        pdf_service.smart_extract(path)


def test_magic_byte_check():
    assert pdf_service.looks_like_pdf(make_pdf(["x"]))
    assert not pdf_service.looks_like_pdf(b"hello, I am a .pdf by name only")


def test_upload_is_private_and_uniquely_named_per_user(tmp_path, fake_storage):
    path = write(tmp_path, make_pdf(["x"]))
    key_a = pdf_service.upload_to_cloudinary(path, "user-a")
    key_b = pdf_service.upload_to_cloudinary(path, "user-a")
    key_c = pdf_service.upload_to_cloudinary(path, "user-b")

    assert len({key_a, key_b, key_c}) == 3  # same file twice never overwrites
    assert key_a.startswith("medical_docs/user-a/") and key_c.startswith("medical_docs/user-b/")
    assert all(u["type"] == "private" and u["resource_type"] == "raw" for u in fake_storage)
