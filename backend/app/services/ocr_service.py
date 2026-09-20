"""
OCR Extraction Service for Money Lens.
Provides a fallback text extraction layer for scanned/image-based PDFs
where native PDF text extraction yields insufficient content.

Uses pytesseract + pdf2image. Degrades gracefully if Tesseract binary
is not installed — returns empty text with source="ocr_unavailable".
"""

import io
import re
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Minimum average chars-per-page threshold below which we trigger OCR
_MIN_CHARS_PER_PAGE = 40


def _has_sufficient_text(pages_text: List[str]) -> bool:
    """Returns True if pypdf extracted enough text to skip OCR."""
    if not pages_text:
        return False
    total = sum(len(t.strip()) for t in pages_text)
    avg = total / len(pages_text)
    return avg >= _MIN_CHARS_PER_PAGE


def _tesseract_available() -> bool:
    """Check if Tesseract OCR binary is installed and accessible."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


class OcrService:
    """
    Fallback OCR extraction for scanned or image-based PDFs.

    Usage:
        service = OcrService()
        text, source = service.extract_text_from_pdf(pdf_bytes)
    """

    def __init__(self):
        self._tesseract_ok: Optional[bool] = None

    def _check_tesseract(self) -> bool:
        if self._tesseract_ok is None:
            self._tesseract_ok = _tesseract_available()
            if not self._tesseract_ok:
                logger.warning(
                    "[OcrService] Tesseract binary not found. "
                    "OCR fallback disabled. Install Tesseract for scanned PDF support."
                )
        return self._tesseract_ok

    def extract_text_from_pdf(
        self, pdf_bytes: bytes
    ) -> Tuple[str, str]:
        """
        Extract full text from a PDF.

        Returns:
            (full_text, source) where source is one of:
              "text"            - native pypdf extraction was sufficient
              "ocr"             - OCR was used
              "ocr_unavailable" - OCR needed but Tesseract not installed
              "empty"           - no usable text found by any method
        """
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            pages_text = []
            for page in reader.pages:
                t = page.extract_text() or ""
                pages_text.append(t)
        except Exception as e:
            logger.error("[OcrService] pypdf extraction failed: %s", e)
            pages_text = []

        if _has_sufficient_text(pages_text):
            return "\n".join(pages_text), "text"

        # Native extraction insufficient — try OCR
        logger.info(
            "[OcrService] Native text extraction insufficient "
            "(avg chars/page < %d). Attempting OCR fallback.", _MIN_CHARS_PER_PAGE
        )

        if not self._check_tesseract():
            partial = "\n".join(pages_text).strip()
            return partial, "ocr_unavailable"

        try:
            from pdf2image import convert_from_bytes
            import pytesseract
            from PIL import Image

            images = convert_from_bytes(pdf_bytes, dpi=250)
            ocr_pages = []
            for img in images:
                # Preprocess: convert to grayscale for better OCR accuracy
                gray = img.convert("L")
                text = pytesseract.image_to_string(
                    gray,
                    lang="eng",
                    config="--psm 6",  # Assume uniform block of text
                )
                ocr_pages.append(text)

            full_text = "\n".join(ocr_pages).strip()
            if full_text:
                logger.info(
                    "[OcrService] OCR extracted %d chars from %d pages.",
                    len(full_text), len(images)
                )
                return full_text, "ocr"
            else:
                return "", "empty"

        except Exception as e:
            logger.error("[OcrService] OCR extraction failed: %s", e)
            # Return whatever native pypdf got, even if sparse
            return "\n".join(pages_text).strip(), "text"

    def extract_transactions_with_confidence(
        self,
        text: str,
        source: str,
    ) -> List[Dict[str, Any]]:
        """
        Post-process OCR/text output into raw transaction records
        with a confidence score per transaction.

        Confidence is reduced for OCR-sourced rows due to potential
        character recognition errors in amounts and dates.
        """
        from app.services.statement_service import StatementService
        svc = StatementService.__new__(StatementService)
        # Inject just the methods we need without full __init__
        StatementService.__init__(svc)

        # Use the existing PDF line parser on the OCR output text
        raw_txs = svc._parse_text_lines(text)

        base_confidence = 0.90 if source == "text" else 0.72
        result = []
        for tx in raw_txs:
            # Reduce confidence further if amount looks unusual
            amt = tx.get("amount", 0.0)
            confidence = base_confidence
            if source == "ocr":
                # Heuristic: very large or oddly-small amounts from OCR are less reliable
                if amt > 10_000_000 or (0 < amt < 1):
                    confidence -= 0.20
                # Round amounts (common OCR artifact) are slightly less trusted
                if amt > 0 and amt == round(amt, 0) and amt > 100:
                    confidence = min(confidence, 0.85)

            result.append({
                **tx,
                "source": source,
                "confidence": round(max(0.0, min(1.0, confidence)), 2),
            })

        return result
