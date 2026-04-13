#ifndef DREAMPLACE_NET_WEIGHTING_SCHEME_H_
#define DREAMPLACE_NET_WEIGHTING_SCHEME_H_
#define PYBIND11_DETAILED_ERROR_MESSAGES

#include <memory>
#include <algorithm>
#include <array>
#include <cmath>
#include <deque>
#include <functional>
#include <fstream>
#include <limits>
#include <string>
#include <type_traits>
#include <unordered_map>
#include <utility>
#include <vector>

#include <ot/timer/timer.hpp>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "place_io/src/Util.h"
#include "utility/src/torch.h"
#include "utility/src/utils.h"

namespace _timing_impl {
template <typename T>
using index_type = typename DREAMPLACE_NAMESPACE::coordinate_traits<T>::index_type;
using string2index_map_type = std::unordered_map<std::string, index_type<int> >;
}

DREAMPLACE_BEGIN_NAMESPACE

enum class NetWeightingScheme {
  ADAMS, LILITH, PIN2PIN, DCF, DCF_V2
};

#define DEFINE_APPLY_SCHEME                                        \
  static pybind11::dict apply(                                     \
      ot::Timer& timer, int n,                                     \
      const std::vector<std::string>& pin_names,                   \
      const _timing_impl::string2index_map_type& net_name2id_map,  \
      const _timing_impl::string2index_map_type& pin_name2id_map,  \
      const T* pos, int num_nodes, const int* pin2node_map,        \
      const T* pin_offset_x, const T* pin_offset_y,                \
      T* net_criticality, T* net_criticality_deltas,               \
      T* net_weights, T* net_weight_deltas, const int* degree_map, \
      pybind11::dict& pin2pin_net_weight,                          \
      bool enable_dcf, const T* dcf_bin_edges,                     \
      T dcf_tau_A, T dcf_tau_S, T dcf_momentum,                    \
      int endpoint_grouped_path_k,                                 \
      T endpoint_grouped_slack_delta,                              \
      T endpoint_repair_tau, T endpoint_repair_alpha,              \
      T endpoint_repair_beta, bool endpoint_repair_enable_dump,    \
      T decay, T max_net_weight, int ignore_net_degree,            \
      int num_threads,                                             \
      int pin2pin_max_weight, int pin2pin_min_weight,              \
      double pin2pin_accumulate_weight)

template <typename T, NetWeightingScheme scm>
struct NetWeighting {
  DEFINE_APPLY_SCHEME;
};

inline float report_pin_slack(ot::Timer& timer, const std::string& name) {
  using namespace ot;
  float ps = std::numeric_limits<float>::max();
  FOR_EACH_EL_RF(el, rf) {
    auto s = timer.report_slack(name, el, rf);
    if (s) {
      ps = std::min(ps, *s);
    }
  }
  return ps;
}

inline float report_net_slack(ot::Timer& timer, const ot::Net& net) {
  float slack = std::numeric_limits<float>::max();
  const ot::Pin* root = net.root();
  for (const auto ptr : net.pins()) {
    if (ptr == root) {
      continue;
    }
    float ps = report_pin_slack(timer, ptr->name());
    slack = std::min(slack, ps);
  }
  return slack;
}

template <typename T>
using dcf_hist_type = std::array<T, 4>;

template <typename T>
inline dcf_hist_type<T> make_zero_dcf_hist() {
  return {T(0), T(0), T(0), T(0)};
}

template <typename T>
inline size_t dcf_state_index(size_t pin_idx, ot::Tran rf, size_t num_pins) {
  return pin_idx + (rf == ot::FALL ? num_pins : 0);
}

template <typename T>
inline int dcf_bin_index(T deficit, const std::array<T, 3>& edges) {
  if (deficit < edges[0]) {
    return 0;
  }
  if (deficit < edges[1]) {
    return 1;
  }
  if (deficit < edges[2]) {
    return 2;
  }
  return 3;
}

template <typename T>
inline T dcf_hist_mass(const dcf_hist_type<T>& hist) {
  return hist[0] + hist[1] + hist[2] + hist[3];
}

template <typename T>
inline void dcf_add_hist(dcf_hist_type<T>& dst, const dcf_hist_type<T>& src) {
  for (int i = 0; i < 4; ++i) {
    dst[i] += src[i];
  }
}

template <typename T>
inline dcf_hist_type<T> dcf_scale_hist(const dcf_hist_type<T>& hist, T scale) {
  dcf_hist_type<T> out = make_zero_dcf_hist<T>();
  for (int i = 0; i < 4; ++i) {
    out[i] = hist[i] * scale;
  }
  return out;
}

template <typename T>
inline T dcf_hist_weighted_sum(
    const dcf_hist_type<T>& hist,
    const std::array<T, 4>& representatives) {
  T sum = 0;
  for (int i = 0; i < 4; ++i) {
    sum += hist[i] * representatives[i];
  }
  return sum;
}

template <typename T>
inline T dcf_safe_exp(T exponent) {
  return std::exp(std::clamp(exponent, T(-50), T(50)));
}

template <typename T>
inline T dcf_pair_length(
    const T* pos,
    int num_nodes,
    const int* pin2node_map,
    const T* pin_offset_x,
    const T* pin_offset_y,
    int pin1,
    int pin2) {
  if (!pos) {
    return T(0);
  }
  const T* pos_y = pos + num_nodes;
  const int node1 = pin2node_map[pin1];
  const int node2 = pin2node_map[pin2];
  const T x1 = pos[node1] + pin_offset_x[pin1];
  const T y1 = pos_y[node1] + pin_offset_y[pin1];
  const T x2 = pos[node2] + pin_offset_x[pin2];
  const T y2 = pos_y[node2] + pin_offset_y[pin2];
  return std::abs(x1 - x2) + std::abs(y1 - y2);
}

template <typename T>
inline T dcf_pin_max_arrival(const ot::Pin& pin) {
  T best = std::numeric_limits<T>::lowest();
  bool valid = false;
  for (auto rf : {ot::RISE, ot::FALL}) {
    if (auto at = pin.at(ot::MAX, rf); at) {
      best = std::max(best, static_cast<T>(*at));
      valid = true;
    }
  }
  return valid ? best : T(0);
}

