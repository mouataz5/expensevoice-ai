"""
OCR Service for extracting text from invoice images.

Supports multiple OCR engines:
- PaddleOCR (recommended for Arabic/French invoices)
- EasyOCR (fallback option)
- Custom OCR providers via configuration
"""
import logging
import os
from abc import ABC, abstractmethod
from typing import Optional

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class OCRService(ABC):
    """Abstract base class for OCR services."""

    @abstractmethod
    def extract_text(self, image_path: str) -> str:
        """Extract text from image file."""
        pass


class PaddleOCRService(OCRService):
    """PaddleOCR implementation for Arabic/French invoice processing."""

    def __init__(self):
        # Don't initialize PaddleOCR in constructor to avoid slow startup
        self._ocr = None
    
    @property
    def ocr(self):
        if self._ocr is None:
            try:
                from paddleocr import PaddleOCR
                
                # Different versions of PaddleOCR may have different parameter support
                init_params = [
                    # Try with all parameters first
                    {
                        'lang': 'ar',
                        'use_angle_cls': True,
                        'det': True,
                        'rec': True,
                        'cls': True
                    },
                    # Try with minimal parameters
                    {
                        'lang': 'ar',
                        'use_angle_cls': True
                    },
                    # Try with basic parameters
                    {
                        'lang': 'ar'
                    }
                ]
                
                # Try each parameter set until one works
                for params in init_params:
                    try:
                        self._ocr = PaddleOCR(**params)
                        logger.info(f"PaddleOCR initialized successfully with parameters: {list(params.keys())}")
                        return self._ocr
                    except TypeError as e:
                        logger.debug(f"PaddleOCR init failed with params {list(params.keys())}: {e}")
                        continue  # Try the next parameter set
                    except Exception as e:
                        logger.debug(f"PaddleOCR init failed with unexpected error for params {list(params.keys())}: {e}")
                        continue  # Try the next parameter set
                
                # If all attempts failed, raise an error
                logger.error("All PaddleOCR initialization attempts failed")
                raise RuntimeError("Could not initialize PaddleOCR with any parameter combination")
                
            except ImportError:
                logger.warning(
                    "PaddleOCR not installed. Install with: pip install paddleocr==2.7.3"
                )
                raise
        return self._ocr

    def extract_text(self, image_path: str) -> str:
        """Extract text from image using PaddleOCR."""
        try:
            # Run OCR on the image
            result = self.ocr.ocr(image_path, cls=True)
            
            # Extract text from result (PaddleOCR returns nested structure)
            texts = []
            for page_result in result:
                if page_result is not None:  # Handle case where OCR fails
                    for line in page_result:
                        if line and len(line) > 0:
                            for box in line:
                                if len(box) > 1 and box[1] is not None:
                                    text = box[1][0] if isinstance(box[1], tuple) else str(box[1])
                                    if text:
                                        texts.append(text)
            
            return '\n'.join(texts)
        except Exception as e:
            logger.error(f"PaddleOCR extraction failed: {e}")
            raise


class EasyOCRService(OCRService):
    """EasyOCR implementation as fallback option."""

    def __init__(self):
        # Don't initialize EasyOCR in constructor to avoid slow startup
        self._reader = None
    
    @property
    def reader(self):
        if self._reader is None:
            try:
                import easyocr
                # Try the combination suggested by the error message for Arabic support
                self._reader = easyocr.Reader(['ar', 'fa', 'ur', 'ug', 'en'])  # Persian, Urdu, Uyghur, English
            except Exception as e:
                logger.warning(f"Primary language pack failed: {e}, trying alternative...")
                try:
                    # Alternative: Standard Arabic + English + French
                    import easyocr
                    self._reader = easyocr.Reader(['ar', 'en', 'fr'])
                except ImportError:
                    logger.warning(
                        "EasyOCR not installed. Install with: pip install easyocr"
                    )
                    raise
            except ImportError:
                logger.warning(
                    "EasyOCR not installed. Install with: pip install easyocr"
                )
                raise
        return self._reader

    def extract_text(self, image_path: str) -> str:
        """Extract text from image using EasyOCR."""
        try:
            result = self.reader.readtext(image_path, detail=0)
            return '\n'.join(result)
        except Exception as e:
            logger.error(f"EasyOCR extraction failed: {e}")
            raise


