#ifndef DREAMPLACE_NET_WEIGHTING_SCHEME_H_
#define DREAMPLACE_NET_WEIGHTING_SCHEME_H_
#define PYBIND11_DETAILED_ERROR_MESSAGES

#include <memory>
#include <algorithm>
#include <array>
#include <cmath>
#include <deque>
#include <vector>
#include <string>
#include <unordered_map>
#include <ot/timer/timer.hpp>
#include "utility/src/torch.h"
#include "utility/src/utils.h"
#include "place_io/src/Util.h"
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <unordered_map>
#include <functional>
#include <utility>
#include <fstream>



namespace _timing_impl {
template<typename T>
using index_type = typename DREAMPLACE_NAMESPACE::coordinate_traits<T>::index_type;
using string2index_map_type = std::unordered_map<std::string, index_type<int> >;
}

DREAMPLACE_BEGIN_NAMESPACE

// The net-weighting scheme enum class.
// We try to implement different net-weighting schemes.
// For different schemes, we implement different algorithms to update net
// weights in each timing iteration.
enum class NetWeightingScheme {
  ADAMS, LILITH, PIN2PIN, DCF, DCF_HYBRID
};

///
/// \brief Implementation of net-weighting scheme.
/// \param timer the OpenTimer object.
/// \param n the maximum number of paths.
/// \param flat_netpin flatened net pins.
/// \param netpin_start the start index of each net in the flat netpin
/// \param net_name2id_map the net name to id map.
/// \param net_criticality the criticality values of nets (array).
/// \param net_criticality_deltas the criticality delta values of nets (array).
/// \param net_weights the weights of nets (array).
/// \param net_weight_deltas the increment of net weights.
/// \param degree_map the degree map of nets.
/// \param decay the decay factor in momemtum iteration.
/// \param max_net_weight the maximum net weight in timing opt.
/// \param ignore_net_degree the net degree threshold.
/// \param num_threads number of threads for parallel computing.
///
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
      pybind11::dict& pin2pin_base_net_weight,                     \
      bool enable_dcf, const T* dcf_bin_edges,                     \
      T dcf_tau_A, T dcf_tau_S, T dcf_momentum,                    \
      int dcf_version, T dcf_beta,                                 \
      T dcf_v4_base_beta, int dcf_v4_decay_start_step,             \
      int dcf_v4_decay_end_step, T dcf_hybrid_lambda,              \
      bool dcf_hybrid_debug,                                       \
      bool enable_dcf_diagnostics, int diagnostics_step_id,        \
      bool diagnostics_dump_step, bool dcf_diag_dump_state_stats,  \
      int dcf_diag_dump_pair_limit, int dcf_diag_dump_topk,        \
      T decay, T max_net_weight, int ignore_net_degree,            \
      int num_threads,                                             \
      int pin2pin_max_weight, int pin2pin_min_weight, double pin2pin_accumulate_weight)

///
/// \brief The implementation of net-weighting algorithms.
/// \tparam T the array data type (usually float).
/// \tparam scm the enum net-weighting scheme.
/// Partial specialization of full class should be implemented to correctly
/// enable compile-time polymorphism.
///
template <typename T, NetWeightingScheme scm>
struct NetWeighting {
  DEFINE_APPLY_SCHEME;
};

///
/// \brief Report the slack of a specific pin (given the name of this pin).
//    The report_slack method will be invoked. Note that we extract the worst
//    one of [MIN, MAX] * [FALL, RISE] (4 slacks).
/// \param timer the OpenTimer object.
/// \param name the specific pin name.
///
inline float report_pin_slack(ot::Timer& timer, const std::string& name) {
  using namespace ot;
  // The pin slack defaults to be the largest float number.
  // Use a valid float number instead of the infinity.
  float ps = std::numeric_limits<float>::max();
  FOR_EACH_EL_RF (el, rf) {
    auto s = timer.report_slack(name, el, rf);
    // Check whether the std::optional<float> value indeed has a value or not.
    // The comparison is enabled only when @s has a value.
    if (s) ps = std::min(ps, *s);
  }
  return ps;
}

