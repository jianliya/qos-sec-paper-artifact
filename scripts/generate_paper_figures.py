from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle


ROOT = Path(__file__).resolve().parents[1]
PAPER_DIR = ROOT
FIG_DIR = ROOT / "figures" / "generated"
APP_DIR = FIG_DIR / "appendix"
GEN_DIR = FIG_DIR / "intermediate"
QOS_TABLES = ROOT / "reference_results" / "tables"
QOS_RESULTS = ROOT / "reference_results" / "results"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def ensure_dirs() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    APP_DIR.mkdir(parents=True, exist_ok=True)
    GEN_DIR.mkdir(parents=True, exist_ok=True)


def style() -> None:
    plt.rcParams.update(
        {
            "font.size": 12.0,
            "axes.titlesize": 13.0,
            "axes.labelsize": 12.0,
            "xtick.labelsize": 10.5,
            "ytick.labelsize": 10.5,
            "legend.fontsize": 10.2,
            "figure.dpi": 160,
            "savefig.bbox": "tight",
        }
    )


def fmt_float(value: float, digits: int = 4) -> str:
    return f"{value:.{digits}f}"


def fmt_ci_interval(center: float, half_width: float, digits: int = 4) -> str:
    lower = center - half_width
    upper = center + half_width
    return f"[{lower:.{digits}f}, {upper:.{digits}f}]"


def student_t_multiplier(df: int) -> float:
    # Two-sided 95% critical values for small degrees of freedom; falls back to
    # the Gaussian limit when df exceeds the table used in this paper.
    table = {
        1: 12.706,
        2: 4.303,
        3: 3.182,
        4: 2.776,
        5: 2.571,
        6: 2.447,
        7: 2.365,
        8: 2.306,
        9: 2.262,
        10: 2.228,
        11: 2.201,
        12: 2.179,
        13: 2.160,
        14: 2.145,
        15: 2.131,
        16: 2.120,
        17: 2.110,
        18: 2.101,
        19: 2.093,
        20: 2.086,
        21: 2.080,
        22: 2.074,
        23: 2.069,
        24: 2.064,
        25: 2.060,
        26: 2.056,
        27: 2.052,
        28: 2.048,
        29: 2.045,
        30: 2.042,
    }
    return table.get(df, 1.96)


def tex_escape(text: str) -> str:
    return text.replace("_", r"\_")


def write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_table_snippets() -> None:
    backend_map = {7: "L7", 13: "L13", 27: "G27"}
    catalog_rows = read_csv(QOS_TABLES / "timing_compile_catalog.csv")

    main_catalog_lines = []
    appendix_catalog_lines = []
    for row in catalog_rows:
        family = tex_escape(row["family"])
        backend = backend_map[int(row["backend_qubits"])]
        main_catalog_lines.append(
            "        "
            + " & ".join(
                [
                    rf"\texttt{{{family}}}",
                    backend,
                    row["compiled_depth"],
                    row["cx_count"],
                    row["swap_count"],
                    fmt_float(float(row["expected_fidelity"])),
                ]
            )
            + r" \\"
        )
        appendix_catalog_lines.append(
            "        "
            + " & ".join(
                [
                    rf"\texttt{{{family}}}",
                    backend,
                    "1",
                    row["compiled_depth"],
                    row["cx_count"],
                    row["swap_count"],
                    row["layout_span"],
                    fmt_float(float(row["expected_fidelity"])),
                    fmt_float(float(row["backend_suitability"])),
                    row["topology"],
                ]
            )
            + r" \\"
        )

    compile_profiles = {row["profile"]: row for row in read_csv(QOS_TABLES / "timing_compile_awareness.csv")}
    compile_contrasts = {row["compare"]: row for row in read_csv(QOS_TABLES / "timing_compile_awareness_contrasts.csv")}
    compile_control_order = [
        ("compile_visible", "Compile visible"),
        ("logical_only", "Logical only"),
        ("shuffled_compile_features", "Shuffled compile features"),
        ("random_matched_features", "Random matched features"),
        ("compile_path_neutralized", "Compile-path neutralized"),
    ]
    compile_control_lines = []
    for key, label in compile_control_order:
        profile = compile_profiles[key]
        if key == "compile_visible":
            delta_adv = delta_adv_ci = delta_backend = delta_backend_ci = "---"
        else:
            contrast = compile_contrasts[key]
            delta_adv_value = float(contrast["delta_leakage_advantage"])
            delta_adv_half = float(contrast["delta_leakage_ci95"])
            delta_backend_value = float(contrast["delta_backend_choice_leakage_advantage"])
            delta_backend_half = float(contrast["delta_backend_choice_leakage_ci95"])
            delta_adv = fmt_float(delta_adv_value)
            delta_adv_ci = fmt_ci_interval(delta_adv_value, delta_adv_half)
            delta_backend = fmt_float(delta_backend_value)
            delta_backend_ci = fmt_ci_interval(delta_backend_value, delta_backend_half)
        compile_control_lines.append(
            "        "
            + " & ".join(
                [
                    label,
                    fmt_float(float(profile["leakage_advantage"])),
                    fmt_float(float(profile["backend_choice_leakage_advantage"])),
                    delta_adv,
                    delta_adv_ci,
                    delta_backend,
                    delta_backend_ci,
                ]
            )
            + r" \\"
        )

    hardware_rows = read_csv(QOS_TABLES / "hardware_timing_runs.csv")
    hardware_lines = []
    for row in hardware_rows:
        hardware_lines.append(
            "        "
            + " & ".join(
                [
                    str(int(row["run_index"]) + 1),
                    f"{float(row['raw_threshold_accuracy']):.2f}",
                    f"{float(row['coarse_threshold_accuracy']):.2f}",
                    f"{float(row['grouped_threshold_accuracy']):.2f}",
                    f"{float(row['raw_class_gap']):.2f}",
                    f"{float(row['coarse_class_gap']):.2f}",
                    f"{float(row['grouped_class_gap']):.2f}",
                    f"{float(row['pending_jobs']):.1f}",
                    row["operational"],
                ]
            )
            + r" \\"
        )

    write_lines(GEN_DIR / "compile_catalog_main_rows.tex", main_catalog_lines)
    write_lines(GEN_DIR / "compile_catalog_appendix_rows.tex", appendix_catalog_lines)
    write_lines(GEN_DIR / "compile_control_table_rows.tex", compile_control_lines)
    write_lines(GEN_DIR / "hardware_run_rows.tex", hardware_lines)


