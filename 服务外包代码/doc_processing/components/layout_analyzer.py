from __future__ import annotations

import os
from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff"}


class LayoutAnalyzer:
    def __init__(self) -> None:
        self.enabled = os.getenv("ENABLE_LAYOUT_ANALYZER", "0") == "1"
        self._model = None
        self._load_error = ""

    def analyze(self, file_path: str) -> dict[str, Any]:
        path = Path(file_path)
        extension = path.suffix.lower()

        if extension not in IMAGE_EXTENSIONS and extension != ".pdf":
            return {
                "layout_elements": [],
                "total_elements": 0,
                "status": "skipped",
                "reason": "当前文件类型无需版面分析。",
            }

        if not self.enabled:
            return {
                "layout_elements": [],
                "total_elements": 0,
                "status": "skipped",
                "reason": "版面分析默认关闭；如需启用，请设置 ENABLE_LAYOUT_ANALYZER=1。",
            }

        image = self._load_image(path)
        if image is None:
            return {
                "layout_elements": [],
                "total_elements": 0,
                "status": "skipped",
                "reason": self._load_error or "无法读取待分析页面。",
            }

        model = self._get_model()
        if model is None:
            return {
                "layout_elements": [],
                "total_elements": 0,
                "status": "skipped",
                "reason": self._load_error or "版面模型未就绪。",
            }

        try:
            layout = model.detect(image)
            elements = []
            for block in layout:
                coordinates = getattr(block, "coordinates", None)
                elements.append(
                    {
                        "type": getattr(block, "type", "unknown"),
                        "coordinates": coordinates.tolist() if coordinates is not None else [],
                        "score": float(getattr(block, "score", 0.0)),
                    }
                )
            return {
                "layout_elements": elements,
                "total_elements": len(elements),
                "status": "completed",
            }
        except Exception as exc:
            return {
                "layout_elements": [],
                "total_elements": 0,
                "status": "skipped",
                "reason": f"版面分析失败: {exc}",
            }

    def _get_model(self):
        if self._model is not None or self._load_error:
            return self._model

        try:
            import layoutparser as lp

            self._model = lp.Detectron2LayoutModel(
                config_path="lp://PubLayNet/mask_rcnn_X_101_32x8d_FPN_3x/config",
                label_map={0: "Text", 1: "Title", 2: "List", 3: "Table", 4: "Figure"},
                extra_config=["MODEL.ROI_HEADS.SCORE_THRESH_TEST", 0.8],
            )
        except Exception as exc:
            self._load_error = str(exc)

        return self._model

    def _load_image(self, path: Path):
        try:
            import numpy as np
            from PIL import Image

            if path.suffix.lower() in IMAGE_EXTENSIONS:
                with Image.open(path) as image:
                    return np.array(image.convert("RGB"))

            from pdf2image import convert_from_path

            pages = convert_from_path(path, first_page=1, last_page=1)
            if pages:
                return np.array(pages[0].convert("RGB"))
            self._load_error = "PDF 未能转换为图片页面。"
            return None
        except Exception as exc:
            self._load_error = str(exc)
            return None
