/* SPDX-License-Identifier: Apache-2.0 */
#ifndef EDGE_WALKER_RADAR_VIEW_H
#define EDGE_WALKER_RADAR_VIEW_H
#include "ew_safety.h"
typedef enum {
  EW_RADAR_VIEW_READY, EW_RADAR_VIEW_ALERT, EW_RADAR_VIEW_WAIT,
  EW_RADAR_VIEW_NO_FRAME, EW_RADAR_VIEW_ERROR
} ew_radar_view_t;

/* LD2451 can be silent after the last target. An old observation is not a
 * fresh measurement, but silence alone cannot prove a disconnected module.
 * Preserve raw link/staleness in snapshots; this is only display policy. */
static inline ew_radar_view_t ew_radar_view(const ew_safety_snapshot_t *s,
                                           uint32_t now, uint32_t warmup)
{
  if (!s->running) return EW_RADAR_VIEW_ERROR;
  if (s->decision.level != EW_ALERT_NONE) return EW_RADAR_VIEW_ALERT;
  if (s->radar_error != 0) return EW_RADAR_VIEW_ERROR;
  if (s->decision.link == EW_LINK_NOISE) return EW_RADAR_VIEW_NO_FRAME;
  if (s->decision.link == EW_LINK_DEAD && !s->ever_frame) {
    if (s->ever_bytes) return EW_RADAR_VIEW_NO_FRAME;
    if (!s->ever_bytes && (uint32_t)(now - s->started_ms) < warmup)
      return EW_RADAR_VIEW_WAIT;
    return EW_RADAR_VIEW_ERROR;
  }
  return EW_RADAR_VIEW_READY;
}
#endif
