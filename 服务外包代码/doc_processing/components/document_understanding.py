from __future__ import annotations

import re
from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff"}
DOMAIN_KEYWORDS = {
    "government_statistics": ("统计公报", "统计局", "国民经济", "GDP", "人口", "财政"),
    "environment_monitoring": ("空气质量", "水质", "污染", "AQI", "PM2.5", "监测", "环保"),
    "healthcare": ("医院", "门诊", "住院", "患者", "手术", "医疗", "病床"),
    "finance": ("营收", "收入", "利润", "资产", "负债", "现金流", "利率"),
    "manufacturing": ("产量", "产值", "设备", "生产线", "良品率", "工单", "库存"),
    "education": ("学校", "学生", "教师", "招生", "毕业", "课程", "科研"),
    "agriculture": ("农业", "粮食", "播种", "养殖", "畜牧", "渔业"),
    "transportation": ("客运", "货运", "里程", "港口", "航班", "物流", "车辆"),
    "energy": ("发电", "用电", "装机", "千瓦时", "能耗", "新能源"),
    "retail_consumption": ("零售", "销量", "订单", "客单价", "门店", "销售额"),
    "human_resources": ("员工", "招聘", "离职", "薪酬", "绩效", "培训"),
    "legal_compliance": ("合同", "诉讼", "处罚", "合规", "监管", "条例"),
    "technology_operations": ("服务器", "请求量", "延迟", "可用性", "部署", "故障"),
}


class DocumentUnderstanding:
    def __init__(self, model_type: str = "heuristic") -> None:
        self.model_type = model_type or "heuristic"

    def understand(
        self,
        file_path: str,
        parsed_document: dict[str, Any] | None = None,
        layout_result: dict[str, Any] | None = None,
        ocr_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        document = parsed_document or {}
        path = Path(file_path)
        text = self._get_text(document, ocr_result)
        tables = document.get("tables", []) if isinstance(document, dict) else []
        category = self._infer_category(path, text, tables)
        candidate_fields = self._extract_candidate_fields(document, text)
        industry_domains = self._infer_domains(text, candidate_fields)

        return {
            "model": "heuristic",
            "document_category": category,
            "industry_domains": industry_domains,
            "candidate_fields": candidate_fields,
            "has_tables": bool(tables),
            "has_layout": bool((layout_result or {}).get("layout_elements")),
            "has_ocr_text": bool((ocr_result or {}).get("text", "").strip()),
            "summary": self._build_summary(category, text, tables, industry_domains),
        }

    def _infer_category(self, path: Path, text: str, tables: list[dict[str, Any]]) -> str:
        if tables:
            return "tabular_dataset"

        key_value_count = len(re.findall(r"^[^\n:：=]{1,40}[:：=].+$", text, flags=re.MULTILINE))
        heading_count = len(re.findall(r"^[一二三四五六七八九十\d]+[、.．)]\s*.+$", text, flags=re.MULTILINE))
        numeric_density = len(re.findall(r"\d", text))

        if key_value_count >= 2:
            return "key_value_document"
        if heading_count >= 2 and numeric_density >= 10:
            return "report_document"
        if path.suffix.lower() in IMAGE_EXTENSIONS or path.suffix.lower() == ".pdf":
            return "scanned_document" if text.strip() else "image_document"
        return "plain_text_document"

    def _infer_domains(self, text: str, candidate_fields: list[str]) -> list[str]:
        corpus = " ".join([text, *[str(item) for item in candidate_fields]]).lower()
        scores: dict[str, int] = {}
        for domain, keywords in DOMAIN_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                keyword_text = str(keyword).lower()
                if keyword_text and keyword_text in corpus:
                    score += 1
            if score:
                scores[domain] = score
        if not scores:
            return ["general"] if corpus.strip() else []
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        return [domain for domain, _ in ranked[:3]]

    def _extract_candidate_fields(self, document: dict[str, Any], text: str) -> list[str]:
        tables = document.get("tables", []) if isinstance(document, dict) else []
        if tables:
            return tables[0].get("headers", [])[:20]

        keys = []
        for match in re.finditer(r"^([^\n:：=]{1,40})[:：=].+$", text, flags=re.MULTILINE):
            key = match.group(1).strip()
            if key and key not in keys:
                keys.append(key)
        return keys[:20]

    def _build_summary(self, category: str, text: str, tables: list[dict[str, Any]], industry_domains: list[str]) -> str:
        domain_suffix = f" 领域倾向: {', '.join(industry_domains)}。" if industry_domains else ""
        if category == "tabular_dataset":
            total_rows = sum(table.get("row_count", 0) for table in tables)
            return f"检测到 {len(tables)} 个数据表，共 {total_rows} 行记录。{domain_suffix}".strip()

        paragraph_count = len([line for line in text.splitlines() if line.strip()])
        if category == "key_value_document":
            return f"检测到键值型文本，包含 {paragraph_count} 个有效文本段。{domain_suffix}".strip()
        if category == "report_document":
            return f"检测到报告型文本，包含 {paragraph_count} 个有效文本段。{domain_suffix}".strip()
        return f"检测到普通文本，包含 {paragraph_count} 个有效文本段。{domain_suffix}".strip()

    def _get_text(
        self,
        document: dict[str, Any],
        ocr_result: dict[str, Any] | None,
    ) -> str:
        content = document.get("content", "") if isinstance(document, dict) else ""
        if content:
            return str(content)
        if ocr_result:
            return str(ocr_result.get("text", ""))
        return ""
