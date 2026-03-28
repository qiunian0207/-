from __future__ import annotations

from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff"}


class OCRProcessor:
    def __init__(self) -> None:
        self._ocr = None
        self._load_error = ""

    def process(self, file_path: str) -> dict[str, Any]:
        path = Path(file_path)
        extension = path.suffix.lower()

        if extension not in IMAGE_EXTENSIONS and extension != ".pdf":
            return {
                "ocr_results": [],
                "total_pages": 0,
                "text": "",
                "status": "skipped",
                "reason": "当前文件类型无需 OCR。",
            }

        ocr = self._get_ocr_engine()
        if ocr is None:
            return {
                "ocr_results": [],
                "total_pages": 0,
                "text": "",
                "status": "skipped",
                "reason": self._load_error or "PaddleOCR 不可用。",
            }

        try:
            if extension in IMAGE_EXTENSIONS:
                raw_pages = self._normalize_pages(ocr.ocr(str(path), cls=True))
            else:
                raw_pages = []
                for page_number, image in enumerate(self._load_pdf_images(path), start=1):
                    normalized = self._normalize_pages(ocr.ocr(image, cls=True))
                    raw_pages.append(
                        {
                            "page": page_number,
                            "result": normalized[0].get("result", []) if normalized else [],
                        }
                    )

            pages = self._extract_page_results(raw_pages)
            text = "\n\n".join(
                "\n".join(item["text"] for item in page["texts"])
                for page in pages
                if page["texts"]
            )
            return {
                "ocr_results": pages,
                "total_pages": len(pages),
                "text": text,
                "status": "completed" if pages else "skipped",
                "reason": "" if pages else "OCR 未识别到文本。",
            }
        except Exception as exc:
            return {
                "ocr_results": [],
                "total_pages": 0,
                "text": "",
                "status": "skipped",
                "reason": f"OCR 处理失败: {exc}",
            }

    def _get_ocr_engine(self):
        if self._ocr is not None or self._load_error:
            return self._ocr

        try:
            from paddleocr import PaddleOCR

            self._ocr = PaddleOCR(use_angle_cls=True, lang="ch")
        except Exception as exc:
            self._load_error = str(exc)

        return self._ocr

    def _load_pdf_images(self, path: Path):
        from pdf2image import convert_from_path

        return convert_from_path(path)

    def _normalize_pages(self, raw_result: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_result, list):
            return []

        if raw_result and isinstance(raw_result[0], dict) and "page" in raw_result[0]:
            return raw_result

        if raw_result and isinstance(raw_result[0], list):
            return [{"page": 1, "result": raw_result[0]}]

        return [{"page": 1, "result": raw_result}]

    def _extract_page_results(self, raw_pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        pages = []
        for page in raw_pages:
            texts = []
            for line in page.get("result", []):
                if not isinstance(line, list) or len(line) < 2:
                    continue
                coordinates, payload = line[0], line[1]
                if not isinstance(payload, (list, tuple)) or len(payload) < 2:
                    continue
                text, score = payload[0], payload[1]
                texts.append(
                    {
                        "text": str(text).strip(),
                        "confidence": float(score),
                        "coordinates": coordinates,
                    }
                )
            pages.append({"page": page.get("page", len(pages) + 1), "texts": texts})
        return pages