class NoOpOCRService(OCRService):
    """Fallback when no OCR engine is available; returns empty string and logs warning."""

    def extract_text(self, image_path: str) -> str:
        logger.warning(
            "No OCR engine available (install easyocr or paddleocr). Invoice scan will show 0%% extraction."
        )
        return ""


class HEICConverter:
    """Convert HEIC images to JPEG for better OCR compatibility."""
    
    @staticmethod
    def convert_heic_to_jpeg(heic_path: str, output_path: Optional[str] = None) -> str:
        """Convert HEIC image to JPEG format."""
        try:
            from pillow_heif import register_heif_opener
            register_heif_opener()
        except ImportError:
            logger.error("pillow-heif not installed. Install with: pip install pillow-heif")
            raise
        
        if not output_path:
            output_path = heic_path.replace('.heic', '.jpeg').replace('.HEIC', '.jpeg')
        
        # Open HEIC image and convert to RGB
        heic_image = Image.open(heic_path)
        if heic_image.mode in ('RGBA', 'LA', 'P'):
            heic_image = heic_image.convert('RGB')
        
        # Save as JPEG
        heic_image.save(output_path, 'JPEG', quality=95)
        return output_path


class MultiFormatOCRService(OCRService):
    """Main OCR service that handles different image formats and OCR engines."""

    def __init__(self):
        # Use EasyOCR as default since PaddleOCR seems to have compatibility issues in Docker
        self.preferred_engine = os.getenv("OCR_ENGINE", "easy").lower()
        self._ocr_service = None
    
    def _get_ocr_service(self) -> OCRService:
        """Initialize and return the appropriate OCR service."""
        if self._ocr_service:
            return self._ocr_service

        # Try the preferred engine first, then fallback
        if self.preferred_engine == "paddle":
            try:
                self._ocr_service = PaddleOCRService()
                logger.info("Using PaddleOCR engine")
            except ImportError:
                pass
            if self._ocr_service is None:
                try:
                    self._ocr_service = EasyOCRService()
                    logger.info("Using EasyOCR engine (fallback)")
                except ImportError:
                    pass
        else:
            try:
                self._ocr_service = EasyOCRService()
                logger.info("Using EasyOCR engine")
            except ImportError:
                pass
            if self._ocr_service is None:
                try:
                    self._ocr_service = PaddleOCRService()
                    logger.info("Using PaddleOCR engine (fallback)")
                except ImportError:
                    pass

        if self._ocr_service is None:
            logger.warning(
                "No OCR engine available. Install easyocr (pip install easyocr) for invoice scan extraction."
            )
            self._ocr_service = NoOpOCRService()
        return self._ocr_service

    @staticmethod
    def _text_quality(text: str) -> float:
        """
        Quality score for OCR output — 0..1.
        All Tunisian invoices contain French text + standard 0-9 digits, so we
        require a minimum ratio of ASCII letters+digits. A document with almost
        no ASCII is almost certainly garbled (e.g. sideways scan read as Arabic).
        """
        if not text or len(text) < 10:
            return 0.0
        total = len(text)

        # ASCII letters (a-z) and standard digits (0-9) only — not Arabic-Indic
        ascii_useful = sum(
            1 for ch in text if ("a" <= ch.lower() <= "z") or ("0" <= ch <= "9")
        )
        ascii_ratio = ascii_useful / total

        # If very few ASCII chars (< 6%), text is almost certainly garbled —
        # return a low score to trigger rotation detection.
        if ascii_ratio < 0.06:
            return ascii_ratio  # max ≈ 0.06 → always below 0.45 threshold

        # Normal case: combine char usefulness with ASCII presence
        useful = sum(
            1 for ch in text
            if ch.isalpha() or ch.isdigit() or ch in " \n\t.,;:/-_()'%@°+="
        )
        char_ratio = useful / total
        return 0.6 * char_ratio + 0.4 * ascii_ratio

    def _preprocess_image(self, image_path: str) -> str:
        """Preprocess image: HEIC conversion + upscaling for better OCR quality."""
        # Convert HEIC to JPEG if needed
        if image_path.lower().endswith(('.heic', '.heif')):
            image_path = HEICConverter.convert_heic_to_jpeg(image_path)

        # Upscale small images (width < 1200px) to improve OCR accuracy
        try:
            img = Image.open(image_path)
            w, h = img.size
            if w < 1200:
                scale = 1200 / w
                img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
                tmp = image_path + "_scaled.jpg"
                img.save(tmp, "JPEG", quality=95)
                return tmp
        except Exception as e:
            logger.debug("Image upscale failed: %s", e)

        return image_path

    @staticmethod
    def _enhance_contrast(image_path: str) -> Optional[str]:
        """
        Apply CLAHE contrast enhancement + denoising to improve OCR on
        low-contrast or noisy scans (e.g. MEDIMIX-style invoices).
        Returns path to enhanced image, or None on failure.
        """
        try:
            img_bgr = cv2.imread(image_path)
            if img_bgr is None:
                return None

            # Convert to grayscale for CLAHE
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

            # CLAHE: adaptive contrast enhancement (tiles to handle uneven lighting)
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)

            # Mild denoising to remove scan noise without blurring text
            denoised = cv2.fastNlMeansDenoising(enhanced, h=8, templateWindowSize=7, searchWindowSize=21)

            # Slight sharpening via unsharp mask
            blurred = cv2.GaussianBlur(denoised, (0, 0), 2)
            sharpened = cv2.addWeighted(denoised, 1.4, blurred, -0.4, 0)

            # Save as high-quality JPEG for OCR
            out_path = image_path + "_clahe.jpg"
            result_bgr = cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)
            cv2.imwrite(out_path, result_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
            return out_path
        except Exception as e:
            logger.debug("CLAHE enhancement failed: %s", e)
            return None

    def extract_text(self, image_path: str) -> str:
        """Extract text with preprocessing, rotation detection, and fallback."""
        processed_path = self._preprocess_image(image_path)
        ocr_svc = self._get_ocr_service()

        # First attempt at original orientation
        try:
            text = ocr_svc.extract_text(processed_path)
            text = text.strip()
        except Exception as e:
            logger.error("OCR extraction failed: %s", e)
            return ""

        quality = self._text_quality(text)
        logger.debug("OCR quality %.2f for %s", quality, image_path)

        # If quality is poor, try rotations (handles sideways-scanned documents)
        if quality < 0.45:
            try:
                img = Image.open(processed_path)
                best_text, best_quality = text, quality
                for angle in (90, 270, 180):
                    rotated = img.rotate(angle, expand=True)
                    tmp_path = f"/tmp/_ocr_rot{angle}.jpg"
                    rotated.save(tmp_path, "JPEG", quality=95)
                    try:
                        rot_text = ocr_svc.extract_text(tmp_path).strip()
                        rot_q = self._text_quality(rot_text)
                        logger.debug("  rotation %d° → quality %.2f", angle, rot_q)
                        if rot_q > best_quality:
                            best_text, best_quality = rot_text, rot_q
                            if best_quality > 0.55:
                                break  # Good enough, stop trying
                    except Exception as e:
                        logger.debug("  rotation %d° OCR failed: %s", angle, e)
                text = best_text
                quality = best_quality
                logger.info("Best rotation quality %.2f for %s", best_quality, image_path)
            except Exception as e:
                logger.warning("Rotation detection failed: %s", e)

        # If quality is still below threshold, try CLAHE-enhanced version
        # (handles low-contrast / noisy scans like MEDIMIX invoices)
        if quality < 0.58:
            enhanced_path = self._enhance_contrast(processed_path)
            if enhanced_path:
                try:
                    enh_text = ocr_svc.extract_text(enhanced_path).strip()
                    enh_quality = self._text_quality(enh_text)
                    logger.debug("CLAHE-enhanced quality %.2f vs original %.2f", enh_quality, quality)
                    if enh_quality > quality + 0.03:  # Must be meaningfully better
                        text = enh_text
                        quality = enh_quality
                        logger.info(
                            "Using CLAHE-enhanced OCR (%.2f > %.2f) for %s",
                            enh_quality, quality, image_path,
                        )
                except Exception as e:
                    logger.debug("CLAHE-enhanced OCR failed: %s", e)

        return text


# Global instance
ocr_service = MultiFormatOCRService()


def get_ocr_service() -> OCRService:
    """Get the OCR service instance."""
    return ocr_service


def extract_text(image_path: str) -> str:
    """Module-level helper used by invoice_processing.py."""
    return ocr_service.extract_text(image_path)


# Constants used by invoices.py for file validation
ALLOWED_MIME = {"image/jpeg", "image/png", "image/heic", "image/heif", "image/webp"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB