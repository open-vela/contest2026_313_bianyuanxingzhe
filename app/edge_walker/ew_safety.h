/* SPDX-License-Identifier: Apache-2.0 */
#ifndef EDGE_WALKER_SAFETY_H
#define EDGE_WALKER_SAFETY_H

#include "ew_ld2451.h"

typedef struct {
  ew_decision_t decision;
  ew_sniff_stats_t sniff;
  unsigned long event_id;
  uint32_t updated_ms;
  uint32_t started_ms;
  uint32_t dropped_events;
  int radar_error;
  bool running;
  bool ever_bytes;
  bool ever_frame;
  /* Latest complete sensor frame, independent of the held alert. Filtered
   * targets remain visible here; an empty frame clears has_target. The time
   * is UART receipt time, never the periodically refreshed updated_ms. */
  ew_radar_observation_t observation;
  ew_decision_t observation_decision;
  uint32_t observation_ms;
  /* Bounded diagnostics copied by the existing UART owner, never a reader. */
  uint8_t sample[64];
  unsigned sample_bytes;
  uint32_t sample_total;
  uint32_t read_calls;
  uint32_t read_max_gap_ms;
} ew_safety_snapshot_t;

typedef struct {
  ew_decision_t decision;
  unsigned long event_id;
} ew_safety_event_t;

/* Owns the radar UART, parser, Hold and buzzer floor independently of pages,
 * Wi-Fi, LLM, mirror transport and Agent/IPC delivery. No LVGL in this task. */
int ew_safety_start(void);
void ew_safety_snapshot(ew_safety_snapshot_t *out);
bool ew_safety_take_event(ew_safety_event_t *out);

/* Opt-in bounded UART evidence, copied by the sole reader; no console I/O
 * on the safety worker. Empty records preserve Hold/link timeout timing.
 * A sequence gap or dropped>0 invalidates a lossless replay claim. */
typedef struct {
  uint32_t seq;
  uint32_t timestamp_ms;
  unsigned size;
  uint8_t bytes[64];
} ew_road_record_t;
void ew_safety_road_enable(bool enabled);
bool ew_safety_road_take(ew_road_record_t *out);
void ew_safety_road_status(bool *enabled, uint32_t *dropped, unsigned *pending);

#endif
