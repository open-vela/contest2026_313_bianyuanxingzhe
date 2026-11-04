"""Regress the stable LD2451 idle display without hiding malformed streams."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class RadarViewTests(unittest.TestCase):
    def test_actual_display_policy_preserves_alerts_faults_and_raw_staleness(self):
        source = r'''
#include <assert.h>
#include <string.h>
#include "ew_radar_view.h"
int main(void) {
  ew_safety_snapshot_t s={0}, saved;
  s.running=true;s.started_ms=100;s.decision.link=EW_LINK_DEAD;
  assert(ew_radar_view(&s,200,3000)==EW_RADAR_VIEW_WAIT);
  assert(ew_radar_view(&s,3100,3000)==EW_RADAR_VIEW_ERROR);
  s.ever_bytes=true;
  assert(ew_radar_view(&s,20000,3000)==EW_RADAR_VIEW_NO_FRAME);
  s.ever_frame=true;
  saved=s;
  /* Captured target -> 2.789s silence -> valid empty frame. No heartbeat
   * exists in this protocol mode; silence alone does not prove unplugging. */
  assert(ew_radar_view(&s,20000,3000)==EW_RADAR_VIEW_READY);
  assert(!memcmp(&s,&saved,sizeof(s)) && s.decision.link==EW_LINK_DEAD);
  s.decision.link=EW_LINK_NOISE;
  assert(ew_radar_view(&s,20000,3000)==EW_RADAR_VIEW_NO_FRAME);
  s.decision.link=EW_LINK_OK;
  assert(ew_radar_view(&s,20000,3000)==EW_RADAR_VIEW_READY);
  s.radar_error=5;
  assert(ew_radar_view(&s,20000,3000)==EW_RADAR_VIEW_ERROR);
  s.decision.level=EW_ALERT_STRONG;
  assert(ew_radar_view(&s,20000,3000)==EW_RADAR_VIEW_ALERT);
  s.running=false;
  assert(ew_radar_view(&s,20000,3000)==EW_RADAR_VIEW_ERROR);
  memset(&s,0,sizeof(s));s.running=true;s.started_ms=UINT32_MAX-100;
  assert(ew_radar_view(&s,200,3000)==EW_RADAR_VIEW_WAIT);
  return 0;
}
'''
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "view.c"
            exe = Path(d) / ("view.exe" if os.name == "nt" else "view")
            src.write_text(source)
            subprocess.run(["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                            "-I", str(ROOT / "app/edge_walker"), str(src), "-o", str(exe)], check=True)
            subprocess.run([str(exe)], check=True, timeout=5)


if __name__ == "__main__":
    unittest.main()
