from __future__ import annotations

import html
import json
import os
import sys
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from config.config import (
        DETAIL_MODEL,
        ENABLE_POSTPROCESSING,
        ENABLE_PREPROCESSING,
        ENABLE_PROMPT_OPTIMIZATION,
        MAX_FILE_SIZE,
        OUTPUT_DIR,
        ROUTER_MODEL,
        SEMANTIC_MODEL,
        SUMMARY_MODEL,
        SUPPORTED_FORMATS,
        UPLOAD_DIR,
    )
    from components.chart_renderer import ChartRenderer
    from components.task_planner import TaskPlanner
except ImportError:
    from doc_processing.config.config import (
        DETAIL_MODEL,
        ENABLE_POSTPROCESSING,
        ENABLE_PREPROCESSING,
        ENABLE_PROMPT_OPTIMIZATION,
        MAX_FILE_SIZE,
        OUTPUT_DIR,
        ROUTER_MODEL,
        SEMANTIC_MODEL,
        SUMMARY_MODEL,
        SUPPORTED_FORMATS,
        UPLOAD_DIR,
    )
    from doc_processing.components.chart_renderer import ChartRenderer
    from doc_processing.components.task_planner import TaskPlanner


NATURAL_INPUT_FORMATS = [item for item in SUPPORTED_FORMATS if item != ".json"]
STRUCTURED_INPUT_FORMATS = [".json", ".xlsx"]
MODE_OPTIONS = [
    "文档/自然语言 -> 结构化",
    "结构化数据 -> 调查报告",
]
MODE_CARD_CONTENT = {
    "文档/自然语言 -> 结构化": {
        "title": "统一结构化入口",
        "tag": "文件 + 文本",
        "description": "把文档文件上传和自然语言粘贴合并到一个入口里，统一做结构化抽取、摘要主表和分类子表生成。",
        "highlights": ["同时支持上传文件与粘贴文本", "统一输出摘要主表和分类子表", "适合报告、公报、说明文和原始材料"],
    },
    "结构化数据 -> 调查报告": {
        "title": "调查报告生成",
        "tag": "报告输出",
        "description": "把结构化 JSON 或 Excel 重新组织成更像调查报告、分析稿和情况说明的非结构化文本。",
        "highlights": ["输出更接近调查报告体", "自动生成基本情况、主要发现和结论建议", "支持 JSON 与 Excel 双入口"],
    },
}

PIPELINE_STEPS = [
    ("预处理", "清洗文本、识别章节和数值线索，为后续抽取准备稳定输入。"),
    ("模型路由", "根据文档类型和领域信号，选择明细模型、摘要模型和提示模板。"),
    ("结果生成", "分别生成摘要主表与详细子表，并执行提示词自检与字段对齐。"),
    ("导出交付", "统一输出 JSON、Excel、Word、TXT、PDF，并保留处理链路信息。"),
]

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
CHART_RENDERER = ChartRenderer(output_dir=OUTPUT_DIR)


def format_mode_label(mode: str) -> str:
    labels = {
        "natural_to_structured": "文档/自然语言 -> 结构化",
        "structured_to_natural": "结构化数据 -> 调查报告",
    }
    return labels.get(mode, mode or "unknown")



def format_document_type_label(document_type: str | None) -> str:
    labels = {
        "tabular_dataset": "表格数据集",
        "report_document": "报告文档",
        "key_value_document": "字段文档",
        "plain_text_document": "纯文本",
    }
    return labels.get(document_type or "", document_type or "")



def format_metric_type_label(metric_type: str | None) -> str:
    labels = {
        "value": "数值",
        "ratio": "比例",
        "growth_rate": "增速",
        "change_value": "变动量",
        "attribute": "属性",
        "date": "日期",
    }
    return labels.get(metric_type or "", metric_type or "")



def format_record_type_label(record_type: str | None) -> str:
    labels = {
        "measurement": "度量",
        "attribute": "属性",
    }
    return labels.get(record_type or "", record_type or "")



def format_file_size(size: int | None) -> str:
    if size is None:
        return ""
    value = float(size)
    units = ["B", "KB", "MB", "GB"]
    unit_index = 0
    while value >= 1024 and unit_index < len(units) - 1:
        value /= 1024
        unit_index += 1
    if unit_index == 0:
        return f"{int(value)} {units[unit_index]}"
    return f"{value:.1f} {units[unit_index]}"



def count_ready_outputs(output_files: dict[str, Any]) -> int:
    ready = 0
    for file_info in output_files.values():
        path = file_info.get("path", "") if isinstance(file_info, dict) else ""
        if path and os.path.exists(path):
            ready += 1
    return ready



def html_escape_text(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)



def build_pipeline_glance_cards(pipeline_summary: dict[str, Any]) -> list[dict[str, str]]:
    semantic = pipeline_summary.get("semantic", {}) if isinstance(pipeline_summary.get("semantic"), dict) else {}
    routing = semantic.get("routing", {}) if isinstance(semantic.get("routing"), dict) else {}
    preprocessing = semantic.get("preprocessing", {}) if isinstance(semantic.get("preprocessing"), dict) else {}
    prompting = semantic.get("prompting", {}) if isinstance(semantic.get("prompting"), dict) else {}
    postprocessing = semantic.get("postprocessing", {}) if isinstance(semantic.get("postprocessing"), dict) else {}
    detail_groups = semantic.get("detail_groups", {}) if isinstance(semantic.get("detail_groups"), dict) else {}
    stats = preprocessing.get("stats", {}) if isinstance(preprocessing.get("stats"), dict) else {}
    detail_prompt = prompting.get("detail", {}) if isinstance(prompting.get("detail"), dict) else {}
    validation = pipeline_summary.get("validation", {}) if isinstance(pipeline_summary.get("validation"), dict) else {}
    return [
        {
            "label": "路由策略",
            "value": str(routing.get("prompt_profile") or "standard"),
            "copy": str(routing.get("document_type_hint") or "未识别类型"),
        },
        {
            "label": "组合模式",
            "value": str(routing.get("combination_mode") or "基础流程"),
            "copy": str(detail_prompt.get("profile") or "未设置模板"),
        },
        {
            "label": "预处理分块",
            "value": str(stats.get("chunk_count", 0)),
            "copy": f"章节 {stats.get('section_count', 0)} · 表格 {stats.get('table_count', 0)}",
        },
        {
            "label": "结果整理",
            "value": str(postprocessing.get("duplicates_removed", 0)),
            "copy": "已通过" if validation.get("is_valid", False) else "需人工复核",
        },
        {
            "label": "分类子表",
            "value": str(len(detail_groups.get("groups", [])) if isinstance(detail_groups.get("groups"), list) else 0),
            "copy": str(semantic.get("document_summary", {}).get("prompt_version") or "提示未记录"),
        },
    ]



