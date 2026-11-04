/* SPDX-License-Identifier: Apache-2.0 */
#ifndef EDGE_WALKER_UART_DIAG_H
#define EDGE_WALKER_UART_DIAG_H
#include <stdint.h>
/* Private, read-only UART ioctl. Include sys/ioctl.h before using the code. */
#define EW_UART_RX_DIAG _TIOC(0x00f0)
typedef struct {
  uint32_t dma_bytes;
  uint32_t dma_events;
  uint32_t dropped;
  uint32_t overruns;
  uint32_t frame_errors;
  uint32_t noise_errors;
  uint32_t irq_bytes;
  uint32_t rx_dma_enabled;
} ew_uart_rx_diag_t;
#endif
