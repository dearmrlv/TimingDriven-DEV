#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
from pathlib import Path

import numpy as np


TOP_KS = [100, 1000, 5000]
LENGTH_QUANTILES = {
    "mean": None,
    "median": 0.5,
    "q90": 0.9,
    "q99": 0.99,
    "max": 1.0,
}


def load_pin2pin_rows(path: Path) -> list[dict[str, object]]:
    rows = []
    with gzip.open(path, "rt", newline="") as fin:
        reader = csv.DictReader(fin)
        for row in reader:
            rows.append(
                {
                    "pair": (int(row["src_pin_id"]), int(row["dst_pin_id"])),
                    "length": float(row["current_manhattan_length"]),
                    "score": float(row["final_exported_weight"]),
                }
            )
    return sorted(rows, key=lambda row: (-float(row["score"]), row["pair"]))


def load_dcf_rows(path: Path) -> list[dict[str, object]]:
    rows = []
    with gzip.open(path, "rt", newline="") as fin:
        reader = csv.DictReader(fin)
        for row in reader:
            utility_u = float(row["utility_U"])
            m_value = float(row["M"])
            s_value = float(row["S"])
            if (
                "final_exported_weight_after_ema" in row
                and row["final_exported_weight_after_ema"]
            ):
                original_score = float(row["final_exported_weight_after_ema"])
            elif "mapped_weight_before_ema" in row and row["mapped_weight_before_ema"]:
                original_score = float(row["mapped_weight_before_ema"])
            else:
                original_score = float(row["final_exported_weight"])
            rows.append(
                {
                    "pair": (int(row["src_pin_id"]), int(row["dst_pin_id"])),
                    "length": float(row["current_manhattan_length"]),
                    "original_dcf": original_score,
                    "no_eta": math.log1p(max(0.0, utility_u)),
                    "M_only": math.log1p(max(0.0, m_value)),
                    "S_only": math.log1p(max(0.0, s_value)),
                }
            )
    return rows


def rank_rows(rows: list[dict[str, object]], score_key: str) -> list[dict[str, object]]:
    ranked = []
    for row in rows:
        ranked.append(
            {
                "pair": row["pair"],
                "length": float(row["length"]),
                "score": float(row[score_key]),
            }
        )
    return sorted(ranked, key=lambda row: (-row["score"], row["pair"]))


def concentration(rows: list[dict[str, object]], topk: int) -> float:
    if not rows:
        return 0.0
    scores = np.asarray([float(row["score"]) for row in rows], dtype=np.float64)
    total = float(scores.sum())
    if total <= 0:
        return 0.0
    return float(scores[:topk].sum() / total)


def topk_length_stats(
    rows: list[dict[str, object]], topk: int
) -> dict[str, float | int]:
    subset = rows[:topk]
    if not subset:
        return {
            "count": 0,
            "mean": 0.0,
            "median": 0.0,
            "q90": 0.0,
            "q99": 0.0,
            "max": 0.0,
        }
    lengths = np.asarray([float(row["length"]) for row in subset], dtype=np.float64)
    stats = {"count": int(lengths.size), "mean": float(lengths.mean())}
    for key, quantile in LENGTH_QUANTILES.items():
        if quantile is None:
            continue
        stats[key] = float(np.quantile(lengths, quantile))
    return stats


def topk_overlap(
    lhs: list[dict[str, object]], rhs: list[dict[str, object]], topk: int
) -> dict[str, float | int]:
    lhs_top = {row["pair"] for row in lhs[:topk]}
    rhs_top = {row["pair"] for row in rhs[:topk]}
    overlap = lhs_top & rhs_top
    union = lhs_top | rhs_top
    return {
        "overlap_count": len(overlap),
        "jaccard": float(len(overlap) / len(union)) if union else 0.0,
    }


