#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
RESULTS_ROOT = ROOT_DIR / "results" / "baselines"
LOGS_ROOT = ROOT_DIR / "logs"
SMOKE_CASES = ["superblue1", "superblue16", "superblue18"]
FULL_CASES = [
    "superblue1",
    "superblue3",
    "superblue4",
    "superblue5",
    "superblue7",
    "superblue10",
    "superblue16",
    "superblue18",
]
METHODS = [
    ("dreamplace4", "DREAMPlace 4.0"),
    ("efficient_tdp", "Efficient-TDP"),
]


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(errors="replace")


def last_match(pattern: str, text: str) -> str | None:
    matches = re.findall(pattern, text, re.MULTILINE)
    if not matches:
        return None
    match = matches[-1]
    if isinstance(match, tuple):
        return match[-1]
    return match


def parse_case(method_key: str, case_name: str) -> dict[str, str]:
    run_dir = RESULTS_ROOT / method_key / case_name
    log_path = LOGS_ROOT / method_key / f"{case_name}.log"
    log_text = read_text(log_path)

    placement = run_dir / f"{case_name}.gp.def"
    hpwl = last_match(r"wHPWL\s+([0-9.E+-]+)", log_text)
    tns = last_match(r"TNS\s+([-0-9.]+)\s+\(1e\+5 ps\)", log_text)
    wns = last_match(r"WNS\s+([-0-9.]+)\s+\(1e\+3 ps\)", log_text)
    runtime = last_match(r"placement takes\s+([0-9.]+)\s+seconds", log_text)
    wall = last_match(r"wall_clock_seconds\s+([0-9.]+)", log_text)

    status = "missing"
    notes: list[str] = []
    if placement.exists():
        status = "ok"
    if not log_path.exists():
        notes.append("log missing")
    if "Traceback" in log_text:
        status = "failed"
        notes.append("traceback seen")
    if placement.exists() and not hpwl:
        notes.append("HPWL missing from log")
    if placement.exists() and not tns:
        notes.append("TNS missing from log")
    if placement.exists() and not wns:
        notes.append("WNS missing from log")
    if placement.exists() and not runtime:
        notes.append("runtime missing from log")
    if not notes:
        notes.append("native OpenTimer metrics")

    return {
        "case": case_name,
        "method": dict(METHODS)[method_key],
        "method_key": method_key,
        "tns": tns or "",
        "wns": wns or "",
        "hpwl": hpwl or "",
        "runtime": runtime or wall or "",
        "status": status,
        "notes": "; ".join(notes),
        "log": str(log_path.relative_to(ROOT_DIR)) if log_path.exists() else "",
        "placement": str(placement.relative_to(ROOT_DIR)) if placement.exists() else "",
    }


def write_case_json(row: dict[str, str]) -> None:
    path = RESULTS_ROOT / row["method_key"] / row["case"] / "metrics.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(row)
    payload.pop("method_key", None)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def write_table(rows: list[dict[str, str]], output_path: Path) -> None:
    headers = ["case", "method", "TNS", "WNS", "HPWL", "runtime", "status", "notes"]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row["case"],
                    row["method"],
                    row["tns"] or "pending",
                    row["wns"] or "pending",
                    row["hpwl"] or "pending",
                    row["runtime"] or "pending",
                    row["status"],
                    row["notes"],
                ]
            )
            + " |"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n")


def write_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "case",
                "method",
                "tns",
                "wns",
                "hpwl",
                "runtime",
                "status",
                "notes",
                "log",
                "placement",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in writer.fieldnames})


def collect_rows(cases: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for case_name in cases:
        for method_key, _ in METHODS:
            rows.append(parse_case(method_key, case_name))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method")
    parser.add_argument("--case")
    parser.add_argument("--write-json", action="store_true")
    args = parser.parse_args()

    if args.method and args.case:
        row = parse_case(args.method, args.case)
        if args.write_json:
            write_case_json(row)
        print(json.dumps({k: v for k, v in row.items() if k != "method_key"}, indent=2))
        return

    smoke_rows = collect_rows(SMOKE_CASES)
    full_rows = collect_rows(FULL_CASES)

    write_table(smoke_rows, RESULTS_ROOT / "smoke_summary.md")
    write_csv(smoke_rows, RESULTS_ROOT / "smoke_summary.csv")
    write_table(full_rows, RESULTS_ROOT / "full_suite_template.md")
    write_csv(full_rows, RESULTS_ROOT / "full_suite_template.csv")


if __name__ == "__main__":
    main()
