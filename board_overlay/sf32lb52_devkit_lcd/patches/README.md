# Wi-Fi UART3 RX DMA

## UART receive boundary protection (2026-10-28)

The final `uart_dma_rx_ring.patch` keeps the established UART/DMA transport.
It acknowledges IDLE before publishing DMA bytes, normalizes the producer
head at transfer-complete/circular reload, and drains pending DMA when RX
is re-enabled. It also provides read-only UART diagnostic counters.

Apply with `bash scripts/patches/devkit_uart_dma_ring.sh OPENVELA_ROOT`.
Both build entry points apply it after the existing Wi-Fi DMA patch.
Regression: `python scripts/host/test_uart_rx_stability.py`.

Separate staging-buffer, IRQ-only and asynchronous-TX experiments were not
accepted; their source and failed observations remain only in local output.
The final fix does not alter UART baud rates, pins, alert thresholds or the
1500ms raw data-staleness threshold. LD2451 quiet-idle display semantics are
covered separately by `test_radar_view.py`.

The 2026-09-18 board test measured 12 UART3 hardware overruns during boot
queries with interrupt-driven RX. Frame and noise counters remained zero.
With RX DMA enabled and the attached patch, boot and status queries reported
zero overruns and complete ESP-AT responses.

Apply `wifi_uart_dma.patch` from the `vendor/sifli` directory. It is relative
to the project's existing modified UART driver, not a pristine upstream tree.
Run `git apply --check` before applying; never replace unrelated driver fixes.

Enable `CONFIG_BSP_UART3_RX_USING_DMA=y` in the actual board/build config.
Reconfigure CMake after changing `.config`, then run Ninja. Verify that
`include/nuttx/config.h` defines this option; editing `.config` alone does not
regenerate that header in the current build setup.

UART3 RX uses DMA1 Channel 8. Check SPI2 TX, I2S RX and audio DMA assignments
before enabling those peripherals. They are not enabled in the tested build.

The ISR must not call `uart_recvchars()` on a DMA RX port: DMA owns RDR and
updates the serial buffer. The patch also reports cumulative UART3 overrun,
frame and noise counters on close, outside the ISR.

Keep the `ew_mirror.c` in-place snapshot change: the former 351000-byte static
scratch buffer left only about 7 KB of SRAM in the fully linked ALLSYMS image.
The tested DMA image uses 165900 bytes (31.64%) of SRAM.

Verification:

- `python scripts/host/test_wifi_scan_parser.py`
- `python scripts/host/test_mirror_downscale.py`
- Build the full final image, flash with `--verify`, wait for `EW READY`.
- Run `@status`, then `@scan`; check complete replies and zero UART errors.
- Verify the idle screen and a full-resolution `@mirror snap`.

Artifacts for this run are in `VMware_share/artifacts`: `nuttx_wifi_dma.bin`,
`build_wifi_dma.log`, `flash_wifi_dma_retry.log`, and timestamped
`wifi_scan_capture_20260918_*` logs. Pura hotspot visibility still requires
testing with that hotspot enabled and its exact SSID known.