def build_result_metrics(structured_data: dict[str, Any], validation: dict[str, Any], output_files: dict[str, Any]) -> list[tuple[str, str]]:
    document_type = format_document_type_label(structured_data.get("document_type")) or "未识别"
    record_count = structured_data.get("record_count", len(structured_data.get("records", [])))
    validation_label = "通过" if validation.get("is_valid", False) else "需关注"
    detail_groups = structured_data.get("detail_groups", {}) if isinstance(structured_data.get("detail_groups"), dict) else {}
    detail_sheet_count = len(detail_groups.get("groups", [])) if isinstance(detail_groups.get("groups"), list) else 0
    extra_label = "字段数"
    extra_value = "0"

    if structured_data.get("document_type") == "tabular_dataset":
        extra_label = "数据表"
        extra_value = str(structured_data.get("dataset_count", 0))
    elif detail_sheet_count:
        extra_label = "子表数"
        extra_value = str(detail_sheet_count)
    elif structured_data.get("document_type") == "report_document":
        extra_label = "章节数"
        extra_value = str(len(structured_data.get("sections", [])))
    elif structured_data.get("document_type") == "key_value_document":
        fields = structured_data.get("fields", {}) or structured_data.get("key_values", {})
        extra_label = "字段数"
        extra_value = str(len(fields))
    else:
        extra_label = "输出数"
        extra_value = str(count_ready_outputs(output_files))

    return [
        ("文档类型", document_type),
        ("记录数量", str(record_count)),
        (extra_label, extra_value),
        ("校验结果", validation_label),
    ]



def build_document_overview_cards(pipeline_summary: dict[str, Any]) -> list[dict[str, str]]:
    semantic = pipeline_summary.get("semantic", {}) if isinstance(pipeline_summary.get("semantic"), dict) else {}
    structured = semantic.get("structured_data", {}) if isinstance(semantic.get("structured_data"), dict) else {}
    summary = semantic.get("document_summary", {}) if isinstance(semantic.get("document_summary"), dict) else {}
    detail_groups = semantic.get("detail_groups", {}) if isinstance(semantic.get("detail_groups"), dict) else {}
    group_list = detail_groups.get("groups", []) if isinstance(detail_groups.get("groups"), list) else []
    domain_tags = summary.get("domain_tags") or structured.get("domain_tags", [])
    return [
        {
            "label": "摘要主表",
            "value": str(summary.get("title") or structured.get("title") or "未命名文档"),
            "copy": str(summary.get("document_type") or structured.get("document_type") or "unknown"),
        },
        {
            "label": "明细记录",
            "value": str(summary.get("record_count", structured.get("record_count", 0))),
            "copy": f"指标 {summary.get('indicator_count', 0)} · 章节 {summary.get('section_count', 0)}",
        },
        {
            "label": "分类子表",
            "value": str(len(group_list)),
            "copy": str(group_list[0].get("sheet_name") if group_list else "未生成子表"),
        },
        {
            "label": "文档维度",
            "value": str(summary.get("region") or structured.get("region") or "未识别地区"),
            "copy": str(summary.get("year") or structured.get("year") or "未识别年份"),
        },
        {
            "label": "主题领域",
            "value": " / ".join(str(tag) for tag in domain_tags[:2]) if domain_tags else "通用",
            "copy": str(summary.get("prompt_version") or "未记录提示版本"),
        },
    ]



def render_document_overview(pipeline_summary: dict[str, Any]) -> None:
    cards = build_document_overview_cards(pipeline_summary)
    markup = "".join(
        (
            '<div class="overview-card">'
            f'<span class="overview-label">{html_escape_text(card["label"])}</span>'
            f'<span class="overview-value">{html_escape_text(card["value"])}</span>'
            f'<span class="overview-copy">{html_escape_text(card["copy"])}</span>'
            '</div>'
        )
        for card in cards
    )
    st.markdown(f"<div class='overview-grid'>{markup}</div>", unsafe_allow_html=True)



def build_delivery_cards(output_files: dict[str, Any]) -> list[dict[str, str]]:
    cards = []
    format_labels = {
        "json": "JSON",
        "excel": "Excel",
        "word": "Word",
        "text": "TXT",
        "pdf": "PDF",
    }
    status_labels = {
        "ready": "已生成",
        "error": "失败",
        "pending": "待生成",
    }
    for key, label in format_labels.items():
        file_info = output_files.get(key, {}) if isinstance(output_files.get(key), dict) else {}
        file_path = file_info.get("path", "")
        exists = bool(file_path and os.path.exists(file_path))
        status = "ready" if exists else "error" if file_info.get("error") else "pending"
        cards.append(
            {
                "label": label,
                "status": status,
                "status_label": status_labels.get(status, status),
                "copy": format_file_size(file_info.get("size") or (os.path.getsize(file_path) if exists else None)) or "未生成",
                "path": os.path.basename(file_path) if exists else str(file_info.get("error") or "待生成"),
            }
        )
    return cards



def render_delivery_panel(output_files: dict[str, Any]) -> None:
    cards = build_delivery_cards(output_files)
    markup = "".join(
        (
            f'<div class="delivery-card delivery-{html_escape_text(card["status"])}">'
            f'<span class="delivery-label">{html_escape_text(card["label"])}</span>'
            f'<span class="delivery-status">{html_escape_text(card["status_label"])}</span>'
            f'<span class="delivery-copy">{html_escape_text(card["copy"])}</span>'
            f'<span class="delivery-path">{html_escape_text(card["path"])}</span>'
            '</div>'
        )
        for card in cards
    )
    st.markdown(f"<div class='delivery-grid'>{markup}</div>", unsafe_allow_html=True)



def render_pipeline_glance(pipeline_summary: dict[str, Any]) -> None:
    cards = build_pipeline_glance_cards(pipeline_summary)
    markup = "".join(
        (
            '<div class="glance-card">'
            f'<span class="glance-label">{html_escape_text(card["label"])}</span>'
            f'<span class="glance-value">{html_escape_text(card["value"])}</span>'
            f'<span class="glance-copy">{html_escape_text(card["copy"])}</span>'
            '</div>'
        )
        for card in cards
    )
    st.markdown(f"<div class='glance-grid'>{markup}</div>", unsafe_allow_html=True)



def render_summary_panel(title: str, content: str) -> None:
    lines = [line.strip() for line in str(content or "").splitlines() if line.strip()]
    if not lines:
        lines = ["当前没有可展示的摘要内容。"]
    body = "".join(f"<p>{html_escape_text(line)}</p>" for line in lines)
    st.markdown(
        (
            '<div class="summary-shell">'
            f'<span class="summary-eyebrow">{html_escape_text(title)}</span>'
            f'{body}'
            '</div>'
        ),
        unsafe_allow_html=True,
    )



