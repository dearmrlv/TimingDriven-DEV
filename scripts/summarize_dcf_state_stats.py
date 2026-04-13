#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
from pathlib import Path

import numpy as np


QUANTILES = {
    "min": 0.0,
    "q25": 0.25,
    "q50": 0.5,
    "q75": 0.75,
    "q90": 0.9,
    "q99": 0.99,
    "max": 1.0,
}

SUMMARY_FIELDS = [
    "num_candidate_predecessors",
    "max_prob",
    "top3_prob_sum",
    "attribution_entropy",
    "node_mass_total",
    "outgoing_mass_total",
    "incoming_mass_total",
]

WEIGHTED_FIELDS = [
    "max_prob",
    "top3_prob_sum",
    "attribution_entropy",
    "num_candidate_predecessors",
]

SHARPNESS_RULES = {
    "max_prob_ge_0p9": lambda data: data["max_prob"] >= 0.9,
    "max_prob_ge_0p7": lambda data: data["max_prob"] >= 0.7,
    "max_prob_le_0p3": lambda data: data["max_prob"] <= 0.3,
    "num_candidate_predecessors_eq_1": lambda data: (
        data["num_candidate_predecessors"] == 1
    ),
    "num_candidate_predecessors_ge_3": lambda data: (
        data["num_candidate_predecessors"] >= 3
    ),
    "top3_prob_sum_ge_0p95": lambda data: data["top3_prob_sum"] >= 0.95,
    "top3_prob_sum_le_0p5": lambda data: data["top3_prob_sum"] <= 0.5,
}


def load_state_stats(path: Path) -> dict[str, np.ndarray]:
    columns: dict[str, list[float | str]] = {}
    with gzip.open(path, "rt", newline="") as fin:
        reader = csv.DictReader(fin)
        for row in reader:
            for key, value in row.items():
                columns.setdefault(key, []).append(value)

    arrays: dict[str, np.ndarray] = {}
    for key, values in columns.items():
        if key in {"pin_name", "rf"}:
            arrays[key] = np.asarray(values, dtype=object)
        elif key in {"pin_id", "num_candidate_predecessors"}:
            arrays[key] = np.asarray(values, dtype=np.int64)
        else:
            arrays[key] = np.asarray(values, dtype=np.float64)
    return arrays


def finite_mask(values: np.ndarray) -> np.ndarray:
    return np.isfinite(values)


def safe_quantiles(values: np.ndarray) -> dict[str, float | None]:
    if values.size == 0:
        return {name: None for name in QUANTILES}
    return {name: float(np.quantile(values, q)) for name, q in QUANTILES.items()}


def weighted_mean(values: np.ndarray, weights: np.ndarray) -> float | None:
    if values.size == 0 or weights.size == 0:
        return None
    total = float(weights.sum())
    if total <= 0:
        return None
    return float(np.dot(values, weights) / total)


def weighted_quantiles(
    values: np.ndarray, weights: np.ndarray
) -> dict[str, float | None]:
    if values.size == 0 or weights.size == 0:
        return {name: None for name in QUANTILES}
    order = np.argsort(values, kind="mergesort")
    sorted_values = values[order]
    sorted_weights = weights[order]
    total = float(sorted_weights.sum())
    if total <= 0:
        return {name: None for name in QUANTILES}
    cumulative = np.cumsum(sorted_weights)
    result = {}
    for name, quantile in QUANTILES.items():
        target = quantile * total
        index = int(np.searchsorted(cumulative, target, side="left"))
        index = min(max(index, 0), sorted_values.size - 1)
        result[name] = float(sorted_values[index])
    return result


def weighted_fraction(mask: np.ndarray, weights: np.ndarray) -> float | None:
    if mask.size == 0 or weights.size == 0:
        return None
    total = float(weights.sum())
    if total <= 0:
        return None
    return float(weights[mask].sum() / total)


def summarize_case(data: dict[str, np.ndarray]) -> dict[str, object]:
    node_mass = data["node_mass_total"]
    finite_attr_mask = (
        np.isfinite(data["max_prob"])
        & np.isfinite(data["top3_prob_sum"])
        & np.isfinite(data["attribution_entropy"])
    )
    positive_mass_mask = np.isfinite(node_mass) & (node_mass > 0)

    summary: dict[str, object] = {
        "row_counts": {
            "state_rows": int(node_mass.size),
            "rows_with_nonzero_node_mass_total": int(
                np.count_nonzero(positive_mass_mask)
            ),
            "rows_with_finite_attribution_stats": int(
                np.count_nonzero(finite_attr_mask)
            ),
        },
        "quantiles": {},
        "mass_weighted": {},
        "sharpness_fractions": {},
    }

    for field in SUMMARY_FIELDS:
        values = data[field]
        mask = finite_mask(values)
        summary["quantiles"][field] = safe_quantiles(values[mask])

    weights = node_mass[positive_mass_mask]
    for field in WEIGHTED_FIELDS:
        values = data[field]
        mask = positive_mass_mask & finite_mask(values)
        summary["mass_weighted"][field] = {
            "mean": weighted_mean(values[mask], node_mass[mask]),
            "quantiles": weighted_quantiles(values[mask], node_mass[mask]),
        }

    for name, rule in SHARPNESS_RULES.items():
        mask = finite_attr_mask
        selected = rule(data) & mask
        summary["sharpness_fractions"][name] = {
            "raw_fraction": float(np.count_nonzero(selected) / np.count_nonzero(mask))
            if np.count_nonzero(mask)
            else None,
            "mass_weighted_fraction": weighted_fraction(
                selected[positive_mass_mask], weights
            ),
        }

    normalized_mask = finite_attr_mask & (data["num_candidate_predecessors"] > 1)
    normalized_entropy = np.zeros(node_mass.size, dtype=np.float64)
    normalized_entropy[:] = np.nan
    normalized_entropy[normalized_mask] = data["attribution_entropy"][
        normalized_mask
    ] / np.log(data["num_candidate_predecessors"][normalized_mask])
    finite_normalized = np.isfinite(normalized_entropy)
    summary["normalized_entropy"] = {
        "row_count": int(np.count_nonzero(finite_normalized)),
        "quantiles": safe_quantiles(normalized_entropy[finite_normalized]),
        "mass_weighted": {
            "mean": weighted_mean(
                normalized_entropy[finite_normalized], node_mass[finite_normalized]
            ),
            "quantiles": weighted_quantiles(
                normalized_entropy[finite_normalized], node_mass[finite_normalized]
            ),
        },
    }

    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    summary = summarize_case(load_state_stats(input_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
