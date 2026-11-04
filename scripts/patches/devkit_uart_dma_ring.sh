#!/usr/bin/env bash
# Apply UART IDLE ordering and circular producer-index boundary guards.
set -euo pipefail
root="${1:?openvela workspace required}"
contest="${CONTEST:-$(cd "$(dirname "$0")/../.." && pwd)}"
overlay="$contest/board_overlay/sf32lb52_devkit_lcd/patches"
vendor="$root/vendor/sifli"
patch_file="$overlay/uart_dma_rx_ring.patch"
if git -C "$vendor" apply --reverse --check "$patch_file" >/dev/null 2>&1; then
  echo 'UART RX boundary patch already applied'
else
  git -C "$vendor" apply --check "$patch_file"
  git -C "$vendor" apply "$patch_file"
fi
cp "$contest/app/edge_walker/ew_uart_diag.h" "$vendor/chips/sf32lb52/ew_uart_diag.h"
