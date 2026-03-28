from __future__ import annotations

from collections import Counter, defaultdict
import re
from typing import Any

try:
    from config.config import PROMPT_VERSION
    from components.prompt_registry import PromptRegistry
except ImportError:
    from doc_processing.config.config import PROMPT_VERSION
    from doc_processing.components.prompt_registry import PromptRegistry


DOMAIN_LABELS = {
    "government_statistics": "政府统计",
    "environment_monitoring": "生态环境",
    "healthcare": "医疗健康",
    "finance": "金融财务",
    "manufacturing": "制造业",
    "education": "教育科研",
    "agriculture": "农业",
    "transportation": "交通物流",
    "energy": "能源",
    "retail_consumption": "零售消费",
    "human_resources": "人力资源",
    "legal_compliance": "法务合规",
    "technology_operations": "技术运维",
    "general": "综合领域",
}
GENERIC_SECTION_TITLES = {
    "引言",
    "正文",
    "全文",
    "概况",
    "基本情况",
    "说明",
    "附件",
    "附注",
    "重点数据",
    "字段",
}
GENERIC_INDICATORS = {"值", "数值", "指标", "监测值", "总量", "数据"}
TIME_FIELD_HINTS = ("时间", "日期", "月份", "月", "年", "period", "date", "time", "监测时间")
CATEGORY_FIELD_HINTS = ("地区", "城市", "区县", "行业", "类别", "分类", "名称", "站点", "监测点", "区域", "name")
CONTEXT_FIELD_HINTS = ("站点名称", "站点", "监测点", "点位", "名称", "学校", "医院", "企业", "城市", "区县", "地区", "行业", "类别")
ID_FIELD_HINTS = ("id", "编号", "代码", "序号")
GROWTH_HINTS = ("同比", "环比", "增速", "增长率", "涨幅", "降幅")
RATIO_HINTS = ("率", "占比", "比重", "比例")
AGGREGATE_SUM_HINTS = ("总值", "总额", "总量", "投资", "零售额", "产值", "消费", "收入", "产量")
VALUE_UNIT_PATTERN = re.compile(r"(-?\d+(?:\.\d+)?)\s*(个百分点|%|亿元|万元|元|万亿元|万户|户|万人|人|吨|万吨|千克|公斤|天|次|个|家|项|公里|千米|平方公里|亩|立方米|千瓦时|亿千瓦时|mg/m3|ug/m3)?")
FORBIDDEN_EXPRESSIONS = [
    "该数据集包含",
    "共有",
    "字段包括",
    "JSON",
    "schema",
    "样例数据",
    "样例记录",
    "下面根据数据进行分析",
]
OVERALL_SECTION_TITLE = "一、总体情况"
STRUCTURE_SECTION_TITLE = "二、分项结构"
CHANGE_SECTION_TITLE = "三、重点变化"
RISK_SECTION_TITLE = "四、风险或异常提示"
MAX_TOPIC_COVERAGE = 12
MAX_SUMMARY_METRICS_PER_TOPIC = 8
MAX_BREAKDOWN_ITEMS = 8
MAX_TIME_SERIES_PER_TOPIC = 4
MAX_ANOMALIES_PER_TOPIC = 5
MAX_INSIGHTS_PER_TOPIC = 5
FULL_DETAIL_THRESHOLD = 12