def bar_panel(ax, labels, values, errors=None, colors=None, ylabel="", title="", baseline=None, baseline_label=None, zero_line=False):
    x = list(range(len(labels)))
    palette = colors or ["#3b6ea8"] * len(labels)
    ax.bar(x, values, yerr=errors, color=palette, capsize=3, edgecolor="#27466b", linewidth=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=0)
    ax.set_ylabel(ylabel)
    ax.set_title(title, pad=8)
    if baseline is not None:
        ax.axhline(baseline, color="#777777", linestyle="--", linewidth=1.0)
        if baseline_label:
            ax.text(0.98, baseline, baseline_label, ha="right", va="bottom", fontsize=8, color="#555555", transform=ax.get_yaxis_transform())
    if zero_line:
        ax.axhline(0.0, color="#777777", linestyle="--", linewidth=1.0)
    spread = max([abs(v) + (errors[i] if errors else 0.0) for i, v in enumerate(values)] + [0.05])
    for idx, value in enumerate(values):
        err = errors[idx] if errors else 0.0
        offset = 0.02 * spread if value >= 0 else -0.05 * spread
        va = "bottom" if value >= 0 else "top"
        ax.text(idx, value + err + offset, f"{value:.3f}", ha="center", va=va, fontsize=8)
    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def heatmap_panel(ax, data, row_labels, col_labels, title, cmap, fmt="{:.3f}", center=0.0, markers=None):
    vmax = max(abs(v) for row in data for v in row) or 1.0
    norm = TwoSlopeNorm(vcenter=center, vmin=-vmax, vmax=vmax) if any(v < 0 for row in data for v in row) else None
    im = ax.imshow(data, cmap=cmap, aspect="auto", norm=norm)
    ax.set_xticks(range(len(col_labels)))
    ax.set_xticklabels(col_labels)
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels(row_labels)
    ax.set_title(title, pad=8)
    for i, row in enumerate(data):
        for j, value in enumerate(row):
            ax.text(j, i, fmt.format(value), ha="center", va="center", fontsize=7.6, color="#102030")
            if markers and markers[i][j]:
                ax.add_patch(Rectangle((j - 0.48, i - 0.48), 0.96, 0.96, fill=False, edgecolor="#1e1e1e", linewidth=1.0))
    ax.set_xticks([x - 0.5 for x in range(1, len(col_labels))], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, len(row_labels))], minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=1.0)
    ax.tick_params(which="minor", bottom=False, left=False)
    return im


def dot_line_panel(ax, x_labels, values, ylabel, title, color, yerr=None, zero_line=False):
    x = list(range(len(x_labels)))
    ax.plot(x, values, color=color, linewidth=1.3, alpha=0.8)
    ax.scatter(x, values, color=color, s=38, zorder=3, edgecolor="white", linewidth=0.6)
    if yerr:
        ax.errorbar(x, values, yerr=yerr, fmt="none", ecolor=color, elinewidth=1.0, capsize=3, alpha=0.8)
    if zero_line:
        ax.axhline(0.0, color="#777777", linestyle="--", linewidth=1.0)
    ax.set_xticks(x)
    ax.set_xticklabels(x_labels)
    ax.set_ylabel(ylabel)
    ax.set_title(title, pad=8)
    for idx, value in enumerate(values):
        ax.text(idx, value + (0.02 * max(1.0, max(abs(v) for v in values))), f"{value:.3f}", ha="center", va="bottom", fontsize=8)
    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def short_scheduler_label(name: str) -> str:
    mapping = {
        "queue": "Queue",
        "balanced": "Balanced",
        "quota": "Quota",
        "isolation": "Isolation",
        "secure_joint": "Full",
        "secure_joint_no_risk": "No Risk",
        "secure_joint_no_leakage": "No Timing Obs.",
        "secure_joint_no_quota": "No Quota",
        "secure_joint_no_victim_bias": "No Victim Bias",
        "secure_joint_no_isolation": "No Isolation",
        "hardened": "Restricted",
        "hardened_no_padding": "No Padding",
        "hardened_no_mask": "No Mask",
        "hardened_no_queue_reset": "No Queue Reset",
        "hardened_no_score_suppression": "No Score Suppression",
    }
    return mapping.get(name, name.replace("_", " ").title())