def render_pipeline_preview(pipeline_summary: dict[str, Any]) -> None:
    semantic = pipeline_summary.get("semantic", {}) if isinstance(pipeline_summary.get("semantic"), dict) else {}
    routing = semantic.get("routing", {}) if isinstance(semantic.get("routing"), dict) else {}
    preprocessing = semantic.get("preprocessing", {}) if isinstance(semantic.get("preprocessing"), dict) else {}
    prompting = semantic.get("prompting", {}) if isinstance(semantic.get("prompting"), dict) else {}
    postprocessing = semantic.get("postprocessing", {}) if isinstance(semantic.get("postprocessing"), dict) else {}
    validation = pipeline_summary.get("validation", {}) if isinstance(pipeline_summary.get("validation"), dict) else {}

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("#### 路由与预处理")
        st.json(
            {
                "models": semantic.get("models", {}),
                "routing": routing,
                "preprocessing": {
                    "stats": preprocessing.get("stats", {}),
                    "signals": preprocessing.get("signals", {}),
                },
            },
            expanded=False,
        )
    with right:
        st.markdown("#### 提示词与后处理")
        st.json(
            {
                "prompting": prompting,
                "postprocessing": postprocessing,
                "validation": validation,
            },
            expanded=False,
        )



def format_structured_summary(pipeline_summary: dict[str, Any]) -> str:
    semantic = pipeline_summary.get("semantic", {}) if isinstance(pipeline_summary.get("semantic", {}), dict) else {}
    structured = semantic.get("structured_data", {})
    canonical = semantic.get("canonical_data", {})
    validation = pipeline_summary.get("validation", {})
    routing = semantic.get("routing", {}) if isinstance(semantic.get("routing"), dict) else {}
    preprocessing = semantic.get("preprocessing", {}) if isinstance(semantic.get("preprocessing"), dict) else {}
    prompting = semantic.get("prompting", {}) if isinstance(semantic.get("prompting"), dict) else {}
    postprocessing = semantic.get("postprocessing", {}) if isinstance(semantic.get("postprocessing"), dict) else {}
    document_summary = semantic.get("document_summary", {}) if isinstance(semantic.get("document_summary"), dict) else {}
    if not document_summary and isinstance(structured.get("document_summary"), dict):
        document_summary = structured.get("document_summary", {})
    document_meta = canonical.get("document_meta", {}) if isinstance(canonical.get("document_meta"), dict) else {}
    detail_groups = semantic.get("detail_groups", {}) if isinstance(semantic.get("detail_groups"), dict) else {}
    if not detail_groups and isinstance(structured.get("detail_groups"), dict):
        detail_groups = structured.get("detail_groups", {})

    lines = [
        f"转换模式: {format_mode_label(pipeline_summary.get('operation_mode', 'natural_to_structured'))}",
        f"文档类型: {format_document_type_label(structured.get('document_type')) or 'unknown'}",
    ]

    if semantic.get("router_model") or document_summary.get("router_model"):
        lines.append(f"路由模型: {semantic.get('router_model') or document_summary.get('router_model')}")
    if document_summary.get("summary_model"):
        lines.append(f"摘要模型: {document_summary['summary_model']}")
    if document_summary.get("detail_model"):
        lines.append(f"明细模型: {document_summary['detail_model']}")
    if document_summary.get("prompt_version"):
        lines.append(f"提示版本: {document_summary['prompt_version']}")
    if routing.get("prompt_profile"):
        lines.append(f"路由策略: {routing.get('prompt_profile')}")
    if routing.get("combination_mode"):
        lines.append(f"组合模式: {routing.get('combination_mode')}")
    chunk_count = preprocessing.get("stats", {}).get("chunk_count", 0) if isinstance(preprocessing.get("stats"), dict) else 0
    if chunk_count:
        lines.append(f"预处理分块数: {chunk_count}")
    if postprocessing.get("duplicates_removed"):
        lines.append(f"后处理去重数: {postprocessing.get('duplicates_removed')}")

    overall_summary = document_summary.get("overall_summary")
    if overall_summary:
        lines.append(f"总体摘要: {overall_summary}")

    title = document_summary.get("title") or document_meta.get("title") or structured.get("title")
    if title:
        lines.append(f"标题: {title}")
    domain_tags = document_summary.get("domain_tags") or structured.get("domain_tags", []) or document_meta.get("domain_tags", [])
    if domain_tags:
        lines.append(f"行业标签: {', '.join(str(tag) for tag in domain_tags)}")
    if document_summary.get("region") or document_meta.get("region"):
        lines.append(f"地区: {document_summary.get('region') or document_meta.get('region')}")
    if document_summary.get("year") or document_meta.get("year"):
        lines.append(f"年度: {document_summary.get('year') or document_meta.get('year')}")
    if document_summary.get("publish_date") or document_meta.get("publish_date"):
        lines.append(f"发布日期: {document_summary.get('publish_date') or document_meta.get('publish_date')}")

    detail_sheet_count = len(detail_groups.get("groups", [])) if isinstance(detail_groups.get("groups"), list) else 0
    if detail_sheet_count:
        lines.append(f"分类子表数: {detail_sheet_count}")

    if document_summary.get("record_count") is not None:
        lines.append(f"记录数: {document_summary.get('record_count')}")
    if document_summary.get("indicator_count"):
        lines.append(f"指标数: {document_summary.get('indicator_count')}")
    if document_summary.get("section_count"):
        lines.append(f"章节数: {document_summary.get('section_count')}")
    if document_summary.get("dataset_count"):
        lines.append(f"数据表数: {document_summary.get('dataset_count')}")

    for index, finding in enumerate(document_summary.get("key_findings", [])[:5], start=1):
        lines.append(f"发现{index}: {finding}")

    lines.append(f"校验通过: {validation.get('is_valid', False)}")
    detail_prompt = prompting.get("detail", {}) if isinstance(prompting.get("detail"), dict) else {}
    summary_prompt = prompting.get("summary", {}) if isinstance(prompting.get("summary"), dict) else {}
    if detail_prompt.get("profile"):
        lines.append(f"明细提示模板: {detail_prompt.get('profile')}")
    if summary_prompt.get("profile"):
        lines.append(f"摘要提示模板: {summary_prompt.get('profile')}")
    issues = document_summary.get("validation_issues", []) or validation.get("issues", [])
    for issue in issues[:5]:
        lines.append(f"问题: {issue}")
    if postprocessing.get("error"):
        lines.append(f"后处理异常: {postprocessing.get('error')}")
    return "\n".join(lines)


