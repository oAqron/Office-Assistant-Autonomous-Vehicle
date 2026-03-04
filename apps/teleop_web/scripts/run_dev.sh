#!/usr/bin/env bash
# run_dev.sh – Start vehicle_web_teleop in development mode.
#
# Usage:
#   bash vehicle_web_teleop/scripts/run_dev.sh
#
# Override any variable by exporting it before running, e.g.:
#   VWT_SERIAL_PORT=/dev/ttyTHS0 bash scripts/run_dev.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PKG_DIR="${REPO_ROOT}/vehicle_web_teleop"

# ── Default configuration ──────────────────────────────────────────────────
# Defaults match the existing keyboard teleop script exactly.
export VWT_SERIAL_PORT="${VWT_SERIAL_PORT:-/dev/ttyTHS1}"
export VWT_BAUD="${VWT_BAUD:-115200}"
export VWT_HOST="${VWT_HOST:-0.0.0.0}"
export VWT_PORT="${VWT_PORT:-8080}"
export VWT_DEADMAN_MS="${VWT_DEADMAN_MS:-500}"
export VWT_VX_SCALE="${VWT_VX_SCALE:-100}"    # 1.0 * g * 100 at g=1
export VWT_VY_SCALE="${VWT_VY_SCALE:-100}"    # 1.0 * g * 100 at g=1
export VWT_VZ_SCALE="${VWT_VZ_SCALE:-500}"    # 5.0 * g * 100 at g=1
export VWT_HB_TIMEOUT_S="${VWT_HB_TIMEOUT_S:-5.0}"

echo "────────────────────────────────────────────"
echo "  Vehicle Web Teleop – dev server"
echo "────────────────────────────────────────────"
echo "  Serial port : ${VWT_SERIAL_PORT} @ ${VWT_BAUD} bps"
echo "  Listen      : http://${VWT_HOST}:${VWT_PORT}"
echo "  Deadman     : ${VWT_DEADMAN_MS} ms"
echo "  Scales      : vx=${VWT_VX_SCALE}  vy=${VWT_VY_SCALE}  vz=${VWT_VZ_SCALE}"
echo "────────────────────────────────────────────"

# ── Install package in editable mode if not already installed ──────────────
if ! python3 -c "import vehicle_web_teleop" 2>/dev/null; then
  echo "[setup] Installing vehicle_web_teleop in editable mode…"
  pip install -e "${PKG_DIR}" --quiet
fi

# ── Launch ────────────────────────────────────────────────────────────────
exec python3 -m vehicle_web_teleop.main
