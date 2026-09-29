from __future__ import annotations

import json
import sys
from pathlib import Path


def _color(value: float) -> str:
    if value > 0:
        return "#54a24b"
    if value < 0:
        return "#e45756"
    return "#9d9d9d"


def _scale(value: float, vmin: float, vmax: float, top: float, height: float) -> float:
    if abs(vmax - vmin) < 1e-12:
        return top + height / 2.0
    ratio = (value - vmin) / (vmax - vmin)
    return top + height * (1.0 - ratio)


def _line(x1: float, y1: float, x2: float, y2: float, color: str, width: float = 1.0, dash: str | None = None) -> str:
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{width}"{dash_attr} />'


def _circle(cx: float, cy: float, r: float, fill: str) -> str:
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" />'


def _text(x: float, y: float, text: str, size: int = 12, anchor: str = "middle", weight: str = "normal") -> str:
    safe = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" font-family="Helvetica, Arial, sans-serif">{safe}</text>'


def export_focus_svg(summary_path: Path, contrast_name: str, out_path: Path) -> None:
    data = json.loads(summary_path.read_text(encoding="utf-8")).get("contrasts", {})
    contrast = data.get(contrast_name)
    if not contrast:
        raise ValueError(f"Contrast not found: {contrast_name}")

    runs = contrast.get("runs", [])
    if not runs:
        raise ValueError(f"No seed-level runs found for contrast: {contrast_name}")

    seeds = [str(run["seed"]) for run in runs]
    delta_leak = [float(run["delta_leakage_advantage"]) for run in runs]
    delta_gain = [float(run["delta_defense_gain"]) for run in runs]
    positive_ratio = float(contrast.get("positive_delta_ratio", 0.0))
    mean_delta = float(contrast["metrics"]["delta_leakage_advantage"]["mean"])
    ci95 = float(contrast["metrics"]["delta_leakage_advantage"]["ci95"])

    width = 920
    height = 760
    left = 80
    right = 40
    plot_w = width - left - right
    top1 = 90
    h1 = 230
    top2 = 420
    h2 = 230
    n = len(seeds)
    step = plot_w / max(n - 1, 1)
    xs = [left + i * step for i in range(n)]

    pad = 0.01
    y1_min = min(min(delta_leak), 0.0, mean_delta - ci95) - pad
    y1_max = max(max(delta_leak), 0.0, mean_delta + ci95) + pad
    y2_min = min(min(delta_gain), 0.0) - pad
    y2_max = max(max(delta_gain), 0.0) + pad

    parts: list[str] = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    parts.append('<rect width="100%" height="100%" fill="white" />')

    parts.append(_text(width / 2, 32, "Paired Contrast: Co-execution Sensitivity Contribution", 20, "middle", "bold"))
    parts.append(_text(width / 2, 56, "Matched seed, matched workload, matched defense; only co-execution sensitivity flipped", 11))

    # Panel 1
    parts.append(_text(width / 2, 82, "Seed-level delta leakage advantage", 14, "middle", "bold"))
    zero_y1 = _scale(0.0, y1_min, y1_max, top1, h1)
    mean_y1 = _scale(mean_delta, y1_min, y1_max, top1, h1)
    ci_top = _scale(mean_delta + ci95, y1_min, y1_max, top1, h1)
    ci_bot = _scale(mean_delta - ci95, y1_min, y1_max, top1, h1)
    parts.append(_line(left, zero_y1, left + plot_w, zero_y1, "#888888", 1.2, "6 5"))
    parts.append(_line(left, mean_y1, left + plot_w, mean_y1, "#4c78a8", 1.6))
    parts.append(_line(left + plot_w - 90, ci_top, left + plot_w - 90, ci_bot, "#4c78a8", 2.0))
    parts.append(_text(left + plot_w - 98, mean_y1 - 6, f"mean={mean_delta:.4f}", 11, "end"))
    parts.append(_text(left + plot_w - 98, mean_y1 + 12, f"ci95={ci95:.4f}", 11, "end"))

    prev = None
    for x, yv in zip(xs, delta_leak):
        y = _scale(yv, y1_min, y1_max, top1, h1)
        if prev is not None:
            parts.append(_line(prev[0], prev[1], x, y, "#b8b8b8", 1.0))
        parts.append(_circle(x, y, 5.0, _color(yv)))
        parts.append(_text(x, top1 + h1 + 22, seeds[xs.index(x)], 10))
        prev = (x, y)

    parts.append(_text(left, top1 - 10, f"positive_delta_ratio = {positive_ratio:.4f}", 12, "start"))
    parts.append(_text(left, top1 + h1 + 42, "Seed", 11, "start"))

    # Panel 2
    parts.append(_text(width / 2, 412, "Seed-level delta defense gain", 14, "middle", "bold"))
    zero_y2 = _scale(0.0, y2_min, y2_max, top2, h2)
    parts.append(_line(left, zero_y2, left + plot_w, zero_y2, "#888888", 1.2, "6 5"))

    prev = None
    for idx, (x, yv) in enumerate(zip(xs, delta_gain)):
        y = _scale(yv, y2_min, y2_max, top2, h2)
        if prev is not None:
            parts.append(_line(prev[0], prev[1], x, y, "#b8b8b8", 1.0))
        parts.append(_circle(x, y, 5.0, _color(yv)))
        parts.append(_text(x, top2 + h2 + 22, seeds[idx], 10))
        prev = (x, y)

    parts.append(_text(left, top2 + h2 + 42, "Seed", 11, "start"))

    # Y labels / bounds
    parts.append(_text(24, top1 + h1 / 2, "Delta leakage advantage", 11, "middle"))
    parts.append(_text(24, top2 + h2 / 2, "Delta defense gain", 11, "middle"))
    parts.append(_text(left - 12, top1 + 8, f"{y1_max:.3f}", 10, "end"))
    parts.append(_text(left - 12, top1 + h1 + 4, f"{y1_min:.3f}", 10, "end"))
    parts.append(_text(left - 12, top2 + 8, f"{y2_max:.3f}", 10, "end"))
    parts.append(_text(left - 12, top2 + h2 + 4, f"{y2_min:.3f}", 10, "end"))

    parts.append("</svg>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: export_paired_contrast_focus_svg.py <summary_json> <contrast_name> <out_svg>")
    export_focus_svg(Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]))


if __name__ == "__main__":
    main()