def figure3_compilation_conditioned_observability() -> None:
    fixed_rows = read_csv(QOS_TABLES / "timing_compile_awareness_contrasts.csv")
    fixed_lookup = {row["compare"]: row for row in fixed_rows}
    control_order = [
        ("logical_only", "Logical-Only"),
        ("shuffled_compile_features", "Shuffled Summaries"),
        ("random_matched_features", "Random-Matched Summaries"),
        ("compile_path_neutralized", "Path-Neutralized"),
    ]

    sweep_rows = read_csv(QOS_TABLES / "timing_compile_configuration_sweep_contrasts.csv")
    config_rows = [row for row in sweep_rows if row["contrast"] == "compile_visible_vs_compile_path_neutralized"]

    hetero_rows = read_csv(QOS_TABLES / "timing_noise_heterogeneity.csv")
    hetero_lookup = {row["profile"]: row for row in hetero_rows}
    hetero_order = [
        ("uniform_noise", "Uniform\nQuality"),
        ("moderate_heterogeneity", "Moderate\nHeterogeneity"),
        ("high_drift", "High\nHeterogeneity"),
    ]

    fig = plt.figure(figsize=(12.8, 4.8))
    outer = GridSpec(1, 2, figure=fig, width_ratios=[0.95, 1.35], wspace=0.28)

    ax_a = fig.add_subplot(outer[0, 0])
    y_positions = list(range(len(control_order)))
    for idx, (key, label) in enumerate(control_order):
        row = fixed_lookup[key]
        delta_t = float(row["delta_leakage_advantage"])
        ci_t = float(row["delta_leakage_ci95"])
        delta_b = float(row["delta_backend_choice_leakage_advantage"])
        ci_b = float(row["delta_backend_choice_leakage_ci95"])
        y = y_positions[idx]
        ax_a.errorbar(delta_t, y + 0.14, xerr=ci_t, fmt="o", color="#3b6ea8", capsize=3, markersize=6, linewidth=1.0)
        ax_a.errorbar(delta_b, y - 0.14, xerr=ci_b, fmt="s", color="#2a9d8f", capsize=3, markersize=6, linewidth=1.0)
    ax_a.axvline(0.0, color="#777777", linestyle="--", linewidth=1.0)
    ax_a.set_yticks(y_positions)
    ax_a.set_yticklabels([label for _, label in control_order])
    ax_a.invert_yaxis()
    ax_a.set_xlabel("Diagnostic paired contrast")
    ax_a.set_title("(a) Single-Configuration Controls", pad=8)
    ax_a.grid(axis="x", linestyle=":", linewidth=0.6, alpha=0.5)
    ax_a.scatter([], [], color="#3b6ea8", marker="o", label=r"Diagnostic $\Delta \mathsf{Sep}_{\mathrm{int}}$")
    ax_a.scatter([], [], color="#2a9d8f", marker="s", label=r"Diagnostic $\Delta L_{\mathrm{backend}}$")
    ax_a.legend(frameon=False, loc="lower right")
    ax_a.spines["top"].set_visible(False)
    ax_a.spines["right"].set_visible(False)

    ax_b = fig.add_subplot(outer[0, 1])
    marker_map = {
        ("trivial", "basic"): "o",
        ("trivial", "sabre"): "s",
        ("sabre", "basic"): "^",
        ("sabre", "sabre"): "D",
    }
    color_map = {"0": "#8ecae6", "1": "#219ebc", "2": "#2a9d8f", "3": "#023047"}
    seen = set()
    for row in config_rows:
        layout = row["layout_method"]
        routing = row["routing_method"]
        opt = row["optimization_level"]
        x = float(row["delta_leakage_advantage"])
        y = float(row["delta_backend_choice_leakage_advantage"])
        label = f"Opt {opt} / {layout}-{routing}"
        plot_label = label if label not in seen else None
        seen.add(label)
        ax_b.scatter(
            x,
            y,
            marker=marker_map[(layout, routing)],
            s=88,
            color=color_map[opt],
            edgecolor="#1f2d3d",
            linewidth=0.9,
            alpha=0.95,
            label=plot_label,
        )
    ax_b.axvline(0.0, color="#777777", linestyle="--", linewidth=1.0)
    ax_b.axhline(0.0, color="#777777", linestyle="--", linewidth=1.0)
    ax_b.set_xlabel(r"Diagnostic $\Delta \mathsf{Sep}_{\mathrm{int}}$")
    ax_b.set_ylabel(r"Diagnostic $\Delta L_{\mathrm{backend}}$")
    ax_b.set_title("(b) Configuration Redistribution", pad=8)
    ax_b.xaxis.set_major_formatter(FormatStrFormatter("%.2f"))
    ax_b.yaxis.set_major_formatter(FormatStrFormatter("%.2f"))
    ax_b.grid(linestyle=":", linewidth=0.6, alpha=0.5)
    ax_b.spines["top"].set_visible(False)
    ax_b.spines["right"].set_visible(False)
    marker_handles = [
        Line2D([0], [0], marker=marker_map[key], linestyle="None", markersize=9, markerfacecolor="#c6d4e1", markeredgecolor="#1f2d3d", label=label)
        for key, label in [
            (("trivial", "basic"), "trivial/basic"),
            (("trivial", "sabre"), "trivial/sabre"),
            (("sabre", "basic"), "sabre/basic"),
            (("sabre", "sabre"), "sabre/sabre"),
        ]
    ]
    color_handles = [
        Line2D([0], [0], marker="o", linestyle="None", markersize=9, markerfacecolor=color, markeredgecolor="#1f2d3d", label=f"opt {opt}")
        for opt, color in [("0", "#8ecae6"), ("1", "#219ebc"), ("2", "#2a9d8f"), ("3", "#023047")]
    ]
    legend1 = ax_b.legend(
        handles=marker_handles,
        frameon=False,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.18),
        ncol=2,
        title="Layout/routing",
        title_fontsize=9.2,
        fontsize=8.7,
    )
    ax_b.add_artist(legend1)
    ax_b.legend(
        handles=color_handles,
        frameon=False,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.34),
        ncol=4,
        title="Optimization",
        title_fontsize=9.2,
        fontsize=8.7,
    )

    fig.tight_layout()
    fig.savefig(FIG_DIR / "figure3_compilation_conditioned_observability.pdf")
    plt.close(fig)

    fig = plt.figure(figsize=(8.6, 5.4))
    right = GridSpec(3, 1, figure=fig, hspace=0.42, height_ratios=[1.0, 0.78, 0.78])
    ax_c1 = fig.add_subplot(right[0, 0])
    x_labels = [label for _, label in hetero_order]
    timing_vals = [float(hetero_lookup[key]["leakage_advantage"]) for key, _ in hetero_order]
    backend_vals = [float(hetero_lookup[key]["backend_choice_leakage_advantage"]) for key, _ in hetero_order]
    xs = list(range(len(x_labels)))
    ax_c1.scatter(xs, timing_vals, color="#3b6ea8", marker="o", s=68, edgecolor="#1f2d3d", linewidth=0.7, label=r"Diag. $\mathsf{Sep}_{\mathrm{int}}$")
    ax_c1.scatter(xs, backend_vals, color="#2a9d8f", marker="s", s=68, edgecolor="#1f2d3d", linewidth=0.7, label="Diag. backend obs.")
    ax_c1.set_xticks(xs)
    ax_c1.set_xticklabels([])
    ax_c1.set_ylabel("Diagnostic value")
    ax_c1.set_title("Diagnostic Observability", fontsize=11.5, pad=4)
    ax_c1.text(0.01, 0.95, "(a)", transform=ax_c1.transAxes, ha="left", va="top", fontweight="bold", fontsize=12)
    ax_c1.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.5)
    ax_c1.legend(frameon=False, loc="upper left", fontsize=10.0)
    ax_c1.spines["top"].set_visible(False)
    ax_c1.spines["right"].set_visible(False)

    ax_c2 = fig.add_subplot(right[1, 0])
    wait_vals = [float(hetero_lookup[key]["victim_mean_wait"]) for key, _ in hetero_order]
    ax_c2.scatter(xs, wait_vals, color="#c17c1d", marker="o", s=64, edgecolor="#1f2d3d", linewidth=0.7, label="Victim wait")
    ax_c2.set_xticks(xs)
    ax_c2.set_xticklabels([])
    ax_c2.set_ylabel("Waiting time")
    ax_c2.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.5)
    ax_c2.spines["top"].set_visible(False)
    ax_c2.spines["right"].set_visible(False)
    ax_c2.set_title("Victim Waiting Time", fontsize=11.5, pad=3)
    ax_c2.text(0.01, 0.95, "(b)", transform=ax_c2.transAxes, ha="left", va="top", fontweight="bold", fontsize=12)

    ax_c3 = fig.add_subplot(right[2, 0])
    fidelity_vals = [float(hetero_lookup[key]["victim_fidelity_proxy_shift"]) for key, _ in hetero_order]
    ax_c3.scatter(xs, fidelity_vals, color="#b04a8b", marker="D", s=62, edgecolor="#1f2d3d", linewidth=0.7)
    ax_c3.axhline(0.0, color="#777777", linestyle="--", linewidth=0.9)
    ax_c3.set_xticks(xs)
    ax_c3.set_xticklabels(x_labels)
    ax_c3.set_ylabel("Fidelity shift")
    ax_c3.set_title("Fidelity Shift", fontsize=11.5, pad=3)
    ax_c3.text(0.01, 0.95, "(c)", transform=ax_c3.transAxes, ha="left", va="top", fontweight="bold", fontsize=12)
    ax_c3.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.5)
    ax_c3.spines["top"].set_visible(False)
    ax_c3.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "figure4_backend_heterogeneity_observability.pdf")
    plt.close(fig)