inline torch::Tensor dcf_tensor_from_int_vector(const std::vector<int>& values) {
  auto options = torch::TensorOptions().dtype(torch::kInt32);
  if (values.empty()) {
    return torch::zeros({0}, options);
  }
  return torch::from_blob(
             const_cast<int*>(values.data()),
             {static_cast<long>(values.size())},
             options)
      .clone();
}

template <typename T>
inline torch::Tensor dcf_tensor_from_flat_vector(
    const std::vector<T>& values,
    int cols) {
  auto options = torch::TensorOptions().dtype(
      std::is_same<T, float>::value ? torch::kFloat32 : torch::kFloat64);
  if (values.empty()) {
    if (cols <= 1) {
      return torch::zeros({0}, options);
    }
    return torch::zeros({0, cols}, options);
  }
  if (cols <= 1) {
    return torch::from_blob(
               const_cast<T*>(values.data()),
               {static_cast<long>(values.size())},
               options)
        .clone();
  }
  return torch::from_blob(
             const_cast<T*>(values.data()),
             {static_cast<long>(values.size() / cols), cols},
             options)
      .clone();
}

struct pair_hash {
  template <class T1, class T2>
  std::size_t operator()(const std::pair<T1, T2>& p) const {
    auto hash1 = std::hash<T1>{}(p.first);
    auto hash2 = std::hash<T2>{}(p.second);
    return hash1 ^ (hash2 << 1);
  }
};

struct pair_equal {
  template <class T1, class T2>
  bool operator()(const std::pair<T1, T2>& p1, const std::pair<T1, T2>& p2) const {
    return p1.first == p2.first && p1.second == p2.second;
  }
};

struct PairKey {
  int from_pin_id;
  int to_pin_id;

  bool operator==(const PairKey& rhs) const {
    return from_pin_id == rhs.from_pin_id && to_pin_id == rhs.to_pin_id;
  }
};

struct PairKeyHash {
  std::size_t operator()(const PairKey& key) const {
    return std::hash<int>{}(key.from_pin_id) ^ (std::hash<int>{}(key.to_pin_id) << 1);
  }
};

struct PathInfo {
  float path_slack = std::numeric_limits<float>::quiet_NaN();
  float path_weight = 0.0f;
  std::vector<PairKey> pin_pairs;
};

struct EndpointPathBundle {
  int endpoint_pin_id = -1;
  float endpoint_slack = std::numeric_limits<float>::infinity();
  int num_paths_raw = 0;
  int num_paths_kept = 0;
  std::vector<PathInfo> paths;
};

struct EndpointRepairStats {
  int endpoint_pin_id = -1;
  float endpoint_slack = 0.0f;
  float total_path_mass = 0.0f;
  float rho1 = 0.0f;
  float rho2 = 0.0f;
  int num_paths_raw = 0;
  int num_paths_kept = 0;
  int num_unique_pairs = 0;
  PairKey top1_pair {-1, -1};
  PairKey top2_pair {-1, -1};
  float top1_pair_cover = 0.0f;
  float top2_union_cover = 0.0f;
  float endpoint_priority = 0.0f;
};

template <typename T>
struct GlobalPairAccum {
  T global_score = 0;
  int num_endpoints_contributing = 0;
  T sum_endpoint_priority = 0;
};

template <typename T>
std::vector<PairKey> extract_actionable_pin_pairs(
    const ot::Path& path,
    const _timing_impl::string2index_map_type& pin_name2id_map) {
  std::vector<PairKey> ordered_pairs;
  std::unordered_map<PairKey, char, PairKeyHash> seen;
  bool first = true;
  int last_id = -1;
  std::string last_node_name;
  for (const auto& point : path) {
    std::string name = point.pin.name();
    auto it = pin_name2id_map.find(name);
    if (it == pin_name2id_map.end()) {
      continue;
    }
    int pin_id = it->second;
    auto gate = point.pin.gate();
    std::string node_name = gate ? gate->name() : std::string("NO_GATE");
    if (first) {
      first = false;
      last_id = pin_id;
      last_node_name = node_name;
      continue;
    }
    if (last_node_name == "NO_GATE" || node_name == "NO_GATE" || node_name != last_node_name) {
      if (last_id == pin_id) {
        last_id = pin_id;
        last_node_name = node_name;
        continue;
      }
      PairKey key {last_id, pin_id};
      if (!seen.count(key)) {
        ordered_pairs.push_back(key);
        seen[key] = 1;
      }
    }
    last_id = pin_id;
    last_node_name = node_name;
  }
  return ordered_pairs;
}

template <typename T>
void write_slack_data_to_file(
    const std::unordered_map<std::string, std::vector<float>>& net_slack_differences,
    const std::string& filename) {
  std::ofstream file(filename);
  if (!file.is_open()) {
    std::cerr << "Unable to open file: " << filename << std::endl;
    return;
  }
  file << "NetName,PinCount,MinSlack,MaxSlack,AvgSlack\n";
  for (const auto& item : net_slack_differences) {
    file << item.first << "," << item.second[0] << "," << item.second[1] << ","
         << item.second[2] << "," << item.second[3] << "\n";
  }
}

template <typename T>
struct NetWeighting<T, NetWeightingScheme::ADAMS> {
  DEFINE_APPLY_SCHEME {
    dreamplacePrint(kINFO, "apply adams net-weighting scheme...\n");

    auto beg = std::chrono::steady_clock::now();
    const auto& paths = timer.report_timing(n);
    auto end = std::chrono::steady_clock::now();
    dreamplacePrint(
        kINFO,
        "finish report-timing (%f s)\n",
        std::chrono::duration_cast<std::chrono::milliseconds>(end - beg).count() * 0.001);

    if (paths.empty()) {
      dreamplacePrint(kWARN, "report_timing: no critical path found\n");
      return pybind11::dict();
    }
    size_t num_nets = timer.num_nets();
    std::vector<bool> net_critical_flag(num_nets, 0);
    beg = std::chrono::steady_clock::now();
    for (auto& path : paths) {
      for (auto& point : path) {
        auto name = point.pin.net()->name();
        int net_id = net_name2id_map.at(name);
        net_critical_flag.at(net_id) = 1;
      }
    }

#pragma omp parallel for num_threads(num_threads)
    for (size_t i = 0; i < num_nets; ++i) {
      if (degree_map[i] > ignore_net_degree) {
        continue;
      }
      net_criticality[i] *= 0.5;
      if (net_critical_flag[i]) {
        net_criticality[i] += 0.5;
      }
      net_weights[i] *= (1 + net_criticality[i]);
    }
    end = std::chrono::steady_clock::now();
    dreamplacePrint(
        kINFO,
        "finish net-weighting (%f s)\n",
        std::chrono::duration_cast<std::chrono::milliseconds>(end - beg).count() * 0.001);
    return pybind11::dict();
  }
};

