from __future__ import annotations

from typing import Any


class StructuredPostprocessor:
    def process_structured_data(
        self,
        structured_data: dict[str, Any],
        routing_plan: dict[str, Any] | None = None,
        preprocessing: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = dict(structured_data) if isinstance(structured_data, dict) else {}
        document_type = normalized.get("document_type", "unknown")
        report = {
            "enabled": True,
            "profile": (routing_plan or {}).get("postprocess_profile", "field_normalization"),
            "document_type": document_type,
            "actions": [],
        }

        if isinstance(normalized.get("fields"), dict):
            normalized["fields"] = self._normalize_mapping(normalized.get("fields", {}))
            report["actions"].append("normalized_fields")
        if isinstance(normalized.get("key_values"), dict):
            normalized["key_values"] = self._normalize_mapping(normalized.get("key_values", {}))
            report["actions"].append("normalized_key_values")

        if isinstance(normalized.get("datasets"), list):
            normalized["datasets"] = [self._normalize_dataset(dataset) for dataset in normalized.get("datasets", [])]
            normalized["dataset_count"] = len(normalized.get("datasets", []))
            normalized["record_count"] = sum(int(dataset.get("row_count", 0) or 0) for dataset in normalized.get("datasets", []))
            report["actions"].append("normalized_datasets")

        records = normalized.get("records", []) if isinstance(normalized.get("records"), list) else []
        if records:
            deduplicated_records, record_report = self._normalize_records(records, normalized, preprocessing)
            normalized["records"] = deduplicated_records
            normalized["record_count"] = len(deduplicated_records)
            report.update(record_report)
            report["actions"].append("normalized_records")

        normalized["postprocess_report"] = report
        return {"structured_data": normalized, "report": report}

    def finalize_document_summary(
        self,
        document_summary: dict[str, Any],
        structured_data: dict[str, Any],
        validation_result: dict[str, Any] | None = None,
        routing_plan: dict[str, Any] | None = None,
        prompt_plan: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        summary = dict(document_summary) if isinstance(document_summary, dict) else {}
        detail_groups = structured_data.get("detail_groups", {}) if isinstance(structured_data.get("detail_groups"), dict) else {}
        detail_group_list = detail_groups.get("groups", []) if isinstance(detail_groups.get("groups"), list) else []
        summary["detail_sheet_count"] = len(detail_group_list)
        summary["detail_sheet_names"] = [group.get("sheet_name") for group in detail_group_list[:20]]
        summary["routing_profile"] = (routing_plan or {}).get("prompt_profile", "")
        summary["combination_mode"] = (routing_plan or {}).get("combination_mode", "")
        summary["preprocess_profile"] = (routing_plan or {}).get("preprocess_profile", "")
        summary["postprocess_profile"] = (routing_plan or {}).get("postprocess_profile", "")
        summary["prompt_version"] = self._prompt_version(prompt_plan)
        summary["consistency"] = {
            "record_count_matches": summary.get("record_count", 0) == structured_data.get("record_count", 0),
            "detail_sheet_count_matches": summary.get("detail_sheet_count", 0) == len(detail_group_list),
            "validation_issue_count": len((validation_result or {}).get("issues", [])),
        }
        if validation_result and validation_result.get("issues") and "risk_notes" not in summary:
            summary["risk_notes"] = list(validation_result.get("issues", []))[:5]
        return summary

    def _normalize_mapping(self, mapping: dict[str, Any]) -> dict[str, Any]:
        normalized = {}
        for key, value in mapping.items():
            key_text = str(key or "").strip()
            if not key_text:
                continue
            normalized[key_text] = self._clean_scalar(value)
        return normalized

    def _normalize_dataset(self, dataset: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(dataset) if isinstance(dataset, dict) else {}
        headers = [str(header).strip() for header in normalized.get("headers", []) if str(header).strip()]
        normalized["headers"] = headers
        records = []
        for raw_record in normalized.get("records", []) or []:
            if not isinstance(raw_record, dict):
                continue
            records.append({header: self._clean_scalar(raw_record.get(header)) for header in headers})
        normalized["records"] = records
        normalized["row_count"] = len(records)
        normalized["column_count"] = len(headers)
        return normalized

    def _normalize_records(
        self,
        records: list[dict[str, Any]],
        structured_data: dict[str, Any],
        preprocessing: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        deduplicated = []
        seen = set()
        duplicate_count = 0
        region = structured_data.get("region")
        year = structured_data.get("year")
        publish_date = structured_data.get("publish_date")

        for raw_record in records:
            if not isinstance(raw_record, dict):
                continue
            record = dict(raw_record)
            for key in [
                "document_title",
                "section",
                "indicator_name",
                "metric_type",
                "unit",
                "comparison_unit",
                "comparison_text",
                "value_text",
                "source_sentence",
                "source_clause",
                "time_reference",
                "location_reference",
            ]:
                if key in record:
                    record[key] = self._clean_scalar(record.get(key))
            if not record.get("location_reference") and region:
                record["location_reference"] = region
            if not record.get("time_reference"):
                record["time_reference"] = publish_date or (f"{year}年" if year else None)
            record["confidence_score"] = self._confidence_score(record)
            record["quality_flags"] = self._quality_flags(record)

            signature = (
                record.get("record_type"),
                record.get("section"),
                record.get("indicator_name"),
                record.get("value_text") or record.get("value"),
                record.get("unit"),
                record.get("time_reference"),
                record.get("location_reference"),
            )
            if signature in seen:
                duplicate_count += 1
                continue
            seen.add(signature)
            deduplicated.append(record)

        deduplicated.sort(
            key=lambda item: (
                0 if item.get("record_type") == "measurement" else 1,
                str(item.get("section") or ""),
                str(item.get("indicator_name") or ""),
                str(item.get("time_reference") or ""),
            )
        )
        for index, record in enumerate(deduplicated, start=1):
            record["record_id"] = f"rec_{index}"

        low_confidence = sum(1 for record in deduplicated if float(record.get("confidence_score", 0.0)) < 0.55)
        return deduplicated, {
            "records_before": len(records),
            "records_after": len(deduplicated),
            "duplicates_removed": duplicate_count,
            "low_confidence_records": low_confidence,
        }

    def _confidence_score(self, record: dict[str, Any]) -> float:
        score = 0.3
        if record.get("indicator_name"):
            score += 0.2
        if record.get("value") is not None or record.get("value_text"):
            score += 0.2
        if record.get("source_sentence"):
            score += 0.15
        if record.get("section"):
            score += 0.05
        if record.get("time_reference"):
            score += 0.05
        if record.get("location_reference"):
            score += 0.05
        return min(round(score, 3), 0.99)

    def _quality_flags(self, record: dict[str, Any]) -> list[str]:
        flags = []
        if not record.get("indicator_name"):
            flags.append("missing_indicator")
        if record.get("value") is None and not record.get("value_text"):
            flags.append("missing_value")
        if not record.get("source_sentence"):
            flags.append("missing_source")
        if not record.get("time_reference"):
            flags.append("missing_time")
        return flags

    def _prompt_version(self, prompt_plan: dict[str, Any] | None) -> str:
        if not isinstance(prompt_plan, dict):
            return ""
        for key in ("summary", "detail"):
            node = prompt_plan.get(key, {})
            if isinstance(node, dict) and node.get("version"):
                return str(node.get("version"))
        return ""

    def _clean_scalar(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            return " ".join(value.replace("\n", " ").split()).strip()
        return value
