#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path

import numpy as np


TOP_KS = [100, 1000, 5000]
LENGTH_QUANTILES = [0.0, 0.25, 0.5, 0.75, 0.9, 0.99, 1.0]


def safe_corr(lhs: np.ndarray, rhs: np.ndarray) -> float | None:
    if lhs.size < 2 or rhs.size < 2:
        return None
    if np.allclose(lhs, lhs[0]) or np.allclose(rhs, rhs[0]):
        return None
    return float(np.corrcoef(lhs, rhs)[0, 1])


def rankdata(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(values.shape[0], dtype=np.float64)
    start = 0
    while start < order.size:
        end = start + 1
        while end < order.size and values[order[end]] == values[order[start]]:
            end += 1
        avg_rank = 0.5 * (start + end - 1) + 1.0
        ranks[order[start:end]] = avg_rank
        start = end
    return ranks


def safe_spearman(lhs: np.ndarray, rhs: np.ndarray) -> float | None:
    if lhs.size < 2 or rhs.size < 2:
        return None
    return safe_corr(rankdata(lhs), rankdata(rhs))


def load_rows(path: Path) -> list[dict[str, float | int | tuple[int, int]]]:
    rows = []
    with gzip.open(path, "rt", newline="") as fin:
        reader = csv.DictReader(fin)
        for row in reader:
            pair = (int(row["src_pin_id"]), int(row["dst_pin_id"]))
            rows.append(
                {
                    "pair": pair,
                    "weight": float(row["final_exported_weight"]),
                    "length": float(row["current_manhattan_length"]),
                }
            )
    rows.sort(key=lambda row: row["weight"], reverse=True)
    return rows


def rows_to_maps(rows):
    weight_map = {}
    length_map = {}
    rank_map = {}
    for index, row in enumerate(rows, start=1):
        pair = row["pair"]
        weight_map[pair] = row["weight"]
        length_map[pair] = row["length"]
        rank_map[pair] = index
    return weight_map, length_map, rank_map


def length_stats(rows, topk=None):
    subset = rows if topk is None else rows[:topk]
    if not subset:
        return {
            "count": 0,
            "mean": 0.0,
            "median": 0.0,
            "quantiles": {str(q): 0.0 for q in LENGTH_QUANTILES},
        }
    lengths = np.asarray([row["length"] for row in subset], dtype=np.float64)
    return {
        "count": int(lengths.size),
        "mean": float(lengths.mean()),
        "median": float(np.median(lengths)),
        "quantiles": {str(q): float(np.quantile(lengths, q)) for q in LENGTH_QUANTILES},
    }


def cumulative_mass_fraction(rows, topk):
    if not rows:
        return 0.0
    weights = np.asarray([row["weight"] for row in rows], dtype=np.float64)
    return float(weights[:topk].sum() / weights.sum())


def build_summary(rows):
    weights = np.asarray([row["weight"] for row in rows], dtype=np.float64)
    total_mass = float(weights.sum()) if weights.size else 0.0
    return {
        "total_pair_count": len(rows),
        "total_weight_mass": total_mass,
        "length_stats": {
            "all": length_stats(rows),
            "top_100": length_stats(rows, 100),
            "top_1000": length_stats(rows, 1000),
        },
        "topk_cumulative_weight_mass_fraction": {
            str(k): cumulative_mass_fraction(rows, k) for k in TOP_KS
        },
    }


def compare_rows(dcf_rows, pin2pin_rows):
    dcf_weight_map, dcf_length_map, dcf_rank_map = rows_to_maps(dcf_rows)
    pin_weight_map, pin_length_map, pin_rank_map = rows_to_maps(pin2pin_rows)

    dcf_pairs = set(dcf_weight_map)
    pin_pairs = set(pin_weight_map)
    shared_pairs = sorted(dcf_pairs & pin_pairs)
    union_pairs = dcf_pairs | pin_pairs

    dcf_summary = build_summary(dcf_rows)
    pin_summary = build_summary(pin2pin_rows)

    topk_jaccard = {}
    for topk in TOP_KS:
        dcf_top = {row["pair"] for row in dcf_rows[:topk]}
        pin_top = {row["pair"] for row in pin2pin_rows[:topk]}
        union_top = dcf_top | pin_top
        topk_jaccard[str(topk)] = {
            "dcf_topk_count": len(dcf_top),
            "pin2pin_topk_count": len(pin_top),
            "overlap_count": len(dcf_top & pin_top),
            "jaccard": float(len(dcf_top & pin_top) / len(union_top))
            if union_top
            else 0.0,
        }

    weighted_jaccard = None
    shared_weight_min_sum = 0.0
    union_weight_max_sum = 0.0
    for pair in union_pairs:
        dcf_weight = dcf_weight_map.get(pair, 0.0)
        pin_weight = pin_weight_map.get(pair, 0.0)
        shared_weight_min_sum += min(dcf_weight, pin_weight)
        union_weight_max_sum += max(dcf_weight, pin_weight)
    if union_weight_max_sum > 0:
        weighted_jaccard = float(shared_weight_min_sum / union_weight_max_sum)

    shared_dcf_weights = np.asarray(
        [dcf_weight_map[pair] for pair in shared_pairs], dtype=np.float64
    )
    shared_pin_weights = np.asarray(
        [pin_weight_map[pair] for pair in shared_pairs], dtype=np.float64
    )
    shared_dcf_ranks = np.asarray(
        [dcf_rank_map[pair] for pair in shared_pairs], dtype=np.float64
    )
    shared_pin_ranks = np.asarray(
        [pin_rank_map[pair] for pair in shared_pairs], dtype=np.float64
    )

    shared_lengths = np.asarray(
        [0.5 * (dcf_length_map[pair] + pin_length_map[pair]) for pair in shared_pairs],
        dtype=np.float64,
    )

    return {
        "dcf": dcf_summary,
        "pin2pin": pin_summary,
        "shared": {
            "overlap_count": len(shared_pairs),
            "union_count": len(union_pairs),
            "overlap_fraction_of_union": float(len(shared_pairs) / len(union_pairs))
            if union_pairs
            else 0.0,
            "shared_weight_min_sum": shared_weight_min_sum,
            "weighted_jaccard": weighted_jaccard,
            "pearson_weight_correlation": safe_corr(
                shared_dcf_weights, shared_pin_weights
            ),
            "spearman_weight_correlation": safe_spearman(
                shared_dcf_weights, shared_pin_weights
            ),
            "spearman_rank_correlation": safe_spearman(
                shared_dcf_ranks, shared_pin_ranks
            ),
            "shared_length_stats": {
                "count": int(shared_lengths.size),
                "mean": float(shared_lengths.mean()) if shared_lengths.size else 0.0,
                "median": float(np.median(shared_lengths))
                if shared_lengths.size
                else 0.0,
            },
        },
        "topk_jaccard": topk_jaccard,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dcf", required=True)
    parser.add_argument("--pin2pin", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    dcf_path = Path(args.dcf)
    pin2pin_path = Path(args.pin2pin)
    output_path = Path(args.output)

    result = compare_rows(load_rows(dcf_path), load_rows(pin2pin_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
