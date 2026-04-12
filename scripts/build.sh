#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(git rev-parse --show-toplevel)
BUILD_DIR=${BUILD_DIR:-"$ROOT_DIR/build"}
INSTALL_DIR=${INSTALL_DIR:-"$ROOT_DIR/install"}
VENV_PYTHON=${VENV_PYTHON:-"$ROOT_DIR/.venv/bin/python"}
BUILD_JOBS=${BUILD_JOBS:-$(nproc)}
REPO_CUB_DIR=${REPO_CUB_DIR:-"$ROOT_DIR/thirdparty/cub"}

if [ ! -x "$VENV_PYTHON" ]; then
  printf 'Expected Python environment at %s. Run scripts/setup_env.sh first.\n' "$VENV_PYTHON" >&2
  exit 1
fi

if [ ! -e "$ROOT_DIR/benchmarks/iccad2015.ot" ]; then
  printf 'Missing benchmark payload at %s/benchmarks/iccad2015.ot\n' "$ROOT_DIR" >&2
  exit 1
fi

mkdir -p "$INSTALL_DIR/benchmarks"
ln -sfn "$ROOT_DIR/benchmarks/iccad2015.ot" "$INSTALL_DIR/benchmarks/iccad2015.ot"

TORCH_CXX_ABI=$(
  "$VENV_PYTHON" -c 'import torch; print(int(getattr(torch._C, "_GLIBCXX_USE_CXX11_ABI", 1)))'
)

RAW_CUDA_CAPABILITY=${CMAKE_CUDA_ARCHITECTURES:-}
if [ -z "$RAW_CUDA_CAPABILITY" ]; then
  RAW_CUDA_CAPABILITY=$(
    "$VENV_PYTHON" -c 'import torch; print("".join(map(str, torch.cuda.get_device_capability(0))) if torch.cuda.is_available() else "")'
  )
fi

CUDA_ARCHITECTURES=$RAW_CUDA_CAPABILITY
if [ "$RAW_CUDA_CAPABILITY" = "89" ]; then
  # This repo still builds through FindCUDA, and the CMake helper shipped on
  # this machine does not recognize Ada's 8.9 identifier. 8.6 is the closest
  # supported architecture in that legacy helper.
  CUDA_ARCHITECTURES=8.6
fi

if [ -z "$CUDA_ARCHITECTURES" ]; then
  printf 'Could not determine a CUDA architecture from torch.\n' >&2
  exit 1
fi

"$VENV_PYTHON" -c 'import sys; import torch; device = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "none"; print(f"torch={torch.__version__}"); print(f"torch_cuda={torch.version.cuda}"); print(f"cuda_available={int(torch.cuda.is_available())}"); print(f"device={device}"); sys.exit(0 if torch.cuda.is_available() else 1)'

cmake -S "$ROOT_DIR" -B "$BUILD_DIR" \
  -DCMAKE_BUILD_TYPE="${CMAKE_BUILD_TYPE:-Release}" \
  -DCMAKE_INSTALL_PREFIX="$INSTALL_DIR" \
  -DPython_EXECUTABLE="$VENV_PYTHON" \
  -DPYTHON_EXECUTABLE="$VENV_PYTHON" \
  -DCMAKE_CXX_ABI="$TORCH_CXX_ABI" \
  -DDREAMPLACE_BUILD_DETAILED_PLACE_OPS=OFF \
  -DDREAMPLACE_BUILD_ROUTABILITY_OPS=OFF \
  -DCUB_DIR="$REPO_CUB_DIR" \
  -DCMAKE_CUDA_ARCHITECTURES="$CUDA_ARCHITECTURES"

cmake --build "$BUILD_DIR" --parallel "$BUILD_JOBS"
cmake --install "$BUILD_DIR"

if [ ! -f "$INSTALL_DIR/dreamplace/configure.py" ]; then
  printf 'Install appears incomplete: missing %s/dreamplace/configure.py\n' "$INSTALL_DIR" >&2
  exit 1
fi
