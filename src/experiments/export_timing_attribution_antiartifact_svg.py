from __future__ import annotations

import json
import sys
from pathlib import Path


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _text(x: float, y: float, text: str, size: int = 12, anchor: str = "middle", weight: str = "normal", fill: str = "#222222") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" '
        f'text-anchor="{anchor}" font-weight="{weight}" fill="{fill}" '
        f'font-family="Helvetica, Arial, sans-serif">{_escape(text)}</text>'
    )


def _line(x1: float, y1: float, x2: float, y2: float, color: str = "#888888", width: float = 1.0, dash: str | None = None) -> str:
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{color}" stroke-width="{width}"{dash_attr} />'
    )


def _rect(x: float, y: float, w: float, h: float, fill: str, stroke: str = "none", stroke_width: float = 0.0, rx: float = 0.0) -> str:
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}" rx="{rx}" />'
    )


def _circle(cx: float, cy: float, r: float, fill: str, stroke: str = "white", stroke_width: float = 1.0) -> str:
    return (
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="{stroke_width}" />'
    )


def _scale(value: float, vmin: float, vmax: float, top: float, height: float) -> float:
    if abs(vmax - vmin) < 1e-12:
        return top + height / 2.0
    ratio = (value - vmin) / (vmax - vmin)
    return top + height * (1.0 - ratio)


def _dot_color(value: float) -> str:
    if value > 0:
        return "#2E8B57"
    if value < 0:
        return "#C0392B"
    return "#7F8C8D"


def _mode_label(key: str) -> str:
    mapping = {
        "masked_backend_only": "masked\nbackend",
        "queue_length_only": "queue\nonly",
        "hardened": "hardened",
        "coarse": "coarse",
        "full": "full",
    }
    return mapping.get(key, key.replace("_", "\n"))


def _multiline_text(x: float, y: float, text: str, size: int = 11, anchor: str = "middle", fill: str = "#222222") -> str:
    parts = ['<text '
             f'x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" '
             f'fill="{fill}" font-family="Helvetica, Arial, sans-serif">']
    lines = text.split("\n")
    for idx, line in enumerate(lines):
        dy = 0 if idx == 0 else 12
        parts.append(f'<tspan x="{x:.1f}" dy="{dy}">{_escape(line)}</tspan>')
    parts.append("</text>")
    return "".join(parts)


