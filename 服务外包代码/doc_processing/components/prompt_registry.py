from __future__ import annotations

from typing import Any


DETAIL_PROMPTS = {
    "tabular_precision": {
        "system": "你是表格结构化抽取助手，优先保证字段名、单位、记录边界和来源一致。",
        "constraints": ["只输出可追溯字段", "优先保留原始列名", "不要臆造缺失值"],
        "few_shot_examples": [
            {"input": "监测站 | PM2.5 | 日期", "output": "[{监测站, PM2.5, 日期}]"},
        ],
    },
    "report_sectioned": {
        "system": "你是报告型文档抽取助手，先按章节理解，再抽取带来源句的指标记录。",
        "constraints": ["每条记录保留章节和来源句", "数值、单位、同比分开输出", "避免跨句拼接"],
        "few_shot_examples": [
            {"input": "全年地区生产总值为1234亿元，同比增长5.6%", "output": "indicator=地区生产总值, value=1234, unit=亿元, yoy=5.6"},
        ],
    },
    "report_statistical_brief": {
        "system": "你是统计公报抽取助手，重点提取地区、年度、章节指标和同比信息。",
        "constraints": ["保留地区与年度", "指标名称尽量规范", "同比变化与原值分离"],
        "few_shot_examples": [
            {"input": "常住人口98.7万人", "output": "indicator=常住人口, value=98.7, unit=万人"},
        ],
    },
    "record_dense": {
        "system": "你是通用记录抽取助手，优先保留高密度数值线索。",
        "constraints": ["先抓数值句", "保留时间和地点提示", "来源句必须可回溯"],
        "few_shot_examples": [],
    },
    "field_mapping": {
        "system": "你是字段映射助手，适合键值对、说明文、表单型文本。",
        "constraints": ["优先映射字段和值", "不要把长段解释误当字段值", "字段空值不要输出"],
        "few_shot_examples": [],
    },
}

SUMMARY_PROMPTS = {
    "tabular_precision": {
        "system": "你是数据摘要助手，根据已抽取的表格记录输出 overview sheet 所需摘要。",
        "constraints": ["只引用已抽取结果", "总结数据规模、字段主题和子表结构", "避免生成未出现的结论"],
    },
    "report_sectioned": {
        "system": "你是报告摘要助手，根据章节和记录生成简明的文档总览。",
        "constraints": ["优先总结章节结构、关键指标和风险提示", "避免重复原文", "保持事实一致"],
    },
    "report_statistical_brief": {
        "system": "你是统计公报摘要助手，适合生成总表里的总体摘要和核心发现。",
        "constraints": ["突出地区、年度、重点统计指标和增长情况", "避免臆断趋势原因"],
    },
    "record_dense": {
        "system": "你是结构化记录摘要助手，根据明细记录输出 overview 摘要。",
        "constraints": ["按记录和分类子表总结", "优先总结高频指标与分类结构"],
    },
    "field_mapping": {
        "system": "你是字段摘要助手，根据字段和键值生成结构化总览。",
        "constraints": ["突出字段数量、关键字段和校验提示", "避免将备注当结论"],
    },
}