template <typename T>
struct NetWeighting<T, NetWeightingScheme::LILITH> {
  DEFINE_APPLY_SCHEME {
    dreamplacePrint(kINFO, "apply lilith net-weighting scheme...\n");
    dreamplacePrint(kINFO, "lilith mode momentum decay factor: %f\n", decay);

    auto beg = std::chrono::steady_clock::now();
    float wns = timer.report_wns().value();
    dreamplacePrint(kINFO, "wns: %f\n", wns);
    double max_nw = 0;
    for (const auto& item : timer.nets()) {
      const auto& name = item.first;
      const auto& net = item.second;
      int net_id = net_name2id_map.at(name);
      float slack = report_net_slack(timer, net);
      if (wns < 0) {
        float nc = (slack < 0) ? std::max(0.f, slack / wns) : 0;
        net_criticality[net_id] = std::pow(1 + net_criticality[net_id], decay) *
            std::pow(1 + nc, 1 - decay) - 1;
      }
      if (degree_map[net_id] > ignore_net_degree) {
        continue;
      }
      net_weights[net_id] *= (1 + net_criticality[net_id]);
      if (net_weights[net_id] > max_net_weight) {
        net_weights[net_id] = max_net_weight;
      }
      if (max_nw < net_weights[net_id]) {
        max_nw = net_weights[net_id];
      }
    }

    auto end = std::chrono::steady_clock::now();
    dreamplacePrint(
        kINFO,
        "finish net-weighting (%f s)\n",
        std::chrono::duration_cast<std::chrono::milliseconds>(end - beg).count() * 0.001);
    return pybind11::dict();
  }
};

template <typename T>
struct NetWeighting<T, NetWeightingScheme::PIN2PIN> {
  DEFINE_APPLY_SCHEME {
    dreamplacePrint(kINFO, "apply pin2pin net-weighting scheme...\n");
    auto begT = std::chrono::steady_clock::now();

    dreamplacePrint(kINFO, "extracting paths...\n");
    std::optional<long unsigned int> optionalValue = timer.report_fep();
    int nvp = optionalValue ? static_cast<int>(*optionalValue) : 0;
    const auto& paths = timer.report_timing(nvp);
    dreamplacePrint(kINFO, "paths extraction done...\n");
    int num_unique_pairs = 0;
    int num_all_pairs = 0;
    float wns = timer.report_wns().value();

    for (int path_idx = 0; path_idx < static_cast<int>(paths.size()); ++path_idx) {
      const auto& path = paths[path_idx];
      bool first = true;
      int last_id = -1;
      std::string last_node_name;
      for (const auto& point : path) {
        std::string name = point.pin.name();
        auto gate = point.pin.gate();
        std::string node_name = gate ? gate->name() : std::string("NO_GATE");
        auto it = pin_name2id_map.find(name);
        if (it == pin_name2id_map.end()) {
          continue;
        }
        int pin_id = it->second;
        if (first) {
          last_id = pin_id;
          last_node_name = node_name;
          first = false;
        } else {
          if (last_node_name == "NO_GATE" || node_name == "NO_GATE" || node_name != last_node_name) {
#pragma omp critical
            {
              pybind11::tuple key = pybind11::make_tuple(last_id, pin_id);
              if (pin2pin_net_weight.contains(key)) {
                num_all_pairs += 1;
                pin2pin_net_weight[key] =
                    pin2pin_net_weight[key].cast<float>() + pin2pin_accumulate_weight * path.slack / wns;
                if (pin2pin_net_weight[key].cast<float>() > pin2pin_max_weight) {
                  pin2pin_net_weight[key] = pin2pin_max_weight;
                }
              } else {
                num_unique_pairs += 1;
                pin2pin_net_weight[key] = pin2pin_min_weight;
              }
            }
          }
          last_id = pin_id;
          last_node_name = node_name;
        }
      }
    }

    auto endT = std::chrono::steady_clock::now();
    dreamplacePrint(
        kINFO,
        "finish net-weighting (%f s)\n",
        std::chrono::duration_cast<std::chrono::milliseconds>(endT - begT).count() * 0.001);
    dreamplacePrint(kINFO, "all num %i \n", num_all_pairs);
    dreamplacePrint(kINFO, "unique num %i \n", num_unique_pairs);
    return pybind11::dict();
  }
};

