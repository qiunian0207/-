from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from components.task_planner import TaskPlanner


def build_demo_payload() -> dict:
    monthly_records = [
        {"月份": "1月", "地区": "全市", "社会消费品零售总额(亿元)": 420.5, "同比增速(%)": 5.1, "网上零售额(亿元)": 88.2},
        {"月份": "2月", "地区": "全市", "社会消费品零售总额(亿元)": 438.4, "同比增速(%)": 5.4, "网上零售额(亿元)": 91.7},
        {"月份": "3月", "地区": "全市", "社会消费品零售总额(亿元)": 452.8, "同比增速(%)": 5.8, "网上零售额(亿元)": 96.4},
        {"月份": "4月", "地区": "全市", "社会消费品零售总额(亿元)": 469.6, "同比增速(%)": 6.0, "网上零售额(亿元)": 101.3},
        {"月份": "4月", "地区": "城区", "社会消费品零售总额(亿元)": 281.7, "同比增速(%)": 6.4, "网上零售额(亿元)": 70.8},
        {"月份": "4月", "地区": "郊区", "社会消费品零售总额(亿元)": 187.9, "同比增速(%)": 5.2, "网上零售额(亿元)": 30.5},
    ]
    investment_records = [
        {"行业": "制造业", "固定资产投资(亿元)": 520.0, "同比增速(%)": 6.8},
        {"行业": "基础设施", "固定资产投资(亿元)": 468.5, "同比增速(%)": 4.1},
        {"行业": "房地产", "固定资产投资(亿元)": 312.4, "同比增速(%)": -3.2},
        {"行业": "高技术产业", "固定资产投资(亿元)": 256.8, "同比增速(%)": 9.4},
    ]
    return {
        "title": "2025年某市消费与投资运行监测数据",
        "document_type": "tabular_dataset",
        "region": "某市",
        "year": "2025",
        "domain_tags": ["government_statistics", "retail_consumption"],
        "datasets": [
            {
                "name": "消费运行监测",
                "headers": ["月份", "地区", "社会消费品零售总额(亿元)", "同比增速(%)", "网上零售额(亿元)"],
                "records": monthly_records,
                "row_count": len(monthly_records),
                "column_count": 5,
            },
            {
                "name": "固定资产投资结构",
                "headers": ["行业", "固定资产投资(亿元)", "同比增速(%)"],
                "records": investment_records,
                "row_count": len(investment_records),
                "column_count": 3,
            },
        ],
    }


def main() -> None:
    planner = TaskPlanner()
    pipeline = planner.process_structured_payload(build_demo_payload(), source_name="formal_report_demo.json")
    report = pipeline.get("natural_language", {})
    print("标题:", report.get("title", ""))
    print("-" * 60)
    print(report.get("content", ""))
    print("-" * 60)
    print("图表决策数:", len(report.get("chart_specs", [])))
    print("已渲染图表数:", len(report.get("chart_outputs", [])))
    for key, value in (pipeline.get("output_files", {}) or {}).items():
        if isinstance(value, dict):
            print(f"{key}: {value.get('path', '')}")


if __name__ == "__main__":
    main()
