# SPDX-License-Identifier: Apache-2.0
"""Road capture evidence validity, partial preservation and production C wire handler."""
import csv
from collections import deque
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from roadtest_capture import Capture, VERSION

ROOT = Path(__file__).resolve().parents[2]


class FixturePort:
    def __init__(self, gap=False, dropped=0, broken=False, diagnostic_broken=False,
                 diagnostic_origin="device", initial_dropped=0):
        self.buffer = b""
        self.seq = 0
        self.enabled = False
        self.gap, self.dropped, self.broken = gap, dropped, broken
        self.commands = []
        self.snapshot_seq = 0
        self.diagnostic_broken = diagnostic_broken
        self.diagnostic_origin = diagnostic_origin
        self.diagnostic_updated_ms = None
        self.initial_dropped = initial_dropped
        self.recording_started = False

    def write(self, data):
        verb, token, *action = data.decode().split()
        self.commands.append(verb)
        rows = []
        if verb == "@road":
            if action == ["on"]:
                self.enabled = True
                self.recording_started = True
            elif action == ["off"]:
                self.enabled = False
            elif action == ["poll"] and self.enabled:
                self.seq += 2 if self.gap else 1
                rows.append({"id": token, "seq": self.seq, "timestamp_ms": 100 + self.seq * 20,
                             "raw_hex": "f4f3f2f10000f8f7f6f5"})
            rows.append({"id": token, "end": True, "enabled": self.enabled,
                         "dropped": self.dropped if self.recording_started else self.initial_dropped,
                         "pending": 0, "firmware": VERSION})
        elif verb == "@sensitivity":
            rows.append({"id": token, "ok": True, "profile": "standard"})
        elif verb == "@snapshot":
            if self.broken:
                raise OSError("fixture disconnected")
            self.snapshot_seq += 1
            rows.append({"id": token, "origin": "device", "clock": "device_monotonic",
                         "snapshot_seq": self.snapshot_seq, "updated_ms": 100 + self.seq * 20})
        elif verb == "@radar-diag":
            if self.diagnostic_broken:
                raise OSError("fixture diagnostic disconnected")
            # Same ID with an unrelated prefix must not satisfy this request.
            self.buffer += ("[ew-snapshot] " + json.dumps({"id": token}) + "\n").encode()
            rows.append({"id": token, "origin": self.diagnostic_origin, "clock": "device_monotonic",
                         "updated_ms": self.diagnostic_updated_ms if self.diagnostic_updated_ms is not None else 100 + self.seq * 20,
                         "build": "ew-radar-20261030-r1", "direction_approach": 0,
                         "measurement": {"state": "target", "age_ms": 20,
                                         "speed_kmh": 3, "range_m": 2, "raw_dir": 1,
                                         "snr": 95, "frame_level": "soft",
                                         "reason": "radar_alarm_direction"}})
        prefix = verb[1:]
        self.buffer += ("unrelated credential must not be saved\n" + "\n".join(
            f"[ew-{prefix}] " + json.dumps(row) for row in rows) + "\n").encode()

    def flush(self):
        pass

    def read(self, size):
        # Split wire replies to exercise the real line assembler.
        result, self.buffer = self.buffer[:31], self.buffer[31:]
        return result


class SimulatedClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class DelayedRingPort(FixturePort):
    """Model measured console latency with the real 128/32 buffer limits.

    Device ticks continue during *every* request, including response transfer.
    An immediate-response fixture cannot reveal auxiliary-query starvation.
    """
    def __init__(self, clock):
        super().__init__()
        self.clock = clock
        self.ring = deque()
        self.next_tick = None

    def advance(self, seconds):
        end = self.clock.now + seconds
        while self.enabled and self.next_tick <= end:
            self.seq += 1
            if len(self.ring) == 128:
                self.ring.popleft()
                self.dropped += 1
            self.ring.append({"seq": self.seq, "timestamp_ms": round(self.next_tick * 1000),
                              "raw_hex": "f4f3f2f10000f8f7f6f5" if self.seq % 33 == 0 else ""})
            self.next_tick += .03
        self.clock.now = end

    def write(self, data):
        verb, token, *action = data.decode().split()
        self.commands.append(verb)
        rows = []
        if verb == "@road":
            if action == ["on"]:
                self.enabled = True
                self.seq = self.dropped = 0
                self.ring.clear()
                self.next_tick = self.clock.now + .03
            elif action == ["off"]:
                self.enabled = False
            self.advance(.45)
            if action == ["poll"]:
                for _ in range(min(32, len(self.ring))):
                    rows.append({"id": token, **self.ring.popleft()})
            rows.append({"id": token, "end": True, "enabled": self.enabled,
                         "dropped": self.dropped, "pending": len(self.ring), "firmware": VERSION})
            self.advance(.22)
        else:
            self.advance(.45)
            if verb == "@sensitivity":
                rows.append({"id": token, "ok": True, "profile": "standard"})
            elif verb == "@snapshot":
                self.snapshot_seq += 1
                rows.append({"id": token, "origin": "device", "clock": "device_monotonic",
                             "snapshot_seq": self.snapshot_seq, "updated_ms": round(self.clock.now * 1000)})
            elif verb == "@radar-diag":
                rows.append({"id": token, "origin": "device", "clock": "device_monotonic",
                             "updated_ms": round(self.clock.now * 1000)})
        self.buffer += ("\n".join(f"[ew-{verb[1:]}] " + json.dumps(row) for row in rows) + "\n").encode()