def variant_summary(
    ranked_rows: list[dict[str, object]],
    pin2pin_rows: list[dict[str, object]],
    original_rows: list[dict[str, object]],
) -> dict[str, object]:
    summary = {
        "total_pair_count": len(ranked_rows),
        "total_score_mass": float(
            np.asarray(
                [float(row["score"]) for row in ranked_rows], dtype=np.float64
            ).sum()
        )
        if ranked_rows
        else 0.0,
        "topk_cumulative_score_fraction": {},
        "topk_length_stats": {},
        "pin2pin_overlap": {},
        "original_dcf_overlap": {},
    }
    for topk in TOP_KS:
        key = str(topk)
        summary["topk_cumulative_score_fraction"][key] = concentration(
            ranked_rows, topk
        )
        summary["topk_length_stats"][key] = topk_length_stats(ranked_rows, topk)
        summary["pin2pin_overlap"][key] = topk_overlap(ranked_rows, pin2pin_rows, topk)
        summary["original_dcf_overlap"][key] = topk_overlap(
            ranked_rows, original_rows, topk
        )

    summary["deltas_vs_original_dcf"] = {
        "top_1000_median_length_delta": summary["topk_length_stats"]["1000"]["median"]
        - topk_length_stats(original_rows, 1000)["median"],
        "top_100_score_fraction_delta": summary["topk_cumulative_score_fraction"]["100"]
        - concentration(original_rows, 100),
        "top_1000_score_fraction_delta": summary["topk_cumulative_score_fraction"][
            "1000"
        ]
        - concentration(original_rows, 1000),
        "top_5000_score_fraction_delta": summary["topk_cumulative_score_fraction"][
            "5000"
        ]
        - concentration(original_rows, 5000),
    }
    return summary


def write_csv(output_path: Path, results: dict[str, object]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as fout:
        writer = csv.writer(fout)
        writer.writerow(
            [
                "variant",
                "topk",
                "pin2pin_overlap_count",
                "pin2pin_jaccard",
                "original_dcf_jaccard",
                "topk_mean_length",
                "topk_median_length",
                "topk_q90_length",
                "topk_q99_length",
                "topk_max_length",
                "topk_score_fraction",
            ]
        )
        for variant_name, summary in results["variants"].items():
            for topk in TOP_KS:
                key = str(topk)
                writer.writerow(
                    [
                        variant_name,
                        topk,
                        summary["pin2pin_overlap"][key]["overlap_count"],
                        summary["pin2pin_overlap"][key]["jaccard"],
                        summary["original_dcf_overlap"][key]["jaccard"],
                        summary["topk_length_stats"][key]["mean"],
                        summary["topk_length_stats"][key]["median"],
                        summary["topk_length_stats"][key]["q90"],
                        summary["topk_length_stats"][key]["q99"],
                        summary["topk_length_stats"][key]["max"],
                        summary["topk_cumulative_score_fraction"][key],
                    ]
                )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dcf", required=True)
    parser.add_argument("--pin2pin", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--csv-output")
    args = parser.parse_args()

    dcf_rows = load_dcf_rows(Path(args.dcf))
    pin2pin_rows = load_pin2pin_rows(Path(args.pin2pin))
    original_rows = rank_rows(dcf_rows, "original_dcf")

    results = {
        "variants": {},
        "pin2pin": {
            "total_pair_count": len(pin2pin_rows),
            "total_score_mass": float(
                np.asarray(
                    [float(row["score"]) for row in pin2pin_rows], dtype=np.float64
                ).sum()
            )
            if pin2pin_rows
            else 0.0,
            "topk_cumulative_score_fraction": {
                str(topk): concentration(pin2pin_rows, topk) for topk in TOP_KS
            },
            "topk_length_stats": {
                str(topk): topk_length_stats(pin2pin_rows, topk) for topk in TOP_KS
            },
        },
    }

    for variant_name in ["original_dcf", "no_eta", "M_only", "S_only"]:
        ranked_rows = rank_rows(dcf_rows, variant_name)
        results["variants"][variant_name] = variant_summary(
            ranked_rows, pin2pin_rows, original_rows
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2) + "\n")

    if args.csv_output:
        write_csv(Path(args.csv_output), results)


if __name__ == "__main__":
    main()
