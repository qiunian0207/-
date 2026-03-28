from __future__ import annotations

from typing import Any


class ModelRouter:
    def __init__(
        self,
        router_model: str = "local_router",
        default_detail_model: str = "local",
        default_summary_model: str = "local",
        detail_candidates: list[str] | None = None,
        summary_candidates: list[str] | None = None,
    ) -> None:
        self.router_model = router_model or "local_router"
        self.default_detail_model = default_detail_model or "local"
        self.default_summary_model = default_summary_model or "local"
        self.detail_candidates = detail_candidates or [self.default_detail_model, "local"]
        self.summary_candidates = summary_candidates or [self.default_summary_model, "local"]

    def route(
        self,
        document: dict[str, Any],
        preprocessing: dict[str, Any],
        structured_hint: dict[str, Any] | None = None,
        operation_mode: str = "natural_to_structured",
    ) -> dict[str, Any]:
        signals = preprocessing.get("signals", {}) if isinstance(preprocessing, dict) else {}
        stats = preprocessing.get("stats", {}) if isinstance(preprocessing, dict) else {}
        document_type = (structured_hint or {}).get("document_type") or self._predict_document_type(signals, stats)
        domain_hint = (signals.get("domain_candidates") or ["general"])[0]
        prompt_profile = self._select_prompt_profile(document_type, domain_hint, signals)
        detail_model = self._select_detail_model(document_type, signals)
        summary_model = self._select_summary_model(document_type, domain_hint)
        combination_mode = self._combination_mode(document_type, signals)
        notes = self._build_notes(document_type, signals, stats)

        return {
            "router_model": self.router_model,
            "operation_mode": operation_mode,
            "document_type_hint": document_type,
            "domain_hint": domain_hint,
            "prompt_profile": prompt_profile,
            "combination_mode": combination_mode,
            "preprocess_profile": self._preprocess_profile(document_type, signals),
            "postprocess_profile": self._postprocess_profile(document_type),
            "models": {
                "router": self.router_model,
                "detail_primary": detail_model,
                "detail_fallback": [item for item in self.detail_candidates if item != detail_model],
                "summary_primary": summary_model,
                "summary_fallback": [item for item in self.summary_candidates if item != summary_model],
            },
            "sequence": [
                "preprocess",
                "route",
                "detail_extract",
                "postprocess",
                "summary_generate",
                "self_check",
            ],
            "routing_notes": notes,
            "confidence": self._routing_confidence(signals, stats),
        }

    def _predict_document_type(self, signals: dict[str, Any], stats: dict[str, Any]) -> str:
        if signals.get("has_tables"):
            return "tabular_dataset"
        if signals.get("has_headings") and stats.get("section_count", 0) >= 2:
            return "report_document"
        if stats.get("line_count", 0) <= 12:
            return "key_value_document"
        return "plain_text_document"

    def _select_prompt_profile(self, document_type: str, domain_hint: str, signals: dict[str, Any]) -> str:
        if document_type == "tabular_dataset":
            return "tabular_precision"
        if document_type == "report_document" and domain_hint == "government_statistics":
            return "report_statistical_brief"
        if document_type == "report_document":
            return "report_sectioned"
        if signals.get("measurement_candidates"):
            return "record_dense"
        return "field_mapping"

    def _select_detail_model(self, document_type: str, signals: dict[str, Any]) -> str:
        preferred_tokens = []
        if document_type == "tabular_dataset":
            preferred_tokens = ["table", "vision", "excel", "local"]
        elif document_type == "report_document":
            preferred_tokens = ["reason", "extract", "long", "local"]
        elif signals.get("has_ocr_text"):
            preferred_tokens = ["vision", "ocr", "local"]
        else:
            preferred_tokens = ["extract", "local"]
        return self._prefer_candidate(self.detail_candidates, preferred_tokens, self.default_detail_model)

    def _select_summary_model(self, document_type: str, domain_hint: str) -> str:
        preferred_tokens = ["summary", "small", "fast", "local"]
        if document_type == "report_document":
            preferred_tokens = ["summary", "reason", "small", "local"]
        if domain_hint == "government_statistics":
            preferred_tokens = ["summary", "cn", "reason", "local"]
        return self._prefer_candidate(self.summary_candidates, preferred_tokens, self.default_summary_model)

    def _prefer_candidate(self, candidates: list[str], preferred_tokens: list[str], fallback: str) -> str:
        lowered = [(candidate, candidate.lower()) for candidate in candidates if str(candidate).strip()]
        for token in preferred_tokens:
            for candidate, lowered_candidate in lowered:
                if token in lowered_candidate:
                    return candidate
        return lowered[0][0] if lowered else fallback

    def _combination_mode(self, document_type: str, signals: dict[str, Any]) -> str:
        if document_type == "tabular_dataset":
            return "table_first_detail_plus_summary"
        if document_type == "report_document":
            return "section_chunk_detail_plus_summary"
        if signals.get("measurement_candidates"):
            return "cue_guided_detail_plus_summary"
        return "field_first_detail_plus_summary"

    def _preprocess_profile(self, document_type: str, signals: dict[str, Any]) -> str:
        if document_type == "tabular_dataset":
            return "table_schema_cleanup"
        if signals.get("has_headings"):
            return "section_aware_chunking"
        if signals.get("has_ocr_text"):
            return "ocr_cleanup"
        return "light_normalization"

    def _postprocess_profile(self, document_type: str) -> str:
        if document_type == "tabular_dataset":
            return "dataset_consistency"
        if document_type == "report_document":
            return "record_reconcile"
        return "field_normalization"

    def _build_notes(self, document_type: str, signals: dict[str, Any], stats: dict[str, Any]) -> list[str]:
        notes = [f"文档被路由为 {document_type}。"]
        if signals.get("domain_candidates"):
            notes.append(f"优先领域提示: {', '.join(str(item) for item in signals.get('domain_candidates', [])[:3])}。")
        if stats.get("chunk_count"):
            notes.append(f"预处理生成 {stats.get('chunk_count')} 个文本块用于提示词上下文。")
        if signals.get("measurement_candidates"):
            notes.append(f"检测到 {len(signals.get('measurement_candidates', []))} 个数值线索。")
        return notes

    def _routing_confidence(self, signals: dict[str, Any], stats: dict[str, Any]) -> float:
        score = 0.45
        if signals.get("has_tables"):
            score += 0.25
        if signals.get("has_headings"):
            score += 0.1
        if stats.get("chunk_count", 0) >= 2:
            score += 0.1
        if signals.get("domain_candidates"):
            score += 0.05
        return min(round(score, 3), 0.98)