class RoadCaptureTests(unittest.TestCase):
    def test_capture_preserves_replay_bytes_and_does_not_claim_road_success(self):
        with tempfile.TemporaryDirectory() as d:
            directory = Path(d) / "trial"
            port = FixturePort()
            report = Capture(port, directory, {"transport": "fixture"}).run(0.01)
            self.assertTrue(report["capture_complete"], report)
            self.assertFalse(report["road_performance_verified"])
            self.assertEqual(set(port.commands), {"@road", "@snapshot", "@sensitivity"})
            with (directory / "raw.csv").open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]["raw_hex"], "f4f3f2f10000f8f7f6f5")
            self.assertNotIn("credential", (directory / "protocol.jsonl").read_text())
            with self.assertRaises(FileExistsError):
                Capture(port, directory, {})

    def test_gaps_drops_or_disconnect_keep_partial_evidence_but_fail(self):
        for kwargs in ({"gap": True}, {"dropped": 2}, {"broken": True}):
            with self.subTest(kwargs=kwargs), tempfile.TemporaryDirectory() as d:
                directory = Path(d) / "partial"
                report = Capture(FixturePort(**kwargs), directory, {}).run(0.01)
                self.assertFalse(report["capture_complete"])
                self.assertTrue(report["records"])
                self.assertEqual(json.loads((directory / "session.json").read_text())["capture_complete"], False)

    def test_previous_trial_drop_counter_is_not_carried_into_new_trial(self):
        for active_drops in (0, 2):
            with self.subTest(active_drops=active_drops), tempfile.TemporaryDirectory() as d:
                directory = Path(d) / "trial"
                port = FixturePort(initial_dropped=96, dropped=active_drops)
                report = Capture(port, directory, {}, diagnostics=True).run(.01)
                self.assertEqual(report["capture_complete"], active_drops == 0, report)
                self.assertEqual(report["previous_session_dropped"], 96)
                self.assertEqual(report["dropped"], active_drops)
                evidence = [json.loads(line) for line in (directory / "protocol.jsonl").read_text().splitlines()]
                road_ends = [row["data"] for row in evidence if row["kind"] == "road" and row["data"].get("end")]
                self.assertEqual(road_ends[0]["dropped"], 96)
                self.assertEqual(next(row for row in road_ends if row["enabled"])["dropped"], active_drops)

    def test_optional_diagnostics_preserve_measurements_without_changing_road_version(self):
        with tempfile.TemporaryDirectory() as d:
            directory = Path(d) / "trial"
            port = FixturePort()
            report = Capture(port, directory, {}, diagnostics=True).run(0.01)
            self.assertTrue(report["capture_complete"], report)
            self.assertTrue(report["diagnostics_enabled"])
            self.assertEqual(report["diagnostics"], 1)
            self.assertEqual(set(port.commands), {"@road", "@snapshot", "@sensitivity", "@radar-diag"})
            evidence = [json.loads(line) for line in (directory / "protocol.jsonl").read_text().splitlines()]
            diagnostics = [row["data"] for row in evidence if row["kind"] == "radar-diag"]
            self.assertEqual(diagnostics[0]["build"], "ew-radar-20261030-r1")
            self.assertEqual(diagnostics[0]["measurement"]["reason"], "radar_alarm_direction")
            self.assertTrue(any(row["data"].get("firmware") == VERSION for row in evidence))
            self.assertNotIn("credential", (directory / "protocol.jsonl").read_text())

    def test_diagnostics_are_limited_to_once_per_second(self):
        with tempfile.TemporaryDirectory() as d:
            port = FixturePort()
            report = Capture(port, Path(d) / "trial", {}, diagnostics=True).run(1.15)
            self.assertTrue(report["capture_complete"], report)
            self.assertEqual(report["diagnostics"], 2)
            self.assertGreaterEqual(report["snapshots"], report["diagnostics"])

    def test_slow_console_keeps_live_ring_drained_before_auxiliary_queries(self):
        clock = SimulatedClock()
        with tempfile.TemporaryDirectory() as d, \
                patch("roadtest_capture.time.monotonic", clock.monotonic), \
                patch("roadtest_capture.time.sleep", clock.sleep):
            port = DelayedRingPort(clock)
            report = Capture(port, Path(d) / "trial", {}, diagnostics=True).run(60)
            self.assertTrue(report["capture_complete"], report)
            self.assertEqual(report["dropped"], 0)
            self.assertEqual(report["sequence_gaps"], 0)
            self.assertGreater(report["records"], 1900)
            self.assertGreater(report["snapshots"], 10)
            self.assertGreater(report["diagnostics"], 10)

    def test_failed_or_non_device_diagnostics_preserve_partial_evidence(self):
        for kwargs in ({"diagnostic_broken": True}, {"diagnostic_origin": "fixture"}):
            with self.subTest(kwargs=kwargs), tempfile.TemporaryDirectory() as d:
                directory = Path(d) / "partial"
                report = Capture(FixturePort(**kwargs), directory, {}, diagnostics=True).run(0.01)
                self.assertFalse(report["capture_complete"])
                self.assertEqual(report["diagnostics"], 0)
                self.assertTrue(report["records"])
                self.assertTrue(report["errors"])

    def test_diagnostic_timestamps_accept_wrap_and_reject_backwards_clock(self):
        with tempfile.TemporaryDirectory() as d:
            port = FixturePort()
            capture = Capture(port, Path(d) / "trial", {}, diagnostics=True)
            try:
                for stamp in (0xfffffff0, 10):
                    port.diagnostic_updated_ms = stamp
                    capture.request("radar-diag")
                self.assertEqual(capture.report["diagnostics"], 2)
                port.diagnostic_updated_ms = 9
                with self.assertRaisesRegex(RuntimeError, "clock moved backwards"):
                    capture.request("radar-diag")
            finally:
                capture.evidence.close()
                capture.raw_file.close()

    def test_bad_raw_and_backwards_time_are_rejected_but_uint32_wrap_is_valid(self):
        with tempfile.TemporaryDirectory() as d:
            capture = Capture(FixturePort(), Path(d) / "trial", {})
            try:
                capture.record({"seq": 1, "timestamp_ms": 0xfffffff0, "raw_hex": ""})
                capture.record({"seq": 2, "timestamp_ms": 10, "raw_hex": "ff"})
                for row in ({"seq": 3, "timestamp_ms": 9, "raw_hex": "ff"},
                            {"seq": 3, "timestamp_ms": 11, "raw_hex": "a"},
                            {"seq": 2, "timestamp_ms": 11, "raw_hex": "ff"}):
                    with self.assertRaises(RuntimeError):
                        capture.record(row)
            finally:
                capture.evidence.close()
                capture.raw_file.close()

    def test_production_handler_and_bounded_ring_overflow(self):
        source = ROOT / "app/edge_walker"
        ctl = (source / "ew_serial_ctl.c").read_text(encoding="utf-8")
        handler = ctl[ctl.index("static void ctl_road("):ctl.index("static void ctl_radar_diag(")]
        # Use actual parser helpers, not a Python reconstruction of command syntax.
        # Find exact helper ends by brace count, avoiding dependencies on following UI code.
        def extract(name):
            start = ctl.index("static void " + name + "(")
            brace = ctl.index("{", start)
            depth = 1
            end = brace + 1
            while depth:
                depth += (ctl[end] == "{") - (ctl[end] == "}")
                end += 1
            return ctl[start:end]
        code = r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include "ew_safety.c"
