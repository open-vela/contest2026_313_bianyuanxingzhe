#!/bin/bash
set -u
export PATH="$HOME/bin:$HOME/.local/bin:$HOME/openvela/prebuilts/gcc/linux-x86_64/arm-none-eabi/bin:$HOME/openvela/prebuilts/build-tools/linux-x86_64/bin:$PATH"
cd ~/openvela
LOG=/mnt/hgfs/VMware_share/artifacts/build_ew_main.log
DEF=vendor/sifli/boards/sf32lb52/sf32lb52_devkit_lcd/configs/nsh/defconfig
DEMO=packages/demos/contest2026_313_edge_walker
SRC=contest2026_313_bianyuanxingzhe/app/edge_walker
DMA_PATCH=contest2026_313_bianyuanxingzhe/board_overlay/sf32lb52_devkit_lcd/patches/wifi_uart_dma.patch
DMA_CONFIG=contest2026_313_bianyuanxingzhe/board_overlay/sf32lb52_devkit_lcd/wifi_dma.config

echo "==== TASK_007 edge_walker $(date -Iseconds) ====" | tee "$LOG"

# 0) DevKit-LCD 触摸 I2C 引脚（PA30 SCL / PA31 IRQ）
PATCH_SH=contest2026_313_bianyuanxingzhe/scripts/patches/devkit_lcd_touch_i2c.sh
if [ -f "$PATCH_SH" ]; then
  bash "$PATCH_SH" "$PWD" | tee -a "$LOG"
fi

# 0b) Preserve the independently validated UART3 RX DMA fix on clean builds.
if [ -f "$DMA_PATCH" ]; then
  if git -C vendor/sifli apply --reverse --check "../../$DMA_PATCH" >/dev/null 2>&1; then
    echo "wifi UART DMA patch already applied" | tee -a "$LOG"
  else
    git -C vendor/sifli apply --check "../../$DMA_PATCH" >>"$LOG" 2>&1 || exit $?
    git -C vendor/sifli apply "../../$DMA_PATCH" >>"$LOG" 2>&1 || exit $?
    echo "wifi UART DMA patch applied" | tee -a "$LOG"
  fi
fi
if [ -f "$DMA_CONFIG" ]; then
  while IFS= read -r setting; do
    case "$setting" in
      CONFIG_*=y)
        grep -q "^${setting}$" "$DEF" || echo "$setting" >>"$DEF"
        ;;
    esac
  done <"$DMA_CONFIG"
fi

# 1) sync app + demos symlink
mkdir -p contest2026_313_bianyuanxingzhe/app
if [ ! -d "$SRC" ]; then
  echo "MISSING $SRC" | tee -a "$LOG"
  exit 2
fi
ln -sfn "../../$SRC" "$DEMO"
ls -la "$DEMO" | tee -a "$LOG"

# 2) enable Kconfig in board defconfig
if ! grep -q '^CONFIG_LVX_USE_DEMO_CONTEST2026_313_EDGE_WALKER=y' "$DEF"; then
  echo 'CONFIG_LVX_USE_DEMO_CONTEST2026_313_EDGE_WALKER=y' >>"$DEF"
  echo "defconfig patched" | tee -a "$LOG"
else
  echo "defconfig already has EDGE_WALKER" | tee -a "$LOG"
fi
grep EDGE_WALKER "$DEF" | tee -a "$LOG"

# 2b) 开机前端：整文件写入系统界面（ew boot），覆盖 lvgldemo widgets
OVERLAY=contest2026_313_bianyuanxingzhe/board_overlay/sf32lb52_devkit_lcd/etc/init.d/rcS.user
VETC=vendor/sifli/boards/sf32lb52/sf32lb52_devkit_lcd/src/etc/init.d
mkdir -p "$VETC"
if [ -f "$OVERLAY" ]; then
  # rcS 会当 C 预处理，禁止用 # 注释
  grep -v '^[[:space:]]*#' "$OVERLAY" | sed '/^$/d' >"$VETC/rcS"
  echo "rcS overwritten with overlay (ew boot, no lvgldemo)" | tee -a "$LOG"
  cat "$VETC/rcS" | tee -a "$LOG"
else
  printf 'sleep 2\new boot\n' >"$VETC/rcS"
  echo "rcS written fallback ew boot" | tee -a "$LOG"
fi

# 3) full reconfigure so new demo Kconfig is sourced (symlink must exist first)
rm -f nuttx/.config nuttx/.config.old nuttx/.version
rm -rf cmake_out/sf32lb52_devkit_lcd
cmake -B cmake_out/sf32lb52_devkit_lcd -S "$PWD/nuttx" -GNinja \
  -DBOARD_CONFIG=../vendor/sifli/boards/sf32lb52/sf32lb52_devkit_lcd/configs/nsh \
  -DEXTRA_FLAGS="-Wno-cpp -Wno-deprecated-declarations" >>"$LOG" 2>&1 || exit $?
grep EDGE_WALKER cmake_out/sf32lb52_devkit_lcd/.config | tee -a "$LOG" || exit 3

cmake --build cmake_out/sf32lb52_devkit_lcd >>"$LOG" 2>&1
ec=$?
echo "build_exit=$ec $(date -Iseconds)" | tee -a "$LOG"

if [ -f cmake_out/sf32lb52_devkit_lcd/nuttx.bin ]; then
  cp -f cmake_out/sf32lb52_devkit_lcd/nuttx.bin /mnt/hgfs/VMware_share/artifacts/nuttx.bin
  ls -la cmake_out/sf32lb52_devkit_lcd/nuttx.bin /mnt/hgfs/VMware_share/artifacts/nuttx.bin | tee -a "$LOG"
  strings cmake_out/sf32lb52_devkit_lcd/nuttx.bin | grep -E 'ew |edge_walker|alert_output' | head -5 | tee -a "$LOG" || true
  grep -E 'CONFIG_LVX_USE_DEMO_CONTEST2026_313_EDGE_WALKER' cmake_out/sf32lb52_devkit_lcd/.config | tee -a "$LOG" || true
  echo BUILD_OK | tee -a "$LOG"
fi
exit $ec
