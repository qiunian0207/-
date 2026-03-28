from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

try:
    from config.config import (
        DETAIL_MODEL_CANDIDATES,
        ENABLE_POSTPROCESSING,
        ENABLE_PREPROCESSING,
        ENABLE_PROMPT_OPTIMIZATION,
        ENABLE_SUMMARY_SELF_CHECK,
        PROMPT_VERSION,
        ROUTER_MODEL,
        SEMANTIC_CHUNK_CHARS,
        SUMMARY_MODEL_CANDIDATES,
    )
    from components.canonical_transformer import CanonicalTransformer
    from components.model_router import ModelRouter
    from components.postprocessor import StructuredPostprocessor
    from components.preprocessor import DocumentPreprocessor
    from components.prompt_registry import PromptRegistry
except ImportError:
    from doc_processing.config.config import (
        DETAIL_MODEL_CANDIDATES,
        ENABLE_POSTPROCESSING,
        ENABLE_PREPROCESSING,
        ENABLE_PROMPT_OPTIMIZATION,
        ENABLE_SUMMARY_SELF_CHECK,
        PROMPT_VERSION,
        ROUTER_MODEL,
        SEMANTIC_CHUNK_CHARS,
        SUMMARY_MODEL_CANDIDATES,
    )
    from doc_processing.components.canonical_transformer import CanonicalTransformer
    from doc_processing.components.model_router import ModelRouter
    from doc_processing.components.postprocessor import StructuredPostprocessor
    from doc_processing.components.preprocessor import DocumentPreprocessor
    from doc_processing.components.prompt_registry import PromptRegistry


NULL_MARKERS = {"", "-", "--", "—", "无", "null", "none", "n/a", "nan"}
STANDARD_FIELD_ALIASES = {
    "name": ["name", "姓名"],
    "address": ["address", "地址"],
    "phone": ["phone", "mobile", "电话", "手机号", "联系方式"],
    "email": ["email", "邮箱", "电子邮箱"],
    "date": ["date", "日期", "时间", "发布时间"],
    "amount": ["amount", "金额", "总额", "价款"],
    "id_number": ["id", "id_number", "身份证", "证件号"],
}

NUMBER_UNIT_PATTERN = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*([A-Za-z%‰万亿千百十个分点倍项笔件元美元人民币吨亩公顷千瓦时平方米平方公里公里小时分钟秒人户家台套辆只次年个月日米公斤升克]*)"
)
DATE_PATTERN = re.compile(r"\d{4}[年\-/\.]\d{1,2}[月\-/\.]\d{1,2}(?:日)?")
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_PATTERN = re.compile(r"(?:\+?86)?[\s-]?(1[3-9]\d{9})")
ID_PATTERN = re.compile(
    r"[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[0-9Xx]"
)
HEADING_PATTERN = re.compile(r"^(?:第?[一二三四五六七八九十百\d]+[、.．)]|[一二三四五六七八九十百]+、)\s*.+$")
HEADING_PREFIX_CLEAN_PATTERN = re.compile(
    r"^(?:(?:第?[一二三四五六七八九十百\d]+[、.．)]|[一二三四五六七八九十百]+、|[（(][一二三四五六七八九十百\d]+[）)]))\s*"
)
LEADING_INDICATOR_PREFIX_PATTERN = re.compile(
    r"^(?:全年|全市|全省|全县|全区|年末|年初|其中|截至[^，,；;]*|全社会|全体|全行业|经[^，,；;]*|目前|当前|总体看|从[^，,；;。]{0,20}看)\s*"
)
TRAILING_INDICATOR_ACTION_PATTERN = re.compile(r"(?:为|达到|达|有|拥有|共|实现|完成|形成|保持|维持|继续|持续|新增)$")
KEY_VALUE_PATTERN = re.compile(r"^([^\n:：=]{1,40})[:：=]\s*(.+)$")
YOY_PATTERN = re.compile(
    r"(?:(?:同比|比上年|较上年|较去年)(增长|下降|提高|回落|增加|减少)|"
    r"(增长|下降|提高|回落|增加|减少))(\d+(?:\.\d+)?)\s*(%|个百分点)?"
)
REPORT_TITLE_PATTERN = re.compile(r"(?P<year>\d{4})年(?P<region>.+?)(?:国民经济和社会发展统计公报|统计公报)")
NOISE_KEYWORDS = ("发布日期", "浏览次数", "浏览量", "点击量")
RATIO_KEYWORDS = ("率", "比例", "比重", "占比", "比值")
GROWTH_KEYWORDS = ("增长", "下降", "提高", "回落", "增加", "减少")
FIGURE_TABLE_PATTERN = re.compile(r"^(?:图|表)\s*\d+")
DOMAIN_KEYWORDS = {
    "government_statistics": ("统计公报", "统计局", "国民经济", "GDP", "人口", "财政", "固定资产投资"),
    "environment_monitoring": ("空气质量", "水质", "污染", "AQI", "PM2.5", "监测站", "排放", "环保"),
    "healthcare": ("医院", "门诊", "住院", "患者", "手术", "病床", "疫苗", "医疗"),
    "finance": ("营收", "收入", "利润", "资产", "负债", "现金流", "贷款", "利率", "证券"),
    "manufacturing": ("产量", "产值", "设备", "生产线", "良品率", "工单", "库存", "制造业"),
    "education": ("学校", "学生", "教师", "招生", "毕业", "课程", "学位", "科研"),
    "agriculture": ("农业", "粮食", "播种", "农作物", "养殖", "畜牧", "渔业", "耕地"),
    "transportation": ("客运", "货运", "里程", "港口", "航班", "车辆", "物流", "轨道交通"),
    "energy": ("发电", "用电", "装机", "千瓦时", "油气", "新能源", "能耗", "充电"),
    "retail_consumption": ("零售", "销量", "订单", "客单价", "门店", "会员", "消费", "销售额"),
    "human_resources": ("员工", "招聘", "离职", "薪酬", "绩效", "培训", "人力", "考勤"),
    "legal_compliance": ("合同", "诉讼", "处罚", "合规", "执法", "监管", "条例", "仲裁"),
    "technology_operations": ("服务器", "请求量", "延迟", "可用性", "部署", "告警", "故障", "接口"),
}