def figure4_hardware_main() -> None:
    rows = read_csv(QOS_TABLES / "hardware_timing_runs.csv")
    run_labels = [f"Run {int(row['run_index']) + 1}" for row in rows]
    x = list(range(len(run_labels)))

    raw_acc = [float(row["raw_threshold_accuracy"]) for row in rows]
    coarse_acc = [float(row["coarse_threshold_accuracy"]) for row in rows]
    grouped_acc = [float(row["grouped_threshold_accuracy"]) for row in rows]
    raw_leak = [v - 0.5 for v in raw_acc]
    coarse_leak = [v - 0.5 for v in coarse_acc]
    grouped_leak = [v - 0.5 for v in grouped_acc]

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 3.6))
    for values, color, label in [
        (raw_acc, "#3b6ea8", "Raw"),
        (coarse_acc, "#8d99ae", "Coarse"),
        (grouped_acc, "#2a9d8f", "Grouped"),
    ]:
        axes[0].plot(x, values, marker="o", linewidth=1.3, color=color, label=label)
    axes[0].axhline(0.5, color="#777777", linestyle="--", linewidth=1.0)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(run_labels, rotation=0)
    axes[0].set_ylabel("Threshold Accuracy")
    axes[0].set_title("(a) Accuracy by Run", pad=8)
    axes[0].legend(frameon=False, loc="upper left")
    axes[0].grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.5)
    axes[0].spines["top"].set_visible(False)
    axes[0].spines["right"].set_visible(False)

    for values, color, label in [
        (raw_leak, "#3b6ea8", "Raw"),
        (coarse_leak, "#8d99ae", "Coarse"),
        (grouped_leak, "#2a9d8f", "Grouped"),
    ]:
        axes[1].plot(x, values, marker="o", linewidth=1.3, color=color, label=label)
    axes[1].axhline(0.0, color="#777777", linestyle="--", linewidth=1.0)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(run_labels, rotation=0)
    axes[1].set_ylabel("Signed Advantage")
    axes[1].set_title("(b) Signed Timing Advantage by Run", pad=8)
    axes[1].grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.5)
    axes[1].spines["top"].set_visible(False)
    axes[1].spines["right"].set_visible(False)

    fig.tight_layout(w_pad=2.1)
    fig.savefig(FIG_DIR / "figure4_limited_public_backend_timing.pdf")
    plt.close(fig)


