from __future__ import annotations

import re
from datetime import datetime
from typing import Any

try:
    from config.config import VALIDATION_RULES
except ImportError:
    from doc_processing.config.config import VALIDATION_RULES


class DataValidator:
    def __init__(self) -> None:
        self.validation_rules = VALIDATION_RULES

    def validate(self, data: Any) -> dict[str, Any]:
        structured_data = data if isinstance(data, dict) else {}
        document_type = structured_data.get("document_type", "unknown")

        if document_type == "tabular_dataset":
            return self._validate_tabular_dataset(structured_data)
        if document_type == "report_document":
            return self._validate_report_document(structured_data)
        return self._validate_textual_document(structured_data)

    def _validate_tabular_dataset(self, data: dict[str, Any]) -> dict[str, Any]:
        datasets = data.get("datasets", []) if isinstance(data.get("datasets", []), list) else []
        dataset_validation = []
        issues = []

        for dataset in datasets:
            headers = dataset.get("headers", [])
            records = dataset.get("records", [])
            duplicate_headers = self._find_duplicate_headers(headers)
            row_count_matches = dataset.get("row_count") == len(records)
            is_valid = bool(headers) and bool(records) and not duplicate_headers and row_count_matches

            dataset_report = {
                "name": dataset.get("name", "table"),
                "is_valid": is_valid,
                "header_count": len(headers),
                "record_count": len(records),
                "row_count_matches": row_count_matches,
                "duplicate_headers": duplicate_headers,
            }
            dataset_validation.append(dataset_report)

            if not headers:
                issues.append(f"数据集 {dataset_report['name']} 缺少表头。")
            if not records:
                issues.append(f"数据集 {dataset_report['name']} 没有有效记录。")
            if duplicate_headers:
                issues.append(f"数据集 {dataset_report['name']} 存在重复表头: {', '.join(duplicate_headers)}。")
            if not row_count_matches:
                issues.append(f"数据集 {dataset_report['name']} 的 row_count 与 records 数量不一致。")

        is_valid = bool(datasets) and all(item["is_valid"] for item in dataset_validation)
        return {
            "normalized_data": data,
            "rule_validation": {
                "datasets_present": bool(datasets),
                "record_count": data.get("record_count", 0),
            },
            "dataset_validation": dataset_validation,
            "indicator_validation": [],
            "llm_validation": {
                "skipped": True,
                "reason": "当前使用本地校验模式。",
            },
            "correction_suggestions": self._tabular_suggestions(dataset_validation),
            "issues": issues,
            "validated_at": datetime.now().isoformat(),
            "is_valid": is_valid,
        }

    def _validate_report_document(self, data: dict[str, Any]) -> dict[str, Any]:
        sections = data.get("sections", []) if isinstance(data.get("sections", []), list) else []
        indicators = data.get("indicators", []) if isinstance(data.get("indicators", []), list) else []
        records = data.get("records", []) if isinstance(data.get("records", []), list) else []
        fields = data.get("fields", {}) if isinstance(data.get("fields", {}), dict) else {}

        rule_validation = {
            "sections_present": bool(sections),
            "indicators_present": bool(indicators),
            "records_present": bool(records),
        }
        issues = []
        correction_suggestions = {}
        indicator_validation = []

        if not sections:
            issues.append("报告未识别到章节结构。")
            correction_suggestions["sections"] = "请补充更清晰的章节标题，或检查原文中的标题层级。"
        if not indicators:
            issues.append("报告未识别到可结构化指标。")
            correction_suggestions["indicators"] = "请检查原文是否包含明确数值、单位或同比表述。"
        if not records:
            issues.append("报告未生成逐条记录。")
            correction_suggestions["records"] = "请检查原文是否包含可拆分的指标句，或补充更清晰的统计表述。"

        for section in sections:
            if not str(section.get("title", "")).strip():
                issues.append("存在缺少标题的章节。")
                break

        for indicator in indicators:
            has_name = bool(str(indicator.get("name", "")).strip())
            has_value = indicator.get("value") is not None
            has_statement = bool(str(indicator.get("statement", "")).strip())
            is_valid = has_name and (has_value or has_statement)
            indicator_validation.append(
                {
                    "name": indicator.get("name", ""),
                    "section_id": indicator.get("section_id"),
                    "is_valid": is_valid,
                    "has_value": has_value,
                    "has_statement": has_statement,
                }
            )
            if not is_valid:
                issues.append(f"指标 {indicator.get('name', 'unknown')} 缺少必要信息。")

        field_validation = self._validate_candidate_fields(fields)
        issues.extend(field_validation["issues"])
        correction_suggestions.update(field_validation["correction_suggestions"])
        rule_validation.update(field_validation["rule_validation"])

        is_valid = bool(sections) and (bool(records) or bool(indicators)) and all(item["is_valid"] for item in indicator_validation)
        return {
            "normalized_data": data,
            "rule_validation": rule_validation,
            "dataset_validation": [],
            "indicator_validation": indicator_validation,
            "llm_validation": {
                "skipped": True,
                "reason": "当前使用本地校验模式。",
            },
            "correction_suggestions": correction_suggestions,
            "issues": self._deduplicate(issues),
            "validated_at": datetime.now().isoformat(),
            "is_valid": is_valid,
        }

    def _validate_textual_document(self, data: dict[str, Any]) -> dict[str, Any]:
        fields = data.get("fields", {}) if isinstance(data.get("fields", {}), dict) else {}
        key_values = data.get("key_values", {}) if isinstance(data.get("key_values", {}), dict) else {}
        records = data.get("records", []) if isinstance(data.get("records", []), list) else []
        candidate_fields = fields or key_values

        field_validation = self._validate_candidate_fields(candidate_fields)
        rule_validation = dict(field_validation["rule_validation"])
        rule_validation["records_present"] = bool(records)
        issues = list(field_validation["issues"])
        correction_suggestions = dict(field_validation["correction_suggestions"])
        if not candidate_fields and not records:
            issues.append("未识别到可复用字段或通用记录。")
            correction_suggestions["records"] = "请检查文本中是否包含明确字段、数值和可追溯表述。"
        is_valid = bool(records) or (all(field_validation["rule_validation"].values()) if field_validation["rule_validation"] else bool(data))
        return {
            "normalized_data": data,
            "rule_validation": rule_validation,
            "dataset_validation": [],
            "indicator_validation": [],
            "llm_validation": {
                "skipped": True,
                "reason": "当前使用本地校验模式。",
            },
            "correction_suggestions": correction_suggestions,
            "issues": issues,
            "validated_at": datetime.now().isoformat(),
            "is_valid": is_valid,
        }

    def _validate_candidate_fields(self, candidate_fields: dict[str, Any]) -> dict[str, Any]:
        rule_validation = {}
        correction_suggestions = {}
        issues = []

        for field, value in candidate_fields.items():
            normalized_field = str(field).strip().lower()
            text_value = "" if value is None else str(value).strip()
            if not text_value:
                rule_validation[normalized_field] = False
                correction_suggestions[normalized_field] = "字段值为空，请补充。"
                issues.append(f"字段 {field} 为空。")
                continue

            if normalized_field in self.validation_rules:
                pattern = self.validation_rules[normalized_field]
                matched = bool(re.fullmatch(pattern, text_value))
                rule_validation[normalized_field] = matched
                if not matched:
                    issues.append(f"字段 {field} 不符合预期格式。")
                    correction_suggestions[normalized_field] = self._suggest_field_fix(normalized_field)
            else:
                rule_validation[normalized_field] = True

        return {
            "rule_validation": rule_validation,
            "correction_suggestions": correction_suggestions,
            "issues": issues,
        }

    def _find_duplicate_headers(self, headers: list[str]) -> list[str]:
        duplicates = []
        seen = set()
        for header in headers:
            if header in seen and header not in duplicates:
                duplicates.append(header)
            seen.add(header)
        return duplicates

    def _tabular_suggestions(self, dataset_validation: list[dict[str, Any]]) -> dict[str, str]:
        suggestions = {}
        for dataset in dataset_validation:
            if not dataset["record_count"]:
                suggestions[dataset["name"]] = "请检查原始表格是否存在空行、合并单元格或异常表头。"
            elif dataset["duplicate_headers"]:
                suggestions[dataset["name"]] = "请清理重复列名，避免后续结构化字段冲突。"
        return suggestions

    def _suggest_field_fix(self, field: str) -> str:
        suggestions = {
            "phone": "请使用 11 位手机号，必要时去掉 +86 前缀。",
            "email": "请使用合法邮箱格式，如 name@example.com。",
            "date": "请使用 YYYY-MM-DD 或 YYYY/MM/DD 格式。",
            "id_card": "请检查身份证号位数和校验位。",
        }
        return suggestions.get(field, "请检查字段内容是否完整且格式正确。")

    def _deduplicate(self, values: list[str]) -> list[str]:
        deduplicated = []
        for value in values:
            if value not in deduplicated:
                deduplicated.append(value)
        return deduplicated