def inject_page_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --page-bg: #f5f1e8;
            --panel-bg: rgba(255, 252, 246, 0.88);
            --panel-strong: #fffdf8;
            --line: #d8d0c1;
            --text: #1f332d;
            --muted: #61716b;
            --accent: #1f5c4d;
            --accent-soft: #dcebe5;
            --accent-warm: #94673a;
            --shadow: 0 10px 30px rgba(39, 49, 45, 0.08);
            --radius-lg: 22px;
            --radius-md: 16px;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(223, 235, 229, 0.85), transparent 30%),
                radial-gradient(circle at top right, rgba(242, 231, 212, 0.8), transparent 28%),
                linear-gradient(180deg, #f8f5ee 0%, var(--page-bg) 100%);
            color: var(--text);
        }

        .main .block-container {
            max-width: 1240px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }

        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #f3ede2 0%, #eee6d8 100%);
            border-right: 1px solid rgba(148, 132, 109, 0.16);
        }

        .hero-shell {
            padding: 1.5rem 1.6rem;
            border: 1px solid rgba(148, 132, 109, 0.18);
            background: linear-gradient(135deg, rgba(255, 252, 246, 0.95), rgba(244, 238, 228, 0.88));
            border-radius: 28px;
            box-shadow: var(--shadow);
            margin-bottom: 1.2rem;
        }

        .hero-kicker {
            display: inline-block;
            padding: 0.28rem 0.7rem;
            border-radius: 999px;
            background: var(--accent-soft);
            color: var(--accent);
            font-size: 0.8rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }

        .hero-title {
            margin: 0.85rem 0 0.35rem;
            font-size: 2.4rem;
            line-height: 1.1;
            color: var(--text);
        }

        .hero-copy {
            margin: 0;
            max-width: 760px;
            color: var(--muted);
            font-size: 1rem;
            line-height: 1.7;
        }

        .hero-grid,
        .mode-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.9rem;
            margin-top: 1.25rem;
        }

        .hero-card,
        .mode-card,
        .section-card,
        .result-banner {
            border: 1px solid rgba(148, 132, 109, 0.16);
            background: var(--panel-bg);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow);
        }

        .hero-card {
            padding: 1rem 1rem 0.95rem;
        }

        .hero-label {
            display: block;
            color: var(--muted);
            font-size: 0.82rem;
            margin-bottom: 0.35rem;
        }

        .hero-value {
            display: block;
            color: var(--text);
            font-size: 1.35rem;
            font-weight: 700;
            line-height: 1.2;
        }

        .hero-subvalue {
            display: block;
            margin-top: 0.25rem;
            color: var(--muted);
            font-size: 0.86rem;
        }

        .mode-card {
            padding: 1rem;
            min-height: 128px;
        }

        .mode-card h3 {
            margin: 0 0 0.45rem;
            font-size: 1.02rem;
            color: var(--text);
        }

        .mode-card p {
            margin: 0;
            color: var(--muted);
            line-height: 1.65;
            font-size: 0.94rem;
        }

        .mode-card.active {
            background: linear-gradient(145deg, rgba(234, 243, 239, 0.96), rgba(255, 252, 246, 0.94));
            border-color: rgba(31, 92, 77, 0.2);
            transform: translateY(-2px);
        }

        .mode-tag,
        .summary-eyebrow,
        .workflow-index {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: 999px;
            padding: 0.24rem 0.68rem;
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            background: rgba(31, 92, 77, 0.1);
            color: var(--accent);
        }

        .mode-points {
            margin: 0.8rem 0 0;
            padding-left: 1rem;
            color: var(--muted);
            line-height: 1.65;
        }

        .workflow-shell,
        .glance-grid,
        .overview-grid,
        .delivery-grid {
            display: grid;
            gap: 0.9rem;
        }

        .workflow-shell {
            grid-template-columns: repeat(4, minmax(0, 1fr));
            margin-top: 1.3rem;
        }

        .workflow-step,
        .glance-card,
        .overview-card,
        .delivery-card,
        .summary-shell {
            border: 1px solid rgba(148, 132, 109, 0.16);
            border-radius: 20px;
            background: rgba(255, 252, 246, 0.82);
            box-shadow: var(--shadow);
        }

        .workflow-step {
            padding: 1rem 1rem 1.05rem;
        }

        .workflow-title {
            display: block;
            margin-top: 0.8rem;
            font-size: 1rem;
            font-weight: 700;
            color: var(--text);
        }

        .workflow-copy {
            display: block;
            margin-top: 0.35rem;
            color: var(--muted);
            font-size: 0.9rem;
            line-height: 1.65;
        }

        .glance-grid {
            grid-template-columns: repeat(5, minmax(0, 1fr));
            margin: 1rem 0 1.2rem;
        }

        .overview-grid {
            grid-template-columns: 1fr;
            margin-bottom: 1rem;
        }

        .delivery-grid {
            grid-template-columns: repeat(5, minmax(0, 1fr));
            margin-bottom: 1rem;
        }

        .glance-card,
        .overview-card,
        .delivery-card {
            padding: 0.95rem 1rem;
        }

        .glance-label {
            display: block;
            color: var(--muted);
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .glance-value {
            display: block;
            margin-top: 0.35rem;
            color: var(--text);
            font-size: 1.18rem;
            font-weight: 700;
        }

        .glance-copy {
            display: block;
            margin-top: 0.35rem;
            color: var(--muted);
            font-size: 0.86rem;
            line-height: 1.6;
        }

        .overview-label,
        .delivery-label {
            display: block;
            color: var(--muted);
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .overview-value,
        .delivery-status {
            display: block;
            margin-top: 0.32rem;
            color: var(--text);
            font-size: 1.1rem;
            font-weight: 700;
        }

        .overview-copy,
        .delivery-copy,
        .delivery-path {
            display: block;
            margin-top: 0.32rem;
            color: var(--muted);
            font-size: 0.86rem;
            line-height: 1.6;
        }

        .delivery-ready {
            background: linear-gradient(145deg, rgba(234, 243, 239, 0.96), rgba(255, 252, 246, 0.94));
            border-color: rgba(31, 92, 77, 0.18);
        }

        .delivery-error {
            background: linear-gradient(145deg, rgba(249, 236, 228, 0.92), rgba(255, 252, 246, 0.94));
            border-color: rgba(148, 103, 58, 0.18);
        }

        .delivery-pending {
            background: linear-gradient(145deg, rgba(247, 242, 232, 0.94), rgba(255, 252, 246, 0.94));
        }

        .summary-shell {
            padding: 1rem 1.1rem;
        }

        .summary-shell p {
            margin: 0.55rem 0 0;
            color: var(--text);
            line-height: 1.75;
        }

        .mode-active {
            margin: 0.95rem 0 1.2rem;
            padding: 0.95rem 1rem;
            border-radius: var(--radius-md);
            border: 1px solid rgba(31, 92, 77, 0.14);
            background: rgba(220, 235, 229, 0.68);
            color: var(--accent);
        }

        .section-card {
            padding: 1.15rem 1.15rem 0.2rem;
            margin-bottom: 1rem;
        }

        .section-card h3 {
            margin: 0;
            font-size: 1.06rem;
            color: var(--text);
        }

        .section-card p {
            margin: 0.45rem 0 0;
            color: var(--muted);
            line-height: 1.65;
        }

        .tip-list {
            margin: 0;
            padding-left: 1rem;
            color: var(--muted);
            line-height: 1.7;
        }

        .result-banner {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            padding: 1rem 1.1rem;
            margin-bottom: 1rem;
        }

        .result-kicker {
            margin: 0 0 0.2rem;
            color: var(--muted);
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .result-title {
            margin: 0;
            font-size: 1.3rem;
            color: var(--text);
        }

        .status-pill {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: 999px;
            padding: 0.4rem 0.8rem;
            font-size: 0.88rem;
            font-weight: 700;
            white-space: nowrap;
        }

        .status-ok {
            background: rgba(31, 92, 77, 0.12);
            color: var(--accent);
        }

        .status-warning {
            background: rgba(148, 103, 58, 0.12);
            color: var(--accent-warm);
        }

        div[data-testid="stMetric"] {
            background: var(--panel-bg);
            border: 1px solid rgba(148, 132, 109, 0.16);
            border-radius: 18px;
            padding: 0.7rem 0.9rem;
            box-shadow: var(--shadow);
        }

        div[data-testid="stMetric"] label,
        div[data-testid="stMetricLabel"] {
            color: var(--muted) !important;
        }

        div[data-testid="stMetricValue"] {
            color: var(--text) !important;
        }

        div[data-testid="stFileUploader"] section {
            border: 1.5px dashed rgba(31, 92, 77, 0.28);
            border-radius: 18px;
            background: rgba(255, 252, 246, 0.8);
        }

        div[data-testid="stTextInput"] input,
        div[data-testid="stTextArea"] textarea {
            border-radius: 16px !important;
            border: 1px solid rgba(148, 132, 109, 0.18) !important;
            background: rgba(255, 252, 246, 0.92) !important;
        }

        div[data-baseweb="select"] > div,
        div[role="radiogroup"] {
            border-radius: 16px;
        }

        .stButton > button,
        .stDownloadButton > button {
            border-radius: 14px;
            border: 1px solid rgba(31, 92, 77, 0.16);
        }

        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #1f5c4d, #2b7764);
            color: white;
            border: none;
        }

        .stDownloadButton > button {
            background: rgba(255, 252, 246, 0.92);
            color: var(--text);
        }

        div[data-testid="stExpander"] {
            border-radius: 18px;
            border: 1px solid rgba(148, 132, 109, 0.16);
            background: rgba(255, 252, 246, 0.74);
            overflow: hidden;
        }

        button[data-baseweb="tab"] {
            border-radius: 999px;
            padding-left: 0.95rem;
            padding-right: 0.95rem;
            background: rgba(255, 252, 246, 0.68);
        }

        button[data-baseweb="tab"][aria-selected="true"] {
            background: rgba(220, 235, 229, 0.96);
            color: var(--accent);
        }

        [data-testid="stDataFrame"] {
            border-radius: 18px;
            overflow: hidden;
            border: 1px solid rgba(148, 132, 109, 0.16);
        }

        .download-note {
            margin-top: 0.3rem;
            color: var(--muted);
            font-size: 0.8rem;
            text-align: center;
        }

        @media (max-width: 960px) {
            .hero-grid,
            .mode-grid,
            .workflow-shell,
            .glance-grid,
            .delivery-grid {
                grid-template-columns: 1fr;
            }

            .hero-title {
                font-size: 2rem;
            }

            .result-banner {
                flex-direction: column;
                align-items: flex-start;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )



def render_page_header() -> None:
    max_file_mb = max(1, MAX_FILE_SIZE // (1024 * 1024))
    workflow_markup = "".join(
        (
            '<div class="workflow-step">'
            f'<span class="workflow-index">0{index}</span>'
            f'<span class="workflow-title">{html_escape_text(title)}</span>'
            f'<span class="workflow-copy">{html_escape_text(description)}</span>'
            '</div>'
        )
        for index, (title, description) in enumerate(PIPELINE_STEPS, start=1)
    )
    st.markdown(
        f"""
        <section class="hero-shell">
            <span class="hero-kicker">Document Processing Studio</span>
            <h1 class="hero-title">文档处理系统</h1>
            <p class="hero-copy">把文档、表格、自然语言文本和结构化数据放到同一个工作台里处理，统一产出结构化结果、调查报告草稿、多模型编排信息和可直接交付的导出文件。</p>
            <div class="hero-grid">
                <div class="hero-card">
                    <span class="hero-label">支持输入</span>
                    <span class="hero-value">{len(SUPPORTED_FORMATS)} 种格式</span>
                    <span class="hero-subvalue">覆盖 Excel、Word、PDF、TXT、JSON</span>
                </div>
                <div class="hero-card">
                    <span class="hero-label">模型编排</span>
                    <span class="hero-value">明细 {DETAIL_MODEL} / 摘要 {SUMMARY_MODEL}</span>
                    <span class="hero-subvalue">路由 {ROUTER_MODEL} · 预处理 {'开' if ENABLE_PREPROCESSING else '关'} · 后处理 {'开' if ENABLE_POSTPROCESSING else '关'} · 提示优化 {'开' if ENABLE_PROMPT_OPTIMIZATION else '关'}</span>
                </div>
                <div class="hero-card">
                    <span class="hero-label">上传限制</span>
                    <span class="hero-value">单文件 {max_file_mb} MB</span>
                    <span class="hero-subvalue">支持批量处理与多格式下载</span>
                </div>
            </div>
            <div class="workflow-shell">{workflow_markup}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )



def render_mode_cards(selected_mode: str) -> None:
    cards = []
    for mode in MODE_OPTIONS:
        card = MODE_CARD_CONTENT[mode]
        highlight_markup = "".join(f"<li>{html_escape_text(item)}</li>" for item in card.get("highlights", []))
        active_class = " active" if mode == selected_mode else ""
        cards.append(
            f"""
            <div class="mode-card{active_class}">
                <span class="mode-tag">{html_escape_text(card.get('tag', ''))}</span>
                <h3>{html_escape_text(card['title'])}</h3>
                <p>{html_escape_text(card['description'])}</p>
                <ul class="mode-points">{highlight_markup}</ul>
            </div>
            """
        )
    st.markdown(f'<div class="mode-grid">{"".join(cards)}</div>', unsafe_allow_html=True)
    selected = MODE_CARD_CONTENT[selected_mode]
    st.markdown(
        f"<div class='mode-active'><strong>当前模式：</strong>{html_escape_text(selected_mode)}<br>{html_escape_text(selected['description'])}</div>",
        unsafe_allow_html=True,
    )



def save_uploaded_file(uploaded_file: Any) -> str:
    file_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
    with open(file_path, "wb") as file:
        file.write(uploaded_file.getbuffer())
    return file_path



def build_report_record_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "章节": record.get("section", ""),
                "记录类型": format_record_type_label(record.get("record_type")),
                "指标名称": record.get("indicator_name", ""),
                "指标类型": format_metric_type_label(record.get("metric_type")),
                "数值": record.get("value", ""),
                "值文本": record.get("value_text", ""),
                "单位": record.get("unit", ""),
                "时间参考": record.get("time_reference", ""),
                "地点参考": record.get("location_reference", ""),
                "同比(%)": record.get("yoy_percent", ""),
                "比较值": record.get("comparison_value", ""),
                "比较单位": record.get("comparison_unit", ""),
                "比较说明": record.get("comparison_text", ""),
                "来源句子": record.get("source_sentence", ""),
            }
            for record in records
        ]
    )



def render_structured_preview(structured_data: dict[str, Any]) -> None:
    document_type = structured_data.get("document_type")

    if document_type == "tabular_dataset":
        datasets = structured_data.get("datasets", [])[:3]
        if not datasets:
            st.caption("当前没有可预览的数据表。")
            return
        if len(datasets) == 1:
            dataset = datasets[0]
            dataframe = pd.DataFrame(dataset.get("records", [])[:80])
            if dataframe.empty:
                st.caption("当前数据表没有可展示的记录。")
                return
            st.caption(f"主数据表：{dataset.get('name', 'dataset')}，展示前 80 条记录")
            st.dataframe(dataframe, use_container_width=True, height=460)
            return

        tabs = st.tabs([str(dataset.get("name", f"dataset_{index + 1}"))[:20] for index, dataset in enumerate(datasets)])
        for tab, dataset in zip(tabs, datasets):
            with tab:
                dataframe = pd.DataFrame(dataset.get("records", [])[:80])
                if dataframe.empty:
                    st.caption("当前数据表没有可展示的记录。")
                else:
                    st.dataframe(dataframe, use_container_width=True, height=460)
        return

    records = structured_data.get("records", [])[:120]
    if records:
        st.caption("已按记录行整理为更适合筛选和阅读的结构化表格。")
        st.dataframe(build_report_record_dataframe(records), use_container_width=True, height=460)
        return

    if document_type == "key_value_document":
        fields = structured_data.get("fields", {}) or structured_data.get("key_values", {})
        if fields:
            dataframe = pd.DataFrame([{"field": key, "value": value} for key, value in fields.items()])
            st.dataframe(dataframe, use_container_width=True, height=420)
        else:
            st.caption("当前没有可展示的字段内容。")
        return

    if document_type == "report_document":
        indicators = structured_data.get("indicators", [])[:50]
        if indicators:
            dataframe = pd.DataFrame(
                [
                    {
                        "section": indicator.get("section_title", ""),
                        "name": indicator.get("name", ""),
                        "value": indicator.get("value", ""),
                        "unit": indicator.get("unit", ""),
                        "yoy": indicator.get("yoy", ""),
                        "statement": indicator.get("statement", ""),
                    }
                    for indicator in indicators
                ]
            )
            st.dataframe(dataframe, use_container_width=True, height=420)
        else:
            st.caption("当前没有可展示的指标内容。")
        return

    st.caption("当前结果没有结构化预览内容。")



def render_canonical_preview(canonical_data: dict[str, Any]) -> None:
    if not canonical_data:
        st.caption("当前没有 Canonical 结构数据。")
        return

    document_meta = canonical_data.get("document_meta", {}) if isinstance(canonical_data.get("document_meta"), dict) else {}
    columns = st.columns(3)
    columns[0].metric("Canonical 标题", str(document_meta.get("title") or "未命名"))
    columns[1].metric("Canonical 章节", str(len(canonical_data.get("sections", []))))
    columns[2].metric("Canonical 记录", str(len(canonical_data.get("records", []) if isinstance(canonical_data.get("records", []), list) else [])))

    preview = {
        "document_meta": document_meta,
        "document_summary": canonical_data.get("document_summary", {}),
        "detail_groups": canonical_data.get("detail_groups", {}),
        "routing": canonical_data.get("routing", {}),
        "preprocessing": canonical_data.get("preprocessing", {}),
        "prompting": canonical_data.get("prompting", {}),
        "postprocessing": canonical_data.get("postprocessing", {}),
        "domains": canonical_data.get("domains", []),
        "stats": canonical_data.get("stats", {}),
        "sections": [
            {"id": section.get("id"), "title": section.get("title")}
            for section in canonical_data.get("sections", [])[:10]
        ],
        "tables": [
            {
                "id": table.get("id"),
                "name": table.get("name"),
                "row_count": table.get("row_count"),
                "column_count": table.get("column_count"),
            }
            for table in canonical_data.get("tables", [])[:5]
        ],
        "key_values": canonical_data.get("key_values", [])[:10],
    }
    st.json(preview, expanded=False)




def render_natural_language_preview(natural_language: dict[str, Any]) -> None:
    content = str(natural_language.get("content") or "").strip()
    report_facts = natural_language.get("report_facts", {}) if isinstance(natural_language.get("report_facts"), dict) else {}
    chart_render_specs = natural_language.get("chart_render_specs", []) if isinstance(natural_language.get("chart_render_specs"), list) else []
    chart_outputs = natural_language.get("chart_outputs", []) if isinstance(natural_language.get("chart_outputs"), list) else []
    chart_items = chart_render_specs or chart_outputs
    forbidden = natural_language.get("forbidden_expression_check", {}) if isinstance(natural_language.get("forbidden_expression_check"), dict) else {}

    if not content and not report_facts:
        st.caption("当前结果没有生成正式统计分析报告内容。")
        return

    paragraphs = [item for item in content.split("\n\n") if item.strip()] if content else []
    stats = st.columns(4)
    stats[0].metric("段落数", str(len(paragraphs)))
    stats[1].metric("字符数", str(len(content)))
    stats[2].metric("专题数", str(len(report_facts.get("topics", [])) if isinstance(report_facts.get("topics"), list) else 0))
    stats[3].metric("图表数", str(len(chart_items)))

    matched = forbidden.get("matched", []) if isinstance(forbidden.get("matched", []), list) else []
    if matched:
        st.warning("正文中命中了禁用表达: " + "、".join(str(item) for item in matched))

    if content:
        st.text_area("正式统计分析报告正文", content, height=360)
    else:
        fallback_lines = []
        for item in report_facts.get("highlights", [])[:4] if isinstance(report_facts.get("highlights", []), list) else []:
            fallback_lines.append(str(item))
        st.text_area("正式统计分析报告正文", "\n\n".join(fallback_lines), height=240)

    if chart_items:
        st.markdown("**图表预览**")
        for index, chart in enumerate(chart_items[:4]):
            title = str(chart.get("title") or chart.get("id") or "图表")
            st.caption(title)
            rendered = False
            if chart_render_specs and index < len(chart_render_specs):
                image_buffer = CHART_RENDERER.render_buffer(chart_render_specs[index])
                if image_buffer is not None:
                    try:
                        st.image(image_buffer.getvalue(), use_container_width=True)
                        rendered = True
                    finally:
                        image_buffer.close()
            if not rendered:
                chart_path = str(chart.get("path") or "")
                if chart_path and os.path.exists(chart_path):
                    st.image(chart_path, use_container_width=True)
                    rendered = True
            if not rendered:
                st.caption("当前环境未能渲染图表预览。")
            reason = str(chart.get("reason") or "").strip()
            if reason:
                st.caption(reason)



def render_download_buttons(output_files: dict[str, Any]) -> None:
    columns = st.columns(5)
    file_specs = [
        (columns[0], "json", "JSON", "application/json"),
        (columns[1], "excel", "Excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        (columns[2], "word", "Word", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        (columns[3], "text", "TXT", "text/plain"),
        (columns[4], "pdf", "PDF", "application/pdf"),
    ]

    for column, key, label, mime in file_specs:
        file_info = output_files.get(key, {}) if isinstance(output_files.get(key, {}), dict) else {}
        path = file_info.get("path", "")
        with column:
            if path and os.path.exists(path):
                with open(path, "rb") as file:
                    st.download_button(
                        label=label,
                        data=file.read(),
                        file_name=os.path.basename(path),
                        mime=mime,
                        use_container_width=True,
                    )
                size_text = format_file_size(file_info.get("size") or os.path.getsize(path))
                if size_text:
                    st.markdown(f"<div class='download-note'>{size_text}</div>", unsafe_allow_html=True)
            elif file_info.get("error"):
                st.caption(f"{label} 生成失败")



def save_batch_summary(results: list[dict[str, Any]]) -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_json = os.path.join(OUTPUT_DIR, f"batch_output_{timestamp}.json")
    batch_excel = os.path.join(OUTPUT_DIR, f"batch_output_{timestamp}.xlsx")
    overview_rows = []

    for item in results:
        pipeline = item.get("pipeline", {})
        structured = pipeline.get("semantic", {}).get("structured_data", {})
        overview_rows.append(
            {
                "file_name": item.get("file_name", ""),
                "operation_mode": pipeline.get("operation_mode", "natural_to_structured"),
                "document_type": structured.get("document_type", "unknown"),
                "record_count": structured.get("record_count", 0),
                "indicator_count": len(structured.get("indicators", [])) if isinstance(structured.get("indicators", []), list) else 0,
                "is_valid": pipeline.get("validation", {}).get("is_valid", False),
            }
        )

    with open(batch_json, "w", encoding="utf-8") as file:
        json.dump(overview_rows, file, ensure_ascii=False, indent=2)

    with pd.ExcelWriter(batch_excel, engine="openpyxl") as writer:
        pd.DataFrame(overview_rows).to_excel(writer, sheet_name="overview", index=False)

    st.success(f"批量汇总已保存到 {batch_json} 和 {batch_excel}")



def render_processed_result(display_name: str, pipeline_summary: dict[str, Any]) -> None:
    if pipeline_summary.get("error"):
        st.error(f"处理失败: {pipeline_summary.get('error')}")
        return

    semantic = pipeline_summary.get("semantic", {}) if isinstance(pipeline_summary.get("semantic"), dict) else {}
    parsed_content = pipeline_summary.get("parse", {})
    structured_data = semantic.get("structured_data", {})
    canonical_data = semantic.get("canonical_data", {})
    validation = pipeline_summary.get("validation", {})
    natural_language = pipeline_summary.get("natural_language", {})
    output_files = pipeline_summary.get("output_files", {})
    document_summary = semantic.get("document_summary", {}) if isinstance(semantic.get("document_summary"), dict) else {}
    key_findings = document_summary.get("key_findings", []) if isinstance(document_summary.get("key_findings"), list) else []

    status_class = "status-ok" if validation.get("is_valid", False) else "status-warning"
    status_text = "校验通过" if validation.get("is_valid", False) else "存在待处理问题"
    st.markdown(
        f"""
        <div class="result-banner">
            <div>
                <p class="result-kicker">处理结果</p>
                <h2 class="result-title">{html_escape_text(display_name)}</h2>
            </div>
            <span class="status-pill {status_class}">{status_text}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    metrics = build_result_metrics(structured_data, validation, output_files)
    metric_columns = st.columns(len(metrics))
    for column, (label, value) in zip(metric_columns, metrics):
        column.metric(label, value)

    render_pipeline_glance(pipeline_summary)

    tabs = st.tabs(["总览", "编排", "报告文本", "结构化数据", "Canonical", "源内容", "下载"])

    with tabs[0]:
        left, right = st.columns([1.45, 1], gap="large")
        with left:
            render_summary_panel("结构化摘要", format_structured_summary(pipeline_summary))
        with right:
            render_document_overview(pipeline_summary)
            st.markdown("#### 核心发现")
            if key_findings:
                st.markdown("\n".join(f"- {item}" for item in key_findings[:6]))
            else:
                st.caption("当前没有可展示的核心发现。")
            st.markdown("#### 校验情况")
            if validation.get("issues"):
                st.warning("检测到以下问题: " + "；".join(validation.get("issues", [])[:5]))
            else:
                st.success("当前结果通过校验，适合继续导出或回写。")

    with tabs[1]:
        render_pipeline_preview(pipeline_summary)

    with tabs[2]:
        render_natural_language_preview(natural_language)

    with tabs[3]:
        render_structured_preview(structured_data)

    with tabs[4]:
        render_canonical_preview(canonical_data)

    with tabs[5]:
        if isinstance(parsed_content, dict) and parsed_content.get("content"):
            st.text_area("解析内容预览", parsed_content.get("content", "")[:3000], height=360)
        else:
            st.caption("当前没有可展示的原始解析内容。")

    with tabs[6]:
        render_delivery_panel(output_files)
        render_download_buttons(output_files)
        st.caption(f"已生成 {count_ready_outputs(output_files)} 个输出文件")
        st.caption(f"输出目录: {OUTPUT_DIR}")



def render_sidebar() -> None:
    st.sidebar.markdown("## 系统信息")
    st.sidebar.caption(f"路由模型：{ROUTER_MODEL}")
    st.sidebar.caption(f"明细模型：{DETAIL_MODEL} | 摘要模型：{SUMMARY_MODEL}")
    st.sidebar.caption(f"预处理：{'开启' if ENABLE_PREPROCESSING else '关闭'} | 后处理：{'开启' if ENABLE_POSTPROCESSING else '关闭'} | 提示优化：{'开启' if ENABLE_PROMPT_OPTIMIZATION else '关闭'}")
    st.sidebar.markdown("### 支持输入")
    st.sidebar.caption(" / ".join(SUPPORTED_FORMATS))
    st.sidebar.markdown("### 支持输出")
    st.sidebar.caption("JSON / Excel / Word / TXT / PDF")
    st.sidebar.markdown("### 转换方向")
    st.sidebar.caption("文档/自然语言 -> 结构化")
    st.sidebar.caption("结构化 JSON / Excel -> 调查报告")
    st.sidebar.markdown("### 输出位置")
    st.sidebar.code(OUTPUT_DIR, language=None)



def handle_natural_to_structured_mode(planner: TaskPlanner) -> None:
    left, right = st.columns([1.7, 1], gap="large")
    with left:
        st.markdown(
            """
            <div class="section-card">
                <h3>统一结构化入口</h3>
                <p>在同一个入口里支持上传文档文件和粘贴自然语言文本，统一执行预处理、抽取、摘要主表生成、分类子表整理和导出。</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            """
            <div class="section-card">
                <h3>输入建议</h3>
                <p>文档上传更适合保留原始版式和来源信息，文本粘贴更适合快速试跑内容片段；两种入口会走同一套结构化链路。</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<ul class='tip-list'><li>单文件大小上限：{max(1, MAX_FILE_SIZE // (1024 * 1024))} MB</li><li>优先保留标题、章节、时间、地区和数值句</li><li>最终统一输出摘要主表与分类子表</li></ul>",
            unsafe_allow_html=True,
        )

    upload_tab, text_tab = st.tabs(["上传文档文件", "粘贴自然语言"])
    uploaded_files = []
    title = "manual_input.txt"
    text_input = ""
    run_files = False
    run_text = False

    with upload_tab:
        st.caption("支持 Excel、Word、PDF、TXT、图片等原始材料，适合正式文档和批量处理。")
        uploaded_files = st.file_uploader(
            "选择要处理的文档",
            type=[item[1:] for item in NATURAL_INPUT_FORMATS],
            accept_multiple_files=True,
            key="natural_file_uploader",
        )
        run_files = st.button(
            "开始处理上传文档",
            type="primary",
            disabled=not uploaded_files,
            key="run_natural_files",
            use_container_width=True,
        )

    with text_tab:
        st.caption("适合直接粘贴统计公报、会议纪要、业务说明、运营简报等自然语言内容。")
        title = st.text_input("文本标题", value="manual_input.txt", key="manual_text_title")
        text_input = st.text_area(
            "粘贴自然语言文本",
            height=340,
            placeholder="把统计公报、说明文、会议纪要等自然语言内容粘贴到这里。",
            key="manual_text_content",
        )
        st.code(
            "2024年某市国民经济和社会发展统计公报\n一、综合\n全年地区生产总值为1234.5亿元，同比增长5.6%。",
            language=None,
        )
        run_text = st.button(
            "转换粘贴文本",
            type="primary",
            disabled=not text_input.strip(),
            key="run_manual_text",
            use_container_width=True,
        )

    if run_files and uploaded_files:
        all_results = []
        for uploaded_file in uploaded_files:
            if uploaded_file.size > MAX_FILE_SIZE:
                st.error(f"文件 {uploaded_file.name} 超过大小限制。")
                continue

            file_path = save_uploaded_file(uploaded_file)
            with st.spinner(f"正在处理 {uploaded_file.name} ..."):
                pipeline_summary = planner.plan_and_execute(file_path, mode="natural_to_structured")

            all_results.append({"file_name": uploaded_file.name, "pipeline": pipeline_summary})
            render_processed_result(uploaded_file.name, pipeline_summary)

        if all_results:
            save_batch_summary(all_results)
        return

    if run_text and text_input.strip():
        with st.spinner("正在将粘贴文本转换为结构化结果 ..."):
            pipeline_summary = planner.process_text(text_input, title=title or "manual_input.txt")
        render_processed_result(title or "manual_input.txt", pipeline_summary)
        return


def handle_structured_mode(planner: TaskPlanner) -> None:
    left, right = st.columns([1.7, 1], gap="large")
    with left:
        st.markdown(
            """
            <div class="section-card">
                <h3>结构化数据生成调查报告</h3>
                <p>上传结构化 JSON 或 Excel，系统会把结构化字段重新组织成更像调查报告、分析稿和情况说明的文本，并支持导出为 Word、TXT、PDF 等格式。</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            """
            <div class="section-card">
                <h3>输入建议</h3>
                <p>如果 JSON 已包含文档标题、文档类型、记录列表或数据表，生成出的调查报告会更完整；Excel 则建议保留清晰表头。</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            "<ul class='tip-list'><li>JSON 适合精确控制字段</li><li>Excel 适合直接上传已有报表</li><li>系统会自动补全文档概览</li></ul>",
            unsafe_allow_html=True,
        )

    upload_tab, paste_tab = st.tabs(["上传 JSON / Excel 文件", "粘贴 JSON 文本"])
    uploaded_structured_file = None
    json_text = ""

    with upload_tab:
        uploaded_structured_file = st.file_uploader(
            "上传结构化 JSON 或 Excel 文件",
            type=[item[1:] for item in STRUCTURED_INPUT_FORMATS],
            key="structured_data_uploader",
        )
        st.caption("Excel 会按数据表摘要生成调查报告，JSON 会按结构化对象直接组织成报告文本。")
    with paste_tab:
        json_text = st.text_area(
            "粘贴结构化 JSON",
            height=320,
            placeholder='例如: {"document_type": "report_document", ...}',
            key="structured_json_text",
        )

    run_clicked = st.button(
        "生成调查报告",
        type="primary",
        disabled=not uploaded_structured_file and not json_text.strip(),
        key="run_structured_json",
        use_container_width=True,
    )

    if not run_clicked:
        return

    if uploaded_structured_file is not None:
        if uploaded_structured_file.size > MAX_FILE_SIZE:
            st.error(f"文件 {uploaded_structured_file.name} 超过大小限制。")
            return
        file_path = save_uploaded_file(uploaded_structured_file)
        with st.spinner(f"正在基于 {uploaded_structured_file.name} 生成调查报告 ..."):
            pipeline_summary = planner.plan_and_execute(file_path, mode="structured_to_natural")
        render_processed_result(uploaded_structured_file.name, pipeline_summary)
        return

    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        st.error(f"JSON 解析失败: {exc}")
        return

    with st.spinner("正在根据结构化 JSON 生成调查报告 ..."):
        pipeline_summary = planner.process_structured_payload(payload, source_name="pasted_structured.json")
    render_processed_result("pasted_structured.json", pipeline_summary)



def main() -> None:
    st.set_page_config(page_title="文档处理系统", page_icon="📄", layout="wide")
    inject_page_styles()
    render_sidebar()
    render_page_header()

    st.markdown("### 选择转换方向")
    planner = TaskPlanner(semantic_model=SEMANTIC_MODEL, detail_model=DETAIL_MODEL, summary_model=SUMMARY_MODEL)
    mode = st.radio(
        "选择转换方向",
        MODE_OPTIONS,
        horizontal=True,
        label_visibility="collapsed",
    )
    render_mode_cards(mode)

    if mode == "文档/自然语言 -> 结构化":
        handle_natural_to_structured_mode(planner)
    else:
        handle_structured_mode(planner)


if __name__ == "__main__":
    main()
