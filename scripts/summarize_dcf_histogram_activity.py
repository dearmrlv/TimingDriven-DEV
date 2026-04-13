#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path

import numpy as np


TOP_KS = [100, 1000, 5000]
BIN_NAMES = ["hist_bin0", "hist_bin1", "hist_bin2", "hist_bin3"]
QUANTILES = {
    "min": 0.0,
    "q25": 0.25,
    "q50": 0.5,
    "q75": 0.75,
    "q90": 0.9,
    "q99": 0.99,
    "max": 1.0,
}


def load_rows(path: Path) -> list[dict[str, object]]:
    rows = []
    with gzip.open(path, "rt", newline="") as fin:
        reader = csv.DictReader(fin)
        for row in reader:
            hist = np.asarray(
                [float(row[name]) for name in BIN_NAMES], dtype=np.float64
            )
            rows.append(
                {
                    "hist": hist,
                    "weight": float(
                        row.get("final_exported_weight_after_ema")
                        or row["final_exported_weight"]
                    ),
                    "T": float(row["T"]),
                }
            )
    rows.sort(key=lambda row: (-float(row["weight"]),))
    return rows


def safe_quantiles(values: np.ndarray) -> dict[str, float | None]:
    if values.size == 0:
        return {name: None for name in QUANTILES}
    return {name: float(np.quantile(values, q)) for name, q in QUANTILES.items()}


def average_bin_composition(rows: list[dict[str, object]]) -> dict[str, float]:
    if not rows:
        return {name: 0.0 for name in BIN_NAMES}
    normalized = []
    for row in rows:
        hist = row["hist"]
        total = float(hist.sum())
        if total > 0:
            normalized.append(hist / total)
    if not normalized:
        return {name: 0.0 for name in BIN_NAMES}
    mean_comp = np.mean(np.vstack(normalized), axis=0)
    return {name: float(mean_comp[idx]) for idx, name in enumerate(BIN_NAMES)}


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    hist_matrix = np.vstack([row["hist"] for row in rows]) if rows else np.zeros((0, 4))
    t_values = np.asarray([float(row["T"]) for row in rows], dtype=np.float64)
    total_mass_per_bin = (
        hist_matrix.sum(axis=0) if rows else np.zeros(4, dtype=np.float64)
    )
    total_hist_mass = float(total_mass_per_bin.sum())

    summary = {
        "total_pair_count": len(rows),
        "total_hist_mass_per_bin": {
            name: float(total_mass_per_bin[idx]) for idx, name in enumerate(BIN_NAMES)
        },
        "hist_mass_fraction_per_bin": {
            name: float(total_mass_per_bin[idx] / total_hist_mass)
            if total_hist_mass > 0
            else 0.0
            for idx, name in enumerate(BIN_NAMES)
        },
        "pair_fraction_with_nonzero_bin": {
            name: float(np.count_nonzero(hist_matrix[:, idx] > 0) / len(rows))
            if rows
            else 0.0
            for idx, name in enumerate(BIN_NAMES)
        },
        "topk_average_bin_composition": {},
        "T_summary": {
            "mean": float(t_values.mean()) if t_values.size else 0.0,
            "quantiles": safe_quantiles(t_values),
            "fraction_positive": float(np.count_nonzero(t_values > 0) / t_values.size)
            if t_values.size
            else 0.0,
        },
        "topk_T_fraction_positive": {},
    }

    for topk in TOP_KS:
        subset = rows[:topk]
        key = str(topk)
        summary["topk_average_bin_composition"][key] = average_bin_composition(subset)
        subset_t = np.asarray([float(row["T"]) for row in subset], dtype=np.float64)
        summary["topk_T_fraction_positive"][key] = (
            float(np.count_nonzero(subset_t > 0) / subset_t.size)
            if subset_t.size
            else 0.0
        )

    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    rows = load_rows(Path(args.input))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summarize(rows), indent=2) + "\n")


if __name__ == "__main__":
    main()