template <typename T>
struct NetWeighting<T, NetWeightingScheme::DCF> {
  DEFINE_APPLY_SCHEME {
    if (!enable_dcf) {
      dreamplacePrint(kWARN, "dcf scheme selected but enable_dcf is disabled; skip update\n");
      return pybind11::dict();
    }

    dreamplacePrint(kINFO, "apply dcf net-weighting scheme...\n");
    auto begT = std::chrono::steady_clock::now();

    const std::array<T, 3> edges = {dcf_bin_edges[0], dcf_bin_edges[1], dcf_bin_edges[2]};
    const std::array<T, 4> representatives = {
        edges[0] * T(0.5),
        (edges[0] + edges[1]) * T(0.5),
        (edges[1] + edges[2]) * T(0.5),
        edges[2]};
    const T tau_A = std::max(dcf_tau_A, T(1e-3));
    const T tau_S = std::max(dcf_tau_S, T(1e-3));
    const T momentum = std::clamp(dcf_momentum, T(0), T(0.999));

    const auto endpoints = timer.report_negative_endpoints(ot::MAX);
    const size_t num_pins = timer.num_pins();
    const size_t num_arcs = timer.num_arcs();

    std::vector<dcf_hist_type<T>> node_mass(2 * num_pins, make_zero_dcf_hist<T>());
    std::vector<dcf_hist_type<T>> arc_hist(num_arcs, make_zero_dcf_hist<T>());

    int failing_endpoints = 0;
    for (const auto& endpoint : endpoints) {
      const std::string& pin_name = std::get<0>(endpoint);
      ot::Tran rf = std::get<1>(endpoint);
      float slack = std::get<2>(endpoint);
      const T deficit = std::max(T(0), static_cast<T>(-slack));
      if (deficit <= 0) {
        continue;
      }
      auto pin_itr = timer.pins().find(pin_name);
      if (pin_itr == timer.pins().end()) {
        continue;
      }
      const int bin = dcf_bin_index(deficit, edges);
      auto& hist = node_mass[dcf_state_index<T>(pin_itr->second.idx(), rf, num_pins)];
      hist[bin] += deficit;
      ++failing_endpoints;
    }

    std::vector<int> remaining_fanout(num_pins, 0);
    std::vector<const ot::Pin*> idx2pin(num_pins, nullptr);
    std::vector<char> in_order(num_pins, 0);
    std::deque<const ot::Pin*> ready;
    for (const auto& item : timer.pins()) {
      const auto& pin = item.second;
      remaining_fanout[pin.idx()] = static_cast<int>(pin.num_fanouts());
      idx2pin[pin.idx()] = &pin;
      if (pin.num_fanouts() == 0) {
        ready.push_back(&pin);
      }
    }

    std::vector<const ot::Pin*> reverse_order;
    reverse_order.reserve(num_pins);
    while (!ready.empty()) {
      const ot::Pin* pin = ready.front();
      ready.pop_front();
      if (in_order[pin->idx()]) {
        continue;
      }
      in_order[pin->idx()] = 1;
      reverse_order.push_back(pin);
      for (const ot::Arc* arc : pin->fanins()) {
        const ot::Pin& pred = arc->from();
        auto& fanout_left = remaining_fanout[pred.idx()];
        if (fanout_left > 0 && --fanout_left == 0) {
          ready.push_back(&pred);
        }
      }
    }

    if (reverse_order.size() < num_pins) {
      std::vector<const ot::Pin*> leftovers;
      leftovers.reserve(num_pins - reverse_order.size());
      for (size_t idx = 0; idx < num_pins; ++idx) {
        if (!in_order[idx] && idx2pin[idx]) {
          leftovers.push_back(idx2pin[idx]);
        }
      }
      std::sort(leftovers.begin(), leftovers.end(), [](const ot::Pin* lhs, const ot::Pin* rhs) {
        return dcf_pin_max_arrival<T>(*lhs) > dcf_pin_max_arrival<T>(*rhs);
      });
      reverse_order.insert(reverse_order.end(), leftovers.begin(), leftovers.end());
      dreamplacePrint(
          kWARN,
          "dcf encountered %zu pins outside reverse topological order; appended by arrival\n",
          leftovers.size());
    }

    for (const ot::Pin* pin : reverse_order) {
      for (const auto rf : {ot::RISE, ot::FALL}) {
        auto& q_v = node_mass[dcf_state_index<T>(pin->idx(), rf, num_pins)];
        if (dcf_hist_mass(q_v) <= 0) {
          continue;
        }

        auto v_at = pin->at(ot::MAX, rf);
        auto v_rat = pin->rat(ot::MAX, rf);
        if (!v_at || !v_rat) {
          continue;
        }

        struct Candidate {
          const ot::Arc* arc;
          ot::Tran pred_rf;
          T score;
        };

        std::vector<Candidate> candidates;
        T denom = 0;
        for (const ot::Arc* arc : pin->fanins()) {
          const ot::Pin& pred = arc->from();
          for (const auto pred_rf : {ot::RISE, ot::FALL}) {
            auto pred_at = pred.at(ot::MAX, pred_rf);
            auto delay = arc->delay(ot::MAX, pred_rf, rf);
            if (!pred_at || !delay) {
              continue;
            }
            const T arrival_gap = static_cast<T>(*v_at) -
                (static_cast<T>(*pred_at) + static_cast<T>(*delay));
            const T local_margin = static_cast<T>(*v_rat) -
                (static_cast<T>(*pred_at) + static_cast<T>(*delay));
            const T score = dcf_safe_exp(-arrival_gap / tau_A) *
                dcf_safe_exp(-std::max(T(0), local_margin) / tau_S);
            if (!std::isfinite(score) || score <= 0) {
              continue;
            }
            candidates.push_back({arc, pred_rf, score});
            denom += score;
          }
        }

        if (denom <= 0 || candidates.empty()) {
          continue;
        }

        for (const auto& candidate : candidates) {
          const T prob = candidate.score / denom;
          const auto delta_q = dcf_scale_hist(q_v, prob);
          dcf_add_hist(arc_hist[candidate.arc->idx()], delta_q);
          dcf_add_hist(
              node_mass[dcf_state_index<T>(candidate.arc->from().idx(), candidate.pred_rf, num_pins)],
              delta_q);
        }
      }
    }

    std::unordered_map<std::pair<int, int>, T, pair_hash, pair_equal> previous_weights;
    for (auto item : pin2pin_net_weight) {
      auto key = item.first.cast<pybind11::tuple>();
      previous_weights[{key[0].cast<int>(), key[1].cast<int>()}] = item.second.cast<T>();
    }
    pin2pin_net_weight.attr("clear")();

    size_t arcs_with_mass = 0;
    size_t exported_pairs = 0;
    T total_weight_mass = 0;
    std::vector<std::tuple<T, int, int> > top_pairs;
    top_pairs.reserve(num_arcs);

    for (const auto& arc : timer.arcs()) {
      const auto& hist = arc_hist[arc.idx()];
      const T mass = dcf_hist_mass(hist);
      if (mass <= 0) {
        continue;
      }
      ++arcs_with_mass;
      if (!arc.is_net_arc()) {
        continue;
      }
      auto from_itr = pin_name2id_map.find(arc.from().name());
      auto to_itr = pin_name2id_map.find(arc.to().name());
      if (from_itr == pin_name2id_map.end() || to_itr == pin_name2id_map.end()) {
        continue;
      }
      const int from_pin_id = from_itr->second;
      const int to_pin_id = to_itr->second;
      const T severity_mass = dcf_hist_weighted_sum(hist, representatives);
      const T tail_mass = hist[2] + hist[3];
      const T utility = severity_mass + T(0.5) * tail_mass;
      const T eta = dcf_pair_length(
          pos,
          num_nodes,
          pin2node_map,
          pin_offset_x,
          pin_offset_y,
          from_pin_id,
          to_pin_id);
      const T mapped_weight = std::log1p(std::max(T(0), utility * eta));
      if (!std::isfinite(mapped_weight) || mapped_weight <= 0) {
        continue;
      }
      T final_weight = mapped_weight;
      auto old_itr = previous_weights.find({from_pin_id, to_pin_id});
      if (old_itr != previous_weights.end()) {
        final_weight = momentum * old_itr->second + (T(1) - momentum) * mapped_weight;
      }
      if (!std::isfinite(final_weight) || final_weight <= 0) {
        continue;
      }
      pin2pin_net_weight[pybind11::make_tuple(from_pin_id, to_pin_id)] = final_weight;
      ++exported_pairs;
      total_weight_mass += final_weight;
      top_pairs.emplace_back(final_weight, from_pin_id, to_pin_id);
    }

    std::sort(top_pairs.begin(), top_pairs.end(), [](const auto& lhs, const auto& rhs) {
      return std::get<0>(lhs) > std::get<0>(rhs);
    });

    auto endT = std::chrono::steady_clock::now();
    dreamplacePrint(kINFO, "dcf failing endpoints %d\n", failing_endpoints);
    dreamplacePrint(kINFO, "dcf arcs with nonzero mass %zu\n", arcs_with_mass);
    dreamplacePrint(kINFO, "dcf exported pin pairs %zu\n", exported_pairs);
    dreamplacePrint(kINFO, "dcf total exported weight mass %f\n", static_cast<double>(total_weight_mass));
    for (size_t i = 0; i < std::min<size_t>(5, top_pairs.size()); ++i) {
      const auto& row = top_pairs[i];
      const T weight = std::get<0>(row);
      const int from_pin_id = std::get<1>(row);
      const int to_pin_id = std::get<2>(row);
      const char* from_name = from_pin_id < static_cast<int>(pin_names.size()) ? pin_names[from_pin_id].c_str() : "<unknown>";
      const char* to_name = to_pin_id < static_cast<int>(pin_names.size()) ? pin_names[to_pin_id].c_str() : "<unknown>";
      dreamplacePrint(kINFO, "dcf top pair %zu %s -> %s weight %f\n", i, from_name, to_name, static_cast<double>(weight));
    }
    dreamplacePrint(
        kINFO,
        "finish dcf net-weighting (%f s)\n",
        std::chrono::duration_cast<std::chrono::milliseconds>(endT - begT).count() * 0.001);
    return pybind11::dict();
  }
};

