from __future__ import annotations

import re
from typing import Any


HEADING_PATTERN = re.compile(r"^(?:第?[一二三四五六七八九十百\d]+[、.．)]|[一二三四五六七八九十百]+、|\d+[、.．)])\s*.+$")
MEASUREMENT_PATTERN = re.compile(r"-?\d+(?:\.\d+)?\s*(?:%|‰|万亿千百十元美元人民币吨亩公顷千瓦时平方米平方公里公里小时分钟秒人户家台套辆只次)?")
MULTI_SPACE_PATTERN = re.compile(r"[ \t]{2,}")
DOMAIN_HINTS = {
    "government_statistics": ("统计公报", "国民经济", "统计局", "GDP", "财政", "人口"),
    "environment_monitoring": ("空气质量", "AQI", "PM2.5", "污染", "监测站"),
    "manufacturing": ("工业", "产值", "产量", "生产线", "规上工业"),
    "finance": ("收入", "利润", "资产", "负债", "证券"),
    "energy": ("发电", "用电", "装机", "能耗", "充电"),
    "general": (),
}


class DocumentPreprocessor:
    def __init__(self, max_chunk_chars: int = 900) -> None:
        self.max_chunk_chars = max(300, int(max_chunk_chars))

    def preprocess(self, document: dict[str, Any]) -> dict[str, Any]:
        normalized_document = self._normalize_document(document)
        sections = self._extract_sections(
            normalized_document.get("blocks", []),
            normalized_document.get("content", ""),
        )
        chunks = self._build_chunks(
            sections or [self._fallback_section(normalized_document.get("content", ""))]
        )
        domain_candidates = self._infer_domain_candidates(
            normalized_document.get("metadata", {}).get("title", ""),
            normalized_document.get("content", ""),
        )
        measurement_candidates = self._measurement_candidates(normalized_document.get("content", ""))
        heading_count = sum(1 for block in normalized_document.get("blocks", []) if block.get("is_heading"))

        return {
            "clean_document": normalized_document,
            "stats": {
                "char_count": len(normalized_document.get("content", "")),
                "line_count": len(
                    [line for line in normalized_document.get("content", "").splitlines() if line.strip()]
                ),
                "table_count": len(normalized_document.get("tables", [])),
                "block_count": len(normalized_document.get("blocks", [])),
                "heading_count": heading_count,
                "section_count": len(sections),
                "chunk_count": len(chunks),
            },
            "signals": {
                "has_tables": bool(normalized_document.get("tables")),
                "has_ocr_text": bool(str(document.get("ocr_text", "")).strip()),
                "has_headings": heading_count > 0,
                "domain_candidates": domain_candidates,
                "section_titles": [section.get("title", "") for section in sections[:12]],
                "measurement_candidates": measurement_candidates,
                "source_type": normalized_document.get("type", "unknown"),
            },
            "chunks": chunks[:40],
        }

    def _normalize_document(self, document: dict[str, Any]) -> dict[str, Any]:
        content = self._normalize_text(document.get("content", ""))
        ocr_text = self._normalize_text(document.get("ocr_text", ""))
        merged_text = self._merge_text_sources(content, ocr_text)
        blocks = self._normalize_blocks(document.get("blocks", []) or [], merged_text)
        metadata = dict(document.get("metadata", {}) or {})
        if not metadata.get("title"):
            metadata["title"] = self._infer_title(merged_text)
        return {
            "type": document.get("type", "text"),
            "content": merged_text,
            "tables": document.get("tables", []) or [],
            "blocks": blocks,
            "metadata": metadata,
            "ocr_text": ocr_text,
            "json_data": document.get("json_data"),
        }

    def _merge_text_sources(self, content: str, ocr_text: str) -> str:
        if not content:
            return ocr_text
        if not ocr_text or ocr_text == content:
            return content
        if len(content) >= len(ocr_text) * 0.8:
            return content
        merged_lines: list[str] = []
        for line in (content + "\n" + ocr_text).splitlines():
            cleaned = line.strip()
            if cleaned and cleaned not in merged_lines:
                merged_lines.append(cleaned)
        return "\n".join(merged_lines)

    def _normalize_text(self, text: Any) -> str:
        normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
        lines = [MULTI_SPACE_PATTERN.sub(" ", line).strip() for line in normalized.splitlines()]
        collapsed: list[str] = []
        blank_pending = False
        for line in lines:
            if not line:
                if collapsed and not blank_pending:
                    collapsed.append("")
                    blank_pending = True
                continue
            collapsed.append(line)
            blank_pending = False
        return "\n".join(collapsed).strip()

    def _normalize_blocks(self, blocks: list[dict[str, Any]], fallback_text: str) -> list[dict[str, Any]]:
        normalized_blocks = []
        for index, block in enumerate(blocks, start=1):
            text = self._normalize_text(block.get("text", ""))
            if not text:
                continue
            normalized_blocks.append(
                {
                    "id": block.get("id") or f"block_{index}",
                    "type": block.get("type", "paragraph"),
                    "text": text,
                    "source_anchor": block.get("source_anchor", {})
                    if isinstance(block.get("source_anchor"), dict)
                    else {},
                    "is_heading": self._is_heading_block(block.get("type"), text),
                }
            )
        if normalized_blocks:
            return normalized_blocks
        return [
            {
                "id": f"line_{index}",
                "type": "paragraph",
                "text": line,
                "source_anchor": {"line_index": index},
                "is_heading": self._is_heading_block("paragraph", line),
            }
            for index, line in enumerate(fallback_text.splitlines(), start=1)
            if line.strip()
        ]

    def _extract_sections(self, blocks: list[dict[str, Any]], fallback_text: str) -> list[dict[str, Any]]:
        if not blocks and not fallback_text.strip():
            return []
        sections = []
        current_title = "引言"
        current_lines: list[str] = []
        current_anchor: dict[str, Any] = {}

        def flush_section() -> None:
            nonlocal current_lines, current_title, current_anchor
            content = "\n".join(current_lines).strip()
            if content:
                sections.append(
                    {
                        "id": f"prep_sec_{len(sections) + 1}",
                        "title": current_title,
                        "content": content,
                        "source_anchor": current_anchor,
                    }
                )
            current_lines = []

        for block in blocks:
            text = str(block.get("text", "")).strip()
            if not text:
                continue
            if block.get("is_heading"):
                flush_section()
                current_title = text
                current_anchor = block.get("source_anchor", {})
                continue
            current_lines.append(text)

        flush_section()
        return sections

    def _build_chunks(self, sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
        chunks = []
        for section in sections:
            text = str(section.get("content", "")).strip()
            if not text:
                continue
            parts = self._split_to_chunk_parts(text)
            for index, part in enumerate(parts, start=1):
                chunks.append(
                    {
                        "chunk_id": f"{section.get('id', 'section')}_chunk_{index}",
                        "section_title": section.get("title", "未分段"),
                        "char_count": len(part),
                        "text_preview": part[:320],
                        "source_anchor": section.get("source_anchor", {}),
                    }
                )
        return chunks

    def _split_to_chunk_parts(self, text: str) -> list[str]:
        if len(text) <= self.max_chunk_chars:
            return [text]
        parts: list[str] = []
        current = ""
        for paragraph in [item.strip() for item in text.split("\n") if item.strip()]:
            candidate = paragraph if not current else f"{current}\n{paragraph}"
            if len(candidate) <= self.max_chunk_chars:
                current = candidate
                continue
            if current:
                parts.append(current)
            current = paragraph
            if len(current) > self.max_chunk_chars:
                parts.extend(self._hard_split(current))
                current = ""
        if current:
            parts.append(current)
        return parts or [text[: self.max_chunk_chars]]

    def _hard_split(self, text: str) -> list[str]:
        slices = []
        start = 0
        while start < len(text):
            slices.append(text[start : start + self.max_chunk_chars])
            start += self.max_chunk_chars
        return slices

    def _measurement_candidates(self, text: str) -> list[str]:
        values: list[str] = []
        for match in MEASUREMENT_PATTERN.finditer(text):
            candidate = match.group(0).strip()
            if candidate and candidate not in values:
                values.append(candidate)
            if len(values) >= 10:
                break
        return values

    def _infer_domain_candidates(self, title: str, text: str) -> list[str]:
        corpus = f"{title} {text}".lower()
        scores: list[tuple[str, int]] = []
        for domain, keywords in DOMAIN_HINTS.items():
            score = sum(1 for keyword in keywords if keyword.lower() in corpus)
            if score:
                scores.append((domain, score))
        scores.sort(key=lambda item: (-item[1], item[0]))
        return [domain for domain, _ in scores[:3]] or ["general"]

    def _is_heading_block(self, block_type: str | None, text: str) -> bool:
        if str(block_type or "").lower() in {"heading", "title", "header"}:
            return True
        stripped = text.strip()
        return len(stripped) <= 60 and bool(HEADING_PATTERN.match(stripped))

    def _fallback_section(self, text: str) -> dict[str, Any]:
        return {"id": "prep_sec_1", "title": "全文", "content": text, "source_anchor": {}}

    def _infer_title(self, text: str) -> str:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped[:120]
        return "未命名文档"
