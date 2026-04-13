import csv
import gzip
import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import torch


DESIGNATED_TIMING_STEP_ID = 1


def _json_default(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().tolist()
    return value


def _decode_name(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if hasattr(value, "decode"):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _safe_float(value):
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def _safe_corr_from_arrays(lhs, rhs):
    if lhs.size < 2 or rhs.size < 2:
        return None
    if np.allclose(lhs, lhs[0]) or np.allclose(rhs, rhs[0]):
        return None
    return float(np.corrcoef(lhs, rhs)[0, 1])


def _rankdata(values):
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


def _safe_spearman_from_arrays(lhs, rhs):
    if lhs.size < 2 or rhs.size < 2:
        return None
    return _safe_corr_from_arrays(_rankdata(lhs), _rankdata(rhs))


class DcfDiagnosticsManager(object):
    def __init__(self, params, placedb):
        self.enabled = bool(getattr(params, "enable_dcf_diagnostics", 0))
        self.dump_first_timing_step_only = bool(
            getattr(params, "dcf_diag_dump_first_timing_step_only", 0)
        )
        self.dump_pair_limit = int(getattr(params, "dcf_diag_dump_pair_limit", 0))
        self.dump_state_stats_enabled = bool(
            getattr(params, "dcf_diag_dump_state_stats", 0)
        )
        self.dump_term_grad_norms_enabled = bool(
            getattr(params, "dcf_diag_dump_term_grad_norms", 0)
        )
        self.dump_topk = int(getattr(params, "dcf_diag_dump_topk", 1000))
        self.case_name = (
            getattr(params, "dcf_diag_case_tag", "") or params.design_name()
        )
        self.scheme_name = (
            getattr(params, "dcf_diag_scheme_tag", "") or params.net_weighting_scheme
        )
        self.summary_path = None
        self.scheme_dir = None
        self.pin_names = [_decode_name(name) for name in placedb.pin_names]
        self.num_nodes = int(placedb.num_nodes)
        self.pin2node_map = np.asarray(placedb.pin2node_map, dtype=np.int32)
        self.pin_offset_x = np.asarray(placedb.pin_offset_x)
        self.pin_offset_y = np.asarray(placedb.pin_offset_y)

        if not self.enabled:
            return

        dump_root = Path(getattr(params, "dcf_diag_dump_dir", "results/diagnostics"))
        if not dump_root.is_absolute():
            dump_root = dump_root.resolve()
        self.scheme_dir = dump_root / self.case_name / self.scheme_name
        self.scheme_dir.mkdir(parents=True, exist_ok=True)
        self.summary_path = self.scheme_dir / "timing_steps.jsonl"
        if self.summary_path.exists():
            self.summary_path.unlink()
        self._write_run_artifacts(params, dump_root)

    def _find_git_root(self, start_path):
        current = Path(start_path).resolve()
        for candidate in [current] + list(current.parents):
            if (candidate / ".git").exists():
                return candidate
        return None

    def _run_git(self, git_root, args):
        if git_root is None:
            return None
        try:
            output = subprocess.check_output(
                ["git", "-C", str(git_root)] + list(args),
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except Exception:
            return None
        return output.strip() or None

    def _write_run_artifacts(self, params, dump_root):
        git_root = self._find_git_root(dump_root)
        metadata = {
            "case_name": self.case_name,
            "scheme_name": self.scheme_name,
            "command": " ".join([sys.executable] + sys.argv),
            "git_commit": self._run_git(git_root, ["rev-parse", "HEAD"]),
            "branch_name": self._run_git(
                git_root, ["rev-parse", "--abbrev-ref", "HEAD"]
            ),
            "diagnostics_dump_dir": str(self.scheme_dir),
            "dump_first_timing_step_only": self.dump_first_timing_step_only,
            "dump_pair_limit": self.dump_pair_limit,
            "dump_state_stats": self.dump_state_stats_enabled,
            "dump_term_grad_norms": self.dump_term_grad_norms_enabled,
        }
        with (self.scheme_dir / "config_used.json").open("w") as fout:
            json.dump(params.toJson(), fout, indent=2, default=_json_default)
            fout.write("\n")
        with (self.scheme_dir / "run_metadata.json").open("w") as fout:
            json.dump(metadata, fout, indent=2, default=_json_default)
            fout.write("\n")

    def should_dump_step(self, timing_step_id):
        return self.enabled and timing_step_id == DESIGNATED_TIMING_STEP_ID

    def should_exit_after_step(self, timing_step_id):
        return (
            self.should_dump_step(timing_step_id) and self.dump_first_timing_step_only
        )

    def position_fingerprint(self, pos):
        pos_array = np.ascontiguousarray(pos.detach().cpu().numpy())
        return hashlib.sha256(pos_array.tobytes()).hexdigest()[:16]

    def _pair_arrays(self, pos, pair_dict):
        exported_pair_count = len(pair_dict)
        if exported_pair_count == 0:
            empty_i32 = np.empty(0, dtype=np.int32)
            empty_f64 = np.empty(0, dtype=np.float64)
            return empty_i32, empty_i32, empty_f64, empty_f64

        src_ids = np.empty(exported_pair_count, dtype=np.int32)
        dst_ids = np.empty(exported_pair_count, dtype=np.int32)
        weights = np.empty(exported_pair_count, dtype=np.float64)
        for index, (key, value) in enumerate(pair_dict.items()):
            src_ids[index] = int(key[0])
            dst_ids[index] = int(key[1])
            weights[index] = float(value)

        pos_array = pos.detach().cpu().numpy()
        pos_x = pos_array[: self.num_nodes]
        pos_y = pos_array[self.num_nodes :]
        node_src = self.pin2node_map[src_ids]
        node_dst = self.pin2node_map[dst_ids]
        lengths = np.abs(
            pos_x[node_src]
            + self.pin_offset_x[src_ids]
            - pos_x[node_dst]
            - self.pin_offset_x[dst_ids]
        ) + np.abs(
            pos_y[node_src]
            + self.pin_offset_y[src_ids]
            - pos_y[node_dst]
            - self.pin_offset_y[dst_ids]
        )
        return src_ids, dst_ids, weights, lengths.astype(np.float64, copy=False)

    def build_pair_summary(self, pos, pair_dict):
        src_ids, dst_ids, weights, lengths = self._pair_arrays(pos, pair_dict)
        if weights.size == 0:
            return {
                "exported_pair_count": 0,
                "total_exported_weight_mass": 0.0,
                "top1_weight_mass_ratio": 0.0,
                "top5_weight_mass_ratio": 0.0,
                "average_exported_pair_length": 0.0,
                "median_exported_pair_length": 0.0,
                "max_exported_pair_length": 0.0,
            }

        total_weight_mass = float(weights.sum())
        sorted_weights = np.sort(weights)[::-1]
        top1_mass_ratio = float(sorted_weights[:1].sum() / total_weight_mass)
        top5_mass_ratio = float(sorted_weights[:5].sum() / total_weight_mass)
        return {
            "exported_pair_count": int(weights.size),
            "total_exported_weight_mass": total_weight_mass,
            "top1_weight_mass_ratio": top1_mass_ratio,
            "top5_weight_mass_ratio": top5_mass_ratio,
            "average_exported_pair_length": float(lengths.mean()),
            "median_exported_pair_length": float(np.median(lengths)),
            "max_exported_pair_length": float(lengths.max()),
        }

    def append_timing_step_summary(self, summary_row):
        if not self.enabled:
            return
        with self.summary_path.open("a") as fout:
            fout.write(json.dumps(summary_row, default=_json_default) + "\n")

    def _step_dir(self, timing_step_id):
        step_dir = self.scheme_dir / ("step_%03d" % timing_step_id)
        step_dir.mkdir(parents=True, exist_ok=True)
        return step_dir

    def dump_pair_rows(self, pos, timing_step_id, gp_iter, pair_dict, timing_diag):
        if not self.should_dump_step(timing_step_id):
            return None

        step_dir = self._step_dir(timing_step_id)
        csv_path = step_dir / "exported_pairs.csv.gz"
        scheme = timing_diag.get("scheme_name") or self.scheme_name

        if scheme == "dcf" and timing_diag.get("dcf_pair_src_ids") is not None:
            self._dump_dcf_pair_rows(csv_path, timing_step_id, gp_iter, timing_diag)
        else:
            self._dump_pair_rows_from_dict(
                csv_path, pos, timing_step_id, gp_iter, pair_dict
            )
        return csv_path

    def _dump_pair_rows_from_dict(
        self, csv_path, pos, timing_step_id, gp_iter, pair_dict
    ):
        src_ids, dst_ids, weights, lengths = self._pair_arrays(pos, pair_dict)
        if weights.size:
            order = np.argsort(weights)[::-1]
            if self.dump_pair_limit > 0:
                order = order[: self.dump_pair_limit]
        else:
            order = np.empty(0, dtype=np.int64)

        headers = [
            "timing_step_id",
            "gp_iter",
            "src_pin_id",
            "dst_pin_id",
            "src_pin_name",
            "dst_pin_name",
            "current_manhattan_length",
            "final_exported_weight",
        ]
        with gzip.open(csv_path, "wt", newline="") as fout:
            writer = csv.writer(fout)
            writer.writerow(headers)
            for index in order:
                src_pin_id = int(src_ids[index])
                dst_pin_id = int(dst_ids[index])
                writer.writerow(
                    [
                        timing_step_id,
                        gp_iter,
                        src_pin_id,
                        dst_pin_id,
                        self.pin_names[src_pin_id],
                        self.pin_names[dst_pin_id],
                        float(lengths[index]),
                        float(weights[index]),
                    ]
                )

    def _dump_dcf_pair_rows(self, csv_path, timing_step_id, gp_iter, timing_diag):
        src_ids = timing_diag["dcf_pair_src_ids"].detach().cpu().numpy()
        dst_ids = timing_diag["dcf_pair_dst_ids"].detach().cpu().numpy()
        hist = timing_diag["dcf_pair_hist"].detach().cpu().numpy()
        metrics = timing_diag["dcf_pair_metrics"].detach().cpu().numpy()

        headers = [
            "timing_step_id",
            "gp_iter",
            "src_pin_id",
            "dst_pin_id",
            "src_pin_name",
            "dst_pin_name",
            "current_manhattan_length",
            "final_exported_weight",
            "hist_bin0",
            "hist_bin1",
            "hist_bin2",
            "hist_bin3",
            "M",
            "S",
            "T",
            "utility_U",
            "length_eta",
            "mapped_weight_before_ema",
            "final_exported_weight_after_ema",
        ]

        with gzip.open(csv_path, "wt", newline="") as fout:
            writer = csv.writer(fout)
            writer.writerow(headers)
            for index in range(src_ids.shape[0]):
                src_pin_id = int(src_ids[index])
                dst_pin_id = int(dst_ids[index])
                writer.writerow(
                    [
                        timing_step_id,
                        gp_iter,
                        src_pin_id,
                        dst_pin_id,
                        self.pin_names[src_pin_id],
                        self.pin_names[dst_pin_id],
                        float(metrics[index, 4]),
                        float(metrics[index, 6]),
                        float(hist[index, 0]),
                        float(hist[index, 1]),
                        float(hist[index, 2]),
                        float(hist[index, 3]),
                        float(metrics[index, 0]),
                        float(metrics[index, 1]),
                        float(metrics[index, 2]),
                        float(metrics[index, 3]),
                        float(metrics[index, 4]),
                        float(metrics[index, 5]),
                        float(metrics[index, 6]),
                    ]
                )

    def dump_state_stats(self, timing_step_id, timing_diag):
        if not self.should_dump_step(timing_step_id):
            return None
        if not self.dump_state_stats_enabled:
            return None
        state_pin_ids = timing_diag.get("dcf_state_pin_ids")
        if state_pin_ids is None:
            return None

        step_dir = self._step_dir(timing_step_id)
        csv_path = step_dir / "state_stats.csv.gz"
        pin_ids = state_pin_ids.detach().cpu().numpy()
        rf = timing_diag["dcf_state_rf"].detach().cpu().numpy()
        candidate_counts = (
            timing_diag["dcf_state_candidate_counts"].detach().cpu().numpy()
        )
        metrics = timing_diag["dcf_state_metrics"].detach().cpu().numpy()

        headers = [
            "pin_id",
            "pin_name",
            "rf",
            "node_mass_total",
            "num_candidate_predecessors",
            "max_prob",
            "top1_prob",
            "top3_prob_sum",
            "attribution_entropy",
            "outgoing_mass_total",
            "incoming_mass_total",
        ]
        with gzip.open(csv_path, "wt", newline="") as fout:
            writer = csv.writer(fout)
            writer.writerow(headers)
            for index in range(pin_ids.shape[0]):
                pin_id = int(pin_ids[index])
                if pin_id < 0 or pin_id >= len(self.pin_names):
                    continue
                writer.writerow(
                    [
                        pin_id,
                        self.pin_names[pin_id],
                        "fall" if int(rf[index]) else "rise",
                        float(metrics[index, 0]),
                        int(candidate_counts[index]),
                        float(metrics[index, 1]),
                        float(metrics[index, 2]),
                        float(metrics[index, 3]),
                        float(metrics[index, 4]),
                        float(metrics[index, 5]),
                        float(metrics[index, 6]),
                    ]
                )
        return csv_path

    def dump_utility_summary(self, timing_step_id, timing_diag):
        if not self.should_dump_step(timing_step_id):
            return None
        utility_summary = timing_diag.get("dcf_utility_summary")
        if (
            utility_summary is None
            and timing_diag.get("dcf_all_pair_metrics") is not None
        ):
            utility_summary = compute_dcf_utility_summary_from_pairs(
                timing_diag["dcf_all_pair_metrics"].detach().cpu().numpy()
            )
        if utility_summary is None:
            return None
        step_dir = self._step_dir(timing_step_id)
        json_path = step_dir / "utility_summary.json"
        with json_path.open("w") as fout:
            json.dump(utility_summary, fout, indent=2, default=_json_default)
            fout.write("\n")
        return json_path

    def dump_objective_term_norms(self, timing_step_id, snapshot):
        if not self.should_dump_step(timing_step_id):
            return None
        if not self.dump_term_grad_norms_enabled or snapshot is None:
            return None
        step_dir = self._step_dir(timing_step_id)
        json_path = step_dir / "objective_term_norms.json"
        with json_path.open("w") as fout:
            json.dump(snapshot, fout, indent=2, default=_json_default)
            fout.write("\n")
        return json_path


def compute_dcf_utility_summary_from_pairs(pair_metrics):
    if pair_metrics.size == 0:
        return {
            "quantiles": {},
            "pearson": {},
            "spearman": {},
        }

    quantile_levels = np.asarray([0.0, 0.25, 0.5, 0.75, 0.9, 0.99, 1.0])
    columns = {
        "M": pair_metrics[:, 0],
        "S": pair_metrics[:, 1],
        "T": pair_metrics[:, 2],
        "eta": pair_metrics[:, 4],
        "mapped_weight_before_ema": pair_metrics[:, 5],
        "final_exported_weight_after_ema": pair_metrics[:, 6],
    }
    quantiles = {}
    for key, values in columns.items():
        quantiles[key] = {
            str(level): float(np.quantile(values, level)) for level in quantile_levels
        }

    final_weight = columns["final_exported_weight_after_ema"]
    pearson = {}
    spearman = {}
    for key in ["eta", "S", "T", "M"]:
        pearson[key] = _safe_corr_from_arrays(final_weight, columns[key])
        spearman[key] = _safe_spearman_from_arrays(final_weight, columns[key])

    return {
        "quantiles": quantiles,
        "pearson": pearson,
        "spearman": spearman,
    }