class SemanticAnalyzer:
    def __init__(
        self,
        model_type: str = "local",
        detail_model_type: str | None = None,
        summary_model_type: str | None = None,
    ) -> None:
        self.model_type = model_type or "local"
        self.detail_model_type = detail_model_type or self.model_type
        self.summary_model_type = summary_model_type or self.model_type
        self.router_model = ROUTER_MODEL
        self.preprocessing_enabled = ENABLE_PREPROCESSING
        self.postprocessing_enabled = ENABLE_POSTPROCESSING
        self.prompt_optimization_enabled = ENABLE_PROMPT_OPTIMIZATION
        self.canonical_transformer = CanonicalTransformer()
        self.preprocessor = DocumentPreprocessor(max_chunk_chars=SEMANTIC_CHUNK_CHARS)
        self.model_router = ModelRouter(
            router_model=self.router_model,
            default_detail_model=self.detail_model_type,
            default_summary_model=self.summary_model_type,
            detail_candidates=DETAIL_MODEL_CANDIDATES,
            summary_candidates=SUMMARY_MODEL_CANDIDATES,
        )
        self.prompt_registry = PromptRegistry(
            prompt_version=PROMPT_VERSION,
            enable_self_check=ENABLE_SUMMARY_SELF_CHECK,
        )
        self.postprocessor = StructuredPostprocessor()

    def analyze(self, content: Any) -> dict[str, Any]:
        detail_result = self.extract_details(content)
        return self.build_structured_result(
            structured_data=detail_result.get("structured_data", {}),
            canonical_data=detail_result.get("canonical_data", {}),
            validation_result=None,
            extraction_method=detail_result.get("extraction_method", "detail_rule_based_local"),
            timestamp=detail_result.get("timestamp"),
            preprocessing_result=detail_result.get("preprocessing", {}),
            routing_plan=detail_result.get("routing", {}),
            prompt_plan=detail_result.get("prompting", {}),
            postprocess_report=detail_result.get("postprocessing", {}),
        )

    def extract_details(self, content: Any) -> dict[str, Any]:
        document = self._normalize_document(content)
        preprocessing_result = self._default_preprocessing_result(document)
        if self.preprocessing_enabled:
            try:
                preprocessing_result = self.preprocessor.preprocess(document)
            except Exception as exc:
                preprocessing_result["error"] = str(exc)

        effective_document = preprocessing_result.get("clean_document", document)
        if not isinstance(effective_document, dict):
            effective_document = document

        routing_plan = self._build_routing_plan(
            structured_hint={},
            preprocessing_result=preprocessing_result,
            document=effective_document,
            operation_mode="natural_to_structured",
        )
        detail_prompt_plan = (
            self.prompt_registry.build_detail_prompt_plan(effective_document, preprocessing_result, routing_plan)
            if self.prompt_optimization_enabled
            else self._disabled_prompt_plan("detail")
        )

        structured_data = self._extract_local(effective_document)
        postprocess_report: dict[str, Any] = {
            "enabled": False,
            "actions": [],
            "reason": "postprocessing_disabled",
        }
        if self.postprocessing_enabled:
            try:
                postprocessed = self.postprocessor.process_structured_data(
                    structured_data,
                    routing_plan=routing_plan,
                    preprocessing=preprocessing_result,
                )
                structured_data = postprocessed.get("structured_data", structured_data)
                postprocess_report = postprocessed.get("report", postprocess_report)
            except Exception as exc:
                postprocess_report = {
                    "enabled": True,
                    "actions": ["postprocess_failed"],
                    "error": str(exc),
                }

        detail_groups = self._build_detail_groups(structured_data)
        structured_data = dict(structured_data)
        structured_data["detail_groups"] = detail_groups
        structured_data["preprocessing"] = preprocessing_result
        structured_data["routing"] = routing_plan
        structured_data["prompting"] = detail_prompt_plan
        structured_data["postprocessing"] = postprocess_report

        canonical_data = self.canonical_transformer.transform(structured_data, effective_document)
        canonical_data["detail_groups"] = detail_groups
        canonical_data["preprocessing"] = preprocessing_result
        canonical_data["routing"] = routing_plan
        canonical_data["prompting"] = detail_prompt_plan
        canonical_data["postprocessing"] = postprocess_report

        response = {
            "model": self.detail_model_type,
            "detail_model": self.detail_model_type,
            "summary_model": self.summary_model_type,
            "router_model": self.router_model,
            "models": {
                "router": self.router_model,
                "detail": self.detail_model_type,
                "summary": self.summary_model_type,
            },
            "structured_data": structured_data,
            "canonical_data": canonical_data,
            "detail_groups": detail_groups,
            "preprocessing": preprocessing_result,
            "routing": routing_plan,
            "prompting": detail_prompt_plan,
            "postprocessing": postprocess_report,
            "timestamp": datetime.now().isoformat(),
            "extraction_method": "detail_rule_based_local",
        }
        warnings = self._build_model_warnings()
        if warnings:
            response["warnings"] = warnings
        return response

    def build_summary(
        self,
        structured_data: dict[str, Any],
        canonical_data: dict[str, Any],
        validation_result: dict[str, Any] | None = None,
        routing_plan: dict[str, Any] | None = None,
        preprocessing_result: dict[str, Any] | None = None,
        prompt_plan: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        routing_plan = routing_plan if isinstance(routing_plan, dict) else {}
        preprocessing_result = preprocessing_result if isinstance(preprocessing_result, dict) else {}
        summary_prompt_plan = (
            self.prompt_registry.build_summary_prompt_plan(
                structured_data,
                canonical_data,
                routing_plan,
                preprocessing=preprocessing_result,
            )
            if self.prompt_optimization_enabled
            else self._disabled_prompt_plan("summary")
        )
        combined_prompt_plan = self._merge_prompt_plans(prompt_plan, summary_prompt_plan)
        document_summary = self._build_document_summary(structured_data, canonical_data, validation_result)
        if self.postprocessing_enabled:
            document_summary = self.postprocessor.finalize_document_summary(
                document_summary,
                structured_data,
                validation_result=validation_result,
                routing_plan=routing_plan,
                prompt_plan=combined_prompt_plan,
            )
        else:
            document_summary = dict(document_summary)
            document_summary.setdefault("routing_profile", routing_plan.get("prompt_profile", ""))
            document_summary.setdefault("combination_mode", routing_plan.get("combination_mode", ""))
            document_summary.setdefault("preprocess_profile", routing_plan.get("preprocess_profile", ""))
            document_summary.setdefault("postprocess_profile", routing_plan.get("postprocess_profile", ""))
            document_summary.setdefault("prompt_version", self.prompt_registry.prompt_version)

        response = {
            "model": self.summary_model_type,
            "document_summary": document_summary,
            "prompting": combined_prompt_plan,
            "timestamp": datetime.now().isoformat(),
            "generation_method": "summary_rule_based_local",
        }
        warnings = self._build_model_warnings()
        if warnings:
            response["warnings"] = warnings
        return response

    def build_structured_result(
        self,
        structured_data: dict[str, Any],
        canonical_data: dict[str, Any],
        validation_result: dict[str, Any] | None = None,
        extraction_method: str = "detail_rule_based_local",
        timestamp: str | None = None,
        preprocessing_result: dict[str, Any] | None = None,
        routing_plan: dict[str, Any] | None = None,
        prompt_plan: dict[str, Any] | None = None,
        postprocess_report: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        enriched_structured = dict(structured_data) if isinstance(structured_data, dict) else {}
        detail_groups = enriched_structured.get("detail_groups")
        if not isinstance(detail_groups, dict) or not isinstance(detail_groups.get("groups"), list):
            detail_groups = self._build_detail_groups(enriched_structured)
        enriched_structured["detail_groups"] = detail_groups

        document_context = self._document_from_structured_data(enriched_structured)
        preprocessing_result = (
            preprocessing_result
            if isinstance(preprocessing_result, dict) and preprocessing_result
            else self._default_preprocessing_result(document_context)
        )
        routing_plan = (
            routing_plan
            if isinstance(routing_plan, dict) and routing_plan
            else self._build_routing_plan(
                structured_hint=enriched_structured,
                preprocessing_result=preprocessing_result,
                document=document_context,
                operation_mode=(
                    "structured_to_natural"
                    if extraction_method == "structured_input_normalization"
                    else "natural_to_structured"
                ),
            )
        )
        prompt_plan = prompt_plan if isinstance(prompt_plan, dict) else {}
        postprocess_report = postprocess_report if isinstance(postprocess_report, dict) else {}

        enriched_structured["preprocessing"] = preprocessing_result
        enriched_structured["routing"] = routing_plan
        enriched_structured["prompting"] = prompt_plan
        enriched_structured["postprocessing"] = postprocess_report

        enriched_canonical = dict(canonical_data) if isinstance(canonical_data, dict) else {}
        if not enriched_canonical:
            enriched_canonical = self.canonical_transformer.transform(enriched_structured, document_context)
        enriched_canonical["detail_groups"] = detail_groups
        enriched_canonical["preprocessing"] = preprocessing_result
        enriched_canonical["routing"] = routing_plan
        enriched_canonical["prompting"] = prompt_plan
        enriched_canonical["postprocessing"] = postprocess_report

        summary_result = self.build_summary(
            enriched_structured,
            enriched_canonical,
            validation_result,
            routing_plan=routing_plan,
            preprocessing_result=preprocessing_result,
            prompt_plan=prompt_plan,
        )
        document_summary = summary_result.get("document_summary", {})
        combined_prompt_plan = summary_result.get("prompting", {})
        enriched_structured["document_summary"] = document_summary
        enriched_structured["prompting"] = combined_prompt_plan
        enriched_canonical["document_summary"] = document_summary
        enriched_canonical["prompting"] = combined_prompt_plan

        response = {
            "model": self.detail_model_type,
            "detail_model": self.detail_model_type,
            "summary_model": self.summary_model_type,
            "router_model": self.router_model,
            "models": {
                "router": self.router_model,
                "detail": self.detail_model_type,
                "summary": self.summary_model_type,
            },
            "structured_data": enriched_structured,
            "canonical_data": enriched_canonical,
            "document_summary": document_summary,
            "detail_groups": detail_groups,
            "preprocessing": preprocessing_result,
            "routing": routing_plan,
            "prompting": combined_prompt_plan,
            "postprocessing": postprocess_report,
            "timestamp": timestamp or summary_result.get("timestamp") or datetime.now().isoformat(),
            "extraction_method": extraction_method,
        }
        warnings = self._build_model_warnings()
        if warnings:
            response["warnings"] = warnings
        return response

    def _default_preprocessing_result(self, document: dict[str, Any]) -> dict[str, Any]:
        text = str(document.get("content", "") or "")
        tables = document.get("tables", []) if isinstance(document.get("tables"), list) else []
        blocks = document.get("blocks", []) if isinstance(document.get("blocks"), list) else []
        lines = [line for line in text.splitlines() if line.strip()]
        chunks = []
        if text.strip():
            chunks.append(
                {
                    "chunk_id": "raw_chunk_1",
                    "section_title": "全文",
                    "char_count": len(text),
                    "text_preview": text[:320],
                    "source_anchor": {},
                }
            )
        return {
            "clean_document": document,
            "stats": {
                "char_count": len(text),
                "line_count": len(lines),
                "table_count": len(tables),
                "block_count": len(blocks),
                "heading_count": 0,
                "section_count": 0,
                "chunk_count": len(chunks),
            },
            "signals": {
                "has_tables": bool(tables),
                "has_ocr_text": bool(str(document.get("ocr_text", "") or "").strip()),
                "has_headings": False,
                "domain_candidates": ["general"],
                "section_titles": [],
                "measurement_candidates": [],
                "source_type": document.get("type", "unknown"),
            },
            "chunks": chunks,
        }

    def _document_from_structured_data(self, structured_data: dict[str, Any]) -> dict[str, Any]:
        sections = structured_data.get("sections", []) if isinstance(structured_data.get("sections"), list) else []
        lines = []
        for section in sections[:12]:
            title = str(section.get("title") or "").strip()
            content = str(section.get("content") or "").strip()
            if title and content:
                lines.append(f"{title}\n{content}")
            elif content:
                lines.append(content)
        if not lines:
            for key, value in (structured_data.get("fields", {}) or structured_data.get("key_values", {})).items():
                lines.append(f"{key}: {value}")
        content = "\n\n".join(lines).strip() or str(structured_data.get("content_excerpt", "") or "")
        return {
            "type": structured_data.get("source_type", "structured"),
            "content": content,
            "tables": structured_data.get("datasets", []) if isinstance(structured_data.get("datasets"), list) else [],
            "blocks": [],
            "metadata": {
                "title": structured_data.get("title", ""),
                "region": structured_data.get("region"),
                "year": structured_data.get("year"),
            },
            "ocr_text": "",
            "json_data": None,
        }

    def _build_routing_plan(
        self,
        structured_hint: dict[str, Any],
        preprocessing_result: dict[str, Any],
        document: dict[str, Any],
        operation_mode: str,
    ) -> dict[str, Any]:
        source_document = document if isinstance(document, dict) and document else self._document_from_structured_data(structured_hint)
        preprocessing_result = preprocessing_result if isinstance(preprocessing_result, dict) else {}
        if not preprocessing_result:
            preprocessing_result = self._default_preprocessing_result(source_document)
        return self.model_router.route(
            source_document,
            preprocessing_result,
            structured_hint=structured_hint or None,
            operation_mode=operation_mode,
        )

    def _disabled_prompt_plan(self, stage: str) -> dict[str, Any]:
        return {
            stage: {
                "enabled": False,
                "version": self.prompt_registry.prompt_version,
                "reason": "prompt_optimization_disabled",
            }
        }

    def _merge_prompt_plans(self, *plans: dict[str, Any] | None) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for plan in plans:
            if not isinstance(plan, dict):
                continue
            for key, value in plan.items():
                merged[key] = value
        return merged

    def _normalize_document(self, content: Any) -> dict[str, Any]:
        if isinstance(content, dict):
            return {
                "type": content.get("type", "text"),
                "content": str(content.get("content", "") or ""),
                "tables": content.get("tables", []) or [],
                "blocks": content.get("blocks", []) or [],
                "metadata": content.get("metadata", {}) or {},
                "ocr_text": str(content.get("ocr_text", "") or ""),
                "json_data": content.get("json_data"),
            }
        if isinstance(content, str):
            return {
                "type": "text",
                "content": content,
                "tables": [],
                "blocks": [],
                "metadata": {},
                "ocr_text": "",
                "json_data": None,
            }
        return {
            "type": "text",
            "content": json.dumps(content, ensure_ascii=False, default=str),
            "tables": [],
            "blocks": [],
            "metadata": {},
            "ocr_text": "",
            "json_data": None,
        }

    def _extract_local(self, document: dict[str, Any]) -> dict[str, Any]:
        tables = document.get("tables", [])
        text = self._compose_text(document)
        title = document.get("metadata", {}).get("title") or self._infer_title(text)
        region, year = self._infer_region_and_year(title)

        if tables:
            datasets = [self._normalize_dataset(table) for table in tables]
            datasets = [dataset for dataset in datasets if dataset["row_count"] > 0]
            schema = sorted({header for dataset in datasets for header in dataset["headers"]})
            record_count = sum(dataset["row_count"] for dataset in datasets)
            domain_tags = self._infer_domain_tags(title, text, schema=schema)
            return {
                "document_type": "tabular_dataset",
                "title": title,
                "source_type": document.get("type", "unknown"),
                "dataset_count": len(datasets),
                "record_count": record_count,
                "schema": schema,
                "domain_tags": domain_tags,
                "datasets": datasets,
            }

        key_values = self._extract_key_values(text)
        fields = self._extract_standard_fields(text, key_values)
        dates = self._deduplicate(self._extract_dates(text))
        publish_date = dates[0] if dates else None
        sections = self._extract_sections(document, text)
        indicators = self._extract_indicators(sections, text)
        entities = self._extract_entities(text)
        domain_tags = self._infer_domain_tags(
            title,
            text,
            schema=[*key_values.keys(), *fields.keys()],
        )
        numeric_density = len(re.findall(r"\d", text))
        is_report_like = (len(sections) >= 2 and len(indicators) >= 3) or (len(indicators) >= 5 and numeric_density >= 20)

        if is_report_like:
            report_records = self._merge_record_groups(
                self._build_report_records(
                    sections=sections,
                    text=text,
                    title=title,
                    region=region,
                    year=year,
                    publish_date=publish_date,
                ),
                self._build_key_value_records(
                    key_values={**key_values, **fields},
                    title=title,
                    region=region,
                    year=year,
                    publish_date=publish_date,
                ),
            )
            fields = dict(fields)
            if publish_date and "date" not in fields:
                fields["date"] = publish_date
            return {
                "document_type": "report_document",
                "title": title,
                "source_type": document.get("type", "unknown"),
                "region": region,
                "year": year,
                "publish_date": publish_date,
                "domain_tags": domain_tags,
                "fields": fields,
                "key_values": key_values,
                "dates": dates,
                "sections": sections,
                "record_count": len(report_records),
                "schema": list(report_records[0].keys()) if report_records else [],
                "records": report_records,
                "indicators": indicators,
                "metrics": self._metrics_from_indicators(indicators),
                "entities": entities,
                "summary": {
                    "section_count": len(sections),
                    "metric_count": len(indicators),
                    "record_count": len(report_records),
                },
            }

        generic_records = self._build_generic_records(
            sections=sections,
            text=text,
            key_values={**key_values, **fields},
            title=title,
            region=region,
            year=year,
            publish_date=publish_date,
        )

        if key_values or fields or generic_records:
            return {
                "document_type": "key_value_document" if (key_values or fields) else "plain_text_document",
                "title": title,
                "source_type": document.get("type", "unknown"),
                "region": region,
                "year": year,
                "publish_date": publish_date,
                "domain_tags": domain_tags,
                "fields": fields,
                "key_values": key_values,
                "dates": dates,
                "sections": sections[:20],
                "record_count": len(generic_records),
                "schema": list(generic_records[0].keys()) if generic_records else [],
                "records": generic_records,
                "entities": entities,
                "summary": {
                    "field_count": len(fields),
                    "key_value_count": len(key_values),
                    "record_count": len(generic_records),
                },
                "content_excerpt": text[:2000],
            }

        return {
            "document_type": "plain_text_document",
            "title": title,
            "source_type": document.get("type", "unknown"),
            "region": region,
            "year": year,
            "publish_date": publish_date,
            "domain_tags": domain_tags,
            "dates": dates,
            "record_count": 0,
            "schema": [],
            "records": [],
            "entities": entities,
            "content_excerpt": text[:2000],
        }

    def _build_model_warnings(self) -> list[str]:
        warnings = []
        if self.router_model != "local_router":
            warnings.append("模型路由当前仍走本地启发式策略，请在后续接入真实路由模型调用。")
        if self.detail_model_type != "local":
            warnings.append("明细抽取当前仍走本地规则流程，请在后续接入真实明细模型调用。")
        if self.summary_model_type != "local":
            warnings.append("摘要生成当前仍走本地规则流程，请在后续接入真实摘要模型调用。")
        return warnings

    def _build_detail_groups(self, structured_data: dict[str, Any]) -> dict[str, Any]:
        document_type = structured_data.get("document_type", "unknown")
        if document_type == "tabular_dataset":
            return self._build_tabular_detail_groups(structured_data)
        return self._build_textual_detail_groups(structured_data)

    def _build_tabular_detail_groups(self, structured_data: dict[str, Any]) -> dict[str, Any]:
        datasets = structured_data.get("datasets", []) if isinstance(structured_data.get("datasets"), list) else []
        groups = []
        for index, dataset in enumerate(datasets, start=1):
            dataset_name = str(dataset.get("name") or f"dataset_{index}").strip() or f"dataset_{index}"
            row_count = int(dataset.get("row_count", len(dataset.get("records", []))) or 0)
            groups.append(
                self._detail_group_entry(
                    sheet_name=f"table_{index:02d}_{dataset_name}",
                    sheet_category="dataset",
                    group_value=dataset_name,
                    source_kind="dataset",
                    record_count=row_count,
                    dataset_name=dataset_name,
                    description=f"数据表 {dataset_name}，共 {row_count} 条记录。",
                )
            )

        return {
            "grouping_strategy": ["dataset"],
            "group_count": len(groups),
            "primary_sheet": groups[0]["sheet_name"] if groups else "",
            "groups": groups,
        }

    def _build_textual_detail_groups(self, structured_data: dict[str, Any]) -> dict[str, Any]:
        records = structured_data.get("records", []) if isinstance(structured_data.get("records"), list) else []
        indicators = structured_data.get("indicators", []) if isinstance(structured_data.get("indicators"), list) else []
        groups = []

        measurement_records = [record for record in records if record.get("record_type") == "measurement"]
        attribute_records = [record for record in records if record.get("record_type") != "measurement"]
        metric_type_map = {
            "value": "metric_value",
            "ratio": "metric_ratio",
            "growth_rate": "metric_growth",
            "change_value": "metric_change",
            "attribute": "metric_attribute",
            "date": "metric_date",
        }

        if measurement_records:
            groups.append(
                self._detail_group_entry(
                    sheet_name="metrics_all",
                    sheet_category="record_type",
                    group_value="measurement",
                    source_kind="records",
                    record_count=len(measurement_records),
                    record_ids=self._record_ids(measurement_records),
                    description="全部度量型明细记录。",
                )
            )
        if attribute_records:
            groups.append(
                self._detail_group_entry(
                    sheet_name="attributes",
                    sheet_category="record_type",
                    group_value="attribute",
                    source_kind="records",
                    record_count=len(attribute_records),
                    record_ids=self._record_ids(attribute_records),
                    description="全部属性型与字段型记录。",
                )
            )

        for metric_type, sheet_name in metric_type_map.items():
            grouped_records = [record for record in records if record.get("metric_type") == metric_type]
            if not grouped_records:
                continue
            groups.append(
                self._detail_group_entry(
                    sheet_name=sheet_name,
                    sheet_category="metric_type",
                    group_value=metric_type,
                    source_kind="records",
                    record_count=len(grouped_records),
                    record_ids=self._record_ids(grouped_records),
                    description=f"按指标类型归类: {metric_type}。",
                )
            )

        section_map: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            section_title = str(record.get("section") or "未分组").strip() or "未分组"
            section_map.setdefault(section_title, []).append(record)
        for index, (section_title, section_records) in enumerate(section_map.items(), start=1):
            groups.append(
                self._detail_group_entry(
                    sheet_name=f"sec_{index:02d}_{section_title}",
                    sheet_category="section",
                    group_value=section_title,
                    source_kind="records",
                    record_count=len(section_records),
                    record_ids=self._record_ids(section_records),
                    description=f"章节 {section_title} 的明细记录。",
                )
            )

        if not groups and indicators:
            groups.append(
                self._detail_group_entry(
                    sheet_name="indicator_details",
                    sheet_category="indicator",
                    group_value="all",
                    source_kind="indicators",
                    record_count=len(indicators),
                    description="全部指标明细。",
                )
            )

        return {
            "grouping_strategy": ["record_type", "metric_type", "section"],
            "group_count": len(groups),
            "primary_sheet": groups[0]["sheet_name"] if groups else "",
            "groups": groups,
        }

    def _detail_group_entry(
        self,
        sheet_name: str,
        sheet_category: str,
        group_value: str,
        source_kind: str,
        record_count: int,
        description: str,
        record_ids: list[str] | None = None,
        dataset_name: str | None = None,
    ) -> dict[str, Any]:
        entry = {
            "sheet_name": sheet_name,
            "sheet_category": sheet_category,
            "group_value": group_value,
            "source_kind": source_kind,
            "record_count": record_count,
            "description": description,
        }
        if record_ids:
            entry["record_ids"] = record_ids
        if dataset_name:
            entry["dataset_name"] = dataset_name
        return entry

    def _record_ids(self, records: list[dict[str, Any]]) -> list[str]:
        record_ids = []
        for record in records:
            record_id = str(record.get("record_id") or "").strip()
            if record_id:
                record_ids.append(record_id)
        return record_ids

    def _build_document_summary(
        self,
        structured_data: dict[str, Any],
        canonical_data: dict[str, Any],
        validation_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        document_meta = canonical_data.get("document_meta", {}) if isinstance(canonical_data.get("document_meta"), dict) else {}
        detail_groups = structured_data.get("detail_groups") if isinstance(structured_data.get("detail_groups"), dict) else {}
        detail_group_list = detail_groups.get("groups", []) if isinstance(detail_groups.get("groups"), list) else []
        domain_tags = structured_data.get("domain_tags") or document_meta.get("domain_tags") or canonical_data.get("domains", []) or []
        validation_issues = validation_result.get("issues", []) if isinstance(validation_result, dict) else []
        is_valid = validation_result.get("is_valid") if isinstance(validation_result, dict) else None
        validation_status = "unknown"
        if is_valid is True:
            validation_status = "passed"
        elif is_valid is False:
            validation_status = "needs_attention"

        return {
            "title": document_meta.get("title") or structured_data.get("title") or "未命名文档",
            "document_type": structured_data.get("document_type", document_meta.get("document_type", "unknown")),
            "source_type": structured_data.get("source_type") or document_meta.get("source_type", "unknown"),
            "region": document_meta.get("region") or structured_data.get("region"),
            "year": document_meta.get("year") or structured_data.get("year"),
            "publish_date": document_meta.get("publish_date") or structured_data.get("publish_date"),
            "domain_tags": domain_tags,
            "overall_summary": self._compose_overall_summary(structured_data, canonical_data, validation_result),
            "key_findings": self._build_key_findings(structured_data),
            "validation_status": validation_status,
            "validation_issue_count": len(validation_issues),
            "validation_issues": validation_issues[:10],
            "record_count": structured_data.get("record_count", len(structured_data.get("records", []))),
            "indicator_count": len(structured_data.get("indicators", [])) if isinstance(structured_data.get("indicators"), list) else 0,
            "section_count": len(structured_data.get("sections", [])) if isinstance(structured_data.get("sections"), list) else 0,
            "dataset_count": structured_data.get("dataset_count", len(structured_data.get("datasets", []))) if isinstance(structured_data.get("datasets"), list) else structured_data.get("dataset_count", 0),
            "detail_sheet_count": len(detail_group_list),
            "detail_sheet_names": [group.get("sheet_name") for group in detail_group_list[:20]],
            "router_model": self.router_model,
            "summary_model": self.summary_model_type,
            "detail_model": self.detail_model_type,
            "prompt_version": self.prompt_registry.prompt_version,
            "generated_at": datetime.now().isoformat(),
        }

    def _compose_overall_summary(
        self,
        structured_data: dict[str, Any],
        canonical_data: dict[str, Any],
        validation_result: dict[str, Any] | None = None,
    ) -> str:
        document_meta = canonical_data.get("document_meta", {}) if isinstance(canonical_data.get("document_meta"), dict) else {}
        title = document_meta.get("title") or structured_data.get("title") or "未命名文档"
        document_type = structured_data.get("document_type", "unknown")
        record_count = structured_data.get("record_count", len(structured_data.get("records", [])))
        section_count = len(structured_data.get("sections", [])) if isinstance(structured_data.get("sections"), list) else 0
        indicator_count = len(structured_data.get("indicators", [])) if isinstance(structured_data.get("indicators"), list) else 0
        dataset_count = structured_data.get("dataset_count", len(structured_data.get("datasets", []))) if isinstance(structured_data.get("datasets"), list) else structured_data.get("dataset_count", 0)
        detail_groups = structured_data.get("detail_groups", {}) if isinstance(structured_data.get("detail_groups"), dict) else {}
        detail_sheet_count = len(detail_groups.get("groups", [])) if isinstance(detail_groups.get("groups"), list) else 0
        domain_tags = structured_data.get("domain_tags") or document_meta.get("domain_tags") or canonical_data.get("domains", []) or []

        if document_type == "tabular_dataset":
            summary = f"《{title}》已整理为 {dataset_count} 个数据子表，共 {record_count} 条记录，并生成 {detail_sheet_count} 个明细 sheet。"
        elif document_type == "report_document":
            summary = f"《{title}》已拆解为 {section_count} 个章节、{indicator_count} 项指标和 {record_count} 条明细记录，并归类生成 {detail_sheet_count} 个子表。"
        elif document_type == "key_value_document":
            field_count = len(structured_data.get("fields", {}) or structured_data.get("key_values", {}))
            summary = f"《{title}》已提炼出 {field_count} 个字段和 {record_count} 条结构化记录，并归类生成 {detail_sheet_count} 个子表。"
        else:
            summary = f"《{title}》已转换为结构化结果，共 {record_count} 条记录，并归类生成 {detail_sheet_count} 个子表。"

        if domain_tags:
            summary += f" 主题领域包括 {', '.join(str(tag) for tag in domain_tags[:3])}。"
        if isinstance(validation_result, dict):
            if validation_result.get("is_valid"):
                summary += " 当前校验通过。"
            elif validation_result.get("issues"):
                summary += f" 当前有 {len(validation_result.get('issues', []))} 项待关注问题。"
        return summary

    def _build_key_findings(self, structured_data: dict[str, Any]) -> list[str]:
        findings: list[str] = []
        document_type = structured_data.get("document_type")

        if document_type == "tabular_dataset":
            datasets = structured_data.get("datasets", []) if isinstance(structured_data.get("datasets"), list) else []
            for dataset in datasets[:5]:
                headers = dataset.get("headers", []) if isinstance(dataset.get("headers"), list) else []
                header_preview = "、".join(str(header) for header in headers[:6])
                findings.append(
                    f"数据表 {dataset.get('name', 'dataset')} 共 {dataset.get('row_count', 0)} 条记录，核心字段: {header_preview}".rstrip(": ")
                )

        records = structured_data.get("records", []) if isinstance(structured_data.get("records"), list) else []
        measurement_records = [record for record in records if record.get("record_type") == "measurement"]
        for record in (measurement_records or records)[:5]:
            findings.append(self._render_record_finding(record))

        if not findings:
            fields = structured_data.get("fields", {}) if isinstance(structured_data.get("fields"), dict) else {}
            key_values = structured_data.get("key_values", {}) if isinstance(structured_data.get("key_values"), dict) else {}
            merged_mapping = {**key_values, **fields}
            for index, (key, value) in enumerate(merged_mapping.items()):
                findings.append(f"{key}: {value}")
                if index >= 4:
                    break

        deduplicated: list[str] = []
        for item in findings:
            text = str(item or "").strip()
            if text and text not in deduplicated:
                deduplicated.append(text)
        return deduplicated[:8]

    def _render_record_finding(self, record: dict[str, Any]) -> str:
        name = str(record.get("indicator_name") or "相关指标").strip() or "相关指标"
        value_text = str(record.get("value_text") or "").strip()
        value = record.get("value")
        unit = str(record.get("unit") or "").strip()
        time_reference = str(record.get("time_reference") or "").strip()
        section = str(record.get("section") or "").strip()
        comparison_text = str(record.get("comparison_text") or "").strip()
        yoy_percent = record.get("yoy_percent")

        if value_text:
            display_value = value_text
        elif value is not None:
            display_value = f"{self._format_number(value)}{unit}"
        else:
            display_value = ""

        prefix_parts = []
        if section and section != "字段":
            prefix_parts.append(section)
        if time_reference:
            prefix_parts.append(time_reference)
        prefix = " / ".join(prefix_parts)
        statement = f"{name}: {display_value}" if display_value else name
        if yoy_percent is not None:
            direction = "增长" if float(yoy_percent) >= 0 else "下降"
            statement += f"，同比{direction} {self._format_number(abs(float(yoy_percent)))}%"
        elif comparison_text:
            statement += f"，{comparison_text}"
        if prefix:
            return f"{prefix} - {statement}"
        return statement

    def _format_number(self, value: Any) -> str:
        if isinstance(value, float):
            if value.is_integer():
                return str(int(value))
            return f"{value:.4f}".rstrip("0").rstrip(".")
        return str(value)

    def _normalize_dataset(self, table: dict[str, Any]) -> dict[str, Any]:
        headers = [str(header).strip() for header in table.get("headers", []) if str(header).strip()]
        records = []
        null_value_count = 0

        for raw_record in table.get("records", []):
            normalized_record = {}
            for header in headers:
                value = self._coerce_value(raw_record.get(header))
                if value is None:
                    null_value_count += 1
                normalized_record[header] = value
            if any(value is not None for value in normalized_record.values()):
                records.append(normalized_record)

        return {
            "name": table.get("name", "table"),
            "headers": headers,
            "row_count": len(records),
            "column_count": len(headers),
            "null_value_count": null_value_count,
            "records": records,
            "source_anchor": table.get("source_anchor", {}),
            "record_sources": table.get("record_sources", []) or [],
        }

    def _extract_key_values(self, text: str) -> dict[str, Any]:
        pairs: dict[str, Any] = {}
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            match = KEY_VALUE_PATTERN.match(stripped)
            if match:
                key = match.group(1).strip()
                value = match.group(2).strip()
                if key and value:
                    pairs[key] = value
                    continue

            if "\t" in stripped:
                columns = [part.strip() for part in stripped.split("\t") if part.strip()]
                if len(columns) == 2:
                    pairs[columns[0]] = columns[1]

        try:
            json_payload = json.loads(text)
            if isinstance(json_payload, dict):
                for key, value in json_payload.items():
                    pairs.setdefault(str(key), value)
        except Exception:
            pass

        return pairs

    def _extract_standard_fields(self, text: str, key_values: dict[str, Any]) -> dict[str, Any]:
        fields: dict[str, Any] = {}
        lowered_key_values = {str(key).strip().lower(): value for key, value in key_values.items()}

        for standard_field, aliases in STANDARD_FIELD_ALIASES.items():
            for alias in aliases:
                if alias.lower() in lowered_key_values:
                    fields[standard_field] = self._coerce_value(lowered_key_values[alias.lower()])
                    break

        if "phone" not in fields:
            phone_matches = PHONE_PATTERN.findall(text)
            if phone_matches:
                fields["phone"] = phone_matches[0]

        if "email" not in fields:
            email_matches = EMAIL_PATTERN.findall(text)
            if email_matches:
                fields["email"] = email_matches[0].lower()

        if "date" not in fields:
            dates = self._extract_dates(text)
            if dates:
                fields["date"] = dates[0]

        if "id_number" not in fields:
            id_match = ID_PATTERN.search(text)
            if id_match:
                fields["id_number"] = id_match.group(0)

        if "amount" not in fields:
            amount_match = re.search(r"金额[:：]?\s*([\d.,]+)", text)
            if amount_match:
                fields["amount"] = amount_match.group(1)

        return fields

    def _extract_dates(self, text: str) -> list[str]:
        return [match.group(0) for match in DATE_PATTERN.finditer(text)]

    def _infer_domain_tags(
        self,
        title: str,
        text: str,
        schema: list[str] | None = None,
    ) -> list[str]:
        corpus_parts = [title or "", text or ""]
        if schema:
            corpus_parts.extend(str(item) for item in schema if str(item).strip())
        corpus = " ".join(corpus_parts).lower()
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

    def _extract_sections(self, document: dict[str, Any], text: str) -> list[dict[str, Any]]:
        blocks = document.get("blocks", []) if isinstance(document.get("blocks"), list) else []
        if not blocks:
            blocks = [
                {
                    "id": f"line_{index}",
                    "type": "paragraph",
                    "text": line,
                    "source_anchor": {"line_index": index},
                }
                for index, line in enumerate(text.splitlines(), start=1)
                if line.strip()
            ]

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
                        "id": f"sec_{len(sections) + 1}",
                        "title": current_title,
                        "content": content,
                        "source_anchor": current_anchor,
                    }
                )
                current_lines = []

        for block in blocks:
            block_text = str(block.get("text", "")).strip()
            if not block_text:
                continue
            if self._is_heading_block(block):
                flush_section()
                current_title = block_text
                current_anchor = block.get("source_anchor", {}) if isinstance(block.get("source_anchor"), dict) else {}
            else:
                current_lines.append(block_text)

        flush_section()
        return sections

    def _extract_indicators(self, sections: list[dict[str, Any]], full_text: str) -> list[dict[str, Any]]:
        if not sections and full_text.strip():
            sections = [
                {
                    "id": "sec_1",
                    "title": "全文",
                    "content": full_text,
                    "source_anchor": {},
                }
            ]

        indicators = []
        for section in sections:
            sentences = self._split_sentences(section.get("content", ""))
            for sentence_index, sentence in enumerate(sentences, start=1):
                stripped = sentence.strip()
                if not stripped or len(stripped) < 6 or not re.search(r"\d", stripped):
                    continue
                if DATE_PATTERN.fullmatch(stripped):
                    continue

                measurements = self._extract_measurements(stripped)
                if not measurements:
                    continue

                primary_measurement = measurements[0]
                indicator_name = self._extract_indicator_name(stripped, primary_measurement["start"])
                yoy_value, comparison_text = self._extract_yoy(stripped)
                indicator = {
                    "id": f"ind_{len(indicators) + 1}",
                    "section_id": section.get("id"),
                    "section_title": section.get("title"),
                    "name": indicator_name,
                    "value": primary_measurement["value"],
                    "unit": primary_measurement["unit"],
                    "yoy": yoy_value,
                    "statement": stripped[:240],
                    "comparison_text": comparison_text,
                    "values": [
                        {"value": item["value"], "unit": item["unit"]}
                        for item in measurements[:5]
                    ],
                    "source_anchor": {
                        **(section.get("source_anchor", {}) if isinstance(section.get("source_anchor"), dict) else {}),
                        "sentence_index": sentence_index,
                    },
                }
                indicators.append(indicator)

        return self._deduplicate_indicators(indicators)

    def _build_report_records(
        self,
        sections: list[dict[str, Any]],
        text: str,
        title: str,
        region: str | None,
        year: int | None,
        publish_date: str | None,
    ) -> list[dict[str, Any]]:
        skip_titles = {"引言"} if any(section.get("title") != "引言" for section in sections) else set()
        return self._build_measurement_records(
            sections=sections,
            text=text,
            title=title,
            region=region,
            year=year,
            publish_date=publish_date,
            skip_section_titles=skip_titles,
        )

    def _build_generic_records(
        self,
        sections: list[dict[str, Any]],
        text: str,
        key_values: dict[str, Any],
        title: str,
        region: str | None,
        year: int | None,
        publish_date: str | None,
    ) -> list[dict[str, Any]]:
        return self._merge_record_groups(
            self._build_key_value_records(
                key_values=key_values,
                title=title,
                region=region,
                year=year,
                publish_date=publish_date,
            ),
            self._build_measurement_records(
                sections=sections,
                text=text,
                title=title,
                region=region,
                year=year,
                publish_date=publish_date,
                skip_section_titles=set(),
            ),
        )

    def _build_key_value_records(
        self,
        key_values: dict[str, Any],
        title: str,
        region: str | None,
        year: int | None,
        publish_date: str | None,
    ) -> list[dict[str, Any]]:
        records = []
        for index, (key, value) in enumerate(key_values.items(), start=1):
            key_text = str(key).strip()
            value_text = "" if value is None else str(value).strip()
            if not key_text or not value_text:
                continue
            if any(keyword in key_text for keyword in NOISE_KEYWORDS):
                continue
            if "资料来源" in key_text or len(value_text) > 200:
                continue

            metric_type = "attribute"
            normalized_value = self._coerce_value(value)
            unit = None
            if DATE_PATTERN.fullmatch(value_text):
                metric_type = "date"
            elif re.search(r"\d", value_text):
                measurements = self._extract_measurements(value_text)
                if measurements:
                    primary_measurement = measurements[0]
                    normalized_value = primary_measurement["value"]
                    unit = primary_measurement["unit"]
                    metric_type = self._classify_metric_type(value_text, key_text, unit, None)

            records.append(
                {
                    "record_id": f"rec_{index}",
                    "record_type": "attribute",
                    "document_title": title,
                    "section": "字段",
                    "indicator_name": key_text,
                    "metric_type": metric_type,
                    "value": normalized_value,
                    "value_text": value_text,
                    "unit": unit,
                    "yoy_percent": None,
                    "comparison_value": None,
                    "comparison_unit": None,
                    "comparison_text": None,
                    "time_reference": self._resolve_time_reference(value_text, year, publish_date),
                    "location_reference": region,
                    "source_sentence": f"{key_text}: {value_text}",
                    "source_clause": f"{key_text}: {value_text}",
                    "paragraph_index": None,
                    "sentence_index": index,
                    "clause_index": 1,
                }
            )
        return self._deduplicate_records(records)

    def _build_measurement_records(
        self,
        sections: list[dict[str, Any]],
        text: str,
        title: str,
        region: str | None,
        year: int | None,
        publish_date: str | None,
        skip_section_titles: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        records = []
        skipped_titles = skip_section_titles or set()
        for section in self._record_sections(sections, text):
            if section.get("title") in skipped_titles:
                continue
            section_anchor = section.get("source_anchor", {}) if isinstance(section.get("source_anchor"), dict) else {}
            section_latest_record: dict[str, Any] | None = None
            section_latest_indicator_hint: str | None = None
            section_latest_indicator_source: str | None = None
            sentences = self._split_sentences(section.get("content", ""))
            for sentence_index, sentence in enumerate(sentences, start=1):
                if not re.search(r"\d", sentence):
                    sentence_indicator_hint = self._extract_context_indicator_hint(sentence)
                    if sentence_indicator_hint:
                        section_latest_indicator_hint = sentence_indicator_hint
                        section_latest_indicator_source = sentence.strip()
                sentence_record_start = len(records)
                for clause_index, clause in enumerate(self._split_record_clauses(sentence), start=1):
                    normalized_clause = self._clean_record_clause(clause)
                    if not normalized_clause or KEY_VALUE_PATTERN.match(normalized_clause):
                        continue
                    if not self._is_data_clause(normalized_clause):
                        continue
                    measurements = self._extract_measurements(normalized_clause)
                    if not measurements:
                        continue

                    primary_measurement = self._select_primary_measurement(normalized_clause, measurements)
                    if not primary_measurement:
                        continue
                    yoy_value, comparison_text = self._extract_yoy(normalized_clause)
                    context_record = records[-1] if len(records) > sentence_record_start else section_latest_record
                    if self._is_comparison_only_clause(normalized_clause) and context_record is not None:
                        if self._apply_comparison_continuation(
                            latest_record=context_record,
                            clause=normalized_clause,
                            sentence=sentence,
                            primary_measurement=primary_measurement,
                            comparison_text=comparison_text,
                            year=year,
                            publish_date=publish_date,
                        ):
                            section_latest_record = context_record
                            continue
                    if self._is_value_continuation_clause(normalized_clause) and context_record is not None:
                        if self._apply_value_continuation(
                            latest_record=context_record,
                            clause=normalized_clause,
                            sentence=sentence,
                            primary_measurement=primary_measurement,
                            year=year,
                            publish_date=publish_date,
                        ):
                            section_latest_record = context_record
                            continue

                    inherited_indicator_name = None
                    source_sentence_text = sentence.strip()
                    if context_record is None and section_latest_indicator_hint:
                        if self._is_comparison_only_clause(normalized_clause) or self._is_value_continuation_clause(normalized_clause):
                            inherited_indicator_name = section_latest_indicator_hint
                            source_sentence_text = self._merge_text_fragment(
                                section_latest_indicator_source,
                                sentence.strip(),
                                separator=" ",
                            )

                    indicator_name = self._extract_indicator_name(
                        normalized_clause,
                        primary_measurement["start"],
                    )
                    indicator_name = self._normalize_record_indicator_name(indicator_name, normalized_clause)
                    if not indicator_name and inherited_indicator_name:
                        indicator_name = inherited_indicator_name
                    if not indicator_name:
                        continue
                    is_comparison_measurement = self._is_comparison_measurement(
                        normalized_clause,
                        primary_measurement,
                    )
                    metric_type = self._classify_metric_type(
                        clause=normalized_clause,
                        indicator_name=indicator_name,
                        unit=primary_measurement["unit"],
                        comparison_text=comparison_text,
                        is_comparison_measurement=is_comparison_measurement,
                    )
                    records.append(
                        {
                            "record_id": f"rec_{len(records) + 1}",
                            "record_type": "measurement",
                            "document_title": title,
                            "section": section.get("title"),
                            "indicator_name": indicator_name,
                            "metric_type": metric_type,
                            "value": primary_measurement["value"],
                            "value_text": self._extract_value_text(normalized_clause, primary_measurement["start"]),
                            "unit": primary_measurement["unit"],
                            "yoy_percent": yoy_value if primary_measurement["unit"] == "%" else None,
                            "comparison_value": None,
                            "comparison_unit": None,
                            "comparison_text": comparison_text,
                            "time_reference": self._resolve_time_reference(sentence, year, publish_date),
                            "location_reference": region,
                            "source_sentence": source_sentence_text,
                            "source_clause": normalized_clause,
                            "paragraph_index": section_anchor.get("paragraph_index"),
                            "sentence_index": sentence_index,
                            "clause_index": clause_index,
                        }
                    )
                    section_latest_record = records[-1]
                    section_latest_indicator_hint = indicator_name
                    section_latest_indicator_source = source_sentence_text
        return self._deduplicate_records(records)

    def _record_sections(self, sections: list[dict[str, Any]], text: str) -> list[dict[str, Any]]:
        if sections:
            return sections
        if not text.strip():
            return []
        return [
            {
                "id": "sec_1",
                "title": "全文",
                "content": text,
                "source_anchor": {},
            }
        ]

    def _merge_record_groups(self, *record_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged = []
        for group in record_groups:
            if group:
                merged.extend(group)
        return self._renumber_records(self._deduplicate_records(merged))

    def _resolve_time_reference(
        self,
        text: str,
        year: int | None,
        publish_date: str | None,
    ) -> str | None:
        dates = self._extract_dates(text)
        if dates:
            return dates[0]
        if year is not None:
            return f"{year}年"
        return publish_date

    def _extract_measurements(self, sentence: str) -> list[dict[str, Any]]:
        measurements = []
        for match in NUMBER_UNIT_PATTERN.finditer(sentence):
            raw_value = self._coerce_value(match.group(1))
            unit = match.group(2).strip() or None
            if unit in {"年", "月", "日"}:
                continue
            if unit is None and match.start() <= 6:
                numeric_value = self._safe_float(raw_value)
                if numeric_value is not None and 1900 <= numeric_value <= 2100:
                    continue
            measurements.append(
                {
                    "value": raw_value,
                    "unit": unit,
                    "start": match.start(),
                    "end": match.end(),
                }
            )
        return measurements

    def _extract_indicator_name(self, sentence: str, first_measurement_start: int) -> str:
        prefix = sentence[:first_measurement_start].strip(" ，,:：")
        if not prefix:
            return "相关指标"

        match = re.search(r"(?:实现|完成|达到|达|为|有|拥有|共|形成|保持|新增|下降到|增长到|增至|减至)([^，,；;。]{1,32})$", prefix)
        if match:
            candidate = match.group(1)
        else:
            candidate = re.split(r"[，,；;：:]", prefix)[-1]

        candidate = re.sub(HEADING_PREFIX_CLEAN_PATTERN, "", candidate)
        candidate = re.sub(LEADING_INDICATOR_PREFIX_PATTERN, "", candidate)
        candidate = re.sub(TRAILING_INDICATOR_ACTION_PATTERN, "", candidate)
        candidate = candidate.strip(" ，,:：")
        if not candidate:
            return "相关指标"
        if len(candidate) > 32:
            candidate = candidate[-32:]
        return candidate

    def _extract_context_indicator_hint(self, sentence: str) -> str | None:
        cleaned = self._clean_record_clause(sentence)
        if not cleaned or re.search(r"\d", cleaned):
            return None
        cleaned = re.sub(HEADING_PREFIX_CLEAN_PATTERN, "", cleaned)
        cleaned = re.sub(LEADING_INDICATOR_PREFIX_PATTERN, "", cleaned)
        match = re.match(
            r"(.{2,32}?)(?:保持|实现|完成|达到|达|为|有|拥有|共|形成|新增|呈现|处于|维持|继续|持续|稳步|平稳|明显|显著|有所|加快|放缓|改善|回升|回落|下降|增长)",
            cleaned,
        )
        candidate = match.group(1) if match else cleaned
        candidate = self._normalize_record_indicator_name(candidate, cleaned)
        if not candidate:
            return None
        if len(candidate) > 24:
            return None
        return candidate

    def _normalize_record_indicator_name(self, indicator_name: str, clause: str) -> str:
        candidate = indicator_name.strip(" ，,:：")
        candidate = re.sub(HEADING_PREFIX_CLEAN_PATTERN, "", candidate)
        candidate = re.sub(LEADING_INDICATOR_PREFIX_PATTERN, "", candidate)
        candidate = re.sub(r"(?:同比|比上年|比去年|较上年|较去年).*$", "", candidate)
        candidate = re.sub(
            r"(?:增长|下降|提高|回落|增加|减少)\s*\d+(?:\.\d+)?\s*(?:%|个百分点)?(?:到|至)?$",
            "",
            candidate,
        )
        candidate = re.sub(TRAILING_INDICATOR_ACTION_PATTERN, "", candidate)
        candidate = re.sub(r"(?:增长|下降|提高|回落|增加|减少)$", "", candidate)
        candidate = candidate.strip(" ，,:：")
        if candidate in {"到", "达", "为"} or len(candidate) == 1:
            fallback_match = re.search(r"([^，,；;。]{1,32}?)(?:实现|完成|达到|达|为|有|拥有|共)(?=\d)", clause)
            if fallback_match:
                candidate = fallback_match.group(1).strip(" ，,:：")
            else:
                candidate = ""
        candidate = re.sub(HEADING_PREFIX_CLEAN_PATTERN, "", candidate)
        candidate = re.sub(LEADING_INDICATOR_PREFIX_PATTERN, "", candidate)
        candidate = re.sub(TRAILING_INDICATOR_ACTION_PATTERN, "", candidate)
        candidate = re.sub(r"(?:增长|下降|提高|回落|增加|减少)$", "", candidate)
        candidate = candidate.strip(" ，,:：")
        if candidate in {"图", "表", "相关指标"}:
            return ""
        if any(keyword in candidate for keyword in NOISE_KEYWORDS):
            return ""
        if not candidate:
            return ""
        if len(candidate) > 40:
            candidate = candidate[-40:]
        return candidate

    def _classify_metric_type(
        self,
        clause: str,
        indicator_name: str,
        unit: str | None,
        comparison_text: str | None,
        is_comparison_measurement: bool = False,
    ) -> str:
        if any(keyword in indicator_name for keyword in RATIO_KEYWORDS):
            return "ratio"
        if ("：" in clause or ":" in clause) and any(keyword in indicator_name for keyword in ("比例", "比重", "占比")):
            return "ratio"
        if unit in {"%", "‰"} and any(keyword in indicator_name for keyword in ("率", "比重", "占比", "比例")):
            return "ratio"
        if unit == "%" and (is_comparison_measurement or comparison_text or any(keyword in clause for keyword in GROWTH_KEYWORDS)):
            return "growth_rate"
        if is_comparison_measurement and comparison_text and unit and unit not in {"%", "‰"}:
            return "change_value"
        return "value"

    def _select_primary_measurement(
        self,
        clause: str,
        measurements: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not measurements:
            return None
        if any(keyword in clause for keyword in RATIO_KEYWORDS):
            ratio_measurement = next(
                (item for item in measurements if item.get("unit") in {"%", "‰"}),
                None,
            )
            if ratio_measurement is not None:
                return ratio_measurement

        yoy_match = YOY_PATTERN.search(clause)
        if not yoy_match:
            return measurements[0]

        yoy_span = yoy_match.span()
        for item in measurements:
            if not self._measurement_in_span(item, yoy_span) and item.get("unit") not in {"%", "‰"}:
                return item
        for item in measurements:
            if not self._measurement_in_span(item, yoy_span):
                return item
        return measurements[0]

    def _measurement_in_span(self, measurement: dict[str, Any], span: tuple[int, int]) -> bool:
        start = int(measurement.get("start", -1))
        end = int(measurement.get("end", -1))
        return start >= span[0] and end <= span[1]

    def _is_comparison_measurement(
        self,
        clause: str,
        measurement: dict[str, Any],
    ) -> bool:
        yoy_match = YOY_PATTERN.search(clause)
        if not yoy_match:
            return False
        return self._measurement_in_span(measurement, yoy_match.span())

    def _is_value_continuation_clause(self, clause: str) -> bool:
        normalized = clause.strip()
        return bool(
            re.match(
                r"^(?:实现|完成|达到|达|为|有|拥有|共|形成|保持|新增|下降到|增长到|增至|减至|总量(?:达|为)|总额(?:达|为)|总值(?:达|为))",
                normalized,
            )
        )

    def _apply_comparison_continuation(
        self,
        latest_record: dict[str, Any],
        clause: str,
        sentence: str,
        primary_measurement: dict[str, Any],
        comparison_text: str | None,
        year: int | None,
        publish_date: str | None,
    ) -> bool:
        if not isinstance(latest_record, dict) or latest_record.get("record_type") != "measurement":
            return False

        latest_record["comparison_text"] = self._merge_text_fragment(
            latest_record.get("comparison_text"),
            comparison_text or clause,
        )
        if primary_measurement.get("unit") == "%":
            latest_record["yoy_percent"] = primary_measurement.get("value")
        else:
            latest_record["comparison_value"] = primary_measurement.get("value")
            latest_record["comparison_unit"] = primary_measurement.get("unit")

        resolved_time = self._resolve_time_reference(sentence, year, publish_date)
        if resolved_time:
            latest_record["time_reference"] = resolved_time
        latest_record["source_sentence"] = self._merge_text_fragment(
            latest_record.get("source_sentence"),
            sentence.strip(),
            separator=" ",
        )
        latest_record["source_clause"] = self._merge_text_fragment(latest_record.get("source_clause"), clause)
        return True

    def _apply_value_continuation(
        self,
        latest_record: dict[str, Any],
        clause: str,
        sentence: str,
        primary_measurement: dict[str, Any],
        year: int | None,
        publish_date: str | None,
    ) -> bool:
        if not isinstance(latest_record, dict) or latest_record.get("record_type") != "measurement":
            return False
        if primary_measurement.get("value") in {None, ""}:
            return False

        existing_value = latest_record.get("value")
        existing_unit = str(latest_record.get("unit") or "").strip()
        existing_metric_type = str(latest_record.get("metric_type") or "")
        should_update = (
            existing_value in {None, ""}
            or existing_metric_type == "growth_rate"
            or existing_unit in {"", "%", "‰"}
        )
        if not should_update:
            return False

        latest_record["value"] = primary_measurement.get("value")
        latest_record["unit"] = primary_measurement.get("unit")
        latest_record["value_text"] = self._extract_value_text(clause, primary_measurement["start"])
        latest_record["metric_type"] = self._classify_metric_type(
            clause=clause,
            indicator_name=str(latest_record.get("indicator_name") or "相关指标"),
            unit=primary_measurement.get("unit"),
            comparison_text=latest_record.get("comparison_text"),
            is_comparison_measurement=False,
        )
        resolved_time = self._resolve_time_reference(sentence, year, publish_date)
        if resolved_time:
            latest_record["time_reference"] = resolved_time
        latest_record["source_sentence"] = self._merge_text_fragment(
            latest_record.get("source_sentence"),
            sentence.strip(),
            separator=" ",
        )
        latest_record["source_clause"] = self._merge_text_fragment(latest_record.get("source_clause"), clause)
        return True

    def _merge_text_fragment(self, existing: Any, fragment: Any, separator: str = "；") -> str:
        existing_text = str(existing or "").strip()
        fragment_text = str(fragment or "").strip()
        if not existing_text:
            return fragment_text
        if not fragment_text or fragment_text in existing_text:
            return existing_text
        return f"{existing_text}{separator}{fragment_text}"

    def _extract_value_text(self, clause: str, value_start: int) -> str | None:
        value_text = clause[value_start:].strip(" ，；;。")
        if not value_text:
            return None
        yoy_match = YOY_PATTERN.search(value_text)
        if yoy_match and yoy_match.start() > 0:
            value_text = value_text[:yoy_match.start()].strip(" ，；;。")
        if not value_text:
            return None
        return value_text

    def _extract_yoy(self, sentence: str) -> tuple[float | None, str | None]:
        match = YOY_PATTERN.search(sentence)
        if not match:
            return None, None
        direction = match.group(1) or match.group(2)
        value = float(match.group(3))
        if direction in {"下降", "减少", "回落"}:
            value = -value
        return value, match.group(0)

    def _metrics_from_indicators(self, indicators: list[dict[str, Any]]) -> list[dict[str, Any]]:
        metrics = []
        for indicator in indicators:
            values = []
            if indicator.get("value") is not None:
                values.append({"value": indicator.get("value"), "unit": indicator.get("unit")})
            if indicator.get("yoy") is not None:
                values.append({"value": indicator.get("yoy"), "unit": "%"})
            metrics.append(
                {
                    "label": indicator.get("name", ""),
                    "statement": indicator.get("statement", ""),
                    "values": values,
                }
            )
        return metrics

    def _extract_entities(self, text: str) -> dict[str, Any]:
        return {
            "phones": self._deduplicate(PHONE_PATTERN.findall(text)),
            "emails": self._deduplicate([match.lower() for match in EMAIL_PATTERN.findall(text)]),
            "id_numbers": self._deduplicate([match.group(0) for match in ID_PATTERN.finditer(text)]),
        }

    def _infer_title(self, text: str) -> str:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped[:120]
        return "未命名文档"

    def _compose_text(self, document: dict[str, Any]) -> str:
        content = str(document.get("content", "") or "")
        ocr_text = str(document.get("ocr_text", "") or "")
        if content and ocr_text and ocr_text not in content:
            return f"{content}\n\n{ocr_text}"
        return content or ocr_text

    def _is_heading_block(self, block: dict[str, Any]) -> bool:
        text = str(block.get("text", "")).strip()
        if not text or len(text) > 50:
            return False
        style = str(block.get("style", "")).lower()
        if style and ("heading" in style or "title" in style or "标题" in style):
            return True
        return bool(HEADING_PATTERN.match(text))

    def _split_sentences(self, text: str) -> list[str]:
        parts = re.split(r"(?<=[。！？；;])|\n+", text)
        return [part.strip() for part in parts if part and part.strip()]

    def _split_record_clauses(self, sentence: str) -> list[str]:
        coarse_parts = re.split(r"[；;，]", sentence)
        clauses = []
        for part in coarse_parts:
            stripped = part.strip()
            if not stripped:
                continue
            measurements = self._extract_measurements(stripped)
            if "、" in stripped and len(measurements) >= 2:
                subparts = [item.strip() for item in stripped.split("、") if item and item.strip()]
                numeric_subparts = [item for item in subparts if re.search(r"\d", item)]
                if len(numeric_subparts) >= 2:
                    clauses.extend(numeric_subparts)
                    continue
            clauses.append(stripped)
        return clauses

    def _clean_record_clause(self, clause: str) -> str:
        normalized = re.sub(r"\s+", " ", clause or "").strip(" ，；;。")
        if not normalized:
            return ""
        if FIGURE_TABLE_PATTERN.match(normalized):
            for marker in ("全年", "年末", "年初", "全市", "全省", "全区", "全县", "全社会", "其中", "经", "截至", "人均", "2024年", "2025年", "2026年"):
                index = normalized.find(marker, 2)
                if index > 0:
                    candidate = normalized[index:].strip()
                    if candidate and not FIGURE_TABLE_PATTERN.match(candidate):
                        normalized = candidate
                        break
            else:
                return ""
        return normalized

    def _is_data_clause(self, clause: str) -> bool:
        if len(clause) < 4:
            return False
        if not re.search(r"\d", clause):
            return False
        if FIGURE_TABLE_PATTERN.match(clause):
            return False
        if DATE_PATTERN.fullmatch(clause):
            return False
        if any(keyword in clause for keyword in NOISE_KEYWORDS):
            return False
        measurements = self._extract_measurements(clause)
        return bool(measurements)

    def _is_comparison_only_clause(self, clause: str) -> bool:
        normalized = clause.strip()
        prefixes = ("同比", "比上年", "比去年", "较上年", "较去年", "增长", "下降", "提高", "回落", "增加", "减少")
        return normalized.startswith(prefixes)

    def _infer_region_and_year(self, title: str) -> tuple[str | None, int | None]:
        match = REPORT_TITLE_PATTERN.search(title)
        if match:
            return match.group("region"), int(match.group("year"))
        year_match = re.search(r"(19|20)\d{2}", title)
        year = int(year_match.group(0)) if year_match else None
        return None, year

    def _coerce_value(self, value: Any) -> Any:
        if value is None:
            return None

        text = str(value).strip()
        if not text:
            return None
        if text.lower() in NULL_MARKERS or text in NULL_MARKERS:
            return None

        if re.fullmatch(r"-?\d+", text):
            try:
                return int(text)
            except ValueError:
                return text

        if re.fullmatch(r"-?\d+\.\d+", text):
            try:
                return float(text)
            except ValueError:
                return text

        if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}\s+\d{2}:\d{2}:\d{2}(?:\.0+)?", text):
            return text.replace(".0", "")

        return text

    def _safe_float(self, value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _deduplicate(self, values: list[Any]) -> list[Any]:
        deduplicated = []
        for value in values:
            if value not in deduplicated:
                deduplicated.append(value)
        return deduplicated

    def _deduplicate_indicators(self, indicators: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduplicated = []
        seen = set()
        for indicator in indicators:
            signature = (
                indicator.get("section_id"),
                indicator.get("name"),
                indicator.get("value"),
                indicator.get("unit"),
                indicator.get("statement"),
            )
            if signature in seen:
                continue
            seen.add(signature)
            deduplicated.append(indicator)
        return deduplicated

    def _deduplicate_records(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduplicated = []
        seen = set()
        for record in records:
            signature = (
                record.get("record_type"),
                record.get("section"),
                record.get("indicator_name"),
                record.get("metric_type"),
                record.get("value"),
                record.get("unit"),
                record.get("source_clause"),
            )
            if signature in seen:
                continue
            seen.add(signature)
            deduplicated.append(record)
        return deduplicated

    def _renumber_records(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        renumbered = []
        for index, record in enumerate(records, start=1):
            updated = dict(record)
            updated["record_id"] = f"rec_{index}"
            renumbered.append(updated)
        return renumbered
