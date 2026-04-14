#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


SWEEP_METHOD_ORDER = [
    "dcf_v1",
    "dcf_v3b",
    "dcf_v3c_b005",
    "dcf_v3c_b010",
    "dcf_v3c_b015",
    "dcf_v3c_b020",
    "dcf_v3c_b025",
]

STABILITY_PREVIOUS_MAP = {
    "dcf_v1": "dcf_v1",
    "dcf_v3b": "dcf_v3b",
    "dcf_v3c_b025": "dcf_v3c",
}


def method_metadata(method_key: str) -> tuple[str, str, str]:
    if method_key == "dcf_v1":
        return ("DCF v1", "v1", "")
    if method_key == "dcf_v3a":
        return ("DCF v3a", "v3a", "")
    if method_key == "dcf_v3b":
        return ("DCF v3b", "v3b", "")
    if method_key == "dcf_v3c":
        return ("DCF v3c", "v3c", "0.25")
    if method_key.startswith("dcf_v3c_b"):
        digits = method_key.rsplit("_b", 1)[-1]
        beta = f"{int(digits) / 100:.2f}"
        return ("DCF v3c", "v3c", beta)
    return (method_key, "", "")


def load_metrics(root_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not root_dir.exists():
        return rows
    for metrics_path in sorted(root_dir.glob("*/*/metrics.json")):
        with metrics_path.open() as f:
            row = json.load(f)
        method_key = row.get("method_key") or metrics_path.parent.parent.name
        method, variant, beta = method_metadata(method_key)
        row.setdefault("method_key", method_key)
        row.setdefault("method", method)
        row.setdefault("variant", variant)
        row.setdefault("beta", beta)
        row.setdefault("case", metrics_path.parent.name)
        row.setdefault("output_tag", root_dir.name)
        rows.append(row)
    return rows


def load_timing_steps(
    root_dir: Path, case_name: str, method_key: str
) -> list[dict[str, object]]:
    path = root_dir / "diagnostics" / case_name / method_key / "timing_steps.jsonl"
    rows: list[dict[str, object]] = []
    if not path.exists():
        return rows
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_sweep_rows(metrics_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    order = {method_key: index for index, method_key in enumerate(SWEEP_METHOD_ORDER)}
    rows: list[dict[str, object]] = []
    for row in metrics_rows:
        method_key = row["method_key"]
        if method_key not in order:
            continue
        rows.append(
            {
                "case": row["case"],
                "method": row["method"],
                "method_key": method_key,
                "variant": row["variant"],
                "beta": row["beta"],
                "tns": row["tns"],
                "wns": row["wns"],
                "hpwl": row["hpwl"],
                "runtime": row["runtime"],
                "status": row["status"],
                "output_tag": row.get("output_tag", ""),
                "run_label": row.get("run_label", ""),
                "sort_key": order[method_key],
            }
        )
    rows.sort(key=lambda row: (row["case"], row["sort_key"]))
    for row in rows:
        row.pop("sort_key", None)
    return rows


def build_stability_rows(
    previous_rows: list[dict[str, str]],
    repeat_rows: list[dict[str, str]],
    case_name: str,
) -> list[dict[str, object]]:
    previous_lookup = {(row["case"], row["method_key"]): row for row in previous_rows}
    repeat_lookup = {(row["case"], row["method_key"]): row for row in repeat_rows}
    rows: list[dict[str, object]] = []
    for repeat_key in ["dcf_v1", "dcf_v3b", "dcf_v3c_b025"]:
        previous_key = STABILITY_PREVIOUS_MAP[repeat_key]
        if (case_name, previous_key) not in previous_lookup:
            previous_key = repeat_key
        previous = previous_lookup[(case_name, previous_key)]
        repeat = repeat_lookup[(case_name, repeat_key)]
        method, variant, beta = method_metadata(repeat_key)
        rows.append(
            {
                "case": case_name,
                "method": method,
                "method_key_previous": previous_key,
                "method_key_repeat": repeat_key,
                "variant": variant,
                "beta": beta,
                "previous_tns": previous["tns"],
                "repeat_tns": repeat["tns"],
                "delta_tns": f"{float(repeat['tns']) - float(previous['tns']):.6f}",
                "previous_wns": previous["wns"],
                "repeat_wns": repeat["wns"],
                "delta_wns": f"{float(repeat['wns']) - float(previous['wns']):.6f}",
                "previous_hpwl": previous["hpwl"],
                "repeat_hpwl": repeat["hpwl"],
                "delta_hpwl": f"{float(repeat['hpwl']) - float(previous['hpwl']):.6f}",
                "previous_runtime": previous["runtime"],
                "repeat_runtime": repeat["runtime"],
                "delta_runtime": f"{float(repeat['runtime']) - float(previous['runtime']):.6f}",
            }
        )
    return rows


def build_trajectory_rows(
    root_dir: Path, case_name: str
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    long_rows: list[dict[str, object]] = []
    by_method: dict[str, dict[int, dict[str, object]]] = {}
    for method_key in SWEEP_METHOD_ORDER:
        rows = load_timing_steps(root_dir, case_name, method_key)
        method, variant, beta = method_metadata(method_key)
        by_method[method_key] = {}
        for row in rows:
            step_id = int(row["timing_step_id"])
            by_method[method_key][step_id] = row
            long_rows.append(
                {
                    "case": case_name,
                    "method": method,
                    "method_key": method_key,
                    "variant": variant,
                    "beta": beta,
                    "timing_step_id": row["timing_step_id"],
                    "gp_iter": row["gp_iter"],
                    "tns": row["TNS"],
                    "wns": row["WNS"],
                    "exported_pair_count": row["exported_pair_count"],
                    "total_exported_weight_mass": row["total_exported_weight_mass"],
                }
            )

    delta_rows: list[dict[str, object]] = []
    baseline = by_method.get("dcf_v3b", {})
    for method_key in [
        key for key in SWEEP_METHOD_ORDER if key.startswith("dcf_v3c_b")
    ]:
        method, variant, beta = method_metadata(method_key)
        for step_id, row in sorted(by_method.get(method_key, {}).items()):
            if step_id not in baseline:
                continue
            baseline_row = baseline[step_id]
            delta_rows.append(
                {
                    "case": case_name,
                    "method": method,
                    "method_key": method_key,
                    "variant": variant,
                    "beta": beta,
                    "timing_step_id": step_id,
                    "gp_iter": row["gp_iter"],
                    "tns": row["TNS"],
                    "wns": row["WNS"],
                    "exported_pair_count": row["exported_pair_count"],
                    "total_exported_weight_mass": row["total_exported_weight_mass"],
                    "tns_delta_vs_v3b": float(row["TNS"]) - float(baseline_row["TNS"]),
                    "wns_delta_vs_v3b": float(row["WNS"]) - float(baseline_row["WNS"]),
                    "exported_pair_count_delta_vs_v3b": int(row["exported_pair_count"])
                    - int(baseline_row["exported_pair_count"]),
                    "total_exported_weight_mass_delta_vs_v3b": float(
                        row["total_exported_weight_mass"]
                    )
                    - float(baseline_row["total_exported_weight_mass"]),
                }
            )

    long_rows.sort(key=lambda row: (row["method_key"], int(row["timing_step_id"])))
    delta_rows.sort(key=lambda row: (row["method_key"], int(row["timing_step_id"])))
    return long_rows, delta_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--sweep-tag", default="dcf_v3_beta_sweep")
    parser.add_argument("--repeat-tag", default="dcf_v3_beta_sweep_repeat1")
    parser.add_argument("--previous-tag", default="dcf_v3")
    parser.add_argument("--case", default="superblue16")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    sweep_root = root / "results" / args.sweep_tag
    repeat_root = root / "results" / args.repeat_tag
    previous_root = root / "results" / args.previous_tag

    sweep_metrics = load_metrics(sweep_root)
    repeat_metrics = load_metrics(repeat_root)
    previous_metrics = load_metrics(previous_root)

    summary_dir = sweep_root / "summary"
    summary_dir.mkdir(parents=True, exist_ok=True)

    sweep_rows = build_sweep_rows(sweep_metrics)
    write_csv(
        summary_dir / "beta_sweep_metrics.csv",
        sweep_rows,
        [
            "case",
            "method",
            "method_key",
            "variant",
            "beta",
            "tns",
            "wns",
            "hpwl",
            "runtime",
            "status",
            "output_tag",
            "run_label",
        ],
    )

    stability_rows = build_stability_rows(previous_metrics, repeat_metrics, args.case)
    write_csv(
        summary_dir / f"{args.case}_stability.csv",
        stability_rows,
        [
            "case",
            "method",
            "method_key_previous",
            "method_key_repeat",
            "variant",
            "beta",
            "previous_tns",
            "repeat_tns",
            "delta_tns",
            "previous_wns",
            "repeat_wns",
            "delta_wns",
            "previous_hpwl",
            "repeat_hpwl",
            "delta_hpwl",
            "previous_runtime",
            "repeat_runtime",
            "delta_runtime",
        ],
    )

    long_rows, delta_rows = build_trajectory_rows(sweep_root, args.case)
    write_csv(
        summary_dir / f"{args.case}_trajectory_long.csv",
        long_rows,
        [
            "case",
            "method",
            "method_key",
            "variant",
            "beta",
            "timing_step_id",
            "gp_iter",
            "tns",
            "wns",
            "exported_pair_count",
            "total_exported_weight_mass",
        ],
    )
    write_csv(
        summary_dir / f"{args.case}_trajectory_vs_v3b.csv",
        delta_rows,
        [
            "case",
            "method",
            "method_key",
            "variant",
            "beta",
            "timing_step_id",
            "gp_iter",
            "tns",
            "wns",
            "exported_pair_count",
            "total_exported_weight_mass",
            "tns_delta_vs_v3b",
            "wns_delta_vs_v3b",
            "exported_pair_count_delta_vs_v3b",
            "total_exported_weight_mass_delta_vs_v3b",
        ],
    )


if __name__ == "__main__":
    main()