template <typename T>
struct NetWeighting<T, NetWeightingScheme::DCF_V2> {
  DEFINE_APPLY_SCHEME {
    pybind11::dict diagnostics;
    diagnostics["scheme_name"] = pybind11::str("dcf_v2");

    if (!enable_dcf) {
      dreamplacePrint(kWARN, "dcf_v2 scheme selected but enable_dcf is disabled; skip update\n");
      return diagnostics;
    }

    const int requested_k = std::max(1, endpoint_grouped_path_k);
    if (requested_k > 1) {
      dreamplacePrint(
          kWARN,
          "dcf_v2 currently supports grouped-k1 only; requested k=%d and using k=1\n",
          requested_k);
    }

    dreamplacePrint(kINFO, "apply dcf_v2 net-weighting scheme...\n");
    auto total_beg = std::chrono::steady_clock::now();

    auto path_extract_beg = std::chrono::steady_clock::now();
    std::optional<size_t> optional_fep = timer.report_fep();
    size_t failing_endpoints_reported = optional_fep ? *optional_fep : 0;
    const auto& paths = timer.report_timing(failing_endpoints_reported);
    auto path_extract_end = std::chrono::steady_clock::now();

    auto group_build_beg = std::chrono::steady_clock::now();
    std::unordered_map<int, size_t> bundle_map;
    std::vector<EndpointPathBundle> bundles;
    bundles.reserve(paths.size());

    int num_paths_raw_total = 0;
    int num_paths_kept_total = 0;
    for (const auto& path : paths) {
      if (path.empty()) {
        continue;
      }
      auto endpoint_itr = pin_name2id_map.find(path.back().pin.name());
      if (endpoint_itr == pin_name2id_map.end()) {
        continue;
      }
      int endpoint_pin_id = endpoint_itr->second;
      size_t bundle_id = 0;
      auto found_bundle = bundle_map.find(endpoint_pin_id);
      if (found_bundle == bundle_map.end()) {
        bundle_id = bundles.size();
        bundle_map[endpoint_pin_id] = bundle_id;
        EndpointPathBundle bundle;
        bundle.endpoint_pin_id = endpoint_pin_id;
        bundles.push_back(bundle);
      } else {
        bundle_id = found_bundle->second;
      }

      auto& bundle = bundles[bundle_id];
      bundle.num_paths_raw += 1;
      num_paths_raw_total += 1;
      bundle.endpoint_slack = std::min(bundle.endpoint_slack, path.slack);

      PathInfo path_info;
      path_info.path_slack = path.slack;
      path_info.pin_pairs = extract_actionable_pin_pairs<T>(path, pin_name2id_map);
      if (path_info.pin_pairs.empty()) {
        continue;
      }
      bundle.paths.push_back(std::move(path_info));
      bundle.num_paths_kept += 1;
      num_paths_kept_total += 1;
    }
    auto group_build_end = std::chrono::steady_clock::now();

    auto repair_score_beg = std::chrono::steady_clock::now();
    const T tau = std::max(endpoint_repair_tau, T(1e-3));
    const T alpha = std::max(endpoint_repair_alpha, T(0));
    const T beta = std::max(endpoint_repair_beta, T(0));
    std::unordered_map<PairKey, GlobalPairAccum<T>, PairKeyHash> global_pair_scores;
    std::vector<EndpointRepairStats> endpoint_stats;
    endpoint_stats.reserve(bundles.size());
    size_t endpoint_local_pair_rows = 0;

    std::vector<int> endpoint_stat_pin_ids;
    std::vector<int> endpoint_stat_num_paths_raw;
    std::vector<int> endpoint_stat_num_paths_kept;
    std::vector<int> endpoint_stat_num_unique_pairs;
    std::vector<int> endpoint_stat_top_pair_ids_flat;
    std::vector<T> endpoint_stat_metrics_flat;

    std::vector<int> endpoint_pair_cover_endpoint_pin_ids;
    std::vector<int> endpoint_pair_cover_pair_from_ids;
    std::vector<int> endpoint_pair_cover_pair_to_ids;
    std::vector<int> endpoint_pair_cover_pair_ranks;
    std::vector<int> endpoint_pair_cover_touch_counts;
    std::vector<T> endpoint_pair_cover_metrics_flat;

    std::vector<int> bundle_endpoint_pin_ids;
    std::vector<int> bundle_num_paths_raw;
    std::vector<int> bundle_num_paths_kept;
    std::vector<T> bundle_endpoint_slacks;
    std::vector<int> bundle_path_offsets;
    std::vector<T> path_metrics_flat;
    std::vector<int> path_pair_offsets;
    std::vector<int> path_pair_src_ids;
    std::vector<int> path_pair_dst_ids;
    if (endpoint_repair_enable_dump) {
      bundle_path_offsets.push_back(0);
      path_pair_offsets.push_back(0);
    }

    for (auto& bundle : bundles) {
      EndpointRepairStats stats;
      stats.endpoint_pin_id = bundle.endpoint_pin_id;
      stats.endpoint_slack = std::isfinite(bundle.endpoint_slack) ? bundle.endpoint_slack : 0.0f;
      stats.num_paths_raw = bundle.num_paths_raw;
      stats.num_paths_kept = bundle.num_paths_kept;

      std::unordered_map<PairKey, T, PairKeyHash> pair_cover;
      std::unordered_map<PairKey, int, PairKeyHash> pair_touch_count;
      const T s_e = bundle.paths.empty() ? T(0) : static_cast<T>(bundle.endpoint_slack);

      if (endpoint_repair_enable_dump) {
        bundle_endpoint_pin_ids.push_back(bundle.endpoint_pin_id);
        bundle_endpoint_slacks.push_back(static_cast<T>(stats.endpoint_slack));
        bundle_num_paths_raw.push_back(bundle.num_paths_raw);
        bundle_num_paths_kept.push_back(bundle.num_paths_kept);
      }

      for (const auto& path_info_const : bundle.paths) {
        PathInfo& path_info = const_cast<PathInfo&>(path_info_const);
        const T slack = static_cast<T>(path_info.path_slack);
        const T path_weight = dcf_safe_exp(-(slack - s_e) / tau);
        if (!std::isfinite(path_weight) || path_weight <= 0) {
          continue;
        }
        path_info.path_weight = static_cast<float>(path_weight);
        stats.total_path_mass += path_weight;
        const T inv_cardinality = T(1) / static_cast<T>(path_info.pin_pairs.size());
        for (const auto& pair : path_info.pin_pairs) {
          pair_cover[pair] += path_weight * inv_cardinality;
          pair_touch_count[pair] += 1;
        }

        if (endpoint_repair_enable_dump) {
          path_metrics_flat.push_back(slack);
          path_metrics_flat.push_back(path_weight);
          for (const auto& pair : path_info.pin_pairs) {
            path_pair_src_ids.push_back(pair.from_pin_id);
            path_pair_dst_ids.push_back(pair.to_pin_id);
          }
          path_pair_offsets.push_back(static_cast<int>(path_pair_src_ids.size()));
        }
      }

      stats.num_unique_pairs = static_cast<int>(pair_cover.size());
      endpoint_local_pair_rows += pair_cover.size();
      std::vector<std::pair<PairKey, T> > sorted_pairs(pair_cover.begin(), pair_cover.end());
      std::sort(sorted_pairs.begin(), sorted_pairs.end(), [](const auto& lhs, const auto& rhs) {
        if (lhs.second != rhs.second) {
          return lhs.second > rhs.second;
        }
        if (lhs.first.from_pin_id != rhs.first.from_pin_id) {
          return lhs.first.from_pin_id < rhs.first.from_pin_id;
        }
        return lhs.first.to_pin_id < rhs.first.to_pin_id;
      });

      if (!sorted_pairs.empty()) {
        stats.top1_pair = sorted_pairs[0].first;
        stats.top1_pair_cover = sorted_pairs[0].second;
      }
      if (sorted_pairs.size() >= 2) {
        stats.top2_pair = sorted_pairs[1].first;
        stats.top2_union_cover = sorted_pairs[0].second + sorted_pairs[1].second;
      } else {
        stats.top2_union_cover = stats.top1_pair_cover;
      }

      if (stats.total_path_mass > 0 && stats.num_unique_pairs > 0) {
        stats.rho1 = stats.top1_pair_cover / stats.total_path_mass;
        stats.rho2 = stats.top2_union_cover / stats.total_path_mass;
        const T severity = std::max(T(0), static_cast<T>(-stats.endpoint_slack));
        const T priority = std::pow(severity, alpha) *
            std::pow(std::max(T(0), static_cast<T>(stats.rho1)), beta);
        if (std::isfinite(priority)) {
          stats.endpoint_priority = priority;
        }
        for (const auto& item : sorted_pairs) {
          const T normalized_cover = item.second / stats.total_path_mass;
          auto& accum = global_pair_scores[item.first];
          accum.global_score += stats.endpoint_priority * normalized_cover;
          accum.num_endpoints_contributing += 1;
          accum.sum_endpoint_priority += stats.endpoint_priority;
        }
      }

      endpoint_stats.push_back(stats);

      if (endpoint_repair_enable_dump) {
        endpoint_stat_pin_ids.push_back(stats.endpoint_pin_id);
        endpoint_stat_num_paths_raw.push_back(stats.num_paths_raw);
        endpoint_stat_num_paths_kept.push_back(stats.num_paths_kept);
        endpoint_stat_num_unique_pairs.push_back(stats.num_unique_pairs);
        endpoint_stat_top_pair_ids_flat.push_back(stats.top1_pair.from_pin_id);
        endpoint_stat_top_pair_ids_flat.push_back(stats.top1_pair.to_pin_id);
        endpoint_stat_top_pair_ids_flat.push_back(stats.top2_pair.from_pin_id);
        endpoint_stat_top_pair_ids_flat.push_back(stats.top2_pair.to_pin_id);
        endpoint_stat_metrics_flat.push_back(static_cast<T>(stats.endpoint_slack));
        endpoint_stat_metrics_flat.push_back(stats.total_path_mass);
        endpoint_stat_metrics_flat.push_back(stats.rho1);
        endpoint_stat_metrics_flat.push_back(stats.rho2);
        endpoint_stat_metrics_flat.push_back(stats.top1_pair_cover);
        endpoint_stat_metrics_flat.push_back(stats.top2_union_cover);
        endpoint_stat_metrics_flat.push_back(stats.endpoint_priority);

        int pair_rank = 1;
        for (const auto& item : sorted_pairs) {
          endpoint_pair_cover_endpoint_pin_ids.push_back(stats.endpoint_pin_id);
          endpoint_pair_cover_pair_from_ids.push_back(item.first.from_pin_id);
          endpoint_pair_cover_pair_to_ids.push_back(item.first.to_pin_id);
          endpoint_pair_cover_pair_ranks.push_back(pair_rank++);
          endpoint_pair_cover_touch_counts.push_back(pair_touch_count[item.first]);
          endpoint_pair_cover_metrics_flat.push_back(static_cast<T>(stats.endpoint_slack));
          endpoint_pair_cover_metrics_flat.push_back(item.second);
        }

        bundle_path_offsets.push_back(static_cast<int>(path_metrics_flat.size() / 2));
      }
    }
    auto repair_score_end = std::chrono::steady_clock::now();

    auto global_aggregate_beg = std::chrono::steady_clock::now();
    std::unordered_map<std::pair<int, int>, T, pair_hash, pair_equal> previous_weights;
    for (auto item : pin2pin_net_weight) {
      auto key = item.first.cast<pybind11::tuple>();
      previous_weights[{key[0].cast<int>(), key[1].cast<int>()}] = item.second.cast<T>();
    }
    pin2pin_net_weight.attr("clear")();

    const T momentum = std::clamp(dcf_momentum, T(0), T(0.999));
    size_t exported_pairs = 0;
    T total_weight_mass = 0;
    std::vector<std::tuple<T, T, int, int> > top_pairs;

    std::vector<int> global_pair_from_ids;
    std::vector<int> global_pair_to_ids;
    std::vector<int> global_pair_contrib_counts;
    std::vector<T> global_pair_metrics_flat;

    for (const auto& item : global_pair_scores) {
      const PairKey& pair = item.first;
      const GlobalPairAccum<T>& accum = item.second;
      if (!std::isfinite(accum.global_score) || accum.global_score <= 0) {
        continue;
      }
      const T pair_length = dcf_pair_length(
          pos,
          num_nodes,
          pin2node_map,
          pin_offset_x,
          pin_offset_y,
          pair.from_pin_id,
          pair.to_pin_id);
      const T mapped_weight = std::log1p(std::max(T(0), accum.global_score * pair_length));
      if (!std::isfinite(mapped_weight) || mapped_weight <= 0) {
        continue;
      }
      T final_weight = mapped_weight;
      auto old_itr = previous_weights.find({pair.from_pin_id, pair.to_pin_id});
      if (old_itr != previous_weights.end()) {
        final_weight = momentum * old_itr->second + (T(1) - momentum) * mapped_weight;
      }
      if (!std::isfinite(final_weight) || final_weight <= 0) {
        continue;
      }

      pin2pin_net_weight[pybind11::make_tuple(pair.from_pin_id, pair.to_pin_id)] = final_weight;
      ++exported_pairs;
      total_weight_mass += final_weight;
      top_pairs.emplace_back(accum.global_score, final_weight, pair.from_pin_id, pair.to_pin_id);

      if (endpoint_repair_enable_dump) {
        global_pair_from_ids.push_back(pair.from_pin_id);
        global_pair_to_ids.push_back(pair.to_pin_id);
        global_pair_contrib_counts.push_back(accum.num_endpoints_contributing);
        global_pair_metrics_flat.push_back(accum.global_score);
        global_pair_metrics_flat.push_back(final_weight);
        global_pair_metrics_flat.push_back(accum.sum_endpoint_priority);
      }
    }
    std::sort(top_pairs.begin(), top_pairs.end(), [](const auto& lhs, const auto& rhs) {
      return std::get<0>(lhs) > std::get<0>(rhs);
    });
    auto global_aggregate_end = std::chrono::steady_clock::now();

    auto total_end = std::chrono::steady_clock::now();
    const double path_extract_time_ms =
        std::chrono::duration_cast<std::chrono::milliseconds>(path_extract_end - path_extract_beg).count();
    const double group_build_time_ms =
        std::chrono::duration_cast<std::chrono::milliseconds>(group_build_end - group_build_beg).count();
    const double repair_score_time_ms =
        std::chrono::duration_cast<std::chrono::milliseconds>(repair_score_end - repair_score_beg).count();
    const double global_aggregate_time_ms =
        std::chrono::duration_cast<std::chrono::milliseconds>(global_aggregate_end - global_aggregate_beg).count();

    dreamplacePrint(kINFO, "dcf_v2 failing endpoints reported %zu\n", failing_endpoints_reported);
    dreamplacePrint(kINFO, "dcf_v2 grouped bundles built %zu\n", bundles.size());
    dreamplacePrint(kINFO, "dcf_v2 raw paths %d kept paths %d\n", num_paths_raw_total, num_paths_kept_total);
    dreamplacePrint(kINFO, "dcf_v2 endpoint-local pairs %zu\n", endpoint_local_pair_rows);
    dreamplacePrint(kINFO, "dcf_v2 exported global pairs %zu\n", exported_pairs);
    dreamplacePrint(
        kINFO,
        "dcf_v2 runtime breakdown path_extract %.3f ms group_build %.3f ms repair_score %.3f ms global_aggregate %.3f ms\n",
        path_extract_time_ms,
        group_build_time_ms,
        repair_score_time_ms,
        global_aggregate_time_ms);
    for (size_t i = 0; i < std::min<size_t>(5, top_pairs.size()); ++i) {
      const auto& row = top_pairs[i];
      const T global_score = std::get<0>(row);
      const T final_weight = std::get<1>(row);
      const int from_pin_id = std::get<2>(row);
      const int to_pin_id = std::get<3>(row);
      const char* from_name = from_pin_id < static_cast<int>(pin_names.size()) ? pin_names[from_pin_id].c_str() : "<unknown>";
      const char* to_name = to_pin_id < static_cast<int>(pin_names.size()) ? pin_names[to_pin_id].c_str() : "<unknown>";
      dreamplacePrint(
          kINFO,
          "dcf_v2 top global pair %zu %s -> %s score %f final_weight %f\n",
          i,
          from_name,
          to_name,
          static_cast<double>(global_score),
          static_cast<double>(final_weight));
    }
    dreamplacePrint(
        kINFO,
        "finish dcf_v2 net-weighting (%f s)\n",
        std::chrono::duration_cast<std::chrono::milliseconds>(total_end - total_beg).count() * 0.001);

    diagnostics["failing_endpoints_reported"] = pybind11::int_(failing_endpoints_reported);
    diagnostics["bundles_built"] = pybind11::int_(bundles.size());
    diagnostics["num_paths_raw_total"] = pybind11::int_(num_paths_raw_total);
    diagnostics["num_paths_kept_total"] = pybind11::int_(num_paths_kept_total);
    diagnostics["endpoint_local_pair_rows"] = pybind11::int_(endpoint_local_pair_rows);
    diagnostics["exported_global_pairs"] = pybind11::int_(exported_pairs);
    diagnostics["path_extract_time_ms"] = path_extract_time_ms;
    diagnostics["group_build_time_ms"] = group_build_time_ms;
    diagnostics["repair_score_time_ms"] = repair_score_time_ms;
    diagnostics["global_aggregate_time_ms"] = global_aggregate_time_ms;
    diagnostics["pass_runtime_ms"] =
        std::chrono::duration_cast<std::chrono::milliseconds>(total_end - total_beg).count();

    if (endpoint_repair_enable_dump) {
      diagnostics["endpoint_stat_pin_ids"] = dcf_tensor_from_int_vector(endpoint_stat_pin_ids);
      diagnostics["endpoint_stat_num_paths_raw"] = dcf_tensor_from_int_vector(endpoint_stat_num_paths_raw);
      diagnostics["endpoint_stat_num_paths_kept"] = dcf_tensor_from_int_vector(endpoint_stat_num_paths_kept);
      diagnostics["endpoint_stat_num_unique_pairs"] = dcf_tensor_from_int_vector(endpoint_stat_num_unique_pairs);
      diagnostics["endpoint_stat_top_pair_ids"] = dcf_tensor_from_flat_vector(endpoint_stat_top_pair_ids_flat, 4);
      diagnostics["endpoint_stat_metrics"] = dcf_tensor_from_flat_vector(endpoint_stat_metrics_flat, 7);

      diagnostics["endpoint_pair_cover_endpoint_pin_ids"] = dcf_tensor_from_int_vector(endpoint_pair_cover_endpoint_pin_ids);
      diagnostics["endpoint_pair_cover_pair_from_ids"] = dcf_tensor_from_int_vector(endpoint_pair_cover_pair_from_ids);
      diagnostics["endpoint_pair_cover_pair_to_ids"] = dcf_tensor_from_int_vector(endpoint_pair_cover_pair_to_ids);
      diagnostics["endpoint_pair_cover_pair_ranks"] = dcf_tensor_from_int_vector(endpoint_pair_cover_pair_ranks);
      diagnostics["endpoint_pair_cover_touch_counts"] = dcf_tensor_from_int_vector(endpoint_pair_cover_touch_counts);
      diagnostics["endpoint_pair_cover_metrics"] = dcf_tensor_from_flat_vector(endpoint_pair_cover_metrics_flat, 2);

      diagnostics["bundle_endpoint_pin_ids"] = dcf_tensor_from_int_vector(bundle_endpoint_pin_ids);
      diagnostics["bundle_endpoint_slacks"] = dcf_tensor_from_flat_vector(bundle_endpoint_slacks, 1);
      diagnostics["bundle_num_paths_raw"] = dcf_tensor_from_int_vector(bundle_num_paths_raw);
      diagnostics["bundle_num_paths_kept"] = dcf_tensor_from_int_vector(bundle_num_paths_kept);
      diagnostics["bundle_path_offsets"] = dcf_tensor_from_int_vector(bundle_path_offsets);
      diagnostics["path_metrics"] = dcf_tensor_from_flat_vector(path_metrics_flat, 2);
      diagnostics["path_pair_offsets"] = dcf_tensor_from_int_vector(path_pair_offsets);
      diagnostics["path_pair_src_ids"] = dcf_tensor_from_int_vector(path_pair_src_ids);
      diagnostics["path_pair_dst_ids"] = dcf_tensor_from_int_vector(path_pair_dst_ids);

      diagnostics["global_pair_from_ids"] = dcf_tensor_from_int_vector(global_pair_from_ids);
      diagnostics["global_pair_to_ids"] = dcf_tensor_from_int_vector(global_pair_to_ids);
      diagnostics["global_pair_contrib_counts"] = dcf_tensor_from_int_vector(global_pair_contrib_counts);
      diagnostics["global_pair_metrics"] = dcf_tensor_from_flat_vector(global_pair_metrics_flat, 3);
    }

    return diagnostics;
  }
};

#undef DEFINE_APPLY_SCHEME

DREAMPLACE_END_NAMESPACE

#endif  // DREAMPLACE_NET_WEIGHTING_SCHEME_H_
