/* SPDX-License-Identifier: Apache-2.0 */
#include "ew_radar_diag.h"
#include "ew_radar_measurement.h"
#include "ew_radar_build.h"

#include <errno.h>
#include <math.h>
#include <stdio.h>

static void measurement_number(char *out, size_t capacity, float value)
{
  if (isfinite(value) && value >= 0.0f && value <= 10000.0f)
    snprintf(out, capacity, "%.2f", (double)value);
}

/* Reasons are policy strings, but keep the JSON boundary safe and bounded. */
static int measurement_reason_json(char *out, const char *reason)
{
  unsigned i, used = 0;
  if (reason == NULL) {
    strcpy(out, "null");
    return 0;
  }
  out[used++] = '"';
  for (i = 0; i < 96u && reason[i] != '\0'; i++) {
    unsigned char c = (unsigned char)reason[i];
    if (c == '"' || c == '\\') {
      out[used++] = '\\';
      out[used++] = (char)c;
    } else if (c < 0x20u) {
      used += (unsigned)snprintf(out + used, 7u, "\\u%04x", c);
    } else {
      out[used++] = (char)c;
    }
  }
  if (i == 96u) return -EINVAL;
  out[used++] = '"';
  out[used] = '\0';
  return 0;
}

int ew_radar_diag_format(char *out, size_t capacity, const char *request_id,
                        const ew_safety_snapshot_t *snapshot)
{
  static const char hex[] = "0123456789abcdef";
  char sample_hex[sizeof(snapshot->sample) * 2u + 1u];
  char range[32] = "null", speed[32] = "null", snr[32] = "null";
  char ttc[32] = "null", raw_dir[8] = "null";
  char target_count[8] = "null", target_index[8] = "null";
  char observed_ms[24] = "null", age_ms[24] = "null";
  char reason[6u * 96u + 3u] = "null";
  const char *frame_level = "null", *alarm = "null", *approaching = "null";
  const char *state_name;
  ew_measurement_state_t state;
  const char *link;
  size_t i;
  int result;

  if (out == NULL || capacity == 0) return -EINVAL;
  out[0] = '\0';
  if (request_id == NULL || snapshot == NULL) return -EINVAL;
  for (i = 0; request_id[i] != '\0'; i++) {
    unsigned char c = (unsigned char)request_id[i];
    if (i >= 48u || !((c >= 'a' && c <= 'z') ||
                      (c >= 'A' && c <= 'Z') ||
                      (c >= '0' && c <= '9') || c == '_' || c == '-')) {
      return -EINVAL;
    }
  }
  if (i == 0 || snapshot->sample_bytes > sizeof(snapshot->sample)) {
    return -EINVAL;
  }
  switch (snapshot->decision.link) {
    case EW_LINK_DEAD: link = "dead"; break;
    case EW_LINK_NOISE: link = "noise"; break;
    case EW_LINK_OK: link = "ok"; break;
    default: return -EINVAL;
  }
  state = ew_measurement_state(snapshot, snapshot->updated_ms);
  state_name = state == EW_MEASUREMENT_ERROR ? "error" :
               state == EW_MEASUREMENT_WAIT ? "wait" :
               state == EW_MEASUREMENT_STALE ? "stale" :
               state == EW_MEASUREMENT_EMPTY ? "empty" : "target";
  /* Timestamp/age describe freshness; all target fields are null without a
   * fresh target, even while an older alert level is still held. */
  if (snapshot->ever_frame && state != EW_MEASUREMENT_ERROR) {
    snprintf(observed_ms, sizeof(observed_ms), "%lu", (unsigned long)snapshot->observation_ms);
    snprintf(age_ms, sizeof(age_ms), "%lu",
             (unsigned long)(uint32_t)(snapshot->updated_ms - snapshot->observation_ms));
  }
  if (state == EW_MEASUREMENT_TARGET) {
    const ew_track_t *track = &snapshot->observation.track;
    if (track->valid) {
      measurement_number(range, sizeof(range), track->range_m);
      measurement_number(speed, sizeof(speed), track->speed_kmh);
      measurement_number(snr, sizeof(snr), track->snr);
      if (track->approaching && track->speed_kmh > 0.0f)
        measurement_number(ttc, sizeof(ttc), snapshot->observation_decision.ttc_s);
      if (snapshot->observation.raw_dir <= 1u)
        snprintf(raw_dir, sizeof(raw_dir), "%u", (unsigned)snapshot->observation.raw_dir);
      if (snapshot->observation.target_count <= EW_LD2451_MAX_TARGETS &&
          snapshot->observation.target_index < snapshot->observation.target_count) {
        snprintf(target_count, sizeof(target_count), "%u", (unsigned)snapshot->observation.target_count);
        snprintf(target_index, sizeof(target_index), "%u", (unsigned)snapshot->observation.target_index);
      }
      alarm = track->radar_alarm ? "true" : "false";
      approaching = track->approaching ? "true" : "false";
      switch (snapshot->observation_decision.level) {
        case EW_ALERT_NONE: frame_level = "\"none\""; break;
        case EW_ALERT_SOFT: frame_level = "\"soft\""; break;
        case EW_ALERT_STRONG: frame_level = "\"strong\""; break;
        case EW_ALERT_EMERGENCY: frame_level = "\"emergency\""; break;
        default: return -EINVAL;
      }
      if (measurement_reason_json(reason, snapshot->observation_decision.reason) != 0)
        return -EINVAL;
    }
  }
  for (i = 0; i < snapshot->sample_bytes; i++) {
    sample_hex[i * 2u] = hex[snapshot->sample[i] >> 4];
    sample_hex[i * 2u + 1u] = hex[snapshot->sample[i] & 0x0fu];
  }
  sample_hex[snapshot->sample_bytes * 2u] = '\0';
  if (capacity > EW_RADAR_DIAG_MAX_BYTES) capacity = EW_RADAR_DIAG_MAX_BYTES;
  result = snprintf(out, capacity,
      "{\"v\":1,\"id\":\"%s\",\"origin\":\"device\","
      "\"build\":\"" EW_RADAR_BUILD_ID "\",\"direction_approach\":%u,"
      "\"port\":\"/dev/ttyS1\",\"clock\":\"device_monotonic\","
      "\"running\":%s,\"ever_bytes\":%s,\"ever_frame\":%s,"
      "\"started_ms\":%lu,\"updated_ms\":%lu,\"radar_error\":%d,"
      "\"event_id\":%lu,\"link\":\"%s\","
      "\"sniff\":{\"bytes_in\":%lu,\"headers\":%lu,\"frames_ok\":%lu,"
      "\"frames_bad\":%lu,\"frames_empty\":%lu,\"frames_targets\":%lu,"
      "\"approaching\":%lu},\"read_calls\":%lu,\"read_max_gap_ms\":%lu,"
      "\"sample_total\":%lu,\"sample_bytes\":%u,\"sample_hex\":\"%s\","
      "\"measurement\":{\"state\":\"%s\",\"observed_ms\":%s,\"age_ms\":%s,"
      "\"raw_dir\":%s,\"approaching\":%s,\"range_m\":%s,\"speed_kmh\":%s,"
      "\"snr\":%s,\"radar_alarm\":%s,\"ttc_s\":%s,\"frame_level\":%s,"
      "\"reason\":%s,\"target_index\":%s,\"target_count\":%s}}",
      request_id, (unsigned)EW_DIR_APPROACH, snapshot->running ? "true" : "false",
      snapshot->ever_bytes ? "true" : "false",
      snapshot->ever_frame ? "true" : "false",
      (unsigned long)snapshot->started_ms, (unsigned long)snapshot->updated_ms,
      snapshot->radar_error, snapshot->event_id, link,
      (unsigned long)snapshot->sniff.bytes_in,
      (unsigned long)snapshot->sniff.headers,
      (unsigned long)snapshot->sniff.frames_ok,
      (unsigned long)snapshot->sniff.frames_bad,
      (unsigned long)snapshot->sniff.frames_empty,
      (unsigned long)snapshot->sniff.frames_targets,
      (unsigned long)snapshot->sniff.approaching,
      (unsigned long)snapshot->read_calls,
      (unsigned long)snapshot->read_max_gap_ms,
      (unsigned long)snapshot->sample_total,
      snapshot->sample_bytes, sample_hex, state_name, observed_ms, age_ms,
      raw_dir, approaching, range, speed, snr, alarm, ttc, frame_level,
      reason, target_index, target_count);
  if (result < 0 || (size_t)result >= capacity) {
    out[0] = '\0';
    return -ENOSPC;
  }
  return result;
}
