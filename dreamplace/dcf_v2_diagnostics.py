import csv
import json
import time
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


def _tensor_to_numpy(value, cols=0, dtype=None):
    if value is None:
        if cols > 0:
            return np.empty((0, cols), dtype=dtype if dtype is not None else np.float64)
        return np.empty((0,), dtype=dtype if dtype is not None else np.float64)
    array = value.detach().cpu().numpy()
    if dtype is not None:
        if np.issubdtype(np.dtype(dtype), np.integer) and np.issubdtype(
            array.dtype, np.floating
        ):
            array = np.nan_to_num(array, nan=-1.0)
        array = array.astype(dtype, copy=False)
    if cols > 0:
        return array.reshape((-1, cols))
    return array


class DcfV2AnalysisWriter(object):
    def __init__(self, params, placedb):
        self.enabled = bool(
            params.net_weighting_scheme == "dcf_v2"
            and getattr(params, "endpoint_repair_enable_dump", 0)
        )
        self.method = "dcf-v2"
        self.pin_names = [_decode_name(name) for name in placedb.pin_names]
        self.analysis_dir = None
        if not self.enabled:
            return

        self.analysis_dir = (
            Path(params.result_dir).resolve() / params.design_name() / "dcf_v2_analysis"
        )
        self.analysis_dir.mkdir(parents=True, exist_ok=True)
        self.files = {
            "endpoint_repair_stats": self.analysis_dir / "endpoint_repair_stats.csv",
            "endpoint_grouped_paths": self.analysis_dir
            / "endpoint_grouped_paths.jsonl",
            "endpoint_pair_cover": self.analysis_dir / "endpoint_pair_cover.csv",
            "global_pair_weights": self.analysis_dir / "global_pair_weights.csv",
            "repair_runtime_breakdown": self.analysis_dir
            / "repair_runtime_breakdown.csv",
        }
        for path in self.files.values():
            if path.exists():
                path.unlink()
        with (self.analysis_dir / "config_used.json").open("w") as fout:
            json.dump(params.toJson(), fout, indent=2, default=_json_default)
            fout.write("\n")

    def _pin_name(self, pin_id):
        if pin_id is None or pin_id < 0 or pin_id >= len(self.pin_names):
            return ""
        return self.pin_names[pin_id]

    def _append_csv_rows(self, path, fieldnames, rows):
        if not rows:
            return
        need_header = not path.exists()
        with path.open("a", newline="") as fout:
            writer = csv.DictWriter(fout, fieldnames=fieldnames)
            if need_header:
                writer.writeheader()
            writer.writerows(rows)

    def dump_iteration(self, timing_step_id, gp_iter, sta_time_ms, timing_diag):
        if not self.enabled:
            return
        if timing_diag.get("scheme_name") != "dcf_v2":
            return

        dump_beg = time.time()

        endpoint_stat_pin_ids = _tensor_to_numpy(
            timing_diag.get("endpoint_stat_pin_ids"), dtype=np.int32
        )
        endpoint_stat_num_paths_raw = _tensor_to_numpy(
            timing_diag.get("endpoint_stat_num_paths_raw"), dtype=np.int32
        )
        endpoint_stat_num_paths_kept = _tensor_to_numpy(
            timing_diag.get("endpoint_stat_num_paths_kept"), dtype=np.int32
        )
        endpoint_stat_num_unique_pairs = _tensor_to_numpy(
            timing_diag.get("endpoint_stat_num_unique_pairs"), dtype=np.int32
        )
        endpoint_stat_top_pair_ids = _tensor_to_numpy(
            timing_diag.get("endpoint_stat_top_pair_ids"), cols=4, dtype=np.int32
        )
        endpoint_stat_metrics = _tensor_to_numpy(
            timing_diag.get("endpoint_stat_metrics"), cols=7, dtype=np.float64
        )

        endpoint_repair_rows = []
        for idx, endpoint_pin_id in enumerate(endpoint_stat_pin_ids):
            endpoint_slack = float(endpoint_stat_metrics[idx, 0])
            endpoint_repair_rows.append(
                {
                    "iter": timing_step_id,
                    "method": self.method,
                    "endpoint_pin_name": self._pin_name(int(endpoint_pin_id)),
                    "endpoint_pin_id": int(endpoint_pin_id),
                    "endpoint_slack": endpoint_slack,
                    "num_paths_raw": int(endpoint_stat_num_paths_raw[idx]),
                    "num_paths_kept": int(endpoint_stat_num_paths_kept[idx]),
                    "num_unique_pairs": int(endpoint_stat_num_unique_pairs[idx]),
                    "total_path_mass": float(endpoint_stat_metrics[idx, 1]),
                    "rho1": float(endpoint_stat_metrics[idx, 2]),
                    "rho2": float(endpoint_stat_metrics[idx, 3]),
                    "top1_pair_from": self._pin_name(
                        int(endpoint_stat_top_pair_ids[idx, 0])
                    ),
                    "top1_pair_to": self._pin_name(
                        int(endpoint_stat_top_pair_ids[idx, 1])
                    ),
                    "top1_pair_cover": float(endpoint_stat_metrics[idx, 4]),
                    "top2_pair_from": self._pin_name(
                        int(endpoint_stat_top_pair_ids[idx, 2])
                    ),
                    "top2_pair_to": self._pin_name(
                        int(endpoint_stat_top_pair_ids[idx, 3])
                    ),
                    "top2_union_cover": float(endpoint_stat_metrics[idx, 5]),
                    "endpoint_priority": float(endpoint_stat_metrics[idx, 6]),
                }
            )
        self._append_csv_rows(
            self.files["endpoint_repair_stats"],
            [
                "iter",
                "method",
                "endpoint_pin_name",
                "endpoint_pin_id",
                "endpoint_slack",
                "num_paths_raw",
                "num_paths_kept",
                "num_unique_pairs",
                "total_path_mass",
                "rho1",
                "rho2",
                "top1_pair_from",
                "top1_pair_to",
                "top1_pair_cover",
                "top2_pair_from",
                "top2_pair_to",
                "top2_union_cover",
                "endpoint_priority",
            ],
            endpoint_repair_rows,
        )

        bundle_endpoint_pin_ids = _tensor_to_numpy(
            timing_diag.get("bundle_endpoint_pin_ids"), dtype=np.int32
        )
        bundle_endpoint_slacks = _tensor_to_numpy(
            timing_diag.get("bundle_endpoint_slacks"), dtype=np.float64
        )
        bundle_num_paths_raw = _tensor_to_numpy(
            timing_diag.get("bundle_num_paths_raw"), dtype=np.int32
        )
        bundle_num_paths_kept = _tensor_to_numpy(
            timing_diag.get("bundle_num_paths_kept"), dtype=np.int32
        )
        bundle_path_offsets = _tensor_to_numpy(
            timing_diag.get("bundle_path_offsets"), dtype=np.int32
        )
        path_metrics = _tensor_to_numpy(
            timing_diag.get("path_metrics"), cols=2, dtype=np.float64
        )
        path_pair_offsets = _tensor_to_numpy(
            timing_diag.get("path_pair_offsets"), dtype=np.int32
        )
        path_pair_src_ids = _tensor_to_numpy(
            timing_diag.get("path_pair_src_ids"), dtype=np.int32
        )
        path_pair_dst_ids = _tensor_to_numpy(
            timing_diag.get("path_pair_dst_ids"), dtype=np.int32
        )
        with self.files["endpoint_grouped_paths"].open("a") as fout:
            for bundle_idx, endpoint_pin_id in enumerate(bundle_endpoint_pin_ids):
                path_begin = int(bundle_path_offsets[bundle_idx])
                path_end = int(bundle_path_offsets[bundle_idx + 1])
                paths = []
                for path_idx in range(path_begin, path_end):
                    pair_begin = int(path_pair_offsets[path_idx])
                    pair_end = int(path_pair_offsets[path_idx + 1])
                    paths.append(
                        {
                            "rank": path_idx - path_begin + 1,
                            "path_slack": float(path_metrics[path_idx, 0]),
                            "path_weight": float(path_metrics[path_idx, 1]),
                            "ordered_pin_pairs": [
                                {
                                    "from_pin_name": self._pin_name(
                                        int(path_pair_src_ids[pair_idx])
                                    ),
                                    "to_pin_name": self._pin_name(
                                        int(path_pair_dst_ids[pair_idx])
                                    ),
                                    "from_pin_id": int(path_pair_src_ids[pair_idx]),
                                    "to_pin_id": int(path_pair_dst_ids[pair_idx]),
                                }
                                for pair_idx in range(pair_begin, pair_end)
                            ],
                        }
                    )
                fout.write(
                    json.dumps(
                        {
                            "iter": timing_step_id,
                            "gp_iter": gp_iter,
                            "method": self.method,
                            "endpoint_pin_name": self._pin_name(int(endpoint_pin_id)),
                            "endpoint_pin_id": int(endpoint_pin_id),
                            "endpoint_slack": float(bundle_endpoint_slacks[bundle_idx]),
                            "num_paths_raw": int(bundle_num_paths_raw[bundle_idx]),
                            "num_paths_kept": int(bundle_num_paths_kept[bundle_idx]),
                            "paths": paths,
                        },
                        default=_json_default,
                    )
                )
                fout.write("\n")

        endpoint_pair_cover_endpoint_pin_ids = _tensor_to_numpy(
            timing_diag.get("endpoint_pair_cover_endpoint_pin_ids"), dtype=np.int32
        )
        endpoint_pair_cover_pair_from_ids = _tensor_to_numpy(
            timing_diag.get("endpoint_pair_cover_pair_from_ids"), dtype=np.int32
        )
        endpoint_pair_cover_pair_to_ids = _tensor_to_numpy(
            timing_diag.get("endpoint_pair_cover_pair_to_ids"), dtype=np.int32
        )
        endpoint_pair_cover_pair_ranks = _tensor_to_numpy(
            timing_diag.get("endpoint_pair_cover_pair_ranks"), dtype=np.int32
        )
        endpoint_pair_cover_touch_counts = _tensor_to_numpy(
            timing_diag.get("endpoint_pair_cover_touch_counts"), dtype=np.int32
        )
        endpoint_pair_cover_metrics = _tensor_to_numpy(
            timing_diag.get("endpoint_pair_cover_metrics"), cols=2, dtype=np.float64
        )
        endpoint_pair_cover_rows = []
        for idx, endpoint_pin_id in enumerate(endpoint_pair_cover_endpoint_pin_ids):
            endpoint_pair_cover_rows.append(
                {
                    "iter": timing_step_id,
                    "method": self.method,
                    "endpoint_pin_name": self._pin_name(int(endpoint_pin_id)),
                    "endpoint_slack": float(endpoint_pair_cover_metrics[idx, 0]),
                    "pair_from": self._pin_name(
                        int(endpoint_pair_cover_pair_from_ids[idx])
                    ),
                    "pair_to": self._pin_name(
                        int(endpoint_pair_cover_pair_to_ids[idx])
                    ),
                    "pair_cover": float(endpoint_pair_cover_metrics[idx, 1]),
                    "pair_rank_within_endpoint": int(
                        endpoint_pair_cover_pair_ranks[idx]
                    ),
                    "num_paths_touching_pair": int(
                        endpoint_pair_cover_touch_counts[idx]
                    ),
                }
            )
        self._append_csv_rows(
            self.files["endpoint_pair_cover"],
            [
                "iter",
                "method",
                "endpoint_pin_name",
                "endpoint_slack",
                "pair_from",
                "pair_to",
                "pair_cover",
                "pair_rank_within_endpoint",
                "num_paths_touching_pair",
            ],
            endpoint_pair_cover_rows,
        )

        global_pair_from_ids = _tensor_to_numpy(
            timing_diag.get("global_pair_from_ids"), dtype=np.int32
        )
        global_pair_to_ids = _tensor_to_numpy(
            timing_diag.get("global_pair_to_ids"), dtype=np.int32
        )
        global_pair_contrib_counts = _tensor_to_numpy(
            timing_diag.get("global_pair_contrib_counts"), dtype=np.int32
        )
        global_pair_metrics = _tensor_to_numpy(
            timing_diag.get("global_pair_metrics"), cols=3, dtype=np.float64
        )
        global_pair_rows = []
        for idx, pair_from_id in enumerate(global_pair_from_ids):
            global_pair_rows.append(
                {
                    "iter": timing_step_id,
                    "method": self.method,
                    "pair_from": self._pin_name(int(pair_from_id)),
                    "pair_to": self._pin_name(int(global_pair_to_ids[idx])),
                    "global_pair_score": float(global_pair_metrics[idx, 0]),
                    "final_pin2pin_weight": float(global_pair_metrics[idx, 1]),
                    "num_endpoints_contributing": int(global_pair_contrib_counts[idx]),
                    "sum_endpoint_priority": float(global_pair_metrics[idx, 2]),
                }
            )
        self._append_csv_rows(
            self.files["global_pair_weights"],
            [
                "iter",
                "method",
                "pair_from",
                "pair_to",
                "global_pair_score",
                "final_pin2pin_weight",
                "num_endpoints_contributing",
                "sum_endpoint_priority",
            ],
            global_pair_rows,
        )

        dump_time_ms = (time.time() - dump_beg) * 1000.0
        self._append_csv_rows(
            self.files["repair_runtime_breakdown"],
            [
                "iter",
                "method",
                "sta_time_ms",
                "path_extract_time_ms",
                "group_build_time_ms",
                "repair_score_time_ms",
                "global_aggregate_time_ms",
                "dump_time_ms",
            ],
            [
                {
                    "iter": timing_step_id,
                    "method": self.method,
                    "sta_time_ms": float(sta_time_ms),
                    "path_extract_time_ms": float(
                        timing_diag.get("path_extract_time_ms", 0.0)
                    ),
                    "group_build_time_ms": float(
                        timing_diag.get("group_build_time_ms", 0.0)
                    ),
                    "repair_score_time_ms": float(
                        timing_diag.get("repair_score_time_ms", 0.0)
                    ),
                    "global_aggregate_time_ms": float(
                        timing_diag.get("global_aggregate_time_ms", 0.0)
                    ),
                    "dump_time_ms": float(dump_time_ms),
                }
            ],
        )