def figure2_timing_main() -> None:
    with (QOS_RESULTS / "timing" / "summary_multiseed_loso.json").open(encoding="utf-8") as handle:
        timing = json.load(handle)["metrics"]

    fig, axes = plt.subplots(1, 3, figsize=(12.8, 3.7))
    bar_panel(
        axes[0],
        ["Class A", "Class B", "High Iso.", "No Victim"],
        [
            timing["classA_mean_wait"]["mean"],
            timing["classB_mean_wait"]["mean"],
            timing["highIsolation_mean_wait"]["mean"],
            timing["noVictim_mean_wait"]["mean"],
        ],
        errors=[
            timing["classA_mean_wait"]["ci95"],
            timing["classB_mean_wait"]["ci95"],
            timing["highIsolation_mean_wait"]["ci95"],
            timing["noVictim_mean_wait"]["ci95"],
        ],
        colors=["#d17c00", "#e69f00", "#f0b44d", "#9a9a9a"],
        ylabel="Mean Probe Waiting Time",
        title="(a) Probe Waiting Time",
    )
    axes[0].set_xticklabels(["Class A", "Class B", "High Iso.", "No Victim"], rotation=16, ha="right")
    bar_panel(
        axes[1],
        ["Raw Accuracy", "Restricted Accuracy"],
        [timing["accuracy"]["mean"], timing["defended_accuracy"]["mean"]],
        errors=[timing["accuracy"]["ci95"], timing["defended_accuracy"]["ci95"]],
        colors=["#3b6ea8", "#8d99ae"],
        ylabel="Accuracy",
        title="(b) Inference Accuracy",
        baseline=0.5,
    )
    chance_handle = Line2D([0], [0], color="#777777", linestyle="--", linewidth=1.0, label="Majority-class baseline")
    axes[1].legend(handles=[chance_handle], frameon=False, loc="upper right", fontsize=10.0)
    bar_panel(
        axes[2],
        ["Raw", "Restricted", "Reduction"],
        [
            timing["leakage_advantage"]["mean"],
            timing["defended_leakage_advantage"]["mean"],
            timing["defense_gain"]["mean"],
        ],
        errors=[
            timing["leakage_advantage"]["ci95"],
            timing["defended_leakage_advantage"]["ci95"],
            timing["defense_gain"]["ci95"],
        ],
        colors=["#3b6ea8", "#8d99ae", "#2a9d8f"],
        ylabel="Signed Score",
        title="(c) Signed Reduction",
        zero_line=True,
    )
    fig.tight_layout(w_pad=2.0)
    fig.savefig(FIG_DIR / "figure2_timing_main.pdf")
    plt.close(fig)


def appendix_availability_ablation() -> None:
    with (QOS_RESULTS / "ablations" / "availability_ablation.json").open(encoding="utf-8") as handle:
        data = json.load(handle)["ablations"]
    order = list(data.keys())
    labels = [short_scheduler_label(name) for name in order]
    pressure = [data[k]["attacker_delay_pressure_ratio"]["mean"] for k in order]
    wait = [data[k]["victim_avg_wait"]["mean"] for k in order]

    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    ax.bar(labels, pressure, color="#54a24b", edgecolor="#315f2a", linewidth=0.6)
    ax.set_title("Availability ablation: attacker delay pressure")
    ax.set_ylabel("Pressure ratio")
    ax.tick_params(axis="x", rotation=18)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.5)
    fig.tight_layout()
    fig.savefig(APP_DIR / "availability_ablation_attack_success.pdf")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    ax.bar(labels, wait, color="#4c78a8", edgecolor="#27466b", linewidth=0.6)
    ax.set_title("Availability ablation: victim average wait")
    ax.set_ylabel("Victim average wait")
    ax.tick_params(axis="x", rotation=18)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.5)
    fig.tight_layout()
    fig.savefig(APP_DIR / "availability_ablation_wait.pdf")
    plt.close(fig)


def appendix_timing_ablation() -> None:
    with (QOS_RESULTS / "ablations" / "timing_ablation.json").open(encoding="utf-8") as handle:
        data = json.load(handle)["ablations"]
    order = list(data.keys())
    labels = [short_scheduler_label(name) for name in order]
    residual = [data[k]["defended_leakage_advantage"]["mean"] for k in order]
    reduction = [data[k]["defense_gain"]["mean"] for k in order]

    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    ax.bar(labels, residual, color="#e45756", edgecolor="#9f2e2e", linewidth=0.6)
    ax.axhline(0.0, color="gray", linestyle="--", linewidth=1)
    ax.set_title("Timing ablation: restricted signed residual")
    ax.set_ylabel("Restricted signed residual")
    ax.tick_params(axis="x", rotation=18)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.5)
    fig.tight_layout()
    fig.savefig(APP_DIR / "timing_ablation_defended_leak.pdf")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    ax.bar(labels, reduction, color="#54a24b", edgecolor="#315f2a", linewidth=0.6)
    ax.set_title("Timing ablation: signed reduction")
    ax.set_ylabel("Signed reduction")
    ax.tick_params(axis="x", rotation=18)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.5)
    fig.tight_layout()
    fig.savefig(APP_DIR / "timing_ablation_gain.pdf")
    plt.close(fig)


