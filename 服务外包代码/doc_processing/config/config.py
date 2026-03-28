from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUTS_ROOT = PROJECT_ROOT / "outputs"
UPLOAD_DIR = str(OUTPUTS_ROOT / "uploads")
OUTPUT_DIR = str(OUTPUTS_ROOT / "results")


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_csv(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name, "")
    if not value.strip():
        return list(default)
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or list(default)


SEMANTIC_MODEL = os.getenv("SEMANTIC_MODEL", "local").strip() or "local"
ROUTER_MODEL = os.getenv("ROUTER_MODEL", "local_router").strip() or "local_router"
DETAIL_MODEL = os.getenv("DETAIL_MODEL", SEMANTIC_MODEL).strip() or SEMANTIC_MODEL
SUMMARY_MODEL = os.getenv("SUMMARY_MODEL", SEMANTIC_MODEL).strip() or SEMANTIC_MODEL
DETAIL_MODEL_CANDIDATES = _env_csv("DETAIL_MODEL_CANDIDATES", [DETAIL_MODEL, "local"])
SUMMARY_MODEL_CANDIDATES = _env_csv("SUMMARY_MODEL_CANDIDATES", [SUMMARY_MODEL, "local"])
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "cn_v1").strip() or "cn_v1"
ENABLE_PREPROCESSING = _env_flag("ENABLE_PREPROCESSING", True)
ENABLE_POSTPROCESSING = _env_flag("ENABLE_POSTPROCESSING", True)
ENABLE_PROMPT_OPTIMIZATION = _env_flag("ENABLE_PROMPT_OPTIMIZATION", True)
ENABLE_SUMMARY_SELF_CHECK = _env_flag("ENABLE_SUMMARY_SELF_CHECK", True)
SEMANTIC_CHUNK_CHARS = int(os.getenv("SEMANTIC_CHUNK_CHARS", "900"))
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", str(25 * 1024 * 1024)))
SUPPORTED_FORMATS = [
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".tiff",
    ".md",
    ".txt",
    ".docx",
    ".xlsx",
    ".json",
]

TEXT_PREVIEW_CHARS = 4000
TABLE_PREVIEW_ROWS = 5

VALIDATION_RULES = {
    "email": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
    "phone": r"(?:86)?1[3-9]\d{9}",
    "id_card": r"[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[0-9Xx]",
    "date": r"\d{4}(?:[-/\.]|年)\d{1,2}(?:[-/\.]|月)\d{1,2}日?",
}
