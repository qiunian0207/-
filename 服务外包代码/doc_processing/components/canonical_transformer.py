from __future__ import annotations

import os
import re
from typing import Any


BULLETIN_TITLE_PATTERN = re.compile(
    r"(?P<year>\d{4})年(?P<region>.+?)(?:国民经济和社会发展统计公报|统计公报)"
)
YEAR_PATTERN = re.compile(r"(19|20)\d{2}")


class CanonicalTransformer:
    def transform(
        self,
        structured_data: dict[str, Any],
        source_document: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(structured_data, dict):
            structured_data = {}
        if not isinstance(source_document, dict):
            source_document = {}

        document_type = structured_data.get("document_type", "unknown")
        if document_type == "tabular_dataset":
            canonical_data = self._build_tabular_canonical(structured_data, source_document)
        elif document_type == "report_document":
            canonical_data = self._build_report_canonical(structured_data, source_document)
        elif document_type == "key_value_document":
            canonical_data = self._build_key_value_canonical(structured_data, source_document)
        else:
            canonical_data = self._build_plain_text_canonical(structured_data, source_document)

        canonical_data["document_summary"] = structured_data.get("document_summary", {}) if isinstance(structured_data.get("document_summary"), dict) else {}
        canonical_data["detail_groups"] = structured_data.get("detail_groups", {}) if isinstance(structured_data.get("detail_groups"), dict) else {}
        return canonical_data

    def normalize_structured_input(
        self,
        payload: Any,
        source_name: str = "structured_input.json",
    ) -> dict[str, Any]:
        candidate = self._unwrap_payload(payload)

        if self._looks_like_canonical(candidate):
            canonical_data = self._normalize_canonical(candidate, source_name)
            structured_data = self._structured_from_canonical(canonical_data)
        elif isinstance(candidate, dict) and candidate.get("document_type"):
            structured_data = candidate
            canonical_data = self.transform(structured_data, self._source_document_stub(source_name))
        elif isinstance(candidate, list) and candidate and all(isinstance(item, dict) for item in candidate):
            structured_data = self._structured_from_records(candidate, source_name)
            canonical_data = self.transform(structured_data, self._source_document_stub(source_name))
        elif isinstance(candidate, dict):
            structured_data = self._structured_from_mapping(candidate, source_name)
            canonical_data = self.transform(structured_data, self._source_document_stub(source_name))
        else:
            raise ValueError("无法识别结构化输入，请提供 JSON 对象、记录数组或 canonical_data。")

        return {
            "structured_data": structured_data,
            "canonical_data": canonical_data,
        }

    def _unwrap_payload(self, payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload
        if payload.get("canonical_data"):
            return payload.get("canonical_data")
        if payload.get("structured_data"):
            return payload.get("structured_data")
        if payload.get("semantic", {}).get("canonical_data"):
            return payload["semantic"]["canonical_data"]
        if payload.get("semantic", {}).get("structured_data"):
            return payload["semantic"]["structured_data"]
        return payload

    def _looks_like_canonical(self, payload: Any) -> bool:
        return isinstance(payload, dict) and isinstance(payload.get("document_meta"), dict)

    def _normalize_canonical(self, canonical_data: dict[str, Any], source_name: str) -> dict[str, Any]:
        document_meta = canonical_data.get("document_meta", {})
        domain_tags = document_meta.get("domain_tags") or canonical_data.get("domains", []) or []
        normalized_meta = {
            "title": document_meta.get("title") or os.path.splitext(os.path.basename(source_name))[0],
            "document_type": document_meta.get("document_type", "unknown"),
            "source_type": document_meta.get("source_type", "json"),
            "source_file": document_meta.get("source_file") or source_name,
            "region": document_meta.get("region"),
            "year": document_meta.get("year"),
            "publish_date": document_meta.get("publish_date"),
            "domain_tags": domain_tags,
        }
        return {
            "schema_version": canonical_data.get("schema_version", "1.0"),
            "document_meta": normalized_meta,
            "tables": canonical_data.get("tables", []) or [],
            "sections": canonical_data.get("sections", []) or [],
            "indicators": canonical_data.get("indicators", []) or [],
            "records": canonical_data.get("records", []) or [],
            "domains": canonical_data.get("domains", []) or domain_tags,
            "key_values": canonical_data.get("key_values", []) or [],
            "entities": canonical_data.get("entities", {}) or {},
            "narrative_blocks": canonical_data.get("narrative_blocks", []) or [],
            "stats": canonical_data.get("stats", {}) or {},
            "document_summary": canonical_data.get("document_summary", {}) if isinstance(canonical_data.get("document_summary"), dict) else {},
            "detail_groups": canonical_data.get("detail_groups", {}) if isinstance(canonical_data.get("detail_groups"), dict) else {},
        }

    def _build_tabular_canonical(
        self,
        structured_data: dict[str, Any],
        source_document: dict[str, Any],
    ) -> dict[str, Any]:
        datasets = structured_data.get("datasets", []) if isinstance(structured_data.get("datasets"), list) else []
        tables = []
        total_record_count = 0

        for index, dataset in enumerate(datasets, start=1):
            records = dataset.get("records", []) if isinstance(dataset.get("records"), list) else []
            headers = dataset.get("headers", []) if isinstance(dataset.get("headers"), list) else []
            row_count = int(dataset.get("row_count", len(records)) or 0)
            total_record_count += row_count
            tables.append(
                {
                    "id": f"table_{index}",
                    "name": dataset.get("name", f"dataset_{index}"),
                    "headers": headers,
                    "row_count": row_count,
                    "column_count": int(dataset.get("column_count", len(headers)) or len(headers)),
                    "null_value_count": int(dataset.get("null_value_count", 0) or 0),
                    "sample_records": records[:5],
                    "column_profiles": self._build_column_profiles(headers, records),
                    "source_anchor": dataset.get("source_anchor", {}),
                }
            )

        title = structured_data.get("title") or source_document.get("metadata", {}).get("title") or "未命名数据集"
        document_meta = self._build_document_meta(structured_data, source_document, title)
        document_meta["document_type"] = "tabular_dataset"
        domain_tags = structured_data.get("domain_tags", []) if isinstance(structured_data.get("domain_tags"), list) else []

        return {
            "schema_version": "1.0",
            "document_meta": document_meta,
            "tables": tables,
            "sections": [],
            "indicators": [
                {
                    "id": "dataset_count",
                    "name": "数据集数量",
                    "value": len(tables),
                    "unit": "个",
                },
                {
                    "id": "record_count",
                    "name": "记录总数",
                    "value": total_record_count,
                    "unit": "条",
                },
            ],
            "records": [],
            "domains": domain_tags,
            "key_values": [],
            "entities": {},
            "narrative_blocks": [],
            "stats": {
                "dataset_count": len(tables),
                "record_count": total_record_count,
            },
        }

    def _build_report_canonical(
        self,
        structured_data: dict[str, Any],
        source_document: dict[str, Any],
    ) -> dict[str, Any]:
        sections = structured_data.get("sections", []) if isinstance(structured_data.get("sections"), list) else []
        indicators = structured_data.get("indicators", []) if isinstance(structured_data.get("indicators"), list) else []
        records = structured_data.get("records", []) if isinstance(structured_data.get("records"), list) else []
        key_values = structured_data.get("key_values", {}) if isinstance(structured_data.get("key_values"), dict) else {}
        fields = structured_data.get("fields", {}) if isinstance(structured_data.get("fields"), dict) else {}
        domain_tags = structured_data.get("domain_tags", []) if isinstance(structured_data.get("domain_tags"), list) else []

        normalized_sections = []
        section_ids: dict[str, str] = {}
        for index, section in enumerate(sections, start=1):
            section_id = section.get("id") or f"sec_{index}"
            title = section.get("title", f"章节 {index}")
            section_ids[title] = section_id
            normalized_sections.append(
                {
                    "id": section_id,
                    "title": title,
                    "summary": section.get("content", ""),
                    "source_anchor": section.get("source_anchor", {}),
                }
            )

        normalized_indicators = []
        for index, indicator in enumerate(indicators, start=1):
            section_id = indicator.get("section_id")
            if not section_id and indicator.get("section_title") in section_ids:
                section_id = section_ids[indicator["section_title"]]
            normalized_indicators.append(
                {
                    "id": indicator.get("id") or f"ind_{index}",
                    "section_id": section_id,
                    "name": indicator.get("name") or indicator.get("label") or f"指标 {index}",
                    "value": indicator.get("value"),
                    "unit": indicator.get("unit"),
                    "yoy": indicator.get("yoy"),
                    "statement": indicator.get("statement", ""),
                    "comparison_text": indicator.get("comparison_text"),
                    "source_anchor": indicator.get("source_anchor", {}),
                }
            )

        normalized_key_values = []
        for key, value in {**key_values, **fields}.items():
            normalized_key_values.append({"key": key, "value": value})

        document_meta = self._build_document_meta(
            structured_data,
            source_document,
            structured_data.get("title") or source_document.get("metadata", {}).get("title") or "未命名报告",
        )
        document_meta["document_type"] = "report_document"
        publish_date = structured_data.get("publish_date") or (structured_data.get("dates") or [None])[0]
        if publish_date:
            document_meta["publish_date"] = publish_date

        record_table = self._build_record_table(records, name="records")
        tables = [record_table] if record_table else []
        return {
            "schema_version": "1.0",
            "document_meta": document_meta,
            "tables": tables,
            "sections": normalized_sections,
            "indicators": normalized_indicators,
            "records": records,
            "domains": domain_tags,
            "key_values": normalized_key_values,
            "entities": structured_data.get("entities", {}) or {},
            "narrative_blocks": [
                {
                    "id": section.get("id"),
                    "section_id": section.get("id"),
                    "text": section.get("summary", ""),
                }
                for section in normalized_sections
                if section.get("summary")
            ],
            "stats": {
                "section_count": len(normalized_sections),
                "indicator_count": len(normalized_indicators),
                "record_count": len(records),
            },
        }

    def _build_key_value_canonical(
        self,
        structured_data: dict[str, Any],
        source_document: dict[str, Any],
    ) -> dict[str, Any]:
        fields = structured_data.get("fields", {}) if isinstance(structured_data.get("fields"), dict) else {}
        key_values = structured_data.get("key_values", {}) if isinstance(structured_data.get("key_values"), dict) else {}
        records = structured_data.get("records", []) if isinstance(structured_data.get("records"), list) else []
        domain_tags = structured_data.get("domain_tags", []) if isinstance(structured_data.get("domain_tags"), list) else []
        merged_items = []
        for key, value in {**key_values, **fields}.items():
            merged_items.append({"key": key, "value": value})

        document_meta = self._build_document_meta(
            structured_data,
            source_document,
            structured_data.get("title") or source_document.get("metadata", {}).get("title") or "未命名键值文档",
        )
        document_meta["document_type"] = "key_value_document"
        record_table = self._build_record_table(records, name="records")

        return {
            "schema_version": "1.0",
            "document_meta": document_meta,
            "tables": [record_table] if record_table else [],
            "sections": [],
            "indicators": [],
            "records": records,
            "domains": domain_tags,
            "key_values": merged_items,
            "entities": structured_data.get("entities", {}) or {},
            "narrative_blocks": [],
            "stats": {
                "field_count": len(merged_items),
                "record_count": len(records),
            },
        }

    def _build_plain_text_canonical(
        self,
        structured_data: dict[str, Any],
        source_document: dict[str, Any],
    ) -> dict[str, Any]:
        content_excerpt = structured_data.get("content_excerpt", "")
        records = structured_data.get("records", []) if isinstance(structured_data.get("records"), list) else []
        domain_tags = structured_data.get("domain_tags", []) if isinstance(structured_data.get("domain_tags"), list) else []
        document_meta = self._build_document_meta(
            structured_data,
            source_document,
            structured_data.get("title") or source_document.get("metadata", {}).get("title") or "未命名文档",
        )
        document_meta["document_type"] = structured_data.get("document_type", "plain_text_document")
        record_table = self._build_record_table(records, name="records")

        return {
            "schema_version": "1.0",
            "document_meta": document_meta,
            "tables": [record_table] if record_table else [],
            "sections": [],
            "indicators": [],
            "records": records,
            "domains": domain_tags,
            "key_values": [],
            "entities": structured_data.get("entities", {}) or {},
            "narrative_blocks": ([{"id": "excerpt", "text": content_excerpt}] if content_excerpt else []),
            "stats": {
                "excerpt_length": len(content_excerpt),
                "record_count": len(records),
            },
        }

    def _structured_from_canonical(self, canonical_data: dict[str, Any]) -> dict[str, Any]:
        document_meta = canonical_data.get("document_meta", {})
        document_type = document_meta.get("document_type", "unknown")
        domain_tags = canonical_data.get("domains", document_meta.get("domain_tags", []))
        canonical_records = canonical_data.get("records", []) if isinstance(canonical_data.get("records"), list) else []
        document_summary = canonical_data.get("document_summary", {}) if isinstance(canonical_data.get("document_summary"), dict) else {}
        detail_groups = canonical_data.get("detail_groups", {}) if isinstance(canonical_data.get("detail_groups"), dict) else {}

        if document_type == "tabular_dataset":
            tables = canonical_data.get("tables", []) if isinstance(canonical_data.get("tables"), list) else []
            datasets = []
            schema = []
            record_count = 0
            for table in tables:
                headers = table.get("headers", []) if isinstance(table.get("headers"), list) else []
                sample_records = table.get("sample_records", []) if isinstance(table.get("sample_records"), list) else []
                schema.extend(headers)
                record_count += int(table.get("row_count", len(sample_records)) or 0)
                datasets.append(
                    {
                        "name": table.get("name", "dataset"),
                        "headers": headers,
                        "row_count": int(table.get("row_count", len(sample_records)) or 0),
                        "column_count": int(table.get("column_count", len(headers)) or len(headers)),
                        "null_value_count": int(table.get("null_value_count", 0) or 0),
                        "records": sample_records,
                        "source_anchor": table.get("source_anchor", {}),
                    }
                )
            return {
                "document_type": "tabular_dataset",
                "title": document_meta.get("title"),
                "source_type": document_meta.get("source_type", "json"),
                "domain_tags": domain_tags,
                "dataset_count": len(datasets),
                "record_count": record_count,
                "schema": self._deduplicate(schema),
                "datasets": datasets,
                "document_summary": document_summary,
                "detail_groups": detail_groups,
            }

        if document_type == "report_document":
            sections = canonical_data.get("sections", []) if isinstance(canonical_data.get("sections"), list) else []
            indicators = canonical_data.get("indicators", []) if isinstance(canonical_data.get("indicators"), list) else []
            key_values = canonical_data.get("key_values", []) if isinstance(canonical_data.get("key_values"), list) else []
            key_value_mapping = {
                item.get("key", "field"): item.get("value")
                for item in key_values
                if isinstance(item, dict) and item.get("key")
            }
            return {
                "document_type": "report_document",
                "title": document_meta.get("title"),
                "source_type": document_meta.get("source_type", "json"),
                "region": document_meta.get("region"),
                "year": document_meta.get("year"),
                "publish_date": document_meta.get("publish_date"),
                "domain_tags": domain_tags,
                "fields": key_value_mapping,
                "key_values": key_value_mapping,
                "dates": [document_meta.get("publish_date")] if document_meta.get("publish_date") else [],
                "sections": [
                    {
                        "id": section.get("id"),
                        "title": section.get("title", ""),
                        "content": section.get("summary", ""),
                        "source_anchor": section.get("source_anchor", {}),
                    }
                    for section in sections
                ],
                "records": canonical_records,
                "record_count": len(canonical_records),
                "schema": list(canonical_records[0].keys()) if canonical_records else [],
                "indicators": indicators,
                "metrics": [self._metric_from_indicator(indicator) for indicator in indicators],
                "entities": canonical_data.get("entities", {}) or {},
                "summary": {
                    "section_count": len(sections),
                    "metric_count": len(indicators),
                    "record_count": len(canonical_records),
                },
                "document_summary": document_summary,
                "detail_groups": detail_groups,
            }

        if document_type == "key_value_document":
            key_values = canonical_data.get("key_values", []) if isinstance(canonical_data.get("key_values"), list) else []
            mapping = {
                item.get("key", "field"): item.get("value")
                for item in key_values
                if isinstance(item, dict) and item.get("key")
            }
            return {
                "document_type": "key_value_document",
                "title": document_meta.get("title"),
                "source_type": document_meta.get("source_type", "json"),
                "region": document_meta.get("region"),
                "year": document_meta.get("year"),
                "publish_date": document_meta.get("publish_date"),
                "domain_tags": domain_tags,
                "fields": mapping,
                "key_values": mapping,
                "dates": [document_meta.get("publish_date")] if document_meta.get("publish_date") else [],
                "sections": [],
                "records": canonical_records,
                "record_count": len(canonical_records),
                "schema": list(canonical_records[0].keys()) if canonical_records else [],
                "entities": canonical_data.get("entities", {}) or {},
                "summary": {
                    "field_count": len(mapping),
                    "key_value_count": len(mapping),
                    "record_count": len(canonical_records),
                },
                "document_summary": document_summary,
                "detail_groups": detail_groups,
            }

        narrative_blocks = canonical_data.get("narrative_blocks", []) if isinstance(canonical_data.get("narrative_blocks"), list) else []
        excerpt = "\n\n".join(str(block.get("text", "")) for block in narrative_blocks if block.get("text"))[:2000]
        return {
            "document_type": document_type or "plain_text_document",
            "title": document_meta.get("title"),
            "source_type": document_meta.get("source_type", "json"),
            "region": document_meta.get("region"),
            "year": document_meta.get("year"),
            "publish_date": document_meta.get("publish_date"),
            "domain_tags": domain_tags,
            "records": canonical_records,
            "record_count": len(canonical_records),
            "schema": list(canonical_records[0].keys()) if canonical_records else [],
            "entities": canonical_data.get("entities", {}) or {},
            "content_excerpt": excerpt,
            "document_summary": document_summary,
            "detail_groups": detail_groups,
        }

    def _structured_from_records(self, records: list[dict[str, Any]], source_name: str) -> dict[str, Any]:
        headers = []
        for record in records:
            for key in record.keys():
                if key not in headers:
                    headers.append(str(key))
        return {
            "document_type": "tabular_dataset",
            "title": os.path.splitext(os.path.basename(source_name))[0],
            "source_type": "json",
            "dataset_count": 1,
            "record_count": len(records),
            "schema": headers,
            "datasets": [
                {
                    "name": "records",
                    "headers": headers,
                    "row_count": len(records),
                    "column_count": len(headers),
                    "null_value_count": 0,
                    "records": records,
                    "source_anchor": {"source_file": source_name},
                }
            ],
        }

    def _structured_from_mapping(self, payload: dict[str, Any], source_name: str) -> dict[str, Any]:
        records = self._mapping_records(payload, source_name)
        return {
            "document_type": "key_value_document",
            "title": os.path.splitext(os.path.basename(source_name))[0],
            "source_type": "json",
            "domain_tags": [],
            "fields": payload,
            "key_values": payload,
            "dates": [],
            "sections": [],
            "records": records,
            "record_count": len(records),
            "schema": list(records[0].keys()) if records else [],
            "entities": {},
            "summary": {
                "field_count": len(payload),
                "key_value_count": len(payload),
                "record_count": len(records),
            },
        }

    def _build_document_meta(
        self,
        structured_data: dict[str, Any],
        source_document: dict[str, Any],
        title: str,
    ) -> dict[str, Any]:
        metadata = source_document.get("metadata", {}) if isinstance(source_document.get("metadata"), dict) else {}
        region, year = self._infer_region_and_year(title, structured_data)
        publish_date = structured_data.get("publish_date") or metadata.get("publish_date")
        domain_tags = structured_data.get("domain_tags", []) if isinstance(structured_data.get("domain_tags"), list) else []

        return {
            "title": title,
            "document_type": structured_data.get("document_type", "unknown"),
            "source_type": structured_data.get("source_type") or source_document.get("type", "unknown"),
            "source_file": metadata.get("file_name") or structured_data.get("source_file") or title,
            "region": structured_data.get("region") or region,
            "year": structured_data.get("year") or year,
            "publish_date": publish_date,
            "domain_tags": domain_tags,
        }

    def _infer_region_and_year(
        self,
        title: str,
        structured_data: dict[str, Any],
    ) -> tuple[str | None, int | None]:
        match = BULLETIN_TITLE_PATTERN.search(title)
        if match:
            return match.group("region"), int(match.group("year"))

        year_value = structured_data.get("year")
        if isinstance(year_value, int):
            year = year_value
        else:
            year_match = YEAR_PATTERN.search(title)
            year = int(year_match.group(0)) if year_match else None

        region = structured_data.get("region")
        return region, year

    def _build_record_table(self, records: list[dict[str, Any]], name: str = "records") -> dict[str, Any] | None:
        if not records:
            return None
        headers = self._deduplicate([str(key) for record in records for key in record.keys()])
        return {
            "id": f"table_{name}",
            "name": name,
            "headers": headers,
            "row_count": len(records),
            "column_count": len(headers),
            "null_value_count": 0,
            "sample_records": records[:20],
            "column_profiles": self._build_column_profiles(headers, records),
            "source_anchor": {"generated": True},
        }

    def _mapping_records(self, payload: dict[str, Any], source_name: str) -> list[dict[str, Any]]:
        records = []
        for index, (key, value) in enumerate(payload.items(), start=1):
            text_value = "" if value is None else str(value)
            records.append(
                {
                    "record_id": f"rec_{index}",
                    "record_type": "attribute",
                    "document_title": os.path.splitext(os.path.basename(source_name))[0],
                    "section": "字段",
                    "indicator_name": str(key),
                    "metric_type": "attribute",
                    "value": value,
                    "value_text": text_value,
                    "unit": None,
                    "yoy_percent": None,
                    "comparison_value": None,
                    "comparison_unit": None,
                    "comparison_text": None,
                    "time_reference": None,
                    "location_reference": None,
                    "source_sentence": f"{key}: {text_value}",
                    "source_clause": f"{key}: {text_value}",
                    "paragraph_index": None,
                    "sentence_index": index,
                    "clause_index": 1,
                }
            )
        return records

    def _build_column_profiles(
        self,
        headers: list[str],
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        profiles = []
        sample_limit = min(len(records), 200)
        sampled_records = records[:sample_limit]
        for header in headers:
            values = [record.get(header) for record in sampled_records]
            non_null_values = [value for value in values if value not in (None, "")]
            profiles.append(
                {
                    "name": header,
                    "non_null_count": len(non_null_values),
                    "sample_values": self._sample_values(non_null_values),
                }
            )
        return profiles

    def _sample_values(self, values: list[Any], limit: int = 3) -> list[str]:
        sampled = []
        for value in values:
            text = str(value).strip()
            if not text or text in sampled:
                continue
            sampled.append(text)
            if len(sampled) >= limit:
                break
        return sampled

    def _metric_from_indicator(self, indicator: dict[str, Any]) -> dict[str, Any]:
        values = []
        if indicator.get("value") is not None:
            values.append({"value": indicator.get("value"), "unit": indicator.get("unit")})
        if indicator.get("yoy") is not None:
            values.append({"value": indicator.get("yoy"), "unit": "%"})
        return {
            "label": indicator.get("name", ""),
            "statement": indicator.get("statement", ""),
            "values": values,
        }

    def _source_document_stub(self, source_name: str) -> dict[str, Any]:
        return {
            "type": "json",
            "metadata": {
                "file_name": source_name,
                "title": os.path.splitext(os.path.basename(source_name))[0],
            },
        }

    def _deduplicate(self, values: list[Any]) -> list[Any]:
        deduplicated = []
        for value in values:
            if value not in deduplicated:
                deduplicated.append(value)
        return deduplicated