class NaturalLanguageGenerator:
    def __init__(self) -> None:
        self.prompt_registry = PromptRegistry(prompt_version=PROMPT_VERSION, enable_self_check=False)

    def generate(
        self,
        structured_data: dict[str, Any],
        canonical_data: dict[str, Any],
        parsed_document: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        structured_data = structured_data if isinstance(structured_data, dict) else {}
        canonical_data = canonical_data if isinstance(canonical_data, dict) else {}
        parsed_document = parsed_document if isinstance(parsed_document, dict) else {}

        context = self._build_context(structured_data, canonical_data, parsed_document)
        facts_schema = self._extract_report_facts(context)
        report_plan = self._build_report_plan(facts_schema, context)
        chart_decisions = report_plan.get("chart_decisions", []) if isinstance(report_plan.get("chart_decisions"), list) else []
        render_specs = report_plan.get("charts", []) if isinstance(report_plan.get("charts"), list) else []
        chart_outputs = self._build_chart_output_summaries(render_specs, chart_decisions)
        report_body = self._write_report_body(facts_schema, report_plan, context)
        prompt_plan = self.prompt_registry.build_report_generation_prompt_plan(
            context,
            facts_schema,
            report_plan,
            chart_decisions,
        )

        return {
            "report_type": "formal_statistical_report",
            "style": "formal_statistical_report",
            "title": report_plan.get("title") or context.get("report_title") or self._report_title(context.get("title", "未命名材料")),
            "content": report_body,
            "paragraphs": [paragraph for paragraph in report_body.split("\n\n") if paragraph.strip()],
            "facts_schema": facts_schema,
            "report_facts": facts_schema,
            "report_plan": report_plan,
            "chart_specs": chart_decisions,
            "chart_render_specs": render_specs,
            "chart_outputs": chart_outputs,
            "charts": chart_outputs,
            "prompting": prompt_plan,
            "forbidden_expression_check": self._forbidden_expression_check(report_body),
        }

    def _build_context(
        self,
        structured_data: dict[str, Any],
        canonical_data: dict[str, Any],
        parsed_document: dict[str, Any],
    ) -> dict[str, Any]:
        document_meta = canonical_data.get("document_meta", {}) if isinstance(canonical_data.get("document_meta"), dict) else {}
        document_summary = structured_data.get("document_summary", {}) if isinstance(structured_data.get("document_summary"), dict) else {}
        detail_groups = structured_data.get("detail_groups", {}) if isinstance(structured_data.get("detail_groups"), dict) else {}
        records = structured_data.get("records", []) if isinstance(structured_data.get("records"), list) else []
        if not records and isinstance(canonical_data.get("records"), list):
            records = canonical_data.get("records", [])
        sections = structured_data.get("sections", []) if isinstance(structured_data.get("sections"), list) else []
        if not sections:
            sections = self._normalize_sections(canonical_data.get("sections", []))
        datasets = structured_data.get("datasets", []) if isinstance(structured_data.get("datasets"), list) else []
        indicators = structured_data.get("indicators", []) if isinstance(structured_data.get("indicators"), list) else []
        key_values = self._normalize_key_values(structured_data, canonical_data)
        raw_text = str(parsed_document.get("content") or "")
        metadata = parsed_document.get("metadata", {}) if isinstance(parsed_document.get("metadata"), dict) else {}

        domain_tags = structured_data.get("domain_tags", []) if isinstance(structured_data.get("domain_tags"), list) else []
        if not domain_tags:
            domain_tags = document_meta.get("domain_tags", []) if isinstance(document_meta.get("domain_tags"), list) else []
        title = (
            document_meta.get("title")
            or document_summary.get("title")
            or structured_data.get("title")
            or metadata.get("title")
            or metadata.get("file_name")
            or "未命名材料"
        )
        region = structured_data.get("region") or document_summary.get("region") or document_meta.get("region")
        year = structured_data.get("year") or document_summary.get("year") or document_meta.get("year")
        publish_date = structured_data.get("publish_date") or document_summary.get("publish_date") or document_meta.get("publish_date")
        period = self._infer_period(year, publish_date, records, datasets, key_values)
        return {
            "title": title,
            "report_title": self._report_title(title),
            "document_type": structured_data.get("document_type") or document_meta.get("document_type") or "unknown",
            "period": period,
            "region": region,
            "year": year,
            "publish_date": publish_date,
            "domain_tags": domain_tags,
            "records": records,
            "sections": sections,
            "datasets": datasets,
            "indicators": indicators,
            "key_values": key_values,
            "raw_text": raw_text,
            "detail_groups": detail_groups,
        }

    def _extract_report_facts(self, context: dict[str, Any]) -> dict[str, Any]:
        base_records: list[dict[str, Any]] = []
        if isinstance(context.get("records"), list):
            base_records.extend(item for item in context.get("records", []) if isinstance(item, dict))
        base_records.extend(self._records_from_datasets(context.get("datasets", []), context))
        base_records.extend(self._records_from_key_values(context.get("key_values", {}), context))
        base_records = self._deduplicate_records(base_records)

        grouped_topics = self._group_topic_records(base_records)
        topics = []
        for source_order, (name, records) in enumerate(grouped_topics.items(), start=1):
            topic = self._build_topic_fact(name, records)
            topic["source_order"] = source_order
            topics.append(topic)
        topics = [topic for topic in topics if topic.get("summary_metric") or topic.get("breakdowns") or topic.get("time_series")]
        topics.sort(key=lambda item: (item.get("source_order", 10**6), -item.get("priority", 0), item.get("name", "")))

        return {
            "title": context.get("report_title") or self._report_title(context.get("title", "未命名材料")),
            "period": context.get("period") or "本期",
            "domain": self._domain_label((context.get("domain_tags") or [context.get("document_type", "general")])[0]),
            "topics": topics,
            "highlights": self._build_global_highlights(topics),
            "risks": self._build_global_risks(topics),
        }

    def _build_report_plan(self, facts_schema: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        topics = facts_schema.get("topics", []) if isinstance(facts_schema.get("topics"), list) else []
        sections: list[dict[str, Any]] = []
        chart_decisions: list[dict[str, Any]] = []
        charts: list[dict[str, Any]] = []
        figure_index = 1

        overall_topics = topics[: max(4, min(len(topics), MAX_TOPIC_COVERAGE))]
        overall_decisions, overall_actual, figure_index = self._collect_chart_decisions(overall_topics, figure_index, preferred="line")
        chart_decisions.extend(overall_decisions)
        charts.extend(overall_actual)
        sections.append(
            {
                "id": "overall",
                "title": OVERALL_SECTION_TITLE,
                "purpose": "概括整体运行态势和核心指标变化。",
                "topic_refs": [topic.get("name", "") for topic in overall_topics],
                "focus_metrics": self._flatten_metrics(overall_topics, limit=max(10, len(overall_topics) * 2)),
                "chart_specs": overall_actual,
                "chart_decisions": overall_decisions,
            }
        )

        structure_topics = [topic for topic in topics if topic.get("breakdowns")]
        if structure_topics:
            structure_topics = structure_topics[: max(4, min(len(structure_topics), MAX_TOPIC_COVERAGE))]
            structure_decisions, structure_actual, figure_index = self._collect_chart_decisions(structure_topics, figure_index, preferred="bar")
            chart_decisions.extend(structure_decisions)
            charts.extend(structure_actual)
            sections.append(
                {
                    "id": "structure",
                    "title": STRUCTURE_SECTION_TITLE,
                    "purpose": "呈现分地区、分行业、分品类或分指标结构。",
                    "topic_refs": [topic.get("name", "") for topic in structure_topics],
                    "focus_metrics": self._flatten_metrics(structure_topics, limit=max(12, len(structure_topics) * 3)),
                    "chart_specs": structure_actual,
                    "chart_decisions": structure_decisions,
                }
            )

        change_topics = [topic for topic in topics if topic.get("time_series") or topic.get("insights")]
        if change_topics:
            change_topics = change_topics[: max(4, min(len(change_topics), MAX_TOPIC_COVERAGE))]
            change_decisions, change_actual, figure_index = self._collect_chart_decisions(change_topics, figure_index, preferred="line")
            chart_decisions.extend(change_decisions)
            charts.extend(change_actual)
            sections.append(
                {
                    "id": "changes",
                    "title": CHANGE_SECTION_TITLE,
                    "purpose": "归纳主要趋势、亮点和重点变化。",
                    "topic_refs": [topic.get("name", "") for topic in change_topics],
                    "focus_metrics": self._flatten_metrics(change_topics, limit=max(12, len(change_topics) * 3)),
                    "chart_specs": change_actual,
                    "chart_decisions": change_decisions,
                }
            )

        risk_topics = [topic for topic in topics if topic.get("anomalies")]
        if risk_topics or facts_schema.get("risks"):
            risk_topics = risk_topics[: max(4, min(len(risk_topics), MAX_TOPIC_COVERAGE))]
            sections.append(
                {
                    "id": "risk",
                    "title": RISK_SECTION_TITLE,
                    "purpose": "提示异常波动、回落指标和需要关注的风险点。",
                    "topic_refs": [topic.get("name", "") for topic in risk_topics],
                    "focus_metrics": self._flatten_metrics(risk_topics, limit=max(8, len(risk_topics) * 2)),
                    "chart_specs": [],
                    "chart_decisions": [],
                }
            )

        return {
            "title": facts_schema.get("title") or context.get("report_title") or self._report_title(context.get("title", "未命名材料")),
            "period": facts_schema.get("period") or context.get("period") or "本期",
            "sections": sections,
            "chart_decisions": chart_decisions,
            "charts": charts,
        }

    def _write_report_body(self, facts_schema: dict[str, Any], report_plan: dict[str, Any], context: dict[str, Any]) -> str:
        section_map = {section.get("id"): section for section in report_plan.get("sections", []) if isinstance(section, dict)}
        parts: list[str] = []
        if section_map.get("overall"):
            parts.append(self._write_overall_section(facts_schema, section_map["overall"], context))
        if section_map.get("structure"):
            parts.append(self._write_structure_section(facts_schema, section_map["structure"]))
        if section_map.get("changes"):
            parts.append(self._write_change_section(facts_schema, section_map["changes"]))
        if section_map.get("risk"):
            parts.append(self._write_risk_section(facts_schema, section_map["risk"]))
        if not parts:
            parts.append("一、总体情况\n主要指标总体平稳，现有结构化事实已具备形成正式分析正文的条件。")
        return "\n\n".join(part.strip() for part in parts if part.strip())

    def _write_overall_section(self, facts_schema: dict[str, Any], section: dict[str, Any], context: dict[str, Any]) -> str:
        metrics = section.get("focus_metrics", []) if isinstance(section.get("focus_metrics"), list) else []
        topics = self._topic_lookup(facts_schema, section.get("topic_refs", []))
        opening = self._overall_opening(context, facts_schema)
        core_sentences = [self._compose_metric_sentence(metric).rstrip("。；") for metric in metrics[: min(len(metrics), 10)]]
        core_sentences = [sentence for sentence in core_sentences if sentence]
        trend_sentence = self._overall_trend_sentence(topics)
        highlight_sentence = self._global_highlight_sentence(facts_schema)
        chart_ref = self._chart_reference(section.get("chart_specs", []))
        lines = [opening]
        if core_sentences:
            first_sentence = "；".join(core_sentences[:5])
            if chart_ref:
                first_sentence = first_sentence.rstrip("。") + chart_ref + "。"
            lines.append(self._ensure_sentence(first_sentence))
        remaining_sentences = core_sentences[5:]
        if remaining_sentences:
            lines.append(self._ensure_sentence("；".join(remaining_sentences)))
        lines.append(trend_sentence)
        if highlight_sentence:
            lines.append(highlight_sentence)
        body = " ".join(item for item in lines if item)
        return f"{section.get('title', OVERALL_SECTION_TITLE)}\n{body}".strip()

    def _write_structure_section(self, facts_schema: dict[str, Any], section: dict[str, Any]) -> str:
        topics = self._topic_lookup(facts_schema, section.get("topic_refs", []))
        blocks: list[str] = []
        for index, topic in enumerate(topics, start=1):
            topic_name = self._clean_text(topic.get("name")) or "重点指标"
            summary_metrics = topic.get("summary_metric", []) if isinstance(topic.get("summary_metric"), list) else []
            breakdowns = topic.get("breakdowns", []) if isinstance(topic.get("breakdowns"), list) else []
            grouped_line = self._compose_metric_group_sentence(topic_name, self._slice_for_report(summary_metrics, 4))
            body_lines = [grouped_line] if grouped_line else [self._compose_metric_sentence(metric) for metric in self._slice_for_report(summary_metrics, 2)]
            body_lines = [line for line in body_lines if line]
            body_lines.extend(
                self._compose_breakdown_paragraph(topic_name, breakdown)
                for breakdown in breakdowns
                if self._compose_breakdown_paragraph(topic_name, breakdown)
            )
            if not body_lines:
                continue
            block_lines = [self._topic_heading(index, topic_name)] + body_lines
            blocks.append("\n".join(block_lines))
        if not blocks:
            blocks.append("分项结构总体保持稳定，主要指标之间呈现有序分布。")
        chart_ref = self._chart_reference(section.get("chart_specs", []))
        if chart_ref:
            blocks[0] = blocks[0].replace("。", chart_ref + "。", 1) if "。" in blocks[0] else blocks[0] + chart_ref
        return f"{section.get('title', STRUCTURE_SECTION_TITLE)}\n" + "\n\n".join(blocks)

    def _write_change_section(self, facts_schema: dict[str, Any], section: dict[str, Any]) -> str:
        topics = self._topic_lookup(facts_schema, section.get("topic_refs", []))
        blocks: list[str] = []
        for index, topic in enumerate(topics, start=1):
            paragraph = self._compose_topic_change_paragraph(topic)
            if not paragraph:
                continue
            topic_name = self._clean_text(topic.get("name")) or "重点指标"
            blocks.append(f"{self._topic_heading(index, topic_name)}\n{paragraph}")
        if not blocks:
            blocks.append("重点指标总体延续既有运行轨迹，未出现明显偏离。")
        chart_ref = self._chart_reference(section.get("chart_specs", []))
        if chart_ref:
            blocks[0] = blocks[0].replace("。", chart_ref + "。", 1) if "。" in blocks[0] else blocks[0] + chart_ref
        return f"{section.get('title', CHANGE_SECTION_TITLE)}\n" + "\n\n".join(blocks)

    def _write_risk_section(self, facts_schema: dict[str, Any], section: dict[str, Any]) -> str:
        topics = self._topic_lookup(facts_schema, section.get("topic_refs", []))
        risk_entries: list[dict[str, Any]] = []
        for topic in topics:
            topic_name = self._clean_text(topic.get("name")) or "重点指标"
            anomalies = topic.get("anomalies", []) if isinstance(topic.get("anomalies"), list) else []
            normalized = [
                self._clean_text(item.get("description") or item.get("summary")).rstrip("。；")
                for item in anomalies[:MAX_ANOMALIES_PER_TOPIC]
                if self._clean_text(item.get("description") or item.get("summary"))
            ]
            normalized = self._slice_for_report(self._deduplicate_texts(normalized), 4)
            for description in normalized:
                risk_entries.append({"topic_name": topic_name, "description": description})

        merged_entries = self._merge_risk_entries(risk_entries)
        blocks: list[str] = []
        for index, entry in enumerate(merged_entries, start=1):
            heading = self._topic_heading(index, self._risk_heading_label(entry))
            blocks.append(f"{heading}\n{self._risk_body_text(entry)}")

        if not blocks:
            clauses = [self._clean_text(item).rstrip("。；") for item in self._deduplicate_texts(facts_schema.get("risks", [])) if self._clean_text(item)]
            clauses = self._slice_for_report(clauses, 8)
            if clauses:
                chunks = ["；".join(clauses[index:index + 4]) for index in range(0, len(clauses), 4)]
                body = " ".join(("需要关注的是，" + chunk + "。") if index == 0 else (chunk + "。") for index, chunk in enumerate(chunks))
            else:
                body = "主要指标总体平稳，暂未发现需要单独提示的异常波动。"
            blocks.append(body)
        return f"{section.get('title', RISK_SECTION_TITLE)}\n" + "\n\n".join(blocks)

    def _records_from_datasets(self, datasets: list[dict[str, Any]], context: dict[str, Any]) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        if not isinstance(datasets, list):
            return converted
        for dataset_index, dataset in enumerate(datasets, start=1):
            rows = dataset.get("records", []) if isinstance(dataset.get("records"), list) else []
            if not rows:
                continue
            dataset_name = self._clean_text(dataset.get("name") or f"dataset_{dataset_index}")
            time_field = self._pick_time_field(rows)
            category_field = self._pick_category_field(rows, excluded={time_field} if time_field else set())
            context_fields = self._pick_context_fields(rows, excluded={field for field in (time_field,) if field}, preferred=category_field)
            numeric_fields = self._pick_numeric_fields(rows, excluded={field for field in (time_field, category_field) if field})
            if not numeric_fields:
                continue

            growth_fields = [field for field in numeric_fields if self._looks_like_growth_field(field)]
            value_fields = [field for field in numeric_fields if field not in growth_fields]
            paired_growth = {field: self._match_growth_field(field, growth_fields) for field in value_fields}
            used_growth = {field for field in paired_growth.values() if field}
            standalone_growth = [field for field in growth_fields if field not in used_growth]

            for row_index, row in enumerate(rows, start=1):
                if not isinstance(row, dict):
                    continue
                period = self._clean_text(row.get(time_field)) if time_field else self._clean_text(context.get("period"))
                dimension_value = self._clean_text(row.get(category_field)) if category_field else ""
                location = dimension_value or self._clean_text(context.get("region"))
                context_label = self._compose_context_label(row, context_fields, fallback=dimension_value or location)

                for field in value_fields[:10]:
                    value = self._coerce_numeric(row.get(field))
                    if value is None:
                        continue
                    indicator_name = self._normalize_indicator_label(field)
                    growth_field = paired_growth.get(field)
                    yoy_value = self._coerce_numeric(row.get(growth_field)) if growth_field else None
                    unit = self._infer_unit(field)
                    converted.append(
                        {
                            "record_id": f"ds_{dataset_index}_{row_index}_{self._slugify(indicator_name)}",
                            "record_type": "measurement",
                            "section": dataset_name,
                            "topic_name": self._dataset_topic_name(dataset_name, indicator_name),
                            "indicator_name": indicator_name,
                            "metric_type": "value",
                            "value": value,
                            "value_text": self._display_value(value, unit),
                            "unit": unit,
                            "yoy_percent": yoy_value,
                            "comparison_text": self._change_text(yoy_value, field_name=growth_field or field),
                            "time_reference": period,
                            "location_reference": location,
                            "dimension_name": category_field or "",
                            "dimension_value": dimension_value,
                            "context_label": context_label,
                            "source_sentence": self._dataset_source_text(dataset_name, row, [category_field, time_field, field, growth_field]),
                        }
                    )

                for field in standalone_growth[:5]:
                    value = self._coerce_numeric(row.get(field))
                    if value is None:
                        continue
                    indicator_name = self._normalize_indicator_label(field)
                    converted.append(
                        {
                            "record_id": f"ds_{dataset_index}_{row_index}_{self._slugify(indicator_name)}_growth",
                            "record_type": "measurement",
                            "section": dataset_name,
                            "topic_name": self._dataset_topic_name(dataset_name, indicator_name),
                            "indicator_name": indicator_name,
                            "metric_type": "growth_rate",
                            "value": value,
                            "value_text": self._display_value(value, "%"),
                            "unit": "%",
                            "yoy_percent": value,
                            "comparison_text": self._change_text(value, field_name=field),
                            "time_reference": period,
                            "location_reference": location,
                            "dimension_name": category_field or "",
                            "dimension_value": dimension_value,
                            "context_label": context_label,
                            "source_sentence": self._dataset_source_text(dataset_name, row, [category_field, time_field, field]),
                        }
                    )
        return converted

    def _records_from_key_values(self, key_values: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        if not isinstance(key_values, dict):
            return records
        for index, (key, raw_value) in enumerate(key_values.items(), start=1):
            key_text = self._clean_text(key)
            if not key_text:
                continue
            numeric_value, unit = self._parse_value_and_unit(raw_value)
            if numeric_value is None:
                continue
            metric_type = "growth_rate" if self._looks_like_growth_field(key_text) or unit == "%" else "value"
            yoy_value = numeric_value if metric_type == "growth_rate" else None
            indicator_name = self._normalize_indicator_label(key_text)
            records.append(
                {
                    "record_id": f"kv_{index}_{self._slugify(indicator_name)}",
                    "record_type": "measurement",
                    "section": "核心指标",
                    "topic_name": indicator_name,
                    "indicator_name": indicator_name,
                    "metric_type": metric_type,
                    "value": numeric_value,
                    "value_text": self._display_value(numeric_value, unit),
                    "unit": unit,
                    "yoy_percent": yoy_value,
                    "comparison_text": self._change_text(yoy_value, field_name=key_text),
                    "time_reference": self._clean_text(context.get("period")),
                    "location_reference": self._clean_text(context.get("region")),
                    "dimension_name": "",
                    "dimension_value": "",
                    "context_label": self._clean_text(context.get("region")),
                    "source_sentence": f"{key_text}：{self._stringify(raw_value)}",
                }
            )
        return records

    def _group_topic_records(self, records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in records:
            topic_name = self._topic_name_from_record(record)
            if topic_name:
                grouped[topic_name].append(record)
        return grouped

    def _build_topic_fact(self, topic_name: str, records: list[dict[str, Any]]) -> dict[str, Any]:
        selected_records = self._select_topic_records(records, max_items=max(12, min(len(records), 18)))
        latest_period = self._latest_period(records)
        latest_records = [record for record in selected_records if self._clean_text(record.get("time_reference")) == latest_period]
        summary_source = latest_records or selected_records
        summary_metrics = []
        for record in summary_source[:MAX_SUMMARY_METRICS_PER_TOPIC]:
            metric = self._metric_fact_from_record(record)
            if metric:
                summary_metrics.append(metric)
        breakdowns = self._build_topic_breakdowns(topic_name, records)
        time_series = self._build_topic_time_series(topic_name, records)
        anomalies = self._build_topic_anomalies(topic_name, records, breakdowns)
        insights = self._build_topic_insights(topic_name, summary_metrics, breakdowns, time_series, anomalies)
        return {
            "name": topic_name,
            "summary_metric": summary_metrics,
            "breakdowns": breakdowns,
            "time_series": time_series,
            "anomalies": anomalies,
            "insights": insights,
            "priority": self._topic_priority(records, time_series, breakdowns, anomalies),
            "evidence": self._topic_evidence(records),
        }

    def _build_topic_breakdowns(self, topic_name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        dominant_indicator = self._dominant_indicator(records) or topic_name
        dominant_period = self._dominant_period(records)
        dimension_name = self._dominant_dimension_name(records)
        if not dimension_name:
            return []

        candidate_records = [
            record
            for record in records
            if self._clean_text(record.get("indicator_name")) == dominant_indicator and self._clean_text(record.get("dimension_value") or record.get("location_reference"))
        ]
        if dominant_period:
            period_records = [record for record in candidate_records if self._clean_text(record.get("time_reference")) == dominant_period]
            if len(period_records) >= 3:
                candidate_records = period_records
        items = []
        for record in self._select_topic_records(candidate_records, max_items=max(10, min(len(candidate_records), 16))):
            metric = self._metric_fact_from_record(record)
            if not metric:
                continue
            metric["name"] = self._clean_text(record.get("dimension_value") or record.get("location_reference"))
            if metric["name"]:
                items.append(metric)
        items = self._deduplicate_breakdown_items(items)
        distinct_names = {self._clean_text(item.get("name")) for item in items if self._clean_text(item.get("name"))}
        if len(items) < 3 or len(distinct_names) < 3:
            return []
        return [
            {
                "indicator": dominant_indicator,
                "dimension": dimension_name,
                "period": dominant_period,
                "items": items[:MAX_BREAKDOWN_ITEMS],
            }
        ]

    def _build_topic_time_series(self, topic_name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in records:
            indicator_name = self._clean_text(record.get("indicator_name")) or topic_name
            grouped[indicator_name].append(record)

        series_list: list[dict[str, Any]] = []
        for indicator_name, indicator_records in grouped.items():
            points_by_period: dict[str, list[float]] = defaultdict(list)
            representative_unit = ""
            total_records = [record for record in indicator_records if self._is_total_dimension(record.get("dimension_value") or record.get("location_reference"))]
            series_records = total_records or indicator_records
            for record in series_records:
                period = self._clean_text(record.get("time_reference"))
                value = self._safe_float(record.get("value"))
                if not period or value is None:
                    continue
                representative_unit = self._clean_text(record.get("unit")) or representative_unit
                points_by_period[period].append(value)
            if len(points_by_period) < 4:
                continue
            aggregator = self._aggregate_mode(indicator_name, representative_unit)
            points = []
            for period, values in points_by_period.items():
                points.append({"period": period, "value": self._aggregate_values(values, aggregator)})
            points.sort(key=lambda item: self._sort_key(item.get("period")))
            if len(points) >= 4:
                series_list.append(
                    {
                        "indicator": indicator_name,
                        "unit": representative_unit,
                        "points": points,
                        "change_label": "同比增速" if representative_unit == "%" or self._looks_like_growth_field(indicator_name) else "变化趋势",
                    }
                )
        return series_list[:max(MAX_TIME_SERIES_PER_TOPIC, 1)]

    def _build_topic_anomalies(
        self,
        topic_name: str,
        records: list[dict[str, Any]],
        breakdowns: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        anomalies: list[dict[str, Any]] = []
        for record in self._select_topic_records(records, max_items=10):
            yoy_value = self._safe_float(record.get("yoy_percent"))
            indicator_name = self._clean_text(record.get("indicator_name")) or topic_name
            period = self._clean_text(record.get("time_reference")) or "本期"
            if yoy_value is None:
                continue
            if yoy_value <= -5:
                anomalies.append(
                    {
                        "summary": f"{indicator_name}在{period}同比下降{self._format_number(abs(yoy_value))}%",
                        "description": f"{indicator_name}在{period}同比下降{self._format_number(abs(yoy_value))}%，需关注回落压力。",
                    }
                )
            elif yoy_value >= 15:
                anomalies.append(
                    {
                        "summary": f"{indicator_name}在{period}同比增长{self._format_number(yoy_value)}%",
                        "description": f"{indicator_name}在{period}增幅达到{self._format_number(yoy_value)}%，波动幅度相对较大。",
                    }
                )
        for breakdown in breakdowns[:1]:
            items = breakdown.get("items", []) if isinstance(breakdown.get("items"), list) else []
            values = [self._safe_float(item.get("value")) for item in items]
            values = [value for value in values if value is not None]
            if len(values) < 3:
                continue
            high_value = max(values)
            low_value = min(values)
            if low_value != 0 and high_value >= low_value * 1.8:
                top_item = max(items, key=lambda item: self._safe_float(item.get("value")) or float("-inf"))
                bottom_item = min(items, key=lambda item: self._safe_float(item.get("value")) or float("inf"))
                anomalies.append(
                    {
                        "summary": f"{breakdown.get('dimension', '分项')}差异明显",
                        "description": f"分{breakdown.get('dimension', '分项')}看，{top_item.get('name')}与{bottom_item.get('name')}差距较大，结构分化较为明显。",
                    }
                )
        return self._deduplicate_dicts(anomalies, key="description")[:MAX_ANOMALIES_PER_TOPIC]

    def _build_topic_insights(
        self,
        topic_name: str,
        summary_metrics: list[dict[str, Any]],
        breakdowns: list[dict[str, Any]],
        time_series: list[dict[str, Any]],
        anomalies: list[dict[str, Any]],
    ) -> list[str]:
        insights: list[str] = []
        positive = 0
        negative = 0
        for metric in summary_metrics:
            change_value = self._safe_float(metric.get("change_value"))
            if change_value is None:
                continue
            if change_value > 0:
                positive += 1
            elif change_value < 0:
                negative += 1
        if positive and not negative:
            insights.append(f"{topic_name}总体保持增长态势。")
        elif negative and not positive:
            insights.append(f"{topic_name}整体承压，主要指标有所回落。")
        elif positive and negative:
            insights.append(f"{topic_name}内部表现分化，既有增长亮点，也存在回落项。")
        if time_series:
            trend = self._series_trend(topic_name, time_series[0])
            if trend:
                insights.append(trend)
        if breakdowns:
            breakdown_sentence = self._breakdown_comparison_sentence(topic_name, breakdowns[0])
            if breakdown_sentence:
                insights.append(breakdown_sentence)
        if anomalies:
            insights.append(f"{topic_name}仍有局部波动需要关注。")
        return self._deduplicate_texts(insights)[:MAX_INSIGHTS_PER_TOPIC]

    def _breakdown_comparison_sentence(self, topic_name: str, breakdown: dict[str, Any]) -> str:
        items = breakdown.get("items", []) if isinstance(breakdown.get("items"), list) else []
        values = [(item, self._safe_float(item.get("value"))) for item in items]
        values = [(item, value) for item, value in values if value is not None]
        if len(values) < 2:
            return ""
        top_item, _ = max(values, key=lambda item: item[1])
        bottom_item, _ = min(values, key=lambda item: item[1])
        if self._clean_text(top_item.get("name")) == self._clean_text(bottom_item.get("name")):
            return ""
        dimension = self._clean_text(breakdown.get("dimension")) or "分项"
        top_clause = self._metric_core_clause(top_item, include_indicator=False)
        bottom_clause = self._metric_core_clause(bottom_item, include_indicator=False)
        if not top_clause or not bottom_clause:
            return ""
        return f"分{dimension}看，{self._clean_text(top_item.get('name'))}{topic_name}{top_clause}，{self._clean_text(bottom_item.get('name'))}{topic_name}{bottom_clause}。"

    def _build_global_highlights(self, topics: list[dict[str, Any]]) -> list[str]:
        highlights: list[str] = []
        for topic in topics[: min(len(topics), 8)]:
            metrics = topic.get("summary_metric", []) if isinstance(topic.get("summary_metric"), list) else []
            if metrics:
                sentence = self._compose_metric_sentence(metrics[0])
                if sentence:
                    highlights.append(sentence)
        return self._deduplicate_texts(highlights)

    def _build_global_risks(self, topics: list[dict[str, Any]]) -> list[str]:
        risks: list[str] = []
        for topic in topics:
            for anomaly in topic.get("anomalies", [])[:1]:
                text = self._clean_text(anomaly.get("description") or anomaly.get("summary"))
                if text:
                    risks.append(text)
        return self._deduplicate_texts(risks)[:8]

    def _build_chart_output_summaries(
        self,
        render_specs: list[dict[str, Any]],
        chart_decisions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        outputs: list[dict[str, Any]] = []
        specs = render_specs if isinstance(render_specs, list) else []
        decisions = chart_decisions if isinstance(chart_decisions, list) else []
        for index, spec in enumerate(specs):
            decision = decisions[index] if index < len(decisions) and isinstance(decisions[index], dict) else {}
            outputs.append(
                {
                    "id": spec.get("id") or decision.get("id") or f"chart_{index + 1:02d}",
                    "type": spec.get("type") or decision.get("type") or "none",
                    "title": spec.get("title") or decision.get("title") or f"图表{index + 1}",
                    "reason": spec.get("reason") or decision.get("reason") or "",
                    "path": "",
                    "embedded_only": True,
                }
            )
        return outputs

    def _collect_chart_decisions(
        self,
        topics: list[dict[str, Any]],
        figure_index: int,
        preferred: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
        decisions: list[dict[str, Any]] = []
        actual_specs: list[dict[str, Any]] = []
        for topic in topics:
            decision = self._chart_spec_for_topic(topic, preferred=preferred)
            decisions.append(decision)
            if decision.get("type") == "none":
                continue
            spec = dict(decision)
            spec["id"] = f"chart_{figure_index:02d}"
            spec["figure_label"] = f"（见图{figure_index}）"
            actual_specs.append(spec)
            figure_index += 1
            if len(actual_specs) >= 4:
                break
        return decisions, actual_specs, figure_index

    def _chart_spec_for_topic(self, topic: dict[str, Any], preferred: str = "line") -> dict[str, Any]:
        topic_name = self._clean_text(topic.get("name")) or "重点指标"
        time_series = topic.get("time_series", []) if isinstance(topic.get("time_series"), list) else []
        breakdowns = topic.get("breakdowns", []) if isinstance(topic.get("breakdowns"), list) else []

        line_spec = self._line_chart_spec(topic_name, time_series)
        bar_spec = self._bar_chart_spec(topic_name, breakdowns)

        if preferred == "line" and line_spec:
            return line_spec
        if preferred == "bar" and bar_spec:
            return bar_spec
        if line_spec:
            return line_spec
        if bar_spec:
            return bar_spec
        return {
            "type": "none",
            "title": f"{topic_name}图表未生成",
            "x_field": "",
            "y_field": "",
            "series": [],
            "reason": "现有事实以单点描述为主，未形成连续时间序列或显著横向对比，图表提升有限。",
        }

    def _line_chart_spec(self, topic_name: str, time_series: list[dict[str, Any]]) -> dict[str, Any] | None:
        for series in time_series:
            points = series.get("points", []) if isinstance(series.get("points"), list) else []
            if len(points) < 4:
                continue
            return {
                "type": "line",
                "title": self._line_chart_title(topic_name, series),
                "x_field": "时间",
                "y_field": series.get("unit") or "数值",
                "series": [
                    {
                        "name": topic_name,
                        "data": [{"x": point.get("period"), "y": point.get("value")} for point in points],
                    }
                ],
                "reason": "该指标存在不少于4个连续时间点，适合用折线图展示变化趋势。",
            }
        return None

    def _bar_chart_spec(self, topic_name: str, breakdowns: list[dict[str, Any]]) -> dict[str, Any] | None:
        for breakdown in breakdowns:
            items = breakdown.get("items", []) if isinstance(breakdown.get("items"), list) else []
            if len(items) < 3:
                continue
            return {
                "type": "bar",
                "title": self._bar_chart_title(topic_name, breakdown),
                "x_field": breakdown.get("dimension") or "类别",
                "y_field": items[0].get("unit") or "数值",
                "series": [
                    {
                        "name": topic_name,
                        "data": [{"x": item.get("name"), "y": item.get("value")} for item in items[:MAX_BREAKDOWN_ITEMS]],
                    }
                ],
                "reason": "该指标在同一时期存在多个类别或地区对比，适合用柱状图展示结构差异。",
            }
        return None

    def _line_chart_title(self, topic_name: str, series: dict[str, Any]) -> str:
        points = series.get("points", []) if isinstance(series.get("points"), list) else []
        if points:
            first_label = self._clean_text(points[0].get("period"))
            last_label = self._clean_text(points[-1].get("period"))
            if first_label and last_label:
                if first_label == last_label:
                    return f"{first_label}{topic_name}{series.get('change_label', '变化趋势')}"
                return f"{first_label}至{last_label}{topic_name}{series.get('change_label', '变化趋势')}"
        return f"{topic_name}变化趋势"

    def _bar_chart_title(self, topic_name: str, breakdown: dict[str, Any]) -> str:
        dimension = self._clean_text(breakdown.get("dimension")) or "分项"
        indicator = self._clean_text(breakdown.get("indicator")) or topic_name
        if dimension == "指标":
            return f"{topic_name}分项指标对比"
        return f"各{dimension}{indicator}对比"

    def _topic_lookup(self, facts_schema: dict[str, Any], topic_refs: Any) -> list[dict[str, Any]]:
        topics = facts_schema.get("topics", []) if isinstance(facts_schema.get("topics"), list) else []
        topic_map = {self._clean_text(topic.get("name")): topic for topic in topics if isinstance(topic, dict)}
        resolved = []
        for ref in topic_refs if isinstance(topic_refs, list) else []:
            topic = topic_map.get(self._clean_text(ref))
            if topic:
                resolved.append(topic)
        return resolved

    def _compose_metric_group_sentence(self, topic_name: str, metrics: list[dict[str, Any]]) -> str:
        metrics = [metric for metric in metrics if isinstance(metric, dict)]
        if len(metrics) < 2:
            return ""
        periods = [self._display_period_label(metric.get("period")) for metric in metrics if self._display_period_label(metric.get("period"))]
        if not periods or len(set(periods)) != 1:
            return ""
        contexts = []
        values = []
        changes = []
        units = []
        for metric in metrics:
            context_label = self._clean_text(metric.get("context_label") or metric.get("dimension_value"))
            value = self._safe_float(metric.get("value"))
            unit = self._clean_text(metric.get("unit"))
            if not context_label or value is None:
                return ""
            contexts.append(context_label)
            values.append(self._display_value(value, unit))
            units.append(unit)
            changes.append(self._safe_float(metric.get("change_value")))
        if len(set(contexts)) != len(contexts):
            return ""
        sentence = f"{periods[0]}，{'、'.join(contexts)}的{topic_name}分别为" + "、".join(values)
        valid_changes = [value for value in changes if value is not None]
        if len(valid_changes) == len(metrics):
            change_texts = [f"{self._growth_direction(value)}{self._format_number(abs(value))}%" for value in valid_changes]
            sentence += "，同比分别" + "、".join(change_texts)
        return sentence + "。"

    def _compose_breakdown_paragraph(self, topic_name: str, breakdown: dict[str, Any]) -> str:
        items = breakdown.get("items", []) if isinstance(breakdown.get("items"), list) else []
        if not items:
            return f"{topic_name}结构总体平稳。"
        dimension = self._clean_text(breakdown.get("dimension")) or "分项"
        clauses = []
        for item in self._slice_for_report(items, MAX_BREAKDOWN_ITEMS):
            label = self._clean_text(item.get("name"))
            value_clause = self._metric_core_clause(item)
            if label and value_clause:
                clauses.append(f"{label}{value_clause}")
        if not clauses:
            return f"{topic_name}结构总体平稳。"
        prefix = "其中，" if dimension == "指标" else f"分{dimension}看，"
        return prefix + "；".join(clauses) + "。"

    def _compose_topic_change_paragraph(self, topic: dict[str, Any]) -> str:
        topic_name = topic.get("name", "重点指标")
        summary_metrics = topic.get("summary_metric", []) if isinstance(topic.get("summary_metric"), list) else []
        time_series = topic.get("time_series", []) if isinstance(topic.get("time_series"), list) else []
        insights = topic.get("insights", []) if isinstance(topic.get("insights"), list) else []

        grouped_line = self._compose_metric_group_sentence(topic_name, self._slice_for_report(summary_metrics, 6))

        if time_series:
            leading_metrics = [grouped_line] if grouped_line else [self._compose_metric_sentence(metric) for metric in self._slice_for_report(summary_metrics, 6)]
            trend_sentences = [self._series_trend(topic_name, series) for series in self._slice_for_report(time_series, 3)]
            series_point_sentences = [self._series_points_sentence(topic_name, series) for series in self._slice_for_report(time_series, 3)]
            lines = [item for item in leading_metrics + trend_sentences + series_point_sentences if item]
            if insights:
                lines.extend(self._clean_text(item) for item in self._slice_for_report(insights, 3) if self._clean_text(item))
            return " ".join(self._deduplicate_texts(lines))

        if summary_metrics:
            lines = [grouped_line] if grouped_line else [self._compose_metric_sentence(metric) for metric in self._slice_for_report(summary_metrics, 6)]
            lines = [line for line in lines if line]
            if insights:
                lines.extend(self._clean_text(item) for item in self._slice_for_report(insights, 3) if self._clean_text(item))
            return " ".join(self._deduplicate_texts(lines))

        if insights:
            return self._clean_text(insights[0])
        return ""

    def _metric_fact_from_record(self, record: dict[str, Any]) -> dict[str, Any] | None:
        indicator = self._clean_text(record.get("indicator_name"))
        if not indicator or indicator in GENERIC_INDICATORS:
            return None
        value = record.get("value")
        yoy_value = self._safe_float(record.get("yoy_percent"))
        metric_type = self._clean_text(record.get("metric_type")) or "value"
        unit = self._clean_text(record.get("unit"))
        if value in {None, ""} and yoy_value is None:
            return None
        if metric_type == "growth_rate" and yoy_value is None:
            yoy_value = self._safe_float(value)
        return {
            "indicator": indicator,
            "value": value,
            "unit": unit,
            "metric_type": metric_type,
            "period": self._clean_text(record.get("time_reference")),
            "change_value": yoy_value,
            "change_text": self._clean_text(record.get("comparison_text")),
            "dimension_name": self._clean_text(record.get("dimension_name")),
            "dimension_value": self._clean_text(record.get("dimension_value") or record.get("location_reference")),
            "context_label": self._clean_text(record.get("context_label")),
            "source": self._clean_text(record.get("source_sentence") or record.get("source_clause")),
        }

    def _select_topic_records(self, records: list[dict[str, Any]], max_items: int = 6) -> list[dict[str, Any]]:
        scored = []
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            score = 0
            if record.get("record_type") == "measurement":
                score += 10
            if record.get("value") not in {None, ""}:
                score += 5
            if self._safe_float(record.get("yoy_percent")) is not None:
                score += 4
            if self._clean_text(record.get("time_reference")):
                score += 2
            if self._clean_text(record.get("dimension_value") or record.get("location_reference")):
                score += 1
            if self._clean_text(record.get("source_sentence")):
                score += 1
            scored.append((score, index, record))
        scored.sort(key=lambda item: (-item[0], item[1]))

        selected: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for _, _, record in scored:
            dedupe_key = (
                self._clean_text(record.get("indicator_name")),
                self._clean_text(record.get("time_reference")),
                self._clean_text(record.get("dimension_value") or record.get("location_reference")),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            selected.append(record)
            if len(selected) >= max_items:
                break
        return selected

    def _topic_priority(
        self,
        records: list[dict[str, Any]],
        time_series: list[dict[str, Any]],
        breakdowns: list[dict[str, Any]],
        anomalies: list[dict[str, Any]],
    ) -> int:
        priority = len(records) * 2
        if time_series:
            priority += 6
        if breakdowns:
            priority += 4
        if anomalies:
            priority += 3
        return priority

    def _topic_name_from_record(self, record: dict[str, Any]) -> str:
        explicit = self._clean_text(record.get("topic_name"))
        if explicit and explicit not in GENERIC_INDICATORS:
            return explicit
        section = self._clean_text(record.get("section"))
        indicator = self._clean_text(record.get("indicator_name"))
        if section and section not in GENERIC_SECTION_TITLES and indicator in GENERIC_INDICATORS:
            return section
        if section and section not in GENERIC_SECTION_TITLES and indicator and section == indicator:
            return section
        if indicator and indicator not in GENERIC_INDICATORS:
            return indicator
        return section

    def _dominant_indicator(self, records: list[dict[str, Any]]) -> str:
        counter = Counter()
        for record in records:
            indicator = self._clean_text(record.get("indicator_name"))
            if indicator:
                counter[indicator] += 1
        return counter.most_common(1)[0][0] if counter else ""

    def _latest_period(self, records: list[dict[str, Any]]) -> str:
        periods = [self._clean_text(record.get("time_reference")) for record in records if self._clean_text(record.get("time_reference"))]
        if not periods:
            return ""
        return max(periods, key=self._sort_key)

    def _dominant_period(self, records: list[dict[str, Any]]) -> str:
        counter = Counter()
        for record in records:
            period = self._clean_text(record.get("time_reference"))
            if period:
                counter[period] += 1
        return counter.most_common(1)[0][0] if counter else ""

    def _dominant_dimension_name(self, records: list[dict[str, Any]]) -> str:
        counter = Counter()
        for record in records:
            dimension_name = self._clean_text(record.get("dimension_name"))
            if dimension_name:
                counter[dimension_name] += 1
            elif self._clean_text(record.get("dimension_value") or record.get("location_reference")):
                counter["地区"] += 1
        return counter.most_common(1)[0][0] if counter else ""

    def _topic_evidence(self, records: list[dict[str, Any]]) -> list[str]:
        evidences = []
        for record in self._select_topic_records(records, max_items=8):
            text = self._clean_text(record.get("source_sentence") or record.get("source_clause"))
            if text and text not in evidences:
                evidences.append(text)
        return evidences

    def _pick_time_field(self, rows: list[dict[str, Any]]) -> str | None:
        candidates = self._ordered_fields(rows)
        for field in candidates:
            if any(hint.lower() in field.lower() for hint in TIME_FIELD_HINTS):
                return field
        for field in candidates:
            values = [self._clean_text(row.get(field)) for row in rows[:60] if isinstance(row, dict)]
            if values and sum(1 for value in values if self._looks_like_time_value(value)) >= max(3, len(values) // 2):
                return field
        return None

    def _pick_context_fields(self, rows: list[dict[str, Any]], excluded: set[str], preferred: str | None = None) -> list[str]:
        candidates = [field for field in self._ordered_fields(rows) if field not in excluded]
        scored = []
        for index, field in enumerate(candidates):
            if any(hint.lower() in field.lower() for hint in ID_FIELD_HINTS):
                continue
            values = [self._clean_text(row.get(field)) for row in rows[:120] if isinstance(row, dict)]
            values = [value for value in values if value]
            if not values:
                continue
            non_numeric = [value for value in values if self._coerce_numeric(value) is None or re.search(r"[A-Za-z一-鿿]", value)]
            if len(non_numeric) < max(3, len(values) // 2):
                continue
            score = -index
            if preferred and field == preferred:
                score += 100
            if any(hint.lower() in field.lower() for hint in CONTEXT_FIELD_HINTS):
                score += 40
            if "名称" in field or "站点" in field:
                score += 15
            score += min(len(set(non_numeric)), 20)
            scored.append((score, index, field))
        scored.sort(key=lambda item: (-item[0], item[1]))
        result = []
        for _, _, field in scored:
            if field not in result:
                result.append(field)
            if len(result) >= 3:
                break
        return result

    def _pick_category_field(self, rows: list[dict[str, Any]], excluded: set[str]) -> str | None:
        candidates = [field for field in self._ordered_fields(rows) if field not in excluded]
        for field in candidates:
            if any(hint.lower() in field.lower() for hint in CATEGORY_FIELD_HINTS):
                return field
        for field in candidates:
            if any(hint.lower() in field.lower() for hint in ID_FIELD_HINTS):
                continue
            values = [self._clean_text(row.get(field)) for row in rows[:80] if isinstance(row, dict)]
            values = [value for value in values if value]
            distinct = len(set(values))
            if 2 <= distinct <= 12 and sum(1 for value in values if self._coerce_numeric(value) is None) >= max(3, len(values) // 2):
                return field
        return None

    def _pick_numeric_fields(self, rows: list[dict[str, Any]], excluded: set[str]) -> list[str]:
        fields = [field for field in self._ordered_fields(rows) if field not in excluded]
        numeric_fields = []
        for field in fields:
            if any(hint.lower() in field.lower() for hint in ID_FIELD_HINTS):
                continue
            values = [row.get(field) for row in rows[:120] if isinstance(row, dict)]
            numeric_count = sum(1 for value in values if self._coerce_numeric(value) is not None)
            if numeric_count >= max(3, len(values) // 2):
                numeric_fields.append(field)
        return numeric_fields[:10]

    def _match_growth_field(self, value_field: str, growth_fields: list[str]) -> str | None:
        if not growth_fields:
            return None
        value_base = self._indicator_base_name(value_field)
        for growth_field in growth_fields:
            if value_base and value_base == self._indicator_base_name(growth_field):
                return growth_field
        return growth_fields[0] if len(growth_fields) == 1 else None

    def _ordered_fields(self, rows: list[dict[str, Any]]) -> list[str]:
        ordered = []
        for row in rows[:10]:
            if not isinstance(row, dict):
                continue
            for key in row.keys():
                key_text = str(key)
                if key_text not in ordered:
                    ordered.append(key_text)
        return ordered

    def _normalize_indicator_label(self, label: Any) -> str:
        cleaned = self._clean_text(label)
        cleaned = re.sub(r"[（(].*?[）)]", "", cleaned)
        cleaned = re.sub(r"(?:同比|环比|增速|增长率|涨幅|降幅)", "", cleaned)
        cleaned = re.sub(r"(?:监测值|数值|值|指标)$", "", cleaned)
        cleaned = cleaned.strip(" _-/：:")
        return cleaned or self._clean_text(label)

    def _indicator_base_name(self, label: str) -> str:
        cleaned = self._normalize_indicator_label(label)
        cleaned = re.sub(r"(?:同比|环比|增速|增长率|涨幅|降幅)", "", cleaned)
        return cleaned.strip()

    def _is_total_dimension(self, value: Any) -> bool:
        text = self._clean_text(value)
        return text in {"全市", "全区", "全省", "全县", "全行业", "合计", "总计", "总体", "全部"}

    def _dataset_topic_name(self, dataset_name: str, indicator_name: str) -> str:
        if indicator_name in GENERIC_INDICATORS and dataset_name not in GENERIC_SECTION_TITLES:
            return dataset_name
        return indicator_name or dataset_name

    def _infer_unit(self, field_name: Any) -> str:
        name = self._clean_text(field_name)
        if any(hint in name for hint in RATIO_HINTS) or self._looks_like_growth_field(name):
            return "%"
        unit_match = re.search(r"[(（]([^()（）]{1,8})[)）]$", name)
        if unit_match:
            return unit_match.group(1)
        return ""

    def _aggregate_mode(self, indicator_name: str, unit: str) -> str:
        indicator = self._clean_text(indicator_name)
        if unit == "%" or any(hint in indicator for hint in RATIO_HINTS):
            return "avg"
        if any(hint in indicator for hint in AGGREGATE_SUM_HINTS):
            return "sum"
        return "avg"

    def _aggregate_values(self, values: list[float], mode: str) -> float:
        if not values:
            return 0.0
        if mode == "sum":
            return round(sum(values), 4)
        return round(sum(values) / len(values), 4)

    def _compose_metric_sentence(self, metric: dict[str, Any], include_indicator: bool = True) -> str:
        indicator = self._clean_text(metric.get("indicator"))
        if not indicator and include_indicator:
            return ""
        core = self._metric_core_clause(metric, include_indicator=include_indicator)
        if not core:
            return ""
        context_prefix = self._metric_context_prefix(metric)
        if context_prefix:
            return self._ensure_sentence(f"{context_prefix}{core}")
        return self._ensure_sentence(core)

    def _metric_context_prefix(self, metric: dict[str, Any]) -> str:
        period = self._display_period_label(metric.get("period"))
        context_label = self._clean_text(metric.get("context_label"))
        if not context_label:
            context_label = self._clean_text(metric.get("dimension_value"))
        indicator = self._clean_text(metric.get("indicator"))
        if context_label and indicator and context_label == indicator:
            context_label = ""
        if period and context_label:
            return f"{period}，{context_label}"
        if period:
            return f"{period}，"
        return context_label

    def _metric_core_clause(self, metric: dict[str, Any], include_indicator: bool = True) -> str:
        indicator = self._clean_text(metric.get("indicator"))
        value = self._safe_float(metric.get("value"))
        unit = self._clean_text(metric.get("unit"))
        metric_type = self._clean_text(metric.get("metric_type")) or "value"
        change_value = self._safe_float(metric.get("change_value"))
        change_text = self._clean_text(metric.get("change_text"))

        prefix = indicator if include_indicator else ""
        if metric_type == "growth_rate" and change_value is not None:
            return f"{prefix}同比{self._growth_direction(change_value)}{self._format_number(abs(change_value))}%"
        if value is not None:
            value_text = self._display_value(value, unit)
            if change_value is not None:
                return f"{prefix}为{value_text}，同比{self._growth_direction(change_value)}{self._format_number(abs(change_value))}%"
            if change_text:
                return f"{prefix}为{value_text}，{change_text}"
            return f"{prefix}为{value_text}"
        if change_value is not None:
            return f"{prefix}同比{self._growth_direction(change_value)}{self._format_number(abs(change_value))}%"
        return ""

    def _display_period_label(self, value: Any) -> str:
        text = self._clean_text(value)
        if not text:
            return ""
        match = re.search(r"(20\d{2}[-./年]\d{1,2}[-./月]\d{1,2})(?:[ T](\d{1,2}:\d{2}))?", text)
        if match:
            date_text = match.group(1).replace(".", "-").replace("/", "-")
            time_text = match.group(2)
            return f"{date_text} {time_text}".strip() if time_text else date_text
        return text

    def _context_field_rank(self, field: str) -> int:
        field_text = self._clean_text(field)
        if any(token in field_text for token in ["城市", "地区", "区域"]):
            return 0
        if any(token in field_text for token in ["区县", "区", "县"]):
            return 1
        if any(token in field_text for token in ["行业", "类别", "分类"]):
            return 2
        if any(token in field_text for token in ["站点", "监测点", "点位", "名称", "学校", "医院", "企业"]):
            return 3
        return 4

    def _compose_context_label(self, row: dict[str, Any], fields: list[str], fallback: str = "") -> str:
        parts: list[str] = []
        ordered_fields = sorted(fields[:3], key=self._context_field_rank)
        for field in ordered_fields:
            value = self._clean_text(row.get(field))
            if not value:
                continue
            if any(hint.lower() in field.lower() for hint in ID_FIELD_HINTS):
                continue
            if value not in parts:
                parts.append(value)
        if parts:
            return "".join(parts)
        return self._clean_text(fallback)

    def _series_trend(self, topic_name: str, series: dict[str, Any]) -> str:
        points = series.get("points", []) if isinstance(series.get("points"), list) else []
        if len(points) < 2:
            return ""
        first = points[0]
        last = points[-1]
        first_value = self._safe_float(first.get("value"))
        last_value = self._safe_float(last.get("value"))
        if first_value is None or last_value is None:
            return ""
        unit = self._clean_text(series.get("unit"))
        start_label = self._display_period_label(first.get("period"))
        end_label = self._display_period_label(last.get("period"))
        latest_value = self._display_value(last_value, unit)
        if abs(last_value - first_value) < 1e-9:
            if start_label and end_label:
                return f"在{start_label}至{end_label}期间，{topic_name}总体保持平稳，最新值为{latest_value}。"
            return f"{topic_name}总体保持平稳，最新值为{latest_value}。"
        direction = "上升" if last_value > first_value else "下降"
        if start_label and end_label:
            return f"在{start_label}至{end_label}期间，{topic_name}总体呈{direction}趋势，最新值为{latest_value}。"
        return f"{topic_name}总体呈{direction}趋势，最新值为{latest_value}。"

    def _series_points_sentence(self, topic_name: str, series: dict[str, Any]) -> str:
        points = series.get("points", []) if isinstance(series.get("points"), list) else []
        if len(points) < 4:
            return ""
        unit = self._clean_text(series.get("unit"))
        point_clauses = []
        for point in self._slice_for_report(points, 12):
            period = self._display_period_label(point.get("period"))
            value = self._safe_float(point.get("value"))
            if not period or value is None:
                continue
            point_clauses.append(f"{period}为{self._display_value(value, unit)}")
        if len(point_clauses) < 4:
            return ""
        return f"分时点看，{topic_name}在" + "，".join(point_clauses) + "。"

    def _topic_heading(self, index: int, topic_name: str) -> str:
        return f"（{self._index_to_cn(index)}）{self._clean_text(topic_name) or '重点指标'}"

    def _merge_risk_entries(self, risk_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        index_map: dict[str, int] = {}
        for entry in risk_entries:
            description = self._clean_text(entry.get("description"))
            topic_name = self._clean_text(entry.get("topic_name"))
            if not description:
                continue
            signature = self._risk_merge_signature(description)
            if signature in index_map:
                bucket = merged[index_map[signature]]
                if topic_name:
                    bucket["topic_names"].append(topic_name)
                if description not in bucket["descriptions"]:
                    bucket["descriptions"].append(description)
                continue
            index_map[signature] = len(merged)
            merged.append({
                "topic_names": [topic_name] if topic_name else [],
                "descriptions": [description],
                "signature": signature,
            })
        for entry in merged:
            entry["topic_names"] = self._deduplicate_texts(entry.get("topic_names", []))
            entry["descriptions"] = self._deduplicate_texts(entry.get("descriptions", []))
        return merged

    def _risk_merge_signature(self, description: str) -> str:
        text = self._clean_text(description)
        text = re.sub(r"-?\d+(?:\.\d+)?%?", "#", text)
        text = re.sub(r"[，。；、\s]+", "", text)
        return text

    def _risk_heading_label(self, entry: dict[str, Any]) -> str:
        topic_names = entry.get("topic_names", []) if isinstance(entry.get("topic_names"), list) else []
        topic_names = [self._clean_text(name) for name in topic_names if self._clean_text(name)]
        if not topic_names:
            return "重点风险"
        if len(topic_names) == 1:
            return topic_names[0]
        if len(topic_names) <= 3:
            return "、".join(topic_names)
        return "、".join(topic_names[:3]) + "等专题"

    def _risk_body_text(self, entry: dict[str, Any]) -> str:
        descriptions = entry.get("descriptions", []) if isinstance(entry.get("descriptions"), list) else []
        descriptions = [self._clean_text(item).rstrip("。；") for item in descriptions if self._clean_text(item)]
        descriptions = self._slice_for_report(self._deduplicate_texts(descriptions), 4)
        topic_names = entry.get("topic_names", []) if isinstance(entry.get("topic_names"), list) else []
        topic_names = [self._clean_text(name) for name in topic_names if self._clean_text(name)]
        if not descriptions:
            return "主要指标总体平稳，暂未发现需要单独提示的异常波动。"
        if len(topic_names) > 1:
            topic_text = "、".join(topic_names[:3])
            if len(topic_names) > 3:
                topic_text += "等专题"
            return f"需要关注的是，{topic_text}均存在同类风险，" + "；".join(descriptions) + "。"
        return "需要关注的是，" + "；".join(descriptions) + "。"

    def _slice_for_report(self, items: list[Any], max_items: int) -> list[Any]:
        if not isinstance(items, list):
            return []
        if len(items) <= FULL_DETAIL_THRESHOLD:
            return items
        return items[:max_items]

    def _index_to_cn(self, index: int) -> str:
        numerals = {0: "零", 1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八", 9: "九", 10: "十"}
        if index <= 10:
            return numerals.get(index, str(index))
        if index < 20:
            return "十" + numerals.get(index - 10, str(index - 10))
        if index < 100:
            tens, ones = divmod(index, 10)
            return numerals.get(tens, str(tens)) + "十" + (numerals.get(ones, "") if ones else "")
        return str(index)

    def _overall_opening(self, context: dict[str, Any], facts_schema: dict[str, Any]) -> str:
        period = self._clean_text(facts_schema.get("period") or context.get("period"))
        region = self._clean_text(context.get("region"))
        domain = self._clean_text(facts_schema.get("domain"))
        prefix = "".join(item for item in [period, region] if item)
        if domain:
            prefix += domain
        if not prefix:
            return "本期主要指标运行总体平稳。"
        return prefix + "相关指标运行总体平稳。"

    def _overall_trend_sentence(self, topics: list[dict[str, Any]]) -> str:
        positive = 0
        negative = 0
        for topic in topics:
            for metric in topic.get("summary_metric", [])[:4]:
                change_value = self._safe_float(metric.get("change_value"))
                if change_value is None:
                    continue
                if change_value > 0:
                    positive += 1
                elif change_value < 0:
                    negative += 1
        if positive and not negative:
            return "总体看，主要指标延续增长态势。"
        if negative and not positive:
            return "总体看，主要指标仍承受一定下行压力。"
        if positive and negative:
            return "总体看，主要指标运行基本平稳，但不同领域表现有所分化。"
        return "总体看，主要指标保持平稳运行。"

    def _global_highlight_sentence(self, facts_schema: dict[str, Any]) -> str:
        highlights = facts_schema.get("highlights", []) if isinstance(facts_schema.get("highlights"), list) else []
        cleaned = [self._clean_text(item).rstrip("。") for item in highlights[:6] if self._clean_text(item)]
        if not cleaned:
            return ""
        chunks = ["；".join(cleaned[index:index + 3]) for index in range(0, len(cleaned), 3)]
        return " ".join(("亮点主要体现在" if index == 0 else "同时，") + chunk + "。" for index, chunk in enumerate(chunks))

    def _flatten_metrics(self, topics: list[dict[str, Any]], limit: int = 4) -> list[dict[str, Any]]:
        metrics: list[dict[str, Any]] = []
        for topic in topics:
            for metric in topic.get("summary_metric", []) if isinstance(topic.get("summary_metric"), list) else []:
                metrics.append(metric)
                if len(metrics) >= limit:
                    return metrics
        return metrics

    def _chart_reference(self, chart_specs: list[dict[str, Any]]) -> str:
        if not isinstance(chart_specs, list) or not chart_specs:
            return ""
        labels = [self._clean_text(chart.get("figure_label")) for chart in chart_specs if self._clean_text(chart.get("figure_label"))]
        if not labels:
            return ""
        return "".join(labels[:2])

    def _normalize_sections(self, sections: Any) -> list[dict[str, Any]]:
        normalized = []
        for index, section in enumerate(sections if isinstance(sections, list) else [], start=1):
            if isinstance(section, dict):
                normalized.append(
                    {
                        "id": section.get("id", f"section_{index}"),
                        "title": section.get("title") or f"section_{index}",
                        "content": section.get("content") or section.get("text") or "",
                    }
                )
        return normalized

    def _normalize_key_values(self, structured_data: dict[str, Any], canonical_data: dict[str, Any]) -> dict[str, Any]:
        key_values = structured_data.get("key_values")
        if isinstance(key_values, dict):
            return key_values
        if isinstance(key_values, list):
            result = {}
            for item in key_values:
                if not isinstance(item, dict):
                    continue
                key = item.get("key") or item.get("name") or item.get("field")
                value = item.get("value")
                if key:
                    result[str(key)] = value
            return result
        canonical_key_values = canonical_data.get("key_values")
        if isinstance(canonical_key_values, dict):
            return canonical_key_values
        if isinstance(canonical_key_values, list):
            result = {}
            for item in canonical_key_values:
                if not isinstance(item, dict):
                    continue
                key = item.get("key") or item.get("name")
                value = item.get("value")
                if key:
                    result[str(key)] = value
            return result
        return {}

    def _infer_period(
        self,
        year: Any,
        publish_date: Any,
        records: list[dict[str, Any]],
        datasets: list[dict[str, Any]],
        key_values: dict[str, Any],
    ) -> str:
        year_text = self._clean_text(year)
        if year_text:
            if year_text.endswith("年"):
                return year_text
            if year_text.isdigit() and len(year_text) == 4:
                return f"{year_text}年"
            return year_text

        publish_text = self._clean_text(publish_date)
        year_match = re.search(r"(20\d{2})", publish_text)
        if year_match:
            return f"{year_match.group(1)}年"

        periods = []
        for record in records if isinstance(records, list) else []:
            period = self._clean_text(record.get("time_reference"))
            if period:
                periods.append(period)
        if periods:
            counts = Counter(periods)
            return counts.most_common(1)[0][0]

        for dataset in datasets if isinstance(datasets, list) else []:
            rows = dataset.get("records", []) if isinstance(dataset.get("records"), list) else []
            time_field = self._pick_time_field(rows)
            if time_field:
                values = [self._clean_text(row.get(time_field)) for row in rows[:20] if isinstance(row, dict) and self._clean_text(row.get(time_field))]
                if values:
                    return values[0]

        for key, value in key_values.items():
            if "时间" in str(key) or "日期" in str(key):
                return self._clean_text(value)
        return "本期"

    def _report_title(self, source_title: str) -> str:
        cleaned = self._clean_text(source_title).strip("《》") or "未命名材料"
        if any(keyword in cleaned for keyword in ["报告", "公报", "简报", "分析"]):
            return cleaned
        return f"{cleaned}统计分析报告"

    def _domain_label(self, domain_tag: Any) -> str:
        tag = self._clean_text(domain_tag) or "general"
        return DOMAIN_LABELS.get(tag, DOMAIN_LABELS.get("general", "综合领域"))

    def _parse_value_and_unit(self, raw_value: Any) -> tuple[float | None, str]:
        text = self._stringify(raw_value)
        match = VALUE_UNIT_PATTERN.search(text)
        if not match:
            return None, ""
        try:
            return float(match.group(1)), self._clean_text(match.group(2))
        except (TypeError, ValueError):
            return None, ""

    def _display_value(self, value: Any, unit: str = "") -> str:
        numeric = self._safe_float(value)
        if numeric is None:
            return self._clean_text(value)
        return f"{self._format_number(numeric)}{unit}"

    def _change_text(self, change_value: float | None, field_name: Any = "") -> str:
        if change_value is None:
            return ""
        field_text = self._clean_text(field_name)
        if "百分点" in field_text:
            direction = "提高" if change_value >= 0 else "下降"
            return f"较上年同期{direction}{self._format_number(abs(change_value))}个百分点"
        return f"同比{self._growth_direction(change_value)}{self._format_number(abs(change_value))}%"

    def _growth_direction(self, value: float) -> str:
        return "增长" if value >= 0 else "下降"

    def _dataset_source_text(self, dataset_name: str, row: dict[str, Any], fields: list[Any]) -> str:
        fragments = []
        for field in fields:
            if not field:
                continue
            field_text = str(field)
            if field_text not in row:
                continue
            value_text = self._clean_text(row.get(field_text))
            if value_text:
                fragments.append(f"{field_text}为{value_text}")
        prefix = dataset_name or "数据表"
        if fragments:
            return prefix + "中，" + "，".join(fragments)
        return prefix

    def _forbidden_expression_check(self, content: str) -> dict[str, Any]:
        matched = [token for token in FORBIDDEN_EXPRESSIONS if token in content]
        return {"has_forbidden": bool(matched), "matched": matched}

    def _deduplicate_records(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        seen = set()
        for record in records:
            signature = (
                self._clean_text(record.get("indicator_name")),
                self._clean_text(record.get("time_reference")),
                self._clean_text(record.get("dimension_value") or record.get("location_reference")),
                self._safe_float(record.get("value")),
                self._safe_float(record.get("yoy_percent")),
            )
            if signature in seen:
                continue
            seen.add(signature)
            result.append(record)
        return result

    def _deduplicate_breakdown_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        seen = set()
        for item in items:
            signature = (self._clean_text(item.get("name")), self._safe_float(item.get("value")))
            if signature in seen:
                continue
            seen.add(signature)
            result.append(item)
        return result

    def _deduplicate_texts(self, items: list[str]) -> list[str]:
        result = []
        seen = set()
        for item in items:
            text = self._clean_text(item)
            if text and text not in seen:
                seen.add(text)
                result.append(text)
        return result

    def _deduplicate_dicts(self, items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
        result = []
        seen = set()
        for item in items:
            signature = self._clean_text(item.get(key))
            if signature and signature not in seen:
                seen.add(signature)
                result.append(item)
        return result

    def _safe_float(self, value: Any) -> float | None:
        try:
            if value in {None, ""}:
                return None
            if isinstance(value, str):
                cleaned = value.replace(",", "").replace("%", "").strip()
                if cleaned in {"", "-", "--"}:
                    return None
                return float(cleaned)
            return float(value)
        except (TypeError, ValueError):
            return None

    def _coerce_numeric(self, value: Any) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        text = self._stringify(value)
        match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
        if not match:
            return None
        try:
            return float(match.group(0))
        except ValueError:
            return None

    def _looks_like_time_value(self, value: str) -> bool:
        text = self._clean_text(value)
        if not text:
            return False
        return bool(re.search(r"20\d{2}([-./年]\d{1,2})?([-./月]\d{1,2})?", text))

    def _looks_like_growth_field(self, field_name: str) -> bool:
        lowered = str(field_name).lower()
        return any(hint.lower() in lowered for hint in GROWTH_HINTS)

    def _clean_text(self, value: Any) -> str:
        text = self._stringify(value).replace("\u00a0", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _stringify(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return str(value)

    def _format_number(self, value: float) -> str:
        if abs(value - round(value)) < 1e-9:
            return str(int(round(value)))
        return f"{value:.2f}".rstrip("0").rstrip(".")

    def _ensure_sentence(self, text: str) -> str:
        cleaned = self._clean_text(text)
        if not cleaned:
            return ""
        if cleaned.endswith(("。", "！", "？")):
            return cleaned
        return cleaned + "。"

    def _sort_key(self, value: Any) -> tuple[int, ...]:
        text = self._clean_text(value)
        numbers = [int(item) for item in re.findall(r"\d+", text)]
        return tuple(numbers) if numbers else (999999,)

    def _slugify(self, text: str) -> str:
        cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", self._clean_text(text)).strip("_")
        return cleaned or "item"
