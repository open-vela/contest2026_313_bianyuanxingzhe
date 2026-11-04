# SPDX-License-Identifier: Apache-2.0
"""Compile the real radar diagnostic formatter/handler; never open hardware."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "app/edge_walker"

HARNESS = r'''
#include "ew_radar_diag.h"
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static ew_safety_snapshot_t current;
static unsigned snapshot_reads;
void ew_safety_snapshot(ew_safety_snapshot_t *out) {
  snapshot_reads++;
  *out = current;
}
'''

MAIN = r'''
static void fixture_state(void) {
  unsigned i;
  memset(&current, 0, sizeof(current));
  current.running = true;
  current.ever_bytes = true;
  current.decision.link = EW_LINK_NOISE;
  current.started_ms = 17u;
  current.updated_ms = 123456u;
  current.event_id = 41u;
  current.sniff.bytes_in = 1024u;
  current.sniff.headers = 3u;
  current.sniff.frames_bad = 3u;
  current.read_calls = 64u;
  current.read_max_gap_ms = 22u;
  current.sample_total = 1024u;
  current.sample_bytes = sizeof(current.sample);
  for (i = 0; i < current.sample_bytes; i++) current.sample[i] = (uint8_t)i;
}
static void fixture_target(void) {
  fixture_state();
  current.decision.link = EW_LINK_OK;
  current.decision.level = EW_ALERT_EMERGENCY;
  current.decision.speed_kmh = 99;
  current.decision.range_m = 1;
  current.ever_frame = true;
  current.observation_ms = current.updated_ms - 56u;
  current.observation.has_target = true;
  current.observation.raw_dir = EW_DIR_AWAY;
  current.observation.target_index = 0;
  current.observation.target_count = 1;
  current.observation.track.valid = true;
  current.observation.track.range_m = 2;
  current.observation.track.speed_kmh = 3;
  current.observation.track.snr = 95;
  current.observation.track.radar_alarm = true;
  current.observation_decision.level = EW_ALERT_SOFT;
  current.observation_decision.ttc_s = -1;
  current.observation_decision.reason = "radar_alarm_direction";
}
int main(int argc, char **argv) {
  const char *invalid[] = {"", "bad id", "x\"", "x\\", "x\n", "x;id", "x ", "x\t", "\xc3\xa9",
    "012345678901234567890123456789012345678901234567890"};
  char output[EW_RADAR_DIAG_MAX_BYTES], small[8], maximum_id[49], line[256];
  unsigned char saved[sizeof(current)];
  unsigned i;
  int length;
  fixture_state();
  if (argc > 1 && !strcmp(argv[1], "--stdio")) {
    fprintf(stderr, "RADAR_DIAG_FIXTURE_ONLY: no physical UART or board\n");
    while (fgets(line, sizeof(line), stdin)) {
      size_t n = strlen(line);
      while (n && (line[n-1] == '\r' || line[n-1] == '\n')) line[--n] = '\0';
      if (!strncmp(line, "@radar-diag", 11)) ctl_radar_diag_remainder(line + 11);
    }
    fprintf(stderr, "snapshot_reads=%u\n", snapshot_reads);
    return 0;
  }
  assert(ew_radar_diag_format(NULL, 1, "a", &current) == -EINVAL);
  assert(ew_radar_diag_format(output, 0, "a", &current) == -EINVAL);
  assert(ew_radar_diag_format(output, sizeof(output), NULL, &current) == -EINVAL);
  assert(ew_radar_diag_format(output, sizeof(output), "a", NULL) == -EINVAL);
  for (i = 0; i < sizeof(invalid)/sizeof(invalid[0]); i++) {
    strcpy(output, "must disappear");
    assert(ew_radar_diag_format(output, sizeof(output), invalid[i], &current) == -EINVAL);
    assert(output[0] == '\0');
  }
  assert(ew_radar_diag_format(small, sizeof(small), "a", &current) == -ENOSPC);
  assert(small[0] == '\0');
  length = ew_radar_diag_format(output, sizeof(output), "a", &current);
  assert(length > 0 && (unsigned)length < EW_RADAR_DIAG_MAX_BYTES);
  assert(ew_radar_diag_format(output, (size_t)length+1u, "a", &current) == length);
  assert(ew_radar_diag_format(output, (size_t)length, "a", &current) == -ENOSPC);
  assert(output[0] == '\0');
  current.sample_bytes = sizeof(current.sample) + 1u;
  assert(ew_radar_diag_format(output, sizeof(output), "a", &current) == -EINVAL);
  assert(output[0] == '\0');
  fixture_state(); current.decision.link = (ew_link_t)99;
  assert(ew_radar_diag_format(output, sizeof(output), "a", &current) == -EINVAL);
  assert(output[0] == '\0');
  fixture_state(); memcpy(saved, &current, sizeof(current));
  ctl_radar_diag("noise_1-A");
  assert(!memcmp(saved, &current, sizeof(current)));
  current.decision.link = EW_LINK_DEAD;
  current.ever_bytes = false;
  current.sample_bytes = 0;
  ctl_radar_diag("dead");
  fixture_state(); current.decision.link = EW_LINK_OK;
  current.ever_frame = true;
  current.sniff.frames_ok = 5u;
  current.sniff.frames_empty = 2u;
  current.sniff.frames_targets = 3u;
  current.sniff.approaching = 1u;
  current.observation_ms = current.updated_ms;
  ctl_radar_diag("ok");
  fixture_state(); current.running = false; current.radar_error = 5;
  ctl_radar_diag("error");
  fixture_state(); current.sample[0] = 0xf4u; current.sample[1] = 0;
  current.sample[2] = 0xffu; current.sample_bytes = 3;
  ctl_radar_diag("short_sample");
  fixture_target(); ctl_radar_diag("target");
  current.observation.track.approaching = true;
  current.observation.track.radar_alarm = false;
  current.observation_decision.level = EW_ALERT_NONE;
  current.observation_decision.ttc_s = 2.4f;
  current.observation_decision.reason = "below_min_speed";
  ctl_radar_diag("filtered");
  current.observation_ms = current.updated_ms - EW_LINK_STALE_MS;
  ctl_radar_diag("fresh_boundary");
  current.observation_ms--;
  ctl_radar_diag("stale_boundary");
  fixture_target(); current.observation.has_target = false;
  ctl_radar_diag("empty_held");
  fixture_target(); current.running = false;
  ctl_radar_diag("error_held");
  fixture_target(); current.ever_frame = false;
  ctl_radar_diag("wait_held");
  fixture_target(); current.observation_ms = UINT32_MAX - 99u;
  current.updated_ms = 100u; ctl_radar_diag("wrap");
  fixture_target(); current.observation.track.range_m = NAN;
  current.observation.track.speed_kmh = INFINITY;
  current.observation.track.snr = -1;
  current.observation.track.approaching = true;
  current.observation_decision.ttc_s = NAN;
  ctl_radar_diag("invalid_numbers");
  fixture_target(); current.observation_decision.reason = "quote\" slash\\\n";
  ctl_radar_diag("escaped_reason");
  fixture_state();
  current.sniff.bytes_in = current.sniff.headers = current.sniff.frames_ok = UINT32_MAX;
  current.sniff.frames_bad = current.sniff.frames_empty = current.sniff.frames_targets = UINT32_MAX;
  current.sniff.approaching = current.read_calls = current.read_max_gap_ms = UINT32_MAX;
  current.started_ms = current.updated_ms = current.sample_total = UINT32_MAX;
  current.event_id = ULONG_MAX;
  memset(maximum_id, 'Z', 48); maximum_id[48] = '\0';
  ctl_radar_diag(maximum_id);
  fixture_target();
  {
    char worst_reason[96];
    memset(worst_reason, 1, 95); worst_reason[95] = '\0';
    current.observation_decision.reason = worst_reason;
    ctl_radar_diag("worst_reason");
  }
  ctl_radar_diag("bad id");
  fprintf(stderr, "C_CONSTRAINTS_PASSED\n");
  return 0;
}
'''


def build_radar_diag_fixture(directory: Path) -> Path:
    """Use the production formatter, console handler and dispatch argument branch."""
    source = (SOURCE / "ew_serial_ctl.c").read_text(encoding="utf-8")
    handler = source[source.index("static void ctl_radar_diag("):
                     source.index("static void ctl_snapshot(")]
    start = source.index('  if (strcmp(verb, "radar-diag") == 0) {')
    end = source.index('\n  if (strcmp(verb, "join") == 0)', start)
    dispatch = ('static void ctl_radar_diag_remainder(const char *p) {\n'
                '  const char *verb = "radar-diag";\n' + source[start:end] + '\n}\n')
    cfile = directory / "radar_diag_fixture.c"
    exe = directory / "radar_diag_fixture.exe"
    cfile.write_text(HARNESS + handler + dispatch + MAIN, encoding="utf-8")
    compiler = shutil.which("gcc")
    if compiler is None:
        raise RuntimeError("GCC is required for the production C diagnostic fixture")
    os.environ["PATH"] = str(Path(compiler).parent) + os.pathsep + os.environ["PATH"]
    subprocess.run([compiler, "-std=c99", "-Wall", "-Wextra", "-Werror", "-I", str(SOURCE),
                    str(cfile), str(SOURCE / "ew_radar_diag.c"), "-o", str(exe)], check=True)
    return exe


class RadarDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ew_radar_diag_")
        cls.exe = build_radar_diag_fixture(Path(cls.temp.name))
        result = subprocess.run([str(cls.exe)], capture_output=True, text=True, check=True)
        cls.stderr = result.stderr
        cls.lines = result.stdout.splitlines()
        cls.rows = [json.loads(line.split("[ew-radar-diag] ", 1)[1]) for line in cls.lines]
        cls.by_id = {row["id"]: row for row in cls.rows if row["id"] is not None}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_production_handler_preserves_noise_counts_and_ordered_hex_sample(self):
        row = self.by_id["noise_1-A"]
        self.assertEqual((row["v"], row["origin"], row["port"], row["clock"]),
                         (1, "device", "/dev/ttyS1", "device_monotonic"))
        self.assertTrue(row["running"])
        self.assertTrue(row["ever_bytes"])
        self.assertFalse(row["ever_frame"])
        self.assertEqual(row["link"], "noise")
        self.assertEqual(row["started_ms"], 17)
        self.assertEqual(row["updated_ms"], 123456)
        self.assertEqual(row["event_id"], 41)
        build_header = (SOURCE / "ew_radar_build.h").read_text(encoding="utf-8")
        build_id = re.search(r'^#define EW_RADAR_BUILD_ID "([^"]+)"$', build_header, re.M)
        self.assertIsNotNone(build_id)
        self.assertEqual(row["build"], build_id.group(1))
        self.assertEqual(row["direction_approach"], 1)
        self.assertEqual(row["sniff"], dict(bytes_in=1024, headers=3, frames_ok=0, frames_bad=3,
                                           frames_empty=0, frames_targets=0, approaching=0))
        self.assertEqual((row["read_calls"], row["read_max_gap_ms"], row["sample_total"]), (64, 22, 1024))
        self.assertEqual(row["sample_bytes"], 64)
        self.assertEqual(row["sample_hex"], bytes(range(64)).hex())

    def test_dead_valid_and_error_states_do_not_hide_original_counters(self):
        self.assertEqual(self.by_id["dead"]["link"], "dead")
        self.assertEqual(self.by_id["dead"]["sample_hex"], "")
        self.assertEqual(self.by_id["dead"]["sample_bytes"], 0)
        self.assertEqual(self.by_id["ok"]["link"], "ok")
        self.assertEqual(self.by_id["ok"]["sniff"]["frames_ok"], 5)
        self.assertFalse(self.by_id["error"]["running"])
        self.assertEqual(self.by_id["error"]["radar_error"], 5)
        self.assertEqual(self.by_id["short_sample"]["sample_hex"], "f400ff")

    def test_c_constraints_and_worst_case_output_are_bounded(self):
        self.assertIn("C_CONSTRAINTS_PASSED", self.stderr)
        row = self.by_id["Z" * 48]
        self.assertEqual(row["sniff"]["bytes_in"], 0xffffffff)
        self.assertEqual(row["read_calls"], 0xffffffff)
        self.assertEqual(row["updated_ms"], 0xffffffff)
        self.assertTrue(all(len(line.split("[ew-radar-diag] ", 1)[1].encode()) < 2048 for line in self.lines))
        self.assertEqual(self.by_id["worst_reason"]["measurement"]["reason"], "\x01" * 95)
        errors = [row for row in self.rows if row.get("error")]
        self.assertEqual(errors, [{"v": 1, "id": None, "error": {"code": "invalid_request"}}])

    def test_latest_frame_measurements_and_policy_are_distinct_from_held_alarm(self):
        row = self.by_id["target"]["measurement"]
        self.assertEqual(row, dict(state="target", observed_ms=123400, age_ms=56,
                                  raw_dir=0, approaching=False, range_m=2, speed_kmh=3,
                                  snr=95, radar_alarm=True, ttc_s=None, frame_level="soft",
                                  reason="radar_alarm_direction", target_index=0, target_count=1))
        filtered = self.by_id["filtered"]["measurement"]
        self.assertEqual((filtered["speed_kmh"], filtered["frame_level"], filtered["reason"]),
                         (3, "none", "below_min_speed"))
        self.assertAlmostEqual(filtered["ttc_s"], 2.4)
        self.assertEqual(self.by_id["escaped_reason"]["measurement"]["reason"], 'quote" slash\\\n')

    def test_empty_stale_error_wait_never_export_historical_target_as_live(self):
        for name, state in (("empty_held", "empty"), ("stale_boundary", "stale"),
                            ("error_held", "error"), ("wait_held", "wait")):
            with self.subTest(name=name):
                measurement = self.by_id[name]["measurement"]
                self.assertEqual(measurement["state"], state)
                for key in ("raw_dir", "approaching", "range_m", "speed_kmh", "snr",
                            "radar_alarm", "ttc_s", "frame_level", "reason", "target_index", "target_count"):
                    self.assertIsNone(measurement[key], (name, key))
        self.assertEqual(self.by_id["fresh_boundary"]["measurement"]["state"], "target")
        self.assertEqual(self.by_id["stale_boundary"]["measurement"]["age_ms"], 1501)
        self.assertEqual(self.by_id["wrap"]["measurement"]["age_ms"], 200)
        self.assertIsNone(self.by_id["wait_held"]["measurement"]["observed_ms"])
        self.assertIsNone(self.by_id["error_held"]["measurement"]["age_ms"])
        for key in ("range_m", "speed_kmh", "snr", "ttc_s"):
            self.assertIsNone(self.by_id["invalid_numbers"]["measurement"][key])

    def test_real_dispatch_branch_rejects_extra_whitespace_arguments_and_long_ids(self):
        ids = ["valid_1-A", "Z" * 48]
        inputs = ["@radar-diag " + name for name in ids]
        inputs.extend(("@radar-diag", "@radar-diag  extra_space", "@radar-diag\ttab",
                       "@radar-diag trailing ", "@radar-diag id other", "@radar-diag " + "x" * 49,
                       '@radar-diag hidden"secret'))
        result = subprocess.run([str(self.exe), "--stdio"], input="\r\n".join(inputs) + "\r\n",
                                capture_output=True, text=True, check=True)
        rows = [json.loads(line.split("[ew-radar-diag] ", 1)[1]) for line in result.stdout.splitlines()]
        self.assertIn("no physical UART or board", result.stderr)
        self.assertEqual([row["id"] for row in rows[:2]], ids)
        self.assertTrue(all(row == {"v": 1, "id": None, "error": {"code": "invalid_request"}}
                            for row in rows[2:]))
        self.assertNotIn("hidden", result.stdout)
        self.assertIn("snapshot_reads=9", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