int alert_buzzer_prepare(void) { return 0; }
void alert_buzzer_safety_level(ew_alert_level_t level) { (void)level; }
unsigned long ew_agent_next_event_id(void) { return 1; }
'''
        code += extract("skip_spaces") + extract("parse_token") + handler
        code += r'''
int main(void) {
  unsigned i; uint8_t raw[64]; ew_road_record_t record;
  for(i=0;i<64;i++) raw[i]=(uint8_t)i;
  road_capture(raw,64,1); assert(!ew_safety_road_take(&record));
  ctl_road("start on");
  for(i=0;i<140;i++) road_capture(raw,64,i);
  assert(g_road_count==128 && g_road_dropped==12);
  ctl_road("poll1 poll"); assert(g_road_count==96);
  ctl_road("stop off");
  road_capture(raw,64,999); assert(g_road_count==96);
  ctl_road("bad poll extra");
  ctl_road("new on"); assert(g_road_count==0 && g_road_dropped==0);
  road_capture(NULL,0,1000); ctl_road("idle poll");
  return 0;
}
'''
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            cfile = folder / "test.c"
            cfile.write_text(code, encoding="utf-8")
            compiler = shutil.which("gcc")
            self.assertIsNotNone(compiler)
            os.environ["PATH"] = str(Path(compiler).parent) + os.pathsep + os.environ["PATH"]
            exe = folder / ("test.exe" if os.name == "nt" else "test")
            subprocess.run([compiler, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror", "-pthread",
                            "-DEW_SAFETY_HOST_TEST", *(["-DO_NONBLOCK=0"] if os.name == "nt" else []),
                            "-I", str(source), str(cfile), str(source / "ew_ld2451.c"),
                            "-o", str(exe), "-lm"], check=True)
            result = subprocess.run([str(exe)], capture_output=True, text=True, check=True)
            rows = [json.loads(line.split("[ew-road] ")[1]) for line in result.stdout.splitlines()]
            chunks = [r for r in rows if r.get("id") == "poll1" and "seq" in r]
            self.assertEqual(len(chunks), 32)
            self.assertEqual(chunks[0]["seq"], 13)
            self.assertEqual(chunks[0]["raw_hex"], bytes(range(64)).hex())
            self.assertTrue(any(r.get("id") == "idle" and r.get("raw_hex") == "" for r in rows))
            self.assertTrue(any(r.get("error") == "invalid_request" for r in rows))


if __name__ == "__main__":
    unittest.main(verbosity=2)
