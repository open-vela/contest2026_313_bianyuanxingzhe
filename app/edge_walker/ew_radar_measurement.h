/* SPDX-License-Identifier: Apache-2.0 */
#ifndef EDGE_WALKER_RADAR_MEASUREMENT_H
#define EDGE_WALKER_RADAR_MEASUREMENT_H

#include "ew_safety.h"
#include <math.h>
#include <stdio.h>
#include <string.h>

typedef enum {
  EW_MEASUREMENT_WAIT, EW_MEASUREMENT_EMPTY, EW_MEASUREMENT_TARGET,
  EW_MEASUREMENT_STALE, EW_MEASUREMENT_ERROR
} ew_measurement_state_t;

/* Link health and held alert metadata cannot establish measurement freshness.
 * Empty frames and filtered targets are real observations in their own right. */
static inline ew_measurement_state_t ew_measurement_state(
    const ew_safety_snapshot_t *s, uint32_t now)
{
  if (!s->running || s->radar_error != 0) return EW_MEASUREMENT_ERROR;
  if (!s->ever_frame) return EW_MEASUREMENT_WAIT;
  if ((uint32_t)(now - s->observation_ms) > EW_LINK_STALE_MS)
    return EW_MEASUREMENT_STALE;
  return s->observation.has_target ? EW_MEASUREMENT_TARGET : EW_MEASUREMENT_EMPTY;
}

static inline const char *ew_measurement_reason(const char *reason)
{
  if (reason == NULL) return "NO TARGET";
  if (!strcmp(reason, "radar_alarm_direction")) return "FALLBACK: DIR";
  if (!strcmp(reason, "radar_alarm_speed")) return "FALLBACK: SPEED";
  if (!strcmp(reason, "radar_alarm_snr")) return "FALLBACK: SNR";
  if (!strcmp(reason, "radar_alarm_out_of_threshold")) return "FALLBACK: RANGE/TTC";
  if (!strcmp(reason, "not_approaching")) return "FILTER: DIR";
  if (!strcmp(reason, "below_min_speed")) return "FILTER: SPEED";
  if (!strcmp(reason, "below_min_snr")) return "FILTER: SNR";
  if (!strcmp(reason, "out_of_threshold")) return "OUTSIDE RANGE/TTC";
  if (!strcmp(reason, "emergency_range_or_ttc") ||
      !strcmp(reason, "strong_range_or_ttc") ||
      !strcmp(reason, "soft_range_or_ttc")) return "RANGE/TTC";
  return "INVALID TARGET";
}

/* Pure, bounded LCD text. Values describe the latest frame, not the held level.
 * APPROACH/AWAY are the configured interpretation; DIR exposes the raw byte. */
static inline void ew_measurement_text_for_display(char *out, size_t capacity,
    const ew_safety_snapshot_t *s, uint32_t now, ew_alert_level_t displayed_level)
{
  ew_measurement_state_t state = ew_measurement_state(s, now);
  const ew_track_t *t = &s->observation.track;
  uint32_t age = (uint32_t)(now - s->observation_ms);
  char ttc[24] = "--";
  if (state != EW_MEASUREMENT_TARGET) {
    const char *status = state == EW_MEASUREMENT_ERROR ? "RADAR ERROR" :
                         state == EW_MEASUREMENT_WAIT ? "WAITING FRAME" :
                         state == EW_MEASUREMENT_STALE ? "STALE FRAME" : "NO TARGET";
    if (s->ever_frame)
      snprintf(out, capacity, "V -- km/h\nR -- m   TTC -- s\n%s\nALARM %s\nFRAME AGE %lu ms",
               status, ew_alert_level_name(displayed_level), (unsigned long)age);
    else
      snprintf(out, capacity, "V -- km/h\nR -- m   TTC -- s\n%s\nALARM %s",
               status, ew_alert_level_name(displayed_level));
    return;
  }
  if (t->approaching && t->speed_kmh > 0.0f &&
      isfinite(s->observation_decision.ttc_s) &&
      s->observation_decision.ttc_s >= 0.0f)
    snprintf(ttc, sizeof(ttc), "%.2f", (double)s->observation_decision.ttc_s);
  snprintf(out, capacity,
      "V %.0f km/h  %s\nR %.0f m   TTC %s s\n"
      "DIR %u  SNR %.0f  A%u  T%u/%u\nLAST FRAME %s  %s\nALARM %s\nFRAME AGE %lu ms",
      (double)t->speed_kmh, t->approaching ? "APPROACH" : "AWAY",
      (double)t->range_m, ttc, (unsigned)s->observation.raw_dir,
      (double)t->snr, t->radar_alarm ? 1u : 0u,
      (unsigned)s->observation.target_index + 1u,
      (unsigned)s->observation.target_count,
      ew_alert_level_name(s->observation_decision.level),
      ew_measurement_reason(s->observation_decision.reason),
      ew_alert_level_name(displayed_level), (unsigned long)age);
}

/* Non-LCD callers have the radar's held level, while the LCD also accounts
 * for explicitly active manual tests when it supplies displayed_level. */
static inline void ew_measurement_text(char *out, size_t capacity,
    const ew_safety_snapshot_t *s, uint32_t now)
{
  ew_measurement_text_for_display(out, capacity, s, now, s->decision.level);
}
#endif
