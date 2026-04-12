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
  ADAMS, LILITH, PIN2PIN, DCF
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
  static void apply(                                               \
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
      return;
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
struct NetWeighting<T, NetWeightingScheme::PIN2PIN> {
    DEFINE_APPLY_SCHEME {
        // Apply net-weighting scheme.
        dreamplacePrint(kINFO, "apply pin2pin net-weighting scheme...\n");
        // Calculate run-time of net-weighting update.
        auto begT = std::chrono::steady_clock::now();

        dreamplacePrint(kINFO, "extracting paths...\n");
        std::optional<long unsigned int> optionalValue = timer.report_fep();
        int nvp = 0;
        nvp = *optionalValue;
        const auto& paths = timer.report_timing(nvp);
        dreamplacePrint(kINFO, "paths extraction done...\n");
        int num_unique_pairs = 0;
        int num_all_pairs = 0;
        float wns = timer.report_wns().value();

        // #pragma omp parallel for num_threads(52)
        for (int path_idx = 0; path_idx < paths.size(); ++path_idx) {
            const auto& path = paths[path_idx];
            bool first = true;
            int last_id = -1;
            
            std::string last_node_name;
            for (const auto& point : path) {
                std::string name = point.pin.name();

                // Check if `point.pin.gate()` returned a valid pointer
                auto gate = point.pin.gate();
                std::string node_name;

                if (!gate) {
                    node_name = "NO_GATE";
                } else {
                    node_name = gate->name();
                }

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
                          if (pin2pin_net_weight.contains(key)) {
                            {
                              num_all_pairs += 1;
                              pin2pin_net_weight[key] = pin2pin_net_weight[key].cast<float>() + pin2pin_accumulate_weight * path.slack / wns;
                              if (pin2pin_net_weight[key].cast<float>() > pin2pin_max_weight){
                                pin2pin_net_weight[key] = pin2pin_max_weight;
                              }
                            }
                          }
                          else{
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
        dreamplacePrint(kINFO, "finish net-weighting (%f s)\n",
            std::chrono::duration_cast<std::chrono::milliseconds>(
                endT - begT).count() * 0.001);
        dreamplacePrint(kINFO, "all num %i \n", num_all_pairs);
        dreamplacePrint(kINFO, "unique num %i \n", num_unique_pairs);
      }
};

template <typename T>
struct NetWeighting<T, NetWeightingScheme::DCF> {
    DEFINE_APPLY_SCHEME {
        if (!enable_dcf) {
            dreamplacePrint(kWARN, "dcf scheme selected but enable_dcf is disabled; skip update\n");
            return;
        }

        dreamplacePrint(kINFO, "apply dcf net-weighting scheme...\n");
        auto begT = std::chrono::steady_clock::now();

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
        std::vector<std::tuple<T, int, int>> top_pairs;
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
            const auto [weight, from_pin_id, to_pin_id] = top_pairs[i];
            const char* from_name = from_pin_id < static_cast<int>(pin_names.size()) ? pin_names[from_pin_id].c_str() : "<unknown>";
            const char* to_name = to_pin_id < static_cast<int>(pin_names.size()) ? pin_names[to_pin_id].c_str() : "<unknown>";
            dreamplacePrint(kINFO, "dcf top pair %zu %s -> %s weight %f\n", i, from_name, to_name, static_cast<double>(weight));
        }
        dreamplacePrint(kINFO, "finish dcf net-weighting (%f s)\n",
            std::chrono::duration_cast<std::chrono::milliseconds>(endT - begT).count() * 0.001);
    }
};

#undef DEFINE_APPLY_SCHEME

DREAMPLACE_END_NAMESPACE

#endif // DREAMPLACE_NET_WEIGHTING_SCHEME_H_