def appendix_backend_choice_relation() -> None:
    with (QOS_RESULTS / "ablations" / "timing_noise_heterogeneity.json").open(encoding="utf-8") as handle:
        data = json.load(handle)
    profiles = data.get("profiles", {})
    ordered = ["uniform_noise", "moderate_heterogeneity", "high_drift"]
    present = [name for name in ordered if name in profiles]
    label_map = {
        "uniform_noise": "Uniform Quality",
        "moderate_heterogeneity": "Moderate Heterogeneity",
        "high_drift": "High Heterogeneity",
    }
    marker_map = {
        "uniform_noise": "o",
        "moderate_heterogeneity": "s",
        "high_drift": "D",
    }
    color_map = {
        "uniform_noise": "#4c78a8",
        "moderate_heterogeneity": "#f58518",
        "high_drift": "#e45756",
    }

    xs = [profiles[name]["metrics"]["backend_choice_entropy"]["mean"] for name in present]
    ys = [profiles[name]["metrics"]["backend_choice_leakage_advantage"]["mean"] for name in present]
    waits = [profiles[name]["metrics"]["victim_mean_wait"]["mean"] for name in present]
    fshift = [profiles[name]["metrics"]["victim_fidelity_proxy_shift"]["mean"] for name in present]

    fig, ax = plt.subplots(figsize=(6.6, 4.5))
    ax.grid(alpha=0.22)
    for x, y, wait, df, name in zip(xs, ys, waits, fshift, present):
        ax.scatter(x, y, s=86, color=color_map[name], marker=marker_map[name], edgecolors="#1f2d3d", linewidth=0.8, zorder=3)
        ax.annotate(
            f"{label_map[name]}\nwait={wait:.3f}, ΔF={df:.4f}",
            (x, y),
            xytext=(8, 7 if name != "high_drift" else -26),
            textcoords="offset points",
            fontsize=8.7,
            bbox={"facecolor": "white", "alpha": 0.82, "edgecolor": "0.85", "pad": 2.2},
        )
    ax.set_xlabel("Backend-choice entropy")
    ax.set_ylabel("Diagnostic backend-choice observability")
    ax.set_title("Backend-Quality Heterogeneity and Backend-Choice Observability")
    xpad = max(0.015, 0.12 * ((max(xs) - min(xs)) if len(xs) > 1 else 0.1))
    ypad = max(0.01, 0.18 * ((max(ys) - min(ys)) if len(ys) > 1 else 0.05))
    ax.set_xlim(min(xs) - xpad, max(xs) + xpad)
    ax.set_ylim(max(0.0, min(ys) - ypad), max(ys) + ypad)
    fig.tight_layout()
    fig.savefig(APP_DIR / "timing_noise_backend_choice_relation.pdf")
    plt.close(fig)


def figure3_compile_heatmaps() -> None:
    rows = read_csv(QOS_TABLES / "timing_compile_catalog.csv")
    family_order = ["small_qaoa", "bv_like", "grover_like", "random", "mirror"]
    family_labels = ["small_qaoa", "bv_like", "grover_like", "random", "mirror"]
    backend_map = {7: "L7", 13: "L13", 27: "G27"}
    backend_order = ["L7", "L13", "G27"]
    metrics = [
        ("compiled_depth", "Compiled Depth"),
        ("cx_count", "Two-Qubit Gate Count"),
        ("swap_count", "SWAP Proxy"),
        ("expected_fidelity", "Expected-Fidelity Proxy"),
    ]
    lookup = {}
    for row in rows:
        lookup[(row["family"], backend_map[int(row["backend_qubits"])])] = row

    fig, axes = plt.subplots(2, 2, figsize=(9.6, 7.0))
    cmaps = ["Blues", "Greens", "Oranges", "Purples"]
    for ax, (metric, title), cmap_name in zip(axes.flat, metrics, cmaps):
        data = []
        for family in family_order:
            row_vals = []
            for backend in backend_order:
                raw = lookup[(family, backend)][metric]
                row_vals.append(float(raw))
            data.append(row_vals)
        im = ax.imshow(data, cmap=cmap_name, aspect="auto")
        ax.set_xticks(range(len(backend_order)))
        ax.set_xticklabels(backend_order)
        ax.set_yticks(range(len(family_labels)))
        ax.set_yticklabels(family_labels)
        ax.set_title(title, pad=8)
        for i, row in enumerate(data):
            for j, value in enumerate(row):
                label = f"{value:.4f}" if "fidelity" in metric else f"{int(value)}"
                ax.text(j, i, label, ha="center", va="center", fontsize=8, color="#102030")
        ax.set_xticks([x - 0.5 for x in range(1, len(backend_order))], minor=True)
        ax.set_yticks([y - 0.5 for y in range(1, len(family_labels))], minor=True)
        ax.grid(which="minor", color="white", linestyle="-", linewidth=1.0)
        ax.tick_params(which="minor", bottom=False, left=False)
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.ax.tick_params(labelsize=8)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "figure3_compile_variation_heatmaps.pdf")
    plt.close(fig)


