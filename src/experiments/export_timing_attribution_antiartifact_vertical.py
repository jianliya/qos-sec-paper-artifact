from __future__ import annotations

import json
import math
import sys
from pathlib import Path


def _escape_svg(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _escape_pdf(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _rgb_tuple(color: str) -> tuple[float, float, float]:
    named = {
        "white": "#FFFFFF",
        "black": "#000000",
        "none": "#000000",
    }
    color = named.get(color.lower(), color)
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) / 255.0 for i in (0, 2, 4))


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


class SvgCanvas:
    def __init__(self, width: float, height: float) -> None:
        self.width = width
        self.height = height
        self.parts: list[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}">'
        ]

    def rect(self, x: float, y: float, w: float, h: float, fill: str, stroke: str = "none", stroke_width: float = 0.0, rx: float = 0.0) -> None:
        self.parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{stroke_width}" rx="{rx}" />'
        )

    def line(self, x1: float, y1: float, x2: float, y2: float, color: str = "#888888", width: float = 1.0, dash: str | None = None) -> None:
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{width}"{dash_attr} />'
        )

    def circle(self, cx: float, cy: float, r: float, fill: str, stroke: str = "white", stroke_width: float = 1.0) -> None:
        self.parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}" />'
        )

    def text(self, x: float, y: float, text: str, size: int = 12, anchor: str = "middle", weight: str = "normal", fill: str = "#222222") -> None:
        self.parts.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" '
            f'fill="{fill}" font-family="Helvetica, Arial, sans-serif">{_escape_svg(text)}</text>'
        )

    def multiline_text(self, x: float, y: float, text: str, size: int = 11, anchor: str = "middle", fill: str = "#222222", weight: str = "normal", line_gap: int = 12) -> None:
        lines = text.split("\n")
        spans = []
        for idx, line in enumerate(lines):
            dy = 0 if idx == 0 else line_gap
            spans.append(f'<tspan x="{x:.1f}" dy="{dy}">{_escape_svg(line)}</tspan>')
        self.parts.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" '
            f'fill="{fill}" font-family="Helvetica, Arial, sans-serif">{"".join(spans)}</text>'
        )

    def save(self, path: Path) -> None:
        self.parts.append("</svg>")
        path.write_text("\n".join(self.parts) + "\n", encoding="utf-8")


