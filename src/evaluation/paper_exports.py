from __future__ import annotations

from pathlib import Path

from evaluation.paper_summary import (
    export_main_summary,
    export_tradeoff_summary,
    export_ablation_summary,
)
from evaluation.paper_tables import export_paper_main_table


def export_all_paper_summaries(output_dir: str | Path):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    main_results = export_main_summary(output_dir)
    export_paper_main_table(main_results, output_dir / 'paper_main_table.csv')
    tradeoff = export_tradeoff_summary(output_dir)
    ablation = export_ablation_summary(output_dir)

    return {
        'main_results': main_results,
        'tradeoff': tradeoff,
        'ablation': ablation,
    }