def figure4_config_heatmaps() -> None:
    rows = read_csv(QOS_TABLES / "timing_compile_configuration_sweep_contrasts.csv")
    target_rows = [row for row in rows if row["contrast"] == "compile_visible_vs_compile_path_neutralized"]
    row_order = [(opt, seed) for opt in ["0", "1", "2", "3"] for seed in ["23", "29", "31", "37"]]
    col_order = [
        ("trivial", "basic"),
        ("trivial", "sabre"),
        ("sabre", "basic"),
        ("sabre", "sabre"),
    ]
    row_labels = [f"Opt {opt} / Seed {seed}" for opt, seed in row_order]
    col_labels = ["Trivial /\nBasic", "Trivial /\nSabre", "Sabre /\nBasic", "Sabre /\nSabre"]
    lookup = {(row["optimization_level"], row["transpiler_seed"], row["layout_method"], row["routing_method"]): row for row in target_rows}
    delta_time = []
    delta_backend = []
    sig_time = []
    sig_backend = []
    for opt, seed in row_order:
        t_row = []
        b_row = []
        st_row = []
        sb_row = []
        for layout, routing in col_order:
            item = lookup[(opt, seed, layout, routing)]
            d_t = float(item["delta_leakage_advantage"])
            ci_t = float(item["delta_leakage_ci95"])
            d_b = float(item["delta_backend_choice_leakage_advantage"])
            ci_b = float(item["delta_backend_choice_leakage_ci95"])
            t_row.append(d_t)
            b_row.append(d_b)
            st_row.append(abs(d_t) > ci_t)
            sb_row.append(abs(d_b) > ci_b)
        delta_time.append(t_row)
        delta_backend.append(b_row)
        sig_time.append(st_row)
        sig_backend.append(sb_row)

    cmap = LinearSegmentedColormap.from_list("blue_white_teal", ["#d7ecf8", "#ffffff", "#58b8b0"])
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 7.2))
    im1 = heatmap_panel(
        axes[0],
        delta_time,
        row_labels,
        col_labels,
        r"(a) $\Delta \mathsf{Sep}_{\mathrm{int}}$" "\nCompile-Visible vs. Path-Neutralized",
        cmap,
        markers=sig_time,
    )
    im2 = heatmap_panel(
        axes[1],
        delta_backend,
        row_labels,
        col_labels,
        "(b) ΔL_backend\nCompile-Visible vs. Path-Neutralized",
        cmap,
        markers=sig_backend,
    )
    for ax, im in zip(axes, [im1, im2]):
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
        cbar.ax.tick_params(labelsize=8)
    fig.tight_layout(w_pad=2.0)
    fig.savefig(FIG_DIR / "figure4_configuration_sensitivity_heatmaps.pdf")
    plt.close(fig)


def figure5_backend_heterogeneity() -> None:
    rows = read_csv(QOS_TABLES / "timing_noise_heterogeneity.csv")
    contrast_rows = {row["contrast"]: row for row in read_csv(QOS_TABLES / "timing_noise_heterogeneity_contrast.csv")}
    label_map = {
        "uniform_noise": "Uniform",
        "moderate_heterogeneity": "Moderate\nHeterogeneity",
        "high_drift": "High\nHeterogeneity",
    }
    order = ["uniform_noise", "moderate_heterogeneity", "high_drift"]
    x_labels = [label_map[key] for key in order]
    lookup = {row["profile"]: row for row in rows}
    timing_vals = [float(lookup[key]["leakage_advantage"]) for key in order]
    backend_vals = [float(lookup[key]["backend_choice_leakage_advantage"]) for key in order]
    wait_vals = [float(lookup[key]["victim_mean_wait"]) for key in order]
    fidelity_vals = [float(lookup[key]["victim_fidelity_proxy_shift"]) for key in order]
    timing_err = [0.0, float(contrast_rows["uniform_noise_vs_moderate_heterogeneity"]["delta_adv_noise_ci95"]), float(contrast_rows["uniform_noise_vs_high_drift"]["delta_adv_noise_ci95"])]
    backend_err = [0.0, 0.0, 0.0]
    wait_err = [0.0, float(contrast_rows["uniform_noise_vs_moderate_heterogeneity"]["delta_victim_wait_ci95"]), float(contrast_rows["uniform_noise_vs_high_drift"]["delta_victim_wait_ci95"])]
    fidelity_err = [0.0, float(contrast_rows["uniform_noise_vs_moderate_heterogeneity"]["delta_fproxy_shift_ci95"]), float(contrast_rows["uniform_noise_vs_high_drift"]["delta_fproxy_shift_ci95"])]

    fig = plt.figure(figsize=(12.4, 4.8))
    outer = GridSpec(1, 3, figure=fig, width_ratios=[1.05, 1.0, 1.0], wspace=0.35)
    left = outer[0].subgridspec(2, 1, hspace=0.35)
    ax_a1 = fig.add_subplot(left[0, 0])
    ax_a2 = fig.add_subplot(left[1, 0])
    ax_b = fig.add_subplot(outer[1])
    ax_c = fig.add_subplot(outer[2])

    dot_line_panel(ax_a1, x_labels, timing_vals, "Diagnostic value", r"(a) Diagnostic $\mathsf{Sep}_{\mathrm{int}}$", "#3b6ea8", yerr=timing_err)
    dot_line_panel(ax_a2, x_labels, backend_vals, "Diagnostic value", "Diagnostic Backend-Choice Observability", "#2a9d8f", yerr=backend_err)
    dot_line_panel(ax_b, x_labels, wait_vals, "Victim Mean Wait", "(b) Victim Mean Wait", "#c17c1d", yerr=wait_err)
    dot_line_panel(ax_c, x_labels, fidelity_vals, "Fidelity-Proxy Shift", "(c) Fidelity-Proxy Shift", "#b04a8b", yerr=fidelity_err, zero_line=True)
    fig.savefig(FIG_DIR / "figure5_backend_heterogeneity_dotplots.pdf")
    plt.close(fig)


