/**
 * File              : utils_cub.cuh
 * Author            : Yibo Lin <yibolin@pku.edu.cn>
 * Date              : 06.25.2021
 * Last Modified Date: 06.25.2021
 * Last Modified By  : Yibo Lin <yibolin@pku.edu.cn>
 */

#ifndef _DREAMPLACE_UTILITY_UTILS_CUB_CUH
#define _DREAMPLACE_UTILITY_UTILS_CUB_CUH

#include "utility/src/namespace.h"

// include cub in a safe manner. This codebase relies on wrapping CUB inside
// DREAMPLACE_NAMESPACE, which is compatible with the vendored CUB snapshot but
// not with the newer CUB bundled in recent CUDA toolkits.
#define CUB_NS_PREFIX namespace DREAMPLACE_NAMESPACE {
#define CUB_NS_POSTFIX }
#define CUB_NS_QUALIFIER DREAMPLACE_NAMESPACE::cub
#include "../../../../thirdparty/cub/cub/cub.cuh"
#undef CUB_NS_QUALIFIER
#undef CUB_NS_POSTFIX
#undef CUB_NS_PREFIX

#endif