class PdfCanvas:
    def __init__(self, width: float, height: float) -> None:
        self.width = width
        self.height = height
        self.ops: list[str] = []

    def _y(self, y: float) -> float:
        return self.height - y

    def rect(self, x: float, y: float, w: float, h: float, fill: str, stroke: str = "none", stroke_width: float = 0.0, rx: float = 0.0) -> None:
        fy = self.height - y - h
        fr, fg, fb = _rgb_tuple(fill)
        self.ops.append(f"{fr:.4f} {fg:.4f} {fb:.4f} rg")
        if stroke != "none" and stroke_width > 0:
            sr, sg, sb = _rgb_tuple(stroke)
            self.ops.append(f"{sr:.4f} {sg:.4f} {sb:.4f} RG")
            self.ops.append(f"{stroke_width:.2f} w")
            self.ops.append(f"{x:.2f} {fy:.2f} {w:.2f} {h:.2f} re B")
        else:
            self.ops.append(f"{x:.2f} {fy:.2f} {w:.2f} {h:.2f} re f")

    def line(self, x1: float, y1: float, x2: float, y2: float, color: str = "#888888", width: float = 1.0, dash: list[float] | None = None) -> None:
        r, g, b = _rgb_tuple(color)
        self.ops.append(f"{r:.4f} {g:.4f} {b:.4f} RG")
        self.ops.append(f"{width:.2f} w")
        if dash:
            pattern = " ".join(f"{d:.2f}" for d in dash)
            self.ops.append(f"[{pattern}] 0 d")
        else:
            self.ops.append("[] 0 d")
        self.ops.append(f"{x1:.2f} {self._y(y1):.2f} m {x2:.2f} {self._y(y2):.2f} l S")

    def circle(self, cx: float, cy: float, r: float, fill: str, stroke: str = "white", stroke_width: float = 1.0) -> None:
        k = 0.5522847498
        c = r * k
        y = self._y(cy)
        fr, fg, fb = _rgb_tuple(fill)
        sr, sg, sb = _rgb_tuple(stroke)
        self.ops.append(f"{fr:.4f} {fg:.4f} {fb:.4f} rg")
        self.ops.append(f"{sr:.4f} {sg:.4f} {sb:.4f} RG")
        self.ops.append(f"{stroke_width:.2f} w")
        self.ops.append(
            f"{cx + r:.2f} {y:.2f} m "
            f"{cx + r:.2f} {y + c:.2f} {cx + c:.2f} {y + r:.2f} {cx:.2f} {y + r:.2f} c "
            f"{cx - c:.2f} {y + r:.2f} {cx - r:.2f} {y + c:.2f} {cx - r:.2f} {y:.2f} c "
            f"{cx - r:.2f} {y - c:.2f} {cx - c:.2f} {y - r:.2f} {cx:.2f} {y - r:.2f} c "
            f"{cx + c:.2f} {y - r:.2f} {cx + r:.2f} {y - c:.2f} {cx + r:.2f} {y:.2f} c B"
        )

    def text(self, x: float, y: float, text: str, size: int = 12, anchor: str = "middle", weight: str = "normal", fill: str = "#222222") -> None:
        font = "/F2" if weight == "bold" else "/F1"
        approx_width = len(text) * size * 0.52
        if anchor == "middle":
            tx = x - approx_width / 2.0
        elif anchor == "end":
            tx = x - approx_width
        else:
            tx = x
        r, g, b = _rgb_tuple(fill)
        self.ops.append(f"{r:.4f} {g:.4f} {b:.4f} rg")
        self.ops.append(f"BT {font} {size} Tf 1 0 0 1 {tx:.2f} {self._y(y):.2f} Tm ({_escape_pdf(text)}) Tj ET")

    def multiline_text(self, x: float, y: float, text: str, size: int = 11, anchor: str = "middle", fill: str = "#222222", weight: str = "normal", line_gap: int = 12) -> None:
        for idx, line in enumerate(text.split("\n")):
            self.text(x, y + idx * line_gap, line, size=size, anchor=anchor, fill=fill, weight=weight)

    def save(self, path: Path) -> None:
        content = "\n".join(self.ops).encode("latin-1", "replace")
        objs: list[bytes] = []
        objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
        objs.append(f"<< /Type /Pages /Kids [3 0 R] /Count 1 /MediaBox [0 0 {self.width:.0f} {self.height:.0f}] >>".encode())
        objs.append(
            b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>"
        )
        objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
        objs.append(f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream")

        out = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for idx, obj in enumerate(objs, start=1):
            offsets.append(len(out))
            out.extend(f"{idx} 0 obj\n".encode())
            out.extend(obj)
            out.extend(b"\nendobj\n")
        xref_pos = len(out)
        out.extend(f"xref\n0 {len(objs)+1}\n".encode())
        out.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            out.extend(f"{offset:010d} 00000 n \n".encode())
        out.extend(f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode())
        path.write_bytes(out)


def _draw_panel_a(canvas, x: float, y: float, w: float, h: float, anti: dict) -> None:
    runs = anti["runs"]
    seeds = [str(run["seed"]) for run in runs]
    deltas = [float(run["delta_leakage_advantage"]) for run in runs]
    mean = float(anti["metrics"]["delta_leakage_advantage"]["mean"])
    ci95 = float(anti["metrics"]["delta_leakage_advantage"]["ci95"])
    ratio = float(anti["positive_delta_ratio"])

    plot_left = x + 40
    plot_w = w - 62
    plot_top = y + 42
    plot_h = h - 102
    vmin = min(min(deltas), 0.0, mean - ci95) - 0.02
    vmax = max(max(deltas), 0.0, mean + ci95) + 0.02
    zero_y = _scale(0.0, vmin, vmax, plot_top, plot_h)
    mean_y = _scale(mean, vmin, vmax, plot_top, plot_h)
    ci_top = _scale(mean + ci95, vmin, vmax, plot_top, plot_h)
    ci_bot = _scale(mean - ci95, vmin, vmax, plot_top, plot_h)

    canvas.rect(x, y, w, h, "#F8FBFF", "#D6E7F5", 1.0, 10)
    canvas.text(x + w / 2, y + 22, "A. Paired anti-artifact contrast", 15, weight="bold")
    canvas.text(x + w / 2, y + 42, "main_vs_classical_queue", 11, fill="#4c78a8")
    canvas.line(plot_left, zero_y, plot_left + plot_w, zero_y, "#7F8C8D", 1.2, [6, 5])
    canvas.line(plot_left, mean_y, plot_left + plot_w, mean_y, "#4c78a8", 1.5)
    canvas.line(plot_left + plot_w - 12, ci_top, plot_left + plot_w - 12, ci_bot, "#4c78a8", 2.0)
    canvas.text(plot_left + plot_w - 18, mean_y - 8, f"mean={mean:.4f}", 10, anchor="end")
    canvas.text(plot_left + plot_w - 18, mean_y + 10, f"ci95={ci95:.4f}", 10, anchor="end")
    canvas.text(plot_left, plot_top - 8, f"positive_delta_ratio = {ratio:.3f}", 10, anchor="start")
    canvas.text(plot_left - 10, plot_top + 4, f"{vmax:.2f}", 10, anchor="end")
    canvas.text(plot_left - 10, plot_top + plot_h + 6, f"{vmin:.2f}", 10, anchor="end")
    canvas.multiline_text(plot_left - 24, plot_top + plot_h / 2 - 6, "delta\nleakage", 10)

    step = plot_w / max(len(seeds) - 1, 1)
    prev = None
    for idx, (seed, val) in enumerate(zip(seeds, deltas)):
        px = plot_left + idx * step
        py = _scale(val, vmin, vmax, plot_top, plot_h)
        if prev is not None:
            canvas.line(prev[0], prev[1], px, py, "#C7CDD4", 1.0)
        canvas.circle(px, py, 4.8, _dot_color(val))
        canvas.text(px, plot_top + plot_h + 18, seed, 9)
        prev = (px, py)

    canvas.text(x + w / 2, y + h - 18, "Quantum-aware setting remains stronger than classical queue baseline", 10, fill="#333333")


def _draw_panel_b(canvas, x: float, y: float, w: float, h: float, obs: dict) -> None:
    order = ["full", "coarse", "masked_backend_only", "queue_length_only", "hardened"]
    leak = [float(obs[k]["metrics"]["leakage_advantage"]["mean"]) for k in order]
    gain = [float(obs[k]["metrics"]["defense_gain"]["mean"]) for k in order]

    plot_left = x + 46
    plot_w = w - 72
    plot_top = y + 42
    plot_h = h - 104
    all_vals = leak + gain + [0.0]
    vmin = min(all_vals) - 0.03
    vmax = max(all_vals) + 0.03
    zero_y = _scale(0.0, vmin, vmax, plot_top, plot_h)

    canvas.rect(x, y, w, h, "#F8FFF9", "#D8EEDC", 1.0, 10)
    canvas.text(x + w / 2, y + 22, "B. Observability ladder", 15, weight="bold")
    canvas.text(x + w / 2, y + 42, "richer scheduler-visible observability carries the signal", 11, fill="#2E8B57")
    canvas.line(plot_left, zero_y, plot_left + plot_w, zero_y, "#7F8C8D", 1.2, [6, 5])
    canvas.text(plot_left - 10, plot_top + 4, f"{vmax:.2f}", 10, anchor="end")
    canvas.text(plot_left - 10, plot_top + plot_h + 6, f"{vmin:.2f}", 10, anchor="end")
    canvas.multiline_text(plot_left - 28, plot_top + plot_h / 2 - 6, "leak /\ngain", 10)

    step = plot_w / max(len(order) - 1, 1)
    prev_leak = None
    prev_gain = None
    for idx, (mode, lv, gv) in enumerate(zip(order, leak, gain)):
        px = plot_left + idx * step
        ly = _scale(lv, vmin, vmax, plot_top, plot_h)
        gy = _scale(gv, vmin, vmax, plot_top, plot_h)
        if prev_leak is not None:
            canvas.line(prev_leak[0], prev_leak[1], px, ly, "#4c78a8", 1.8)
            canvas.line(prev_gain[0], prev_gain[1], px, gy, "#E45756", 1.8)
        canvas.circle(px, ly, 4.6, "#4c78a8")
        canvas.circle(px, gy, 4.6, "#E45756")
        canvas.multiline_text(px, plot_top + plot_h + 18, _mode_label(mode), 9)
        prev_leak = (px, ly)
        prev_gain = (px, gy)

    legend_y = y + h - 28
    canvas.line(x + 18, legend_y, x + 36, legend_y, "#4c78a8", 2.0)
    canvas.text(x + 42, legend_y + 4, "raw leakage", 10, anchor="start")
    canvas.line(x + 145, legend_y, x + 163, legend_y, "#E45756", 2.0)
    canvas.text(x + 169, legend_y + 4, "defense gain", 10, anchor="start")


def _draw_panel_c(canvas, x: float, y: float, w: float, h: float, coexec: dict) -> None:
    runs = coexec["runs"]
    seeds = [str(run["seed"]) for run in runs]
    deltas = [float(run["delta_leakage_advantage"]) for run in runs]
    mean = float(coexec["metrics"]["delta_leakage_advantage"]["mean"])
    ci95 = float(coexec["metrics"]["delta_leakage_advantage"]["ci95"])
    ratio = float(coexec["positive_delta_ratio"])

    plot_left = x + 40
    plot_w = w - 62
    plot_top = y + 42
    plot_h = h - 102
    vmin = min(min(deltas), 0.0, mean - ci95) - 0.02
    vmax = max(max(deltas), 0.0, mean + ci95) + 0.02
    zero_y = _scale(0.0, vmin, vmax, plot_top, plot_h)
    mean_y = _scale(mean, vmin, vmax, plot_top, plot_h)
    ci_top = _scale(mean + ci95, vmin, vmax, plot_top, plot_h)
    ci_bot = _scale(mean - ci95, vmin, vmax, plot_top, plot_h)

    canvas.rect(x, y, w, h, "#FFF9F7", "#F0DDD6", 1.0, 10)
    canvas.text(x + w / 2, y + 22, "C. Co-execution sensitivity", 15, weight="bold")
    canvas.text(x + w / 2, y + 42, "main_vs_no_coexecution_sensitivity", 11, fill="#B55D3D")
    canvas.line(plot_left, zero_y, plot_left + plot_w, zero_y, "#7F8C8D", 1.2, [6, 5])
    canvas.line(plot_left, mean_y, plot_left + plot_w, mean_y, "#B55D3D", 1.5)
    canvas.line(plot_left + plot_w - 12, ci_top, plot_left + plot_w - 12, ci_bot, "#B55D3D", 2.0)
    canvas.text(plot_left + plot_w - 18, mean_y - 8, f"mean={mean:.4f}", 10, anchor="end")
    canvas.text(plot_left + plot_w - 18, mean_y + 10, f"ci95={ci95:.4f}", 10, anchor="end")
    canvas.text(plot_left, plot_top - 8, f"positive_delta_ratio = {ratio:.3f}", 10, anchor="start")
    canvas.text(plot_left - 10, plot_top + 4, f"{vmax:.2f}", 10, anchor="end")
    canvas.text(plot_left - 10, plot_top + plot_h + 6, f"{vmin:.2f}", 10, anchor="end")
    canvas.multiline_text(plot_left - 24, plot_top + plot_h / 2 - 6, "delta\nleakage", 10)

    step = plot_w / max(len(seeds) - 1, 1)
    prev = None
    for idx, (seed, val) in enumerate(zip(seeds, deltas)):
        px = plot_left + idx * step
        py = _scale(val, vmin, vmax, plot_top, plot_h)
        if prev is not None:
            canvas.line(prev[0], prev[1], px, py, "#D7CCC8", 1.0)
        canvas.circle(px, py, 4.8, _dot_color(val))
        canvas.text(px, plot_top + plot_h + 18, seed, 9)
        prev = (px, py)

    canvas.text(x + w / 2, y + h - 18, "Directionally supportive, but only modest paired effect", 10, fill="#333333")


def export_vertical(paired_path: Path, observability_path: Path, out_stem: Path) -> None:
    paired = json.loads(paired_path.read_text(encoding="utf-8"))["contrasts"]
    observability = json.loads(observability_path.read_text(encoding="utf-8"))["runs"]["observability_mode"]

    anti = paired["main_vs_classical_queue"]
    coexec = paired["main_vs_no_coexecution_sensitivity"]

    width = 500.0
    height = 1100.0
    margin = 28.0
    panel_gap = 22.0
    panel_x = margin
    panel_w = width - 2 * margin
    panel_h = 320.0
    panel1_y = 28.0
    panel2_y = panel1_y + panel_h + panel_gap
    panel3_y = panel2_y + panel_h + panel_gap

    svg = SvgCanvas(width, height)
    svg.rect(0, 0, width, height, "#FFFFFF")
    _draw_panel_a(svg, panel_x, panel1_y, panel_w, panel_h, anti)
    _draw_panel_b(svg, panel_x, panel2_y, panel_w, panel_h, observability)
    _draw_panel_c(svg, panel_x, panel3_y, panel_w, panel_h, coexec)
    svg_path = out_stem.with_suffix(".svg")
    svg.save(svg_path)

    pdf = PdfCanvas(width, height)
    pdf.rect(0, 0, width, height, "#FFFFFF")
    _draw_panel_a(pdf, panel_x, panel1_y, panel_w, panel_h, anti)
    _draw_panel_b(pdf, panel_x, panel2_y, panel_w, panel_h, observability)
    _draw_panel_c(pdf, panel_x, panel3_y, panel_w, panel_h, coexec)
    pdf_path = out_stem.with_suffix(".pdf")
    pdf.save(pdf_path)


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: export_timing_attribution_antiartifact_vertical.py "
            "<paired_contrast_json> <observability_json> <out_stem>"
        )
    export_vertical(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))


if __name__ == "__main__":
    main()
