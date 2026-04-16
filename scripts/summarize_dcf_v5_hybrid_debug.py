#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


LAMBDAS = [
    ("dcf_v5_hybrid_l010", "0.10"),
    ("dcf_v5_hybrid_l020", "0.20"),
    ("dcf_v5_hybrid_l030", "0.30"),
]


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def copy_csv(src: Path, dst: Path) -> None:
    rows = list(csv.DictReader(src.open())) if src.exists() else []
    fieldnames = rows[0].keys() if rows else []
    write_csv(dst, rows, list(fieldnames))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--debug-dir", default="results/hybrid_debug")
    parser.add_argument("--case", default="superblue18")
    parser.add_argument("--timing-step", default="1")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    raw_root = root / args.debug_dir / args.case
    artifacts = root / "docs" / "artifacts"
    step_dir_name = f"step_{int(args.timing_step):03d}"

    first_scheme = raw_root / LAMBDAS[0][0] / step_dir_name
    copy_csv(
        first_scheme / "base_pairs.csv",
        artifacts / "dcf_v5_hybrid_superblue18_base_pairs_step1.csv",
    )
    copy_csv(
        first_scheme / "mhat_pairs.csv",
        artifacts / "dcf_v5_hybrid_superblue18_mhat_pairs_step1.csv",
    )

    summary = {
        "case": args.case,
        "timing_step_id": int(args.timing_step),
        "lambdas": [],
    }
    for scheme, lam in LAMBDAS:
        scheme_dir = raw_root / scheme / step_dir_name
        copy_csv(
            scheme_dir / "final_pairs.csv",
            artifacts
            / f"dcf_v5_hybrid_superblue18_final_pairs_l{lam.replace('.', '')}_step1.csv",
        )
        debug_summary_path = scheme_dir / "debug_summary.json"
        payload = (
            json.loads(debug_summary_path.read_text())
            if debug_summary_path.exists()
            else {}
        )
        payload["lambda"] = lam
        summary["lambdas"].append(payload)

    with (artifacts / "dcf_v5_hybrid_superblue18_debug_summary.json").open("w") as f:
        json.dump(summary, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