///
/// \brief Report the slack of a specific net.
/// \param timer the OpenTimer object.
/// \param net the specific net structure in the OpenTimer object.
///
inline float report_net_slack(ot::Timer& timer, const ot::Net& net) {
  // The net slack defaults to the worst one of sinks.
  float slack = std::numeric_limits<float>::max();
  const ot::Pin* root = net.root();
  for (const auto ptr : net.pins()) {
    // Skip the driver in the traversal.
    if (ptr == root) continue;
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
  if (deficit < edges[0]) return 0;
  if (deficit < edges[1]) return 1;
  if (deficit < edges[2]) return 2;
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

template <typename T>
inline T dcf_v4_effective_beta(
    int timing_step_id,
    T base_beta,
    int decay_start_step,
    int decay_end_step) {
  const T clamped_base_beta = std::max(T(0), base_beta);
  const int safe_start = std::max(1, decay_start_step);
  const int safe_end = std::max(safe_start, decay_end_step);
  if (timing_step_id <= 0 || timing_step_id < safe_start) {
    return clamped_base_beta;
  }
  if (timing_step_id > safe_end) {
    return T(0);
  }
  if (safe_end == safe_start) {
    return timing_step_id < safe_end ? clamped_base_beta : T(0);
  }
  const T span = static_cast<T>(safe_end - safe_start + 1);
  const T offset = static_cast<T>(timing_step_id - safe_start);
  const T ratio = std::clamp(offset / span, T(0), T(1));
  return clamped_base_beta * (T(1) - ratio);
}

template <typename T>
inline T dcf_export_utility(
    int dcf_version,
    T severity_mass,
    T tail_mass,
    T total_mass,
    T dcf_beta,
    T dcf_v4_beta) {
  switch (dcf_version) {
    case 1:
      return severity_mass + T(0.5) * tail_mass;
    case 2:
      return total_mass;
    case 3:
      return total_mass + dcf_beta * tail_mass;
    case 4:
      return total_mass + dcf_v4_beta * tail_mass;
    case 0:
    default:
      return severity_mass + T(0.5) * tail_mass;
  }
}

template <typename T>
inline T dcf_map_export_weight(int dcf_version, T utility, T eta) {
  const T clamped_utility = std::max(T(0), utility);
  if (dcf_version == 0) {
    return std::log1p(clamped_utility * eta);
  }
  return std::log1p(clamped_utility);
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

template <typename T>
inline torch::Tensor dcf_tensor_from_vector(const std::vector<T>& values) {
  auto options = torch::TensorOptions().dtype(
      std::is_same<T, float>::value ? torch::kFloat32 : torch::kFloat64);
  if (values.empty()) {
    return torch::zeros({0}, options);
  }
  return torch::from_blob(
      const_cast<T*>(values.data()),
      {static_cast<long>(values.size())},
      options)
      .clone();
}

////////////////////////////////////////////////////////////////////////////
// Partial specialization of naive net-weighting schemes.
template <typename T>
struct NetWeighting<T, NetWeightingScheme::ADAMS> {
  DEFINE_APPLY_SCHEME {
    // Apply net-weighting scheme.
    dreamplacePrint(kINFO, "apply adams net-weighting scheme...\n");
    
    // Report the first several paths of the critical ones.
    // Note that a path is actually a derived class of std::list<ot::Point>.
    // A Point object contains the corresponding pin.
    // Report timing using the timer object.
    auto beg = std::chrono::steady_clock::now();
    const auto& paths = timer.report_timing(n);
    auto end = std::chrono::steady_clock::now();
    dreamplacePrint(kINFO, "finish report-timing (%f s)\n",
      std::chrono::duration_cast<std::chrono::milliseconds>(
        end - beg).count() * 0.001);

    // Check paths returned by timer.
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
    // Update the net weights accordingly.
#pragma omp parallel for num_threads(num_threads)
    for (size_t i = 0; i < num_nets; ++i) {
      if (degree_map[i] > ignore_net_degree) continue;
      net_criticality[i] *= 0.5;
      if (net_critical_flag[i]) net_criticality[i] += 0.5;
      net_weights[i] *= (1 + net_criticality[i]);
    }
    end = std::chrono::steady_clock::now();
    dreamplacePrint(kINFO, "finish net-weighting (%f s)\n",
      std::chrono::duration_cast<std::chrono::milliseconds>(
        end - beg).count() * 0.001);
    return pybind11::dict();
  }
};

inline void write_slack_data_to_file(const std::unordered_map<std::string, std::vector<float>>& net_slack_differences, const std::string& filename) {
    std::ofstream file(filename);

    if (!file.is_open()) {
        std::cerr << "Unable to open file: " << filename << std::endl;
        return;
    }

    file << "NetName,PinCount,MinSlack,MaxSlack,AvgSlack\n";

    for (const auto& [name, values] : net_slack_differences) {
        file << name << "," << values[0] << "," << values[1] << "," << values[2] << "," << values[3] << "\n";
    }

    file.close();
}

// Partial specialization of lilith net-weighting.
template <typename T>
struct NetWeighting<T, NetWeightingScheme::LILITH> {
  DEFINE_APPLY_SCHEME {
    // Apply net-weighting scheme.
    dreamplacePrint(kINFO, "apply lilith net-weighting scheme...\n");
    dreamplacePrint(kINFO, "lilith mode momentum decay factor: %f\n", decay);
    
    // Calculate run-time of net-weighting update.
    auto beg = std::chrono::steady_clock::now();
    float wns = timer.report_wns().value();
    dreamplacePrint(kINFO, "wns: %f\n", wns);
    double max_nw = 0;
    for (const auto& [name, net] : timer.nets()) {
      // The net id in the dreamplace database.
      int net_id = net_name2id_map.at(name);
      float slack = report_net_slack(timer, net);
      if (wns < 0) {
        float nc = (slack < 0)? std::max(0.f, slack / wns) : 0;
        // Decay the criticality value of the current net.
        net_criticality[net_id] = std::pow(1 + net_criticality[net_id], decay) *
          std::pow(1 + nc, 1 - decay) - 1;
      }

      // Update the net weights accordingly.
      // Ignore the clock net.
      if (degree_map[net_id] > ignore_net_degree)
        continue;
      net_weights[net_id] *= (1 + net_criticality[net_id]);

      // Manually limit the upper bound of the net weights, as it may
      // introduce illegality or divergence for some cases.
      if (net_weights[net_id] > max_net_weight)
        net_weights[net_id] = max_net_weight;
      if (max_nw < net_weights[net_id]) max_nw = net_weights[net_id];
    }

    auto end = std::chrono::steady_clock::now();
    dreamplacePrint(kINFO, "finish net-weighting (%f s)\n",
      std::chrono::duration_cast<std::chrono::milliseconds>(
        end - beg).count() * 0.001);
    return pybind11::dict();
  }
};


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

template <typename T>
inline void update_pin2pin_weight_dict(
    ot::Timer& timer,
    const _timing_impl::string2index_map_type& pin_name2id_map,
    pybind11::dict& pin2pin_weight_dict,
    int pin2pin_max_weight,
    int pin2pin_min_weight,
    double pin2pin_accumulate_weight,
    int& num_unique_pairs,
    int& num_all_pairs) {
  dreamplacePrint(kINFO, "extracting paths...\n");
  std::optional<long unsigned int> optionalValue = timer.report_fep();
  int nvp = 0;
  nvp = *optionalValue;
  const auto& paths = timer.report_timing(nvp);
  dreamplacePrint(kINFO, "paths extraction done...\n");
  const T wns = static_cast<T>(timer.report_wns().value());

  for (int path_idx = 0; path_idx < paths.size(); ++path_idx) {
    const auto& path = paths[path_idx];
    bool first = true;
    int last_id = -1;
    std::string last_node_name;
    for (const auto& point : path) {
      std::string name = point.pin.name();
      auto gate = point.pin.gate();
      std::string node_name = gate ? gate->name() : "NO_GATE";
      auto it = pin_name2id_map.find(name);
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
            if (pin2pin_weight_dict.contains(key)) {
              ++num_all_pairs;
              pin2pin_weight_dict[key] = pin2pin_weight_dict[key].cast<T>() +
                  static_cast<T>(pin2pin_accumulate_weight) * path.slack / wns;
              if (pin2pin_weight_dict[key].cast<T>() > static_cast<T>(pin2pin_max_weight)) {
                pin2pin_weight_dict[key] = static_cast<T>(pin2pin_max_weight);
              }
            } else {
              ++num_unique_pairs;
              pin2pin_weight_dict[key] = static_cast<T>(pin2pin_min_weight);
            }
          }
        }
        last_id = pin_id;
        last_node_name = node_name;
      }
    }
  }
}