REPORT_PIPELINE_PROMPTS = {
    "facts_extraction": {
        "system": "你是统计分析事实抽取助手。请从结构化数据中提取可用于正式统计分析报告的事实，不要生成报告正文。",
        "constraints": [
            "只抽取事实，不写评论性报告正文",
            "禁止输出记录数、字段说明、样例记录、JSON/schema 描述",
            "按 topics 输出 summary_metric、breakdowns、time_series、anomalies、insights",
            "尽量覆盖绝大部分有效事实，不要只保留少量摘要性指标",
            "每条事实尽量包含指标名、时期、对象或地区、单位、变化和来源依据",
            "如果缺少时间、地点、对象限定，不要把单个数值直接写成独立事实句",
        ],
        "output_contract": {
            "title": "str",
            "period": "str",
            "domain": "str",
            "topics": [
                {
                    "name": "str",
                    "summary_metric": "list",
                    "breakdowns": "list",
                    "time_series": "list",
                    "anomalies": "list",
                    "insights": "list",
                }
            ],
        },
        "forbidden": ["该数据集包含", "共有xx条记录", "字段包括", "JSON", "schema", "样例数据"],
    },
    "report_planning": {
        "system": "你是统计分析报告规划助手。请根据 facts schema 设计正式报告提纲和图表规划，不要直接写整篇报告。",
        "constraints": [
            "输出章节顺序、每章关注指标、写作重点、图表插入位置",
            "每章优先覆盖所属专题中的大部分关键事实，而非只列2至3个指标",
            "专题顺序优先贴近原始材料或数据出现顺序",
            "必要时在章内按专题设置小标题，便于承载更多事实",
            "图表仅在明显提升理解时生成",
            "时间序列优先折线图，横向对比优先柱状图，默认不生成饼图",
        ],
        "output_contract": {
            "sections": [
                {
                    "title": "str",
                    "purpose": "str",
                    "topic_refs": "list[str]",
                    "focus_metrics": "list",
                    "chart_specs": "list",
                }
            ],
            "charts": "list[chart_spec]",
        },
        "forbidden": ["字段说明", "数据清洗说明", "样例记录展示"],
    },
    "report_writing": {
        "system": "你是正式统计分析报告撰稿助手。请根据 facts schema 和 report plan 输出正式、简洁、书面化的统计分析报告正文。",
        "constraints": [
            "语言风格参照政府统计公报、经济运行简报、行业监测分析报告",
            "按专题分段，优先写核心指标、同比/环比、结构拆分、亮点或异常",
            "正文应覆盖绝大部分有效事实，先完整展开，再做少量归纳，不要只写概括句",
            "在信息量较大时，可在章节内部按专题设置小标题并分段展开",
            "每个数值句都应尽量交代时间、地区、对象或类别，避免出现孤立数值句",
            "对于重复或高度相近的风险提示，应合并表达，避免机械重复",
            "允许使用同比增长、比上年同期、分地区看、分行业看、其中、总体保持、呈现趋势等表达",
            "严禁出现记录数、字段名、样例记录、JSON、schema、技术口吻说明",
        ],
        "forbidden": ["该数据集包含", "共有xx条记录", "字段包括", "JSON", "schema", "下面根据数据进行分析"],
    },
    "chart_decision": {
        "system": "你是报告图表决策助手。请根据 facts schema 判断哪些指标应生成图表，并输出统一 chart_spec。",
        "constraints": [
            "时间点连续且不少于4个时优先折线图",
            "同一时点多类别对比优先柱状图",
            "图表不能明显提升理解时输出 none",
            "标题必须可直接用于正式报告",
        ],
        "output_contract": {
            "type": "line|bar|none",
            "title": "str",
            "x_field": "str",
            "y_field": "str",
            "series": "list",
            "reason": "str",
        },
        "forbidden": ["默认输出饼图", "生成技术说明"],
    },
}

SELF_CHECK_PROMPT = {
    "system": "你是结果一致性检查助手，请核对摘要与明细记录、子表数量、关键字段是否一致。",
    "checks": ["摘要中的记录数是否与明细一致", "子表数量与 detail_groups 是否一致", "标题、地区、年度是否缺失"],
}


