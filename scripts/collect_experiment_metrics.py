#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", required=True)
    parser.add_argument("--method-key", default="")
    parser.add_argument("--variant", default="")
    parser.add_argument("--beta", default="")
    parser.add_argument("--case", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--output-tag", default="")
    parser.add_argument("--run-label", default="")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    log_path = Path(args.log)
    output_path = Path(args.output) if args.output else run_dir / "metrics.json"
    log_text = read_text(log_path)

    placement = run_dir / f"{args.case}.gp.def"
    if not placement.exists():
        nested_placement = run_dir / args.case / f"{args.case}.gp.def"
        if nested_placement.exists():
            placement = nested_placement
    payload = {
        "case": args.case,
        "method": args.method,
        "method_key": args.method_key,
        "variant": args.variant,
        "beta": args.beta,
        "output_tag": args.output_tag,
        "run_label": args.run_label,
        "tns": last_match(r"TNS\s+([-0-9.]+)\s+\(1e\+5 ps\)", log_text) or "",
        "wns": last_match(r"WNS\s+([-0-9.]+)\s+\(1e\+3 ps\)", log_text) or "",
        "hpwl": last_match(r"wHPWL\s+([0-9.E+-]+)", log_text) or "",
        "runtime": (
            last_match(r"placement takes\s+([0-9.]+)\s+seconds", log_text)
            or last_match(r"wall_clock_seconds\s+([0-9.]+)", log_text)
            or ""
        ),
        "status": "ok"
        if placement.exists() and "Traceback" not in log_text
        else "failed",
        "log": str(log_path),
        "placement": str(placement) if placement.exists() else "",
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