def appendix_b1_classical_queue() -> None:
    rows = {row["ablation"]: row for row in read_csv(QOS_TABLES / "timing_quantum_ablation.csv")}
    fig, ax = plt.subplots(figsize=(5.3, 3.6))
    labels = ["Main Quantum", "Classical Queue"]
    values = [float(rows["main_quantum"]["leakage_advantage"]), float(rows["classical_queue_baseline"]["leakage_advantage"])]
    bar_panel(ax, labels, values, colors=["#4c78a8", "#9ecae1"], ylabel="Scheduler-Boundary Separability", title="Classical Queue Contrast", zero_line=True)
    fig.tight_layout()
    fig.savefig(APP_DIR / "timing_classical_queue_contrast.pdf")
    plt.close(fig)


def appendix_b2_observability_ladder() -> None:
    rows = read_csv(QOS_TABLES / "timing_observability_ablation.csv")
    keep = ["hardened", "jittered", "masked", "coarse"]
    lookup = {row["variant"]: row for row in rows}
    labels = ["Restricted", "Jittered", "Masked", "Coarse"]
    residual = [float(lookup[key]["defended_leakage_advantage"]) for key in keep]
    reduction = [float(lookup[key]["defense_gain"]) for key in keep]
    x = list(range(len(labels)))
    width = 0.34
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    ax.bar([i - width / 2 for i in x], residual, width=width, color="#e45756", label="Restricted Signed Residual")
    ax.bar([i + width / 2 for i in x], reduction, width=width, color="#54a24b", label="Signed Reduction")
    ax.axhline(0.0, color="#777777", linestyle="--", linewidth=1.0)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Signed Separability Value")
    ax.set_title("Observability Ladder")
    ax.legend(frameon=False, loc="upper right")
    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(APP_DIR / "timing_observability_ladder.pdf")
    plt.close(fig)


def appendix_b3_coexecution() -> None:
    with (QOS_RESULTS / "ablations" / "timing_paired_contrast.json").open(encoding="utf-8") as handle:
        contrast = json.load(handle)["contrasts"]["main_vs_no_coexecution_sensitivity"]
    seeds = [run["seed"] for run in contrast["runs"]]
    deltas = [run["delta_leakage_advantage"] for run in contrast["runs"]]
    mean_delta = contrast["metrics"]["delta_leakage_advantage"]["mean"]
    ci95 = contrast["metrics"]["delta_leakage_advantage"]["ci95"]

    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    ax.scatter(seeds, deltas, color="#4c78a8", s=38, zorder=3)
    ax.plot(seeds, deltas, color="#9ecae1", linewidth=1.0, alpha=0.9, zorder=2)
    ax.axhline(0.0, color="#777777", linestyle="--", linewidth=1.0)
    ax.axhline(mean_delta, color="#2a9d8f", linestyle="-", linewidth=1.2, label=rf"Mean paired $\Delta \mathsf{{Sep}}_{{\mathrm{{sb}}}}$ = {mean_delta:.4f}")
    ax.fill_between(
        [min(seeds) - 0.5, max(seeds) + 0.5],
        mean_delta - ci95,
        mean_delta + ci95,
        color="#b8e1dd",
        alpha=0.45,
        label=rf"95\% CI = [{mean_delta - ci95:.4f}, {mean_delta + ci95:.4f}]",
    )
    ax.set_xlabel("Seed")
    ax.set_ylabel(r"Paired $\Delta \mathsf{Sep}_{\mathrm{sb}}$")
    ax.set_title("Co-Execution Sensitivity", pad=8)
    ax.set_xticks(seeds)
    ax.legend(frameon=False, loc="lower left")
    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(APP_DIR / "timing_coexecution_sensitivity.pdf")
    plt.close(fig)


def appendix_b4_stability() -> None:
    with (QOS_RESULTS / "stability" / "timing_stability.json").open(encoding="utf-8") as handle:
        data = json.load(handle)
    seeds = [run["seed"] for run in data["runs"]]
    reductions = [run["defense_gain"] for run in data["runs"]]
    mean_reduction = data["mean_defense_gain"]
    sample_std = statistics.stdev(reductions) if len(reductions) > 1 else 0.0
    ci95 = student_t_multiplier(len(reductions) - 1) * (sample_std / (len(reductions) ** 0.5)) if len(reductions) > 1 else 0.0

    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    ax.scatter(seeds, reductions, color="#3b6ea8", s=36, zorder=3)
    ax.plot(seeds, reductions, color="#9ecae1", linewidth=1.0, alpha=0.8)
    ax.axhline(0.0, color="#777777", linestyle="--", linewidth=1.0)
    ax.axhline(mean_reduction, color="#d95f02", linestyle="-", linewidth=1.2, label=f"Mean = {mean_reduction:.3f}")
    ax.fill_between([min(seeds) - 0.5, max(seeds) + 0.5], mean_reduction - ci95, mean_reduction + ci95, color="#fdd0a2", alpha=0.4, label=f"95% CI = ±{ci95:.3f}")
    ax.set_xlabel("Seed")
    ax.set_ylabel("Signed Reduction")
    ax.set_title("Timing Reduction Stability Across Seeds")
    ax.set_xticks(seeds)
    ax.legend(frameon=False, loc="upper left")
    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(APP_DIR / "timing_stability_by_seed.pdf")
    plt.close(fig)


def main() -> None:
    ensure_dirs()
    style()
    generate_table_snippets()
    figure2_timing_main()
    figure3_compilation_conditioned_observability()
    figure4_hardware_main()
    figure3_compile_heatmaps()
    figure4_config_heatmaps()
    figure5_backend_heterogeneity()
    appendix_b1_classical_queue()
    appendix_b2_observability_ladder()
    appendix_b3_coexecution()
    appendix_b4_stability()
    appendix_timing_ablation()
    appendix_backend_choice_relation()


if __name__ == "__main__":
    main()