def export_svg(paired_path: Path, observability_path: Path, out_path: Path) -> None:
    paired = json.loads(paired_path.read_text(encoding="utf-8"))["contrasts"]
    observability = json.loads(observability_path.read_text(encoding="utf-8"))["runs"]["observability_mode"]

    anti = paired["main_vs_classical_queue"]
    coexec = paired["main_vs_no_coexecution_sensitivity"]

    anti_runs = anti["runs"]
    anti_seeds = [str(run["seed"]) for run in anti_runs]
    anti_deltas = [float(run["delta_leakage_advantage"]) for run in anti_runs]
    anti_mean = float(anti["metrics"]["delta_leakage_advantage"]["mean"])
    anti_ci95 = float(anti["metrics"]["delta_leakage_advantage"]["ci95"])
    anti_ratio = float(anti["positive_delta_ratio"])

    coexec_runs = coexec["runs"]
    coexec_seeds = [str(run["seed"]) for run in coexec_runs]
    coexec_deltas = [float(run["delta_leakage_advantage"]) for run in coexec_runs]
    coexec_mean = float(coexec["metrics"]["delta_leakage_advantage"]["mean"])
    coexec_ci95 = float(coexec["metrics"]["delta_leakage_advantage"]["ci95"])
    coexec_ratio = float(coexec["positive_delta_ratio"])

    obs_order = ["full", "coarse", "masked_backend_only", "queue_length_only", "hardened"]
    obs_leak = [float(observability[k]["metrics"]["leakage_advantage"]["mean"]) for k in obs_order]
    obs_gain = [float(observability[k]["metrics"]["defense_gain"]["mean"]) for k in obs_order]

    width = 1380
    height = 400
    margin = 40
    top = 28
    panel_gap = 28
    panel_w = (width - 2 * margin - 2 * panel_gap) / 3.0
    panel_h = 300

    svg: list[str] = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    svg.append(_rect(0, 0, width, height, "#ffffff"))

    # Panel A: classical queue paired contrast
    panel_a_x = margin
    plot_left = panel_a_x + 38
    plot_w = panel_w - 56
    plot_top = top + 35
    plot_h = 195
    values = anti_deltas
    vmin = min(min(values), 0.0, anti_mean - anti_ci95) - 0.02
    vmax = max(max(values), 0.0, anti_mean + anti_ci95) + 0.02
    zero_y = _scale(0.0, vmin, vmax, plot_top, plot_h)
    mean_y = _scale(anti_mean, vmin, vmax, plot_top, plot_h)
    ci_top = _scale(anti_mean + anti_ci95, vmin, vmax, plot_top, plot_h)
    ci_bot = _scale(anti_mean - anti_ci95, vmin, vmax, plot_top, plot_h)

    svg.append(_rect(panel_a_x, top, panel_w, panel_h, "#F8FBFF", "#D6E7F5", 1.0, 10))
    svg.append(_text(panel_a_x + panel_w / 2, top + 22, "A. Paired anti-artifact contrast", 15, weight="bold"))
    svg.append(_text(panel_a_x + panel_w / 2, top + 42, "main_vs_classical_queue", 11, fill="#4c78a8"))
    svg.append(_line(plot_left, zero_y, plot_left + plot_w, zero_y, "#7F8C8D", 1.2, "6 5"))
    svg.append(_line(plot_left, mean_y, plot_left + plot_w, mean_y, "#4c78a8", 1.5))
    svg.append(_line(plot_left + plot_w - 12, ci_top, plot_left + plot_w - 12, ci_bot, "#4c78a8", 2.0))
    svg.append(_text(plot_left + plot_w - 20, mean_y - 8, f"mean={anti_mean:.4f}", 10, "end"))
    svg.append(_text(plot_left + plot_w - 20, mean_y + 10, f"ci95={anti_ci95:.4f}", 10, "end"))
    svg.append(_text(plot_left, plot_top - 8, f"positive_delta_ratio = {anti_ratio:.3f}", 10, "start"))
    svg.append(_text(plot_left - 10, plot_top + 6, f"{vmax:.2f}", 10, "end"))
    svg.append(_text(plot_left - 10, plot_top + plot_h + 4, f"{vmin:.2f}", 10, "end"))
    svg.append(_multiline_text(plot_left - 24, plot_top + plot_h / 2, "delta\nleakage", 10, "middle"))

    n = len(anti_seeds)
    step = plot_w / max(n - 1, 1)
    prev = None
    for idx, (seed, val) in enumerate(zip(anti_seeds, anti_deltas)):
        x = plot_left + idx * step
        y = _scale(val, vmin, vmax, plot_top, plot_h)
        if prev is not None:
            svg.append(_line(prev[0], prev[1], x, y, "#C7CDD4", 1.0))
        svg.append(_circle(x, y, 4.8, _dot_color(val)))
        svg.append(_text(x, plot_top + plot_h + 20, seed, 9))
        prev = (x, y)

    svg.append(_text(panel_a_x + panel_w / 2, top + panel_h - 24, "Quantum-aware setting remains stronger than classical queue baseline", 10, fill="#333333"))

    # Panel B: observability ladder
    panel_b_x = margin + panel_w + panel_gap
    plot_left = panel_b_x + 42
    plot_w = panel_w - 66
    plot_top = top + 35
    plot_h = 195
    all_vals = obs_leak + obs_gain + [0.0]
    vmin = min(all_vals) - 0.03
    vmax = max(all_vals) + 0.03
    zero_y = _scale(0.0, vmin, vmax, plot_top, plot_h)
    svg.append(_rect(panel_b_x, top, panel_w, panel_h, "#F8FFF9", "#D8EEDC", 1.0, 10))
    svg.append(_text(panel_b_x + panel_w / 2, top + 22, "B. Observability ladder", 15, weight="bold"))
    svg.append(_text(panel_b_x + panel_w / 2, top + 42, "richer scheduler-visible observability carries the signal", 11, fill="#2E8B57"))
    svg.append(_line(plot_left, zero_y, plot_left + plot_w, zero_y, "#7F8C8D", 1.2, "6 5"))
    svg.append(_text(plot_left - 10, plot_top + 6, f"{vmax:.2f}", 10, "end"))
    svg.append(_text(plot_left - 10, plot_top + plot_h + 4, f"{vmin:.2f}", 10, "end"))
    svg.append(_multiline_text(plot_left - 26, plot_top + plot_h / 2, "leak /\ngain", 10, "middle"))

    points = len(obs_order)
    step = plot_w / max(points - 1, 1)
    prev_leak = None
    prev_gain = None
    for idx, (mode, leak, gain) in enumerate(zip(obs_order, obs_leak, obs_gain)):
        x = plot_left + idx * step
        y_leak = _scale(leak, vmin, vmax, plot_top, plot_h)
        y_gain = _scale(gain, vmin, vmax, plot_top, plot_h)
        if prev_leak is not None:
            svg.append(_line(prev_leak[0], prev_leak[1], x, y_leak, "#4c78a8", 1.8))
            svg.append(_line(prev_gain[0], prev_gain[1], x, y_gain, "#E45756", 1.8))
        svg.append(_circle(x, y_leak, 4.6, "#4c78a8"))
        svg.append(_circle(x, y_gain, 4.6, "#E45756"))
        svg.append(_multiline_text(x, plot_top + plot_h + 18, _mode_label(mode), 9))
        prev_leak = (x, y_leak)
        prev_gain = (x, y_gain)

    legend_x = panel_b_x + 18
    legend_y = top + panel_h - 36
    svg.append(_line(legend_x, legend_y, legend_x + 18, legend_y, "#4c78a8", 2.0))
    svg.append(_text(legend_x + 24, legend_y + 4, "raw leakage", 10, "start"))
    svg.append(_line(legend_x + 110, legend_y, legend_x + 128, legend_y, "#E45756", 2.0))
    svg.append(_text(legend_x + 134, legend_y + 4, "defense gain", 10, "start"))

    # Panel C: co-execution sensitivity focus
    panel_c_x = margin + 2 * (panel_w + panel_gap)
    plot_left = panel_c_x + 38
    plot_w = panel_w - 56
    plot_top = top + 35
    plot_h = 195
    values = coexec_deltas
    vmin = min(min(values), 0.0, coexec_mean - coexec_ci95) - 0.02
    vmax = max(max(values), 0.0, coexec_mean + coexec_ci95) + 0.02
    zero_y = _scale(0.0, vmin, vmax, plot_top, plot_h)
    mean_y = _scale(coexec_mean, vmin, vmax, plot_top, plot_h)
    ci_top = _scale(coexec_mean + coexec_ci95, vmin, vmax, plot_top, plot_h)
    ci_bot = _scale(coexec_mean - coexec_ci95, vmin, vmax, plot_top, plot_h)

    svg.append(_rect(panel_c_x, top, panel_w, panel_h, "#FFF9F7", "#F0DDD6", 1.0, 10))
    svg.append(_text(panel_c_x + panel_w / 2, top + 22, "C. Co-execution sensitivity", 15, weight="bold"))
    svg.append(_text(panel_c_x + panel_w / 2, top + 42, "main_vs_no_coexecution_sensitivity", 11, fill="#B55D3D"))
    svg.append(_line(plot_left, zero_y, plot_left + plot_w, zero_y, "#7F8C8D", 1.2, "6 5"))
    svg.append(_line(plot_left, mean_y, plot_left + plot_w, mean_y, "#B55D3D", 1.5))
    svg.append(_line(plot_left + plot_w - 12, ci_top, plot_left + plot_w - 12, ci_bot, "#B55D3D", 2.0))
    svg.append(_text(plot_left + plot_w - 20, mean_y - 8, f"mean={coexec_mean:.4f}", 10, "end"))
    svg.append(_text(plot_left + plot_w - 20, mean_y + 10, f"ci95={coexec_ci95:.4f}", 10, "end"))
    svg.append(_text(plot_left, plot_top - 8, f"positive_delta_ratio = {coexec_ratio:.3f}", 10, "start"))
    svg.append(_text(plot_left - 10, plot_top + 6, f"{vmax:.2f}", 10, "end"))
    svg.append(_text(plot_left - 10, plot_top + plot_h + 4, f"{vmin:.2f}", 10, "end"))
    svg.append(_multiline_text(plot_left - 24, plot_top + plot_h / 2, "delta\nleakage", 10, "middle"))

    n = len(coexec_seeds)
    step = plot_w / max(n - 1, 1)
    prev = None
    for idx, (seed, val) in enumerate(zip(coexec_seeds, coexec_deltas)):
        x = plot_left + idx * step
        y = _scale(val, vmin, vmax, plot_top, plot_h)
        if prev is not None:
            svg.append(_line(prev[0], prev[1], x, y, "#D7CCC8", 1.0))
        svg.append(_circle(x, y, 4.8, _dot_color(val)))
        svg.append(_text(x, plot_top + plot_h + 20, seed, 9))
        prev = (x, y)

    svg.append(_text(panel_c_x + panel_w / 2, top + panel_h - 24, "Directionally supportive, but only modest paired effect", 10, fill="#333333"))
    svg.append("</svg>")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(svg) + "\n", encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: export_timing_attribution_antiartifact_svg.py "
            "<paired_contrast_json> <observability_json> <out_svg>"
        )
    export_svg(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))


if __name__ == "__main__":
    main()
