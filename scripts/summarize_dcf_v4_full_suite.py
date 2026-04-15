#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


CASES = [
    "superblue1",
    "superblue3",
    "superblue4",
    "superblue5",
    "superblue7",
    "superblue10",
    "superblue16",
    "superblue18",
]

METHOD_ORDER = [
    ("efficient_tdp", "Efficient-TDP"),
    ("dcf_v3b", "DCF v3b"),
    ("dcf_v3c_b020", "DCF v3c beta=0.20"),
    ("dcf_v4", "DCF v4"),
]


def read_metrics(path: Path) -> dict[str, str]:
    with path.open() as f:
        return json.load(f)


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_timing_steps(
    root_dir: Path, case_name: str, method_key: str
) -> list[dict[str, object]]:
    path = root_dir / "diagnostics" / case_name / method_key / "timing_steps.jsonl"
    if not path.exists():
        return []
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--dcf-tag", default="dcf_v4_full_suite")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    baseline_root = root / "results" / "baselines" / "efficient_tdp"
    dcf_root = root / "results" / args.dcf_tag
    artifacts_root = root / "docs" / "artifacts"

    metric_rows: list[dict[str, object]] = []
    per_case: dict[str, dict[str, dict[str, str]]] = {}
    for case_name in CASES:
        per_case[case_name] = {}
        baseline_metrics = read_metrics(baseline_root / case_name / "metrics.json")
        per_case[case_name]["efficient_tdp"] = baseline_metrics
        metric_rows.append(
            {
                "case": case_name,
                "method": "Efficient-TDP",
                "method_key": "efficient_tdp",
                "tns": baseline_metrics["tns"],
                "wns": baseline_metrics["wns"],
                "hpwl": baseline_metrics["hpwl"],
                "runtime": baseline_metrics["runtime"],
                "status": baseline_metrics["status"],
            }
        )
        for method_key, method_name in METHOD_ORDER[1:]:
            metrics = read_metrics(dcf_root / method_key / case_name / "metrics.json")
            per_case[case_name][method_key] = metrics
            metric_rows.append(
                {
                    "case": case_name,
                    "method": method_name,
                    "method_key": method_key,
                    "tns": metrics["tns"],
                    "wns": metrics["wns"],
                    "hpwl": metrics["hpwl"],
                    "runtime": metrics["runtime"],
                    "status": metrics["status"],
                }
            )

    order = {case: index for index, case in enumerate(CASES)}
    method_order = {key: index for index, (key, _) in enumerate(METHOD_ORDER)}
    metric_rows.sort(
        key=lambda row: (order[row["case"]], method_order[row["method_key"]])
    )
    write_csv(
        artifacts_root / "dcf_v4_full_suite_metrics.csv",
        metric_rows,
        ["case", "method", "method_key", "tns", "wns", "hpwl", "runtime", "status"],
    )

    def better(metric: str, lhs: dict[str, str], rhs: dict[str, str]) -> bool:
        if metric == "hpwl":
            return float(lhs[metric]) < float(rhs[metric])
        return float(lhs[metric]) > float(rhs[metric])

    summary_row = {
        "cases_total": len(CASES),
        "v4_beats_v3b_tns": sum(
            1
            for case in CASES
            if better("tns", per_case[case]["dcf_v4"], per_case[case]["dcf_v3b"])
        ),
        "v4_beats_v3b_wns": sum(
            1
            for case in CASES
            if better("wns", per_case[case]["dcf_v4"], per_case[case]["dcf_v3b"])
        ),
        "v4_beats_v3c_b020_tns": sum(
            1
            for case in CASES
            if better("tns", per_case[case]["dcf_v4"], per_case[case]["dcf_v3c_b020"])
        ),
        "v4_beats_v3c_b020_wns": sum(
            1
            for case in CASES
            if better("wns", per_case[case]["dcf_v4"], per_case[case]["dcf_v3c_b020"])
        ),
        "v4_beats_v3b_hpwl": sum(
            1
            for case in CASES
            if better("hpwl", per_case[case]["dcf_v4"], per_case[case]["dcf_v3b"])
        ),
        "v4_avg_runtime_sec": f"{sum(float(per_case[case]['dcf_v4']['runtime']) for case in CASES) / len(CASES):.3f}",
        "v3b_avg_runtime_sec": f"{sum(float(per_case[case]['dcf_v3b']['runtime']) for case in CASES) / len(CASES):.3f}",
        "v3c_b020_avg_runtime_sec": f"{sum(float(per_case[case]['dcf_v3c_b020']['runtime']) for case in CASES) / len(CASES):.3f}",
        "hpwl_runtime_note": "Compare per-case rows; v4 summary keeps only lightweight counts and mean runtimes.",
    }
    write_csv(
        artifacts_root / "dcf_v4_full_suite_summary.csv",
        [summary_row],
        list(summary_row.keys()),
    )

    trajectory_rows: list[dict[str, object]] = []
    for method_key, method_name in [
        ("dcf_v3b", "DCF v3b"),
        ("dcf_v3c_b020", "DCF v3c beta=0.20"),
        ("dcf_v4", "DCF v4"),
    ]:
        for row in load_timing_steps(dcf_root, "superblue16", method_key):
            trajectory_rows.append(
                {
                    "case": "superblue16",
                    "method": method_name,
                    "method_key": method_key,
                    "timing_step_id": row["timing_step_id"],
                    "gp_iter": row["gp_iter"],
                    "tns": row["TNS"],
                    "wns": row["WNS"],
                    "exported_pair_count": row["exported_pair_count"],
                    "total_exported_weight_mass": row["total_exported_weight_mass"],
                }
            )
    trajectory_rows.sort(
        key=lambda row: (method_order[row["method_key"]], int(row["timing_step_id"]))
    )
    write_csv(
        artifacts_root / "dcf_v4_superblue16_trajectory.csv",
        trajectory_rows,
        [
            "case",
            "method",
            "method_key",
            "timing_step_id",
            "gp_iter",
            "tns",
            "wns",
            "exported_pair_count",
            "total_exported_weight_mass",
        ],
    )


if __name__ == "__main__":
    main()
