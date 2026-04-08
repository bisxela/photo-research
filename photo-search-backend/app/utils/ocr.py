from pathlib import Path
import logging
from typing import Optional

import pytesseract
from PIL import Image, ImageOps, ImageFilter

from app.config import settings

logger = logging.getLogger(__name__)


class OcrProcessor:
    """基于 Tesseract 的轻量 OCR 工具。"""

    @staticmethod
    def is_available() -> bool:
        if not settings.OCR_ENABLED:
            return False
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception as exc:
            logger.warning("Tesseract is unavailable: %s", exc)
            return False

    @staticmethod
    def extract_text(image_path: Path, languages: Optional[str] = None) -> str:
        languages = languages or settings.OCR_LANGUAGES
        with Image.open(image_path) as image:
            # 统一方向和基础增强，优先提升文档、票据、截图场景下的命中率。
            prepared = ImageOps.exif_transpose(image).convert("L")
            prepared = ImageOps.autocontrast(prepared)
            prepared = prepared.filter(ImageFilter.SHARPEN)
            text = pytesseract.image_to_string(prepared, lang=languages)
            return text.strip()