template <typename T>
struct NetWeighting<T, NetWeightingScheme::PIN2PIN> {
    DEFINE_APPLY_SCHEME {
        // Apply net-weighting scheme.
        dreamplacePrint(kINFO, "apply pin2pin net-weighting scheme...\n");
        // Calculate run-time of net-weighting update.
        auto begT = std::chrono::steady_clock::now();
        int num_unique_pairs = 0;
        int num_all_pairs = 0;

        update_pin2pin_weight_dict<T>(
            timer,
            pin_name2id_map,
            pin2pin_net_weight,
            pin2pin_max_weight,
            pin2pin_min_weight,
            pin2pin_accumulate_weight,
            num_unique_pairs,
            num_all_pairs);
        auto endT = std::chrono::steady_clock::now();
        dreamplacePrint(kINFO, "finish net-weighting (%f s)\n",
            std::chrono::duration_cast<std::chrono::milliseconds>(
                endT - begT).count() * 0.001);
        dreamplacePrint(kINFO, "all num %i \n", num_all_pairs);
        dreamplacePrint(kINFO, "unique num %i \n", num_unique_pairs);
        return pybind11::dict();
      }
};

template <typename T>
struct NetWeighting<T, NetWeightingScheme::DCF> {
    DEFINE_APPLY_SCHEME {
        pybind11::dict diagnostics;
        diagnostics["scheme_name"] = pybind11::str("dcf");
        diagnostics["diagnostics_step_id"] = diagnostics_step_id;
        diagnostics["dcf_diag_dump_topk"] = dcf_diag_dump_topk;
        if (!enable_dcf) {
            dreamplacePrint(kWARN, "dcf scheme selected but enable_dcf is disabled; skip update\n");
            return diagnostics;
        }

        dreamplacePrint(kINFO, "apply dcf net-weighting scheme...\n");
        auto begT = std::chrono::steady_clock::now();
        const bool collect_heavy = enable_dcf_diagnostics && diagnostics_dump_step;
        const bool collect_state = collect_heavy && dcf_diag_dump_state_stats;
        const int pair_limit = std::max(0, dcf_diag_dump_pair_limit);

        const std::array<T, 3> edges = {
            dcf_bin_edges[0], dcf_bin_edges[1], dcf_bin_edges[2]};
        const std::array<T, 4> representatives = {
            edges[0] * T(0.5),
            (edges[0] + edges[1]) * T(0.5),
            (edges[1] + edges[2]) * T(0.5),
            edges[2]};
        const T tau_A = std::max(dcf_tau_A, T(1e-3));
        const T tau_S = std::max(dcf_tau_S, T(1e-3));
        const T momentum = std::clamp(dcf_momentum, T(0), T(0.999));
        const int export_version = (dcf_version >= 0 && dcf_version <= 4) ? dcf_version : 0;
        const T beta = std::max(T(0), dcf_beta);
        const T v4_base_beta = std::max(T(0), dcf_v4_base_beta);
        const T v4_beta = dcf_v4_effective_beta(
            diagnostics_step_id,
            v4_base_beta,
            dcf_v4_decay_start_step,
            dcf_v4_decay_end_step);

        const char* export_version_name = "v1";
        switch (export_version) {
            case 1:
                export_version_name = "v3a";
                break;
            case 2:
                export_version_name = "v3b";
                break;
            case 3:
                export_version_name = "v3c";
                break;
            case 4:
                export_version_name = "v4";
                break;
            default:
                break;
        }

        dreamplacePrint(kINFO, "dcf export utility variant %s (beta=%f, v4_beta=%f, step=%d)\n",
            export_version_name,
            static_cast<double>(beta),
            static_cast<double>(v4_beta),
            diagnostics_step_id);

        const auto endpoints = timer.report_negative_endpoints(ot::MAX);
        const size_t num_pins = timer.num_pins();
        const size_t num_arcs = timer.num_arcs();

        std::vector<dcf_hist_type<T>> node_mass(2 * num_pins, make_zero_dcf_hist<T>());
        std::vector<dcf_hist_type<T>> arc_hist(num_arcs, make_zero_dcf_hist<T>());

        int failing_endpoints = 0;
        for (const auto& [pin_name, rf, slack] : endpoints) {
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
        for (const auto& [name, pin] : timer.pins()) {
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
            dreamplacePrint(kWARN, "dcf encountered %zu pins outside reverse topological order; appended by arrival\n", leftovers.size());
        }

        struct StateRow {
            int pin_id;
            int rf;
            int candidate_count;
            T node_mass_total;
            T max_prob;
            T top1_prob;
            T top3_prob_sum;
            T attribution_entropy;
            T outgoing_mass_total;
            T incoming_mass_total;
        };
        std::vector<StateRow> state_rows;
        if (collect_state) {
            state_rows.reserve(num_pins);
        }

        for (const ot::Pin* pin : reverse_order) {
            for (const auto rf : {ot::RISE, ot::FALL}) {
                auto& q_v = node_mass[dcf_state_index<T>(pin->idx(), rf, num_pins)];
                const T incoming_mass = dcf_hist_mass(q_v);
                if (incoming_mass <= 0) {
                    continue;
                }
                int output_pin_id = -1;
                if (collect_state) {
                    auto output_pin_itr = pin_name2id_map.find(pin->name());
                    if (output_pin_itr != pin_name2id_map.end()) {
                        output_pin_id = output_pin_itr->second;
                    }
                }

                auto v_at = pin->at(ot::MAX, rf);
                auto v_rat = pin->rat(ot::MAX, rf);
                if (!v_at || !v_rat) {
                    if (collect_state && output_pin_id >= 0) {
                        state_rows.push_back({
                            output_pin_id,
                            rf == ot::FALL ? 1 : 0,
                            0,
                            incoming_mass,
                            T(0),
                            T(0),
                            T(0),
                            T(0),
                            T(0),
                            incoming_mass,
                        });
                    }
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
                    if (collect_state && output_pin_id >= 0) {
                        state_rows.push_back({
                            output_pin_id,
                            rf == ot::FALL ? 1 : 0,
                            0,
                            incoming_mass,
                            T(0),
                            T(0),
                            T(0),
                            T(0),
                            T(0),
                            incoming_mass,
                        });
                    }
                    continue;
                }

                if (collect_state && output_pin_id >= 0) {
                    std::vector<T> probs;
                    probs.reserve(candidates.size());
                    T max_prob = T(0);
                    T entropy = T(0);
                    for (const auto& candidate : candidates) {
                        const T prob = candidate.score / denom;
                        probs.push_back(prob);
                        max_prob = std::max(max_prob, prob);
                        if (prob > 0) {
                            entropy -= prob * std::log(prob);
                        }
                    }
                    std::sort(probs.begin(), probs.end(), std::greater<T>());
                    T top3_prob_sum = T(0);
                    for (size_t i = 0; i < std::min<size_t>(3, probs.size()); ++i) {
                        top3_prob_sum += probs[i];
                    }
                    state_rows.push_back({
                        output_pin_id,
                        rf == ot::FALL ? 1 : 0,
                        static_cast<int>(candidates.size()),
                        incoming_mass,
                        max_prob,
                        max_prob,
                        top3_prob_sum,
                        entropy,
                        incoming_mass,
                        incoming_mass,
                    });
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
        std::vector<std::tuple<T, int, int>> top_pairs;
        top_pairs.reserve(num_arcs);
        std::vector<int> all_pair_src_ids;
        std::vector<int> all_pair_dst_ids;
        std::vector<T> all_pair_hist_flat;
        std::vector<T> all_pair_metrics_flat;
        if (collect_heavy) {
            all_pair_src_ids.reserve(num_arcs);
            all_pair_dst_ids.reserve(num_arcs);
            all_pair_hist_flat.reserve(num_arcs * 4);
            all_pair_metrics_flat.reserve(num_arcs * 7);
        }

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
            const T total_mass = mass;
            const T severity_mass = dcf_hist_weighted_sum(hist, representatives);
            const T tail_mass = hist[2] + hist[3];
            const T eta = dcf_pair_length(
                pos,
                num_nodes,
                pin2node_map,
                pin_offset_x,
                pin_offset_y,
                from_pin_id,
                to_pin_id);
            const T utility = dcf_export_utility(
                export_version,
                severity_mass,
                tail_mass,
                total_mass,
                beta,
                v4_beta);
            const T mapped_weight = dcf_map_export_weight(export_version, utility, eta);
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

            if (collect_heavy) {
                all_pair_src_ids.push_back(from_pin_id);
                all_pair_dst_ids.push_back(to_pin_id);
                for (int bin = 0; bin < 4; ++bin) {
                    all_pair_hist_flat.push_back(hist[bin]);
                }
                all_pair_metrics_flat.push_back(mass);
                all_pair_metrics_flat.push_back(severity_mass);
                all_pair_metrics_flat.push_back(tail_mass);
                all_pair_metrics_flat.push_back(utility);
                all_pair_metrics_flat.push_back(eta);
                all_pair_metrics_flat.push_back(mapped_weight);
                all_pair_metrics_flat.push_back(final_weight);
            }
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
            const auto [weight, from_pin_id, to_pin_id] = top_pairs[i];
            const char* from_name = from_pin_id < static_cast<int>(pin_names.size()) ? pin_names[from_pin_id].c_str() : "<unknown>";
            const char* to_name = to_pin_id < static_cast<int>(pin_names.size()) ? pin_names[to_pin_id].c_str() : "<unknown>";
            dreamplacePrint(kINFO, "dcf top pair %zu %s -> %s weight %f\n", i, from_name, to_name, static_cast<double>(weight));
        }
        dreamplacePrint(kINFO, "finish dcf net-weighting (%f s)\n",
            std::chrono::duration_cast<std::chrono::milliseconds>(endT - begT).count() * 0.001);
        diagnostics["dcf_pass_runtime_sec"] =
            std::chrono::duration_cast<std::chrono::milliseconds>(endT - begT).count() * 0.001;
        diagnostics["arcs_with_nonzero_mass"] = pybind11::int_(arcs_with_mass);
        diagnostics["failing_endpoints_injected"] = pybind11::int_(failing_endpoints);

        if (collect_heavy) {
            std::vector<size_t> order(all_pair_src_ids.size());
            for (size_t i = 0; i < order.size(); ++i) {
                order[i] = i;
            }
            std::sort(order.begin(), order.end(), [&](size_t lhs, size_t rhs) {
                return all_pair_metrics_flat[lhs * 7 + 6] > all_pair_metrics_flat[rhs * 7 + 6];
            });
            if (pair_limit > 0 && order.size() > static_cast<size_t>(pair_limit)) {
                order.resize(pair_limit);
            }

            std::vector<int> dump_pair_src_ids;
            std::vector<int> dump_pair_dst_ids;
            std::vector<T> dump_pair_hist_flat;
            std::vector<T> dump_pair_metrics_flat;
            dump_pair_src_ids.reserve(order.size());
            dump_pair_dst_ids.reserve(order.size());
            dump_pair_hist_flat.reserve(order.size() * 4);
            dump_pair_metrics_flat.reserve(order.size() * 7);
            for (size_t row_id : order) {
                dump_pair_src_ids.push_back(all_pair_src_ids[row_id]);
                dump_pair_dst_ids.push_back(all_pair_dst_ids[row_id]);
                for (int j = 0; j < 4; ++j) {
                    dump_pair_hist_flat.push_back(all_pair_hist_flat[row_id * 4 + j]);
                }
                for (int j = 0; j < 7; ++j) {
                    dump_pair_metrics_flat.push_back(all_pair_metrics_flat[row_id * 7 + j]);
                }
            }

            diagnostics["dcf_pair_src_ids"] = dcf_tensor_from_int_vector(dump_pair_src_ids);
            diagnostics["dcf_pair_dst_ids"] = dcf_tensor_from_int_vector(dump_pair_dst_ids);
            diagnostics["dcf_pair_hist"] = dcf_tensor_from_flat_vector(dump_pair_hist_flat, 4);
            diagnostics["dcf_pair_metrics"] = dcf_tensor_from_flat_vector(dump_pair_metrics_flat, 7);
            diagnostics["dcf_all_pair_metrics"] = dcf_tensor_from_flat_vector(all_pair_metrics_flat, 7);
            diagnostics["dcf_exported_pairs_before_limit"] = pybind11::int_(exported_pairs);
            diagnostics["dcf_dumped_pair_count"] = pybind11::int_(dump_pair_src_ids.size());
        }

        if (collect_state) {
            std::vector<int> state_pin_ids;
            std::vector<int> state_rf_values;
            std::vector<int> state_candidate_counts;
            std::vector<T> state_metrics_flat;
            state_pin_ids.reserve(state_rows.size());
            state_rf_values.reserve(state_rows.size());
            state_candidate_counts.reserve(state_rows.size());
            state_metrics_flat.reserve(state_rows.size() * 7);
            for (const auto& row : state_rows) {
                state_pin_ids.push_back(row.pin_id);
                state_rf_values.push_back(row.rf);
                state_candidate_counts.push_back(row.candidate_count);
                state_metrics_flat.push_back(row.node_mass_total);
                state_metrics_flat.push_back(row.max_prob);
                state_metrics_flat.push_back(row.top1_prob);
                state_metrics_flat.push_back(row.top3_prob_sum);
                state_metrics_flat.push_back(row.attribution_entropy);
                state_metrics_flat.push_back(row.outgoing_mass_total);
                state_metrics_flat.push_back(row.incoming_mass_total);
            }
            diagnostics["dcf_state_pin_ids"] = dcf_tensor_from_int_vector(state_pin_ids);
            diagnostics["dcf_state_rf"] = dcf_tensor_from_int_vector(state_rf_values);
            diagnostics["dcf_state_candidate_counts"] = dcf_tensor_from_int_vector(state_candidate_counts);
            diagnostics["dcf_state_metrics"] = dcf_tensor_from_flat_vector(state_metrics_flat, 7);
        }

        return diagnostics;
    }
};

template <typename T>
struct NetWeighting<T, NetWeightingScheme::DCF_HYBRID> {
    DEFINE_APPLY_SCHEME {
        pybind11::dict diagnostics;
        diagnostics["scheme_name"] = pybind11::str("dcf_hybrid");
        diagnostics["diagnostics_step_id"] = diagnostics_step_id;
        if (!enable_dcf) {
            dreamplacePrint(kWARN, "dcf_hybrid scheme selected but enable_dcf is disabled; skip update\n");
            return diagnostics;
        }

        const T hybrid_lambda = std::clamp(dcf_hybrid_lambda, T(0), T(1));
        dreamplacePrint(kINFO, "apply dcf hybrid net-weighting scheme (lambda=%f)\n", static_cast<double>(hybrid_lambda));
        auto begT = std::chrono::steady_clock::now();
        const bool collect_hybrid_debug = dcf_hybrid_debug;

        int num_unique_pairs = 0;
        int num_all_pairs = 0;
        update_pin2pin_weight_dict<T>(
            timer,
            pin_name2id_map,
            pin2pin_base_net_weight,
            pin2pin_max_weight,
            pin2pin_min_weight,
            pin2pin_accumulate_weight,
            num_unique_pairs,
            num_all_pairs);

        const std::array<T, 3> edges = {
            dcf_bin_edges[0], dcf_bin_edges[1], dcf_bin_edges[2]};
        const T tau_A = std::max(dcf_tau_A, T(1e-3));
        const T tau_S = std::max(dcf_tau_S, T(1e-3));

        const auto endpoints = timer.report_negative_endpoints(ot::MAX);
        const size_t num_pins = timer.num_pins();
        const size_t num_arcs = timer.num_arcs();

        std::vector<dcf_hist_type<T>> node_mass(2 * num_pins, make_zero_dcf_hist<T>());
        std::vector<dcf_hist_type<T>> arc_hist(num_arcs, make_zero_dcf_hist<T>());
        int failing_endpoints = 0;
        for (const auto& [pin_name, rf, slack] : endpoints) {
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
        for (const auto& [name, pin] : timer.pins()) {
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
        }

        for (const ot::Pin* pin : reverse_order) {
            for (const auto rf : {ot::RISE, ot::FALL}) {
                auto& q_v = node_mass[dcf_state_index<T>(pin->idx(), rf, num_pins)];
                const T incoming_mass = dcf_hist_mass(q_v);
                if (incoming_mass <= 0) {
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

        std::unordered_map<std::pair<int, int>, T, pair_hash, pair_equal> pair_mass;
        T max_pair_mass = T(0);
        T total_mhat_mass = T(0);
        size_t arcs_with_mass = 0;
        size_t mapped_pairs = 0;
        std::vector<std::tuple<T, int, int>> top_mhat_pairs;
        if (collect_hybrid_debug) {
            top_mhat_pairs.reserve(num_arcs);
        }
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
            const auto key = pybind11::make_tuple(from_itr->second, to_itr->second);
            if (!pin2pin_base_net_weight.contains(key)) {
                continue;
            }
            pair_mass[{from_itr->second, to_itr->second}] = mass;
            max_pair_mass = std::max(max_pair_mass, mass);
            total_mhat_mass += mass;
            ++mapped_pairs;
            if (collect_hybrid_debug) {
                top_mhat_pairs.emplace_back(mass, from_itr->second, to_itr->second);
            }
        }

        pin2pin_net_weight.attr("clear")();
        size_t exported_pairs = 0;
        size_t hybrid_reweighted_pairs = 0;
        T total_weight_mass = 0;
        for (auto item : pin2pin_base_net_weight) {
            auto key = item.first.cast<pybind11::tuple>();
            const int from_pin_id = key[0].cast<int>();
            const int to_pin_id = key[1].cast<int>();
            const auto pair_key = std::make_pair(from_pin_id, to_pin_id);
            const T base_weight = item.second.cast<T>();
            T m_hat = T(0);
            auto mass_itr = pair_mass.find(pair_key);
            if (mass_itr != pair_mass.end() && max_pair_mass > 0) {
                m_hat = std::clamp(mass_itr->second / max_pair_mass, T(0), T(1));
                ++hybrid_reweighted_pairs;
            }
            const T hybrid_weight = base_weight * (T(1) + hybrid_lambda * m_hat);
            if (!std::isfinite(hybrid_weight) || hybrid_weight <= 0) {
                continue;
            }
            pin2pin_net_weight[pybind11::make_tuple(from_pin_id, to_pin_id)] = hybrid_weight;
            ++exported_pairs;
            total_weight_mass += hybrid_weight;
        }

        auto endT = std::chrono::steady_clock::now();
        dreamplacePrint(kINFO, "hybrid arcs with nonzero mass %zu\n", arcs_with_mass);
        dreamplacePrint(kINFO, "hybrid exported pin pairs %zu\n", exported_pairs);
        dreamplacePrint(kINFO, "hybrid reweighted pairs %zu\n", hybrid_reweighted_pairs);
        dreamplacePrint(kINFO, "hybrid total exported weight mass %f\n", static_cast<double>(total_weight_mass));
        dreamplacePrint(kINFO, "finish dcf hybrid net-weighting (%f s)\n",
            std::chrono::duration_cast<std::chrono::milliseconds>(endT - begT).count() * 0.001);

        diagnostics["dcf_pass_runtime_sec"] =
            std::chrono::duration_cast<std::chrono::milliseconds>(endT - begT).count() * 0.001;
        diagnostics["arcs_with_nonzero_mass"] = pybind11::int_(arcs_with_mass);
        diagnostics["failing_endpoints_injected"] = pybind11::int_(failing_endpoints);
        diagnostics["hybrid_lambda"] = pybind11::float_(hybrid_lambda);
        diagnostics["hybrid_max_pair_mass"] = pybind11::float_(max_pair_mass);
        diagnostics["hybrid_reweighted_pairs"] = pybind11::int_(hybrid_reweighted_pairs);
        diagnostics["hybrid_exported_pairs"] = pybind11::int_(exported_pairs);
        diagnostics["hybrid_mhat_pair_count"] = pybind11::int_(mapped_pairs);
        diagnostics["hybrid_mhat_total_mass"] = pybind11::float_(total_mhat_mass);
        if (collect_hybrid_debug) {
            std::sort(top_mhat_pairs.begin(), top_mhat_pairs.end(), [](const auto& lhs, const auto& rhs) {
                return std::get<0>(lhs) > std::get<0>(rhs);
            });
            if (top_mhat_pairs.size() > 10) {
                top_mhat_pairs.resize(10);
            }
            std::vector<int> src_ids;
            std::vector<int> dst_ids;
            std::vector<T> mhat_values;
            src_ids.reserve(top_mhat_pairs.size());
            dst_ids.reserve(top_mhat_pairs.size());
            mhat_values.reserve(top_mhat_pairs.size());
            for (const auto& [mass, src, dst] : top_mhat_pairs) {
                src_ids.push_back(src);
                dst_ids.push_back(dst);
                mhat_values.push_back(max_pair_mass > 0 ? mass / max_pair_mass : T(0));
            }
            diagnostics["hybrid_mhat_src_ids"] = dcf_tensor_from_int_vector(src_ids);
            diagnostics["hybrid_mhat_dst_ids"] = dcf_tensor_from_int_vector(dst_ids);
            diagnostics["hybrid_mhat_values"] = dcf_tensor_from_vector(mhat_values);
        }
        return diagnostics;
    }
};

#undef DEFINE_APPLY_SCHEME

DREAMPLACE_END_NAMESPACE

#endif // DREAMPLACE_NET_WEIGHTING_SCHEME_H_
