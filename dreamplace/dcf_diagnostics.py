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


def _parse_step_ids(raw_value):
    if raw_value is None:
        return []
    if isinstance(raw_value, str):
        tokens = [token.strip() for token in raw_value.split(",") if token.strip()]
    elif isinstance(raw_value, (list, tuple, set, np.ndarray)):
        tokens = list(raw_value)
    else:
        tokens = [raw_value]

    step_ids = []
    for token in tokens:
        try:
            step_id = int(token)
        except (TypeError, ValueError):
            continue
        if step_id > 0:
            step_ids.append(step_id)
    return sorted(set(step_ids))


class DcfDiagnosticsManager(object):
    def __init__(self, params, placedb):
        self.enabled = bool(getattr(params, "enable_dcf_diagnostics", 0))
        self.dump_first_timing_step_only = bool(
            getattr(params, "dcf_diag_dump_first_timing_step_only", 0)
        )
        self.requested_dump_step_ids = _parse_step_ids(
            getattr(params, "dcf_diag_dump_step_ids", [])
        )
        self.requested_snapshot_step_ids = _parse_step_ids(
            getattr(params, "dcf_diag_save_snapshot_step_ids", [])
        )
        self.stop_after_last_dump_step = bool(
            getattr(params, "dcf_diag_stop_after_last_dump_step", 0)
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
        self.command = " ".join([sys.executable] + sys.argv)
        self.config_path = None
        if len(sys.argv) > 1 and str(sys.argv[1]).lower().endswith(".json"):
            self.config_path = str(Path(sys.argv[1]).resolve())
        self.git_commit = None
        self.branch_name = None
        self.pin_names = [_decode_name(name) for name in placedb.pin_names]
        self.num_nodes = int(placedb.num_nodes)
        self.pin2node_map = np.asarray(placedb.pin2node_map, dtype=np.int32)
        self.pin_offset_x = np.asarray(placedb.pin_offset_x)
        self.pin_offset_y = np.asarray(placedb.pin_offset_y)
        self.snapshot_root_dir = getattr(params, "dcf_diag_replay_snapshot_dir", "")
        self.hybrid_debug_enabled = bool(getattr(params, "dcf_hybrid_debug", 0))
        self.hybrid_debug_first_step_only = bool(
            getattr(params, "dcf_hybrid_debug_dump_first_timing_step_only", 0)
        )
        self.hybrid_debug_root_dir = getattr(
            params, "dcf_hybrid_debug_dump_dir", "results/hybrid_debug"
        )
        self.hybrid_debug_summary_only = bool(
            getattr(params, "dcf_hybrid_debug_summary_only", 0)
        )
        self.hybrid_debug_root_dir = Path(self.hybrid_debug_root_dir)
        if not self.hybrid_debug_root_dir.is_absolute():
            self.hybrid_debug_root_dir = self.hybrid_debug_root_dir.resolve()
        if self.snapshot_root_dir:
            self.snapshot_root_dir = Path(self.snapshot_root_dir)
            if not self.snapshot_root_dir.is_absolute():
                self.snapshot_root_dir = self.snapshot_root_dir.resolve()
        else:
            self.snapshot_root_dir = None
        if not self.requested_dump_step_ids and self.dump_first_timing_step_only:
            self.requested_dump_step_ids = [1]
            self.stop_after_last_dump_step = True
        self.requested_dump_step_set = set(self.requested_dump_step_ids)
        self.requested_snapshot_step_set = set(self.requested_snapshot_step_ids)
        self.last_requested_dump_step = (
            self.requested_dump_step_ids[-1] if self.requested_dump_step_ids else None
        )

        if not self.enabled:
            return

        dump_root = Path(getattr(params, "dcf_diag_dump_dir", "results/diagnostics"))
        if not dump_root.is_absolute():
            dump_root = dump_root.resolve()
        self.scheme_dir = dump_root / self.case_name / self.scheme_name
        self.scheme_dir.mkdir(parents=True, exist_ok=True)
        summary_filename = getattr(
            params, "dcf_diag_timing_steps_filename", "timing_steps.jsonl"
        )
        self.summary_path = self.scheme_dir / summary_filename
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
        self.git_commit = self._run_git(git_root, ["rev-parse", "HEAD"])
        self.branch_name = self._run_git(
            git_root, ["rev-parse", "--abbrev-ref", "HEAD"]
        )
        metadata = {
            "case_name": self.case_name,
            "scheme_name": self.scheme_name,
            "command": self.command,
            "config_path": self.config_path,
            "git_commit": self.git_commit,
            "branch_name": self.branch_name,
            "diagnostics_dump_dir": str(self.scheme_dir),
            "dump_first_timing_step_only": self.dump_first_timing_step_only,
            "dump_step_ids": self.requested_dump_step_ids,
            "snapshot_step_ids": self.requested_snapshot_step_ids,
            "replay_snapshot_dir": str(self.snapshot_root_dir)
            if self.snapshot_root_dir is not None
            else None,
            "stop_after_last_dump_step": self.stop_after_last_dump_step,
            "dump_pair_limit": self.dump_pair_limit,
            "dump_state_stats": self.dump_state_stats_enabled,
            "dump_term_grad_norms": self.dump_term_grad_norms_enabled,
            "timing_steps_filename": self.summary_path.name,
        }
        with (self.scheme_dir / "config_used.json").open("w") as fout:
            json.dump(params.toJson(), fout, indent=2, default=_json_default)
            fout.write("\n")
        with (self.scheme_dir / "run_metadata.json").open("w") as fout:
            json.dump(metadata, fout, indent=2, default=_json_default)
            fout.write("\n")

    def should_dump_step(self, timing_step_id):
        return self.enabled and timing_step_id in self.requested_dump_step_set

    def should_save_snapshot_step(self, timing_step_id):
        return self.enabled and timing_step_id in self.requested_snapshot_step_set

    def should_exit_after_step(self, timing_step_id):
        if not self.should_dump_step(timing_step_id):
            return False
        if self.dump_first_timing_step_only and self.last_requested_dump_step == 1:
            return True
        if not self.stop_after_last_dump_step:
            return False
        return (
            self.last_requested_dump_step is not None
            and timing_step_id >= self.last_requested_dump_step
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

    def _target_dir(self, timing_step_id=None, output_dir=None):
        if output_dir is not None:
            path = Path(output_dir)
            path.mkdir(parents=True, exist_ok=True)
            return path
        if timing_step_id is None:
            raise ValueError("timing_step_id or output_dir is required")
        return self._step_dir(timing_step_id)

    def _snapshot_dir(self, timing_step_id):
        if self.snapshot_root_dir is None:
            snapshot_dir = self._step_dir(timing_step_id) / "replay_snapshot"
        else:
            snapshot_dir = (
                self.snapshot_root_dir
                / self.case_name
                / self.scheme_name
                / ("step_%03d" % timing_step_id)
                / "replay_snapshot"
            )
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        return snapshot_dir

    def write_json(self, output_path, payload):
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as fout:
            json.dump(payload, fout, indent=2, default=_json_default)
            fout.write("\n")
        return path

    def write_csv_rows(self, output_path, fieldnames, rows):
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as fout:
            writer = csv.DictWriter(fout, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def build_top_pair_rows(self, pos, pair_dict, limit=10):
        src_ids, dst_ids, weights, lengths = self._pair_arrays(pos, pair_dict)
        if weights.size == 0:
            return []
        order = np.argsort(weights)[::-1][:limit]
        rows = []
        for idx in order:
            rows.append(
                {
                    "src_id": int(src_ids[idx]),
                    "src_name": self.pin_names[int(src_ids[idx])],
                    "dst_id": int(dst_ids[idx]),
                    "dst_name": self.pin_names[int(dst_ids[idx])],
                    "weight": float(weights[idx]),
                    "length": float(lengths[idx]),
                }
            )
        return rows

    def build_stage_summary_from_dict(self, pos, pair_dict):
        src_ids, dst_ids, weights, _ = self._pair_arrays(pos, pair_dict)
        if weights.size == 0:
            return {
                "pair_count": 0,
                "total_weight_mass": 0.0,
                "max_weight": 0.0,
                "min_nonzero_weight": 0.0,
                "top_pair_src_id": None,
                "top_pair_dst_id": None,
                "top_pair_weight": 0.0,
            }
        top_idx = int(np.argmax(weights))
        positive = weights[weights > 0]
        return {
            "pair_count": int(weights.size),
            "total_weight_mass": float(weights.sum()),
            "max_weight": float(weights[top_idx]),
            "min_nonzero_weight": float(positive.min()) if positive.size else 0.0,
            "top_pair_src_id": int(src_ids[top_idx]),
            "top_pair_dst_id": int(dst_ids[top_idx]),
            "top_pair_weight": float(weights[top_idx]),
        }

    def hybrid_debug_step_dir(self, timing_step_id):
        path = (
            self.hybrid_debug_root_dir
            / self.case_name
            / self.scheme_name
            / (f"step_{int(timing_step_id):03d}")
        )
        path.mkdir(parents=True, exist_ok=True)
        return path

    def should_dump_hybrid_debug_step(self, timing_step_id):
        if not self.hybrid_debug_enabled:
            return False
        if self.hybrid_debug_first_step_only:
            return int(timing_step_id) == 1
        return True

    def dump_hybrid_debug(
        self,
        pos,
        timing_step_id,
        base_pair_dict,
        final_pair_dict,
        timing_diag,
        exported_tensor_count,
        exported_tensor_weight_mass,
        exported_tensor_max_weight,
        exported_tensor_min_nonzero_weight,
    ):
        if not self.should_dump_hybrid_debug_step(timing_step_id):
            return None

        step_dir = self.hybrid_debug_step_dir(timing_step_id)
        src_tensor = timing_diag.get("hybrid_mhat_src_ids")
        dst_tensor = timing_diag.get("hybrid_mhat_dst_ids")
        val_tensor = timing_diag.get("hybrid_mhat_values")
        mhat_pair_count = int(timing_diag.get("hybrid_mhat_pair_count") or 0)
        mhat_total_mass = _safe_float(timing_diag.get("hybrid_mhat_total_mass")) or 0.0
        mhat_max_weight = _safe_float(timing_diag.get("hybrid_max_pair_mass")) or 0.0
        mhat_min_nonzero_weight = 0.0
        mhat_top_pair_src_id = None
        mhat_top_pair_dst_id = None
        mhat_top_pair_weight = 0.0
        if src_tensor is not None and dst_tensor is not None and val_tensor is not None:
            src_ids = src_tensor.detach().cpu().numpy()
            dst_ids = dst_tensor.detach().cpu().numpy()
            values = val_tensor.detach().cpu().numpy()
            positive_values = values[values > 0]
            if positive_values.size > 0:
                mhat_min_nonzero_weight = float(positive_values.min())
            if values.size > 0:
                top_idx = int(np.argmax(values))
                mhat_top_pair_src_id = int(src_ids[top_idx])
                mhat_top_pair_dst_id = int(dst_ids[top_idx])
                mhat_top_pair_weight = float(values[top_idx])

            if not self.hybrid_debug_summary_only:
                base_rows = self.build_top_pair_rows(pos, base_pair_dict, limit=10)
                final_rows = self.build_top_pair_rows(pos, final_pair_dict, limit=10)
                fieldnames = [
                    "src_id",
                    "src_name",
                    "dst_id",
                    "dst_name",
                    "weight",
                    "length",
                ]
                self.write_csv_rows(step_dir / "base_pairs.csv", fieldnames, base_rows)
                self.write_csv_rows(
                    step_dir / "final_pairs.csv", fieldnames, final_rows
                )

                mhat_rows = []
                for src_id, dst_id, value in zip(src_ids, dst_ids, values):
                    mhat_rows.append(
                        {
                            "src_id": int(src_id),
                            "src_name": self.pin_names[int(src_id)],
                            "dst_id": int(dst_id),
                            "dst_name": self.pin_names[int(dst_id)],
                            "mhat": float(value),
                        }
                    )
                self.write_csv_rows(
                    step_dir / "mhat_pairs.csv",
                    ["src_id", "src_name", "dst_id", "dst_name", "mhat"],
                    mhat_rows,
                )

        payload = {
            "timing_step_id": int(timing_step_id),
            "scheme_name": self.scheme_name,
            "hybrid_lambda": _safe_float(timing_diag.get("hybrid_lambda")),
            "raw_pin2pin": self.build_stage_summary_from_dict(pos, base_pair_dict),
            "mapped_mhat": {
                "pair_count": mhat_pair_count,
                "total_weight_mass": mhat_total_mass,
                "max_weight": mhat_max_weight,
                "min_nonzero_weight": mhat_min_nonzero_weight,
                "top_pair_src_id": mhat_top_pair_src_id,
                "top_pair_dst_id": mhat_top_pair_dst_id,
                "top_pair_weight": mhat_top_pair_weight,
            },
            "final_hybrid_dict": self.build_stage_summary_from_dict(
                pos, final_pair_dict
            ),
            "exported_tensor_view": {
                "pair_count": int(exported_tensor_count),
                "total_weight_mass": float(exported_tensor_weight_mass),
                "max_weight": float(exported_tensor_max_weight),
                "min_nonzero_weight": float(exported_tensor_min_nonzero_weight),
            },
        }
        self.write_json(step_dir / "debug_summary.json", payload)
        return step_dir

    def write_position_fingerprint(self, output_dir, position_fingerprint):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "position_fingerprint.txt"
        path.write_text(str(position_fingerprint) + "\n")
        return path

    def save_replay_snapshot(
        self, params, timing_step_id, gp_iter, pos, position_fingerprint
    ):
        if not self.should_save_snapshot_step(timing_step_id):
            return None

        snapshot_dir = self._snapshot_dir(timing_step_id)
        pos_path = snapshot_dir / "pos.pt"
        torch.save(pos.detach().cpu(), pos_path)

        metadata = {
            "snapshot_format_version": 1,
            "case_name": self.case_name,
            "scheme_name": self.scheme_name,
            "timing_step_id": int(timing_step_id),
            "gp_iter": int(gp_iter),
            "position_fingerprint": position_fingerprint,
            "command": self.command,
            "config_path": self.config_path,
            "source_scheme_dir": str(self.scheme_dir) if self.scheme_dir else None,
            "git_commit": self.git_commit,
            "branch_name": self.branch_name,
        }
        self.write_json(snapshot_dir / "snapshot_metadata.json", metadata)
        self.write_json(snapshot_dir / "config_used.json", params.toJson())
        self.write_position_fingerprint(snapshot_dir, position_fingerprint)
        return snapshot_dir

    def write_pair_rows(
        self, output_dir, pos, timing_step_id, gp_iter, pair_dict, timing_diag
    ):
        output_dir = self._target_dir(output_dir=output_dir)
        csv_path = output_dir / "exported_pairs.csv.gz"
        scheme = timing_diag.get("scheme_name") or self.scheme_name

        if scheme == "dcf" and timing_diag.get("dcf_pair_src_ids") is not None:
            self._dump_dcf_pair_rows(csv_path, timing_step_id, gp_iter, timing_diag)
        else:
            self._dump_pair_rows_from_dict(
                csv_path, pos, timing_step_id, gp_iter, pair_dict
            )
        return csv_path

    def write_state_stats(self, output_dir, timing_step_id, timing_diag):
        if not self.dump_state_stats_enabled:
            return None
        state_pin_ids = timing_diag.get("dcf_state_pin_ids")
        if state_pin_ids is None:
            return None

        output_dir = self._target_dir(output_dir=output_dir)
        csv_path = output_dir / "state_stats.csv.gz"
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

    def write_utility_summary(self, output_dir, timing_diag):
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
        output_dir = self._target_dir(output_dir=output_dir)
        return self.write_json(output_dir / "utility_summary.json", utility_summary)

    def write_objective_term_norms(self, output_dir, snapshot):
        if not self.dump_term_grad_norms_enabled or snapshot is None:
            return None
        output_dir = self._target_dir(output_dir=output_dir)
        return self.write_json(output_dir / "objective_term_norms.json", snapshot)

    def dump_pair_rows(self, pos, timing_step_id, gp_iter, pair_dict, timing_diag):
        if not self.should_dump_step(timing_step_id):
            return None

        return self.write_pair_rows(
            self._step_dir(timing_step_id),
            pos,
            timing_step_id,
            gp_iter,
            pair_dict,
            timing_diag,
        )

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

        return self.write_state_stats(
            self._step_dir(timing_step_id), timing_step_id, timing_diag
        )

    def dump_utility_summary(self, timing_step_id, timing_diag):
        if not self.should_dump_step(timing_step_id):
            return None

        return self.write_utility_summary(self._step_dir(timing_step_id), timing_diag)

    def dump_objective_term_norms(self, timing_step_id, snapshot):
        if not self.should_dump_step(timing_step_id):
            return None

        return self.write_objective_term_norms(self._step_dir(timing_step_id), snapshot)


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
