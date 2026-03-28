from __future__ import annotations

from io import BytesIO
import os
import re
from typing import Any

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

try:
    from config.config import OUTPUT_DIR
except ImportError:
    from doc_processing.config.config import OUTPUT_DIR


class ChartRenderer:
    def __init__(self, output_dir: str | None = None) -> None:
        base_dir = output_dir or OUTPUT_DIR
        self.chart_dir = os.path.join(base_dir, "charts")
        os.makedirs(self.chart_dir, exist_ok=True)
        if plt is not None:
            plt.rcParams["font.sans-serif"] = [
                "SimHei",
                "Microsoft YaHei",
                "Noto Sans CJK SC",
                "Arial Unicode MS",
                "DejaVu Sans",
            ]
            plt.rcParams["axes.unicode_minus"] = False

    def render_many(self, chart_specs: list[dict[str, Any]], report_title: str) -> list[dict[str, Any]]:
        outputs: list[dict[str, Any]] = []
        if not isinstance(chart_specs, list):
            return outputs

        for index, spec in enumerate(chart_specs, start=1):
            chart_type = str(spec.get("type") or "none")
            if chart_type == "none":
                continue
            chart_id = str(spec.get("id") or f"chart_{index:02d}")
            output_path = os.path.join(self.chart_dir, f"{self._slugify(report_title)}_{index:02d}.png")
            result = {
                "id": chart_id,
                "type": chart_type,
                "title": spec.get("title") or chart_id,
                "path": output_path,
                "reason": spec.get("reason", ""),
            }
            if plt is None:
                result["error"] = "matplotlib_not_installed"
                outputs.append(result)
                continue
            try:
                self._render_single(spec, output_path)
                result["size"] = os.path.getsize(output_path) if os.path.exists(output_path) else 0
            except Exception as exc:  # pragma: no cover - fallback path
                result["error"] = str(exc)
            outputs.append(result)
        return outputs

    def render_buffer(self, spec: dict[str, Any]) -> BytesIO | None:
        if plt is None:
            return None
        buffer = BytesIO()
        try:
            self._render_single(spec, buffer)
            buffer.seek(0)
            return buffer
        except Exception:
            buffer.close()
            return None

    def _render_single(self, spec: dict[str, Any], output_target: Any) -> None:
        chart_type = str(spec.get("type") or "none")
        series = spec.get("series", []) if isinstance(spec.get("series"), list) else []
        title = str(spec.get("title") or "图表").strip() or "图表"

        fig, ax = plt.subplots(figsize=(8.6, 4.8))
        try:
            if chart_type == "line":
                self._render_line(ax, series)
            elif chart_type == "bar":
                self._render_bar(ax, series)
            else:
                raise ValueError(f"unsupported_chart_type: {chart_type}")

            ax.set_title(title, fontsize=13)
            ax.set_xlabel(str(spec.get("x_field") or ""))
            ax.set_ylabel(str(spec.get("y_field") or ""))
            ax.grid(True, axis="y", linestyle="--", alpha=0.25)
            if len(series) > 1:
                ax.legend(loc="best")
            fig.tight_layout()
            save_kwargs = {"dpi": 180, "bbox_inches": "tight"}
            if not isinstance(output_target, (str, bytes, os.PathLike)):
                save_kwargs["format"] = "png"
            fig.savefig(output_target, **save_kwargs)
        finally:
            plt.close(fig)

    def _render_line(self, ax: Any, series: list[dict[str, Any]]) -> None:
        for series_item in series:
            points = series_item.get("data", []) if isinstance(series_item.get("data"), list) else []
            x_values = [str(point.get("x", "")) for point in points]
            y_values = [self._safe_float(point.get("y")) for point in points]
            paired = [(x, y) for x, y in zip(x_values, y_values) if x and y is not None]
            if not paired:
                continue
            ax.plot(
                [item[0] for item in paired],
                [item[1] for item in paired],
                marker="o",
                linewidth=2.0,
                label=str(series_item.get("name") or "指标"),
            )

    def _render_bar(self, ax: Any, series: list[dict[str, Any]]) -> None:
        if not series:
            return
        if len(series) == 1:
            points = series[0].get("data", []) if isinstance(series[0].get("data"), list) else []
            labels = [str(point.get("x", "")) for point in points]
            values = [self._safe_float(point.get("y")) for point in points]
            pairs = [(label, value) for label, value in zip(labels, values) if label and value is not None]
            if not pairs:
                return
            ax.bar([item[0] for item in pairs], [item[1] for item in pairs], color="#4976b7")
            return

        labels = []
        for item in series:
            for point in item.get("data", []) if isinstance(item.get("data"), list) else []:
                label = str(point.get("x", ""))
                if label and label not in labels:
                    labels.append(label)
        if not labels:
            return

        bar_width = 0.8 / max(len(series), 1)
        base_positions = list(range(len(labels)))
        for index, series_item in enumerate(series):
            point_map = {
                str(point.get("x", "")): self._safe_float(point.get("y"))
                for point in series_item.get("data", [])
                if isinstance(point, dict)
            }
            values = [point_map.get(label) or 0.0 for label in labels]
            positions = [position + index * bar_width for position in base_positions]
            ax.bar(positions, values, width=bar_width, label=str(series_item.get("name") or f"系列{index + 1}"))
        center_positions = [position + bar_width * (len(series) - 1) / 2 for position in base_positions]
        ax.set_xticks(center_positions)
        ax.set_xticklabels(labels)

    def _slugify(self, text: str) -> str:
        cleaned = re.sub(r"[^0-9A-Za-z一-鿿]+", "_", str(text or "report")).strip("_")
        return cleaned[:48] or "report"

    def _safe_float(self, value: Any) -> float | None:
        try:
            if value in {None, ""}:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None