class PromptRegistry:
    def __init__(self, prompt_version: str = "cn_v1", enable_self_check: bool = True) -> None:
        self.prompt_version = prompt_version or "cn_v1"
        self.enable_self_check = enable_self_check

    def build_detail_prompt_plan(
        self,
        document: dict[str, Any],
        preprocessing: dict[str, Any],
        routing_plan: dict[str, Any],
    ) -> dict[str, Any]:
        profile = routing_plan.get("prompt_profile", "record_dense")
        template = DETAIL_PROMPTS.get(profile, DETAIL_PROMPTS["record_dense"])
        return {
            "detail": {
                "version": self.prompt_version,
                "profile": profile,
                "system_prompt": template["system"],
                "constraints": template.get("constraints", []),
                "few_shot_examples": template.get("few_shot_examples", []),
                "context_outline": self._detail_context_outline(document, preprocessing),
                "prompt_preview": self._detail_prompt_preview(document, preprocessing, routing_plan, template),
            }
        }

    def build_summary_prompt_plan(
        self,
        structured_data: dict[str, Any],
        canonical_data: dict[str, Any],
        routing_plan: dict[str, Any],
        preprocessing: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        profile = routing_plan.get("prompt_profile", "record_dense")
        template = SUMMARY_PROMPTS.get(profile, SUMMARY_PROMPTS["record_dense"])
        result = {
            "summary": {
                "version": self.prompt_version,
                "profile": profile,
                "system_prompt": template["system"],
                "constraints": template.get("constraints", []),
                "context_outline": self._summary_context_outline(structured_data, canonical_data, preprocessing),
                "prompt_preview": self._summary_prompt_preview(structured_data, canonical_data, template),
            }
        }
        if self.enable_self_check:
            result["self_check"] = {
                "version": self.prompt_version,
                "system_prompt": SELF_CHECK_PROMPT["system"],
                "checks": SELF_CHECK_PROMPT["checks"],
            }
        return result

    def build_report_generation_prompt_plan(
        self,
        context: dict[str, Any],
        facts_schema: dict[str, Any],
        report_plan: dict[str, Any],
        chart_specs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "facts_extraction": self._report_stage_prompt("facts_extraction", context, facts_schema=facts_schema),
            "report_planning": self._report_stage_prompt(
                "report_planning",
                context,
                facts_schema=facts_schema,
                report_plan=report_plan,
                chart_specs=chart_specs,
            ),
            "report_writing": self._report_stage_prompt(
                "report_writing",
                context,
                facts_schema=facts_schema,
                report_plan=report_plan,
                chart_specs=chart_specs,
            ),
            "chart_decision": self._report_stage_prompt(
                "chart_decision",
                context,
                facts_schema=facts_schema,
                report_plan=report_plan,
                chart_specs=chart_specs,
            ),
        }

    def _report_stage_prompt(
        self,
        stage_name: str,
        context: dict[str, Any],
        facts_schema: dict[str, Any] | None = None,
        report_plan: dict[str, Any] | None = None,
        chart_specs: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        template = REPORT_PIPELINE_PROMPTS[stage_name]
        return {
            "version": self.prompt_version,
            "stage": stage_name,
            "system_prompt": template["system"],
            "constraints": template.get("constraints", []),
            "forbidden": template.get("forbidden", []),
            "output_contract": template.get("output_contract", {}),
            "context_outline": {
                "title": context.get("title", ""),
                "period": context.get("period") or context.get("year") or context.get("publish_date", ""),
                "domain": (context.get("domain_tags") or [context.get("document_type", "")])[:3],
                "topic_count": len((facts_schema or {}).get("topics", [])),
                "planned_section_count": len((report_plan or {}).get("sections", [])),
                "chart_candidate_count": len(chart_specs or []),
            },
        }

    def _detail_context_outline(self, document: dict[str, Any], preprocessing: dict[str, Any]) -> dict[str, Any]:
        metadata = document.get("metadata", {}) if isinstance(document.get("metadata"), dict) else {}
        signals = preprocessing.get("signals", {}) if isinstance(preprocessing, dict) else {}
        stats = preprocessing.get("stats", {}) if isinstance(preprocessing, dict) else {}
        return {
            "title": metadata.get("title", ""),
            "source_type": document.get("type", "unknown"),
            "chunk_count": stats.get("chunk_count", 0),
            "section_titles": signals.get("section_titles", [])[:8],
            "domain_candidates": signals.get("domain_candidates", [])[:3],
            "measurement_candidates": signals.get("measurement_candidates", [])[:8],
        }

    def _summary_context_outline(
        self,
        structured_data: dict[str, Any],
        canonical_data: dict[str, Any],
        preprocessing: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        document_meta = canonical_data.get("document_meta", {}) if isinstance(canonical_data.get("document_meta"), dict) else {}
        detail_groups = structured_data.get("detail_groups", {}) if isinstance(structured_data.get("detail_groups"), dict) else {}
        return {
            "title": document_meta.get("title") or structured_data.get("title", ""),
            "document_type": structured_data.get("document_type", "unknown"),
            "record_count": structured_data.get("record_count", len(structured_data.get("records", []))),
            "indicator_count": len(structured_data.get("indicators", [])) if isinstance(structured_data.get("indicators"), list) else 0,
            "section_count": len(structured_data.get("sections", [])) if isinstance(structured_data.get("sections"), list) else 0,
            "detail_sheet_count": len(detail_groups.get("groups", [])) if isinstance(detail_groups.get("groups"), list) else 0,
            "preprocessing_chunk_count": (preprocessing or {}).get("stats", {}).get("chunk_count", 0),
        }

    def _detail_prompt_preview(
        self,
        document: dict[str, Any],
        preprocessing: dict[str, Any],
        routing_plan: dict[str, Any],
        template: dict[str, Any],
    ) -> str:
        metadata = document.get("metadata", {}) if isinstance(document.get("metadata"), dict) else {}
        chunks = preprocessing.get("chunks", []) if isinstance(preprocessing, dict) else []
        preview_chunks = [chunk.get("text_preview", "") for chunk in chunks[:3] if chunk.get("text_preview")]
        instructions = "；".join(template.get("constraints", []))
        return (
            f"任务: 按 {routing_plan.get('combination_mode', 'detail_extract')} 提取结构化明细。\n"
            f"标题: {metadata.get('title', '')}\n"
            f"约束: {instructions}\n"
            f"上下文片段: {' || '.join(preview_chunks)}"
        )[:1200]

    def _summary_prompt_preview(
        self,
        structured_data: dict[str, Any],
        canonical_data: dict[str, Any],
        template: dict[str, Any],
    ) -> str:
        document_meta = canonical_data.get("document_meta", {}) if isinstance(canonical_data.get("document_meta"), dict) else {}
        sections = structured_data.get("sections", []) if isinstance(structured_data.get("sections"), list) else []
        findings = []
        for section in sections[:3]:
            title = section.get("title", "")
            content = str(section.get("content", "")).strip()[:80]
            findings.append(f"{title}: {content}")
        instructions = "；".join(template.get("constraints", []))
        return (
            f"任务: 为 overview sheet 生成摘要。\n"
            f"标题: {document_meta.get('title') or structured_data.get('title', '')}\n"
            f"记录数: {structured_data.get('record_count', len(structured_data.get('records', [])))}\n"
            f"约束: {instructions}\n"
            f"章节线索: {' || '.join(findings)}"
        )[:1200]
