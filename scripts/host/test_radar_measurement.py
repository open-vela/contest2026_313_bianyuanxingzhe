# SPDX-License-Identifier: Apache-2.0
"""Exercise live measurement text separately from held radar alerts."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "app/edge_walker"


class RadarMeasurementTests(unittest.TestCase):
    def test_real_formatter_filtered_targets_empty_stale_hold_and_wrap(self):
        source = r'''
#include <assert.h>
#include "ew_radar_measurement.h"
int main(void) {
  ew_safety_snapshot_t s={0};
  char text[320], tiny[5], direction[16];
  const unsigned char filtered[]={
    0xf4,0xf3,0xf2,0xf1,7,0,1,1,128,6,EW_DIR_AWAY,40,30,0xf8,0xf7,0xf6,0xf5};
  const unsigned char empty[]={0xf4,0xf3,0xf2,0xf1,0,0,0xf8,0xf7,0xf6,0xf5};
  ew_ld2451_parser_t parser;
  ew_track_t selected;
  ew_sniff_stats_t sniff={0};
  ew_ld2451_parser_reset(&parser);
  assert(ew_measurement_state(&s,100)==EW_MEASUREMENT_ERROR);
  s.running=true;
  ew_measurement_text(text,sizeof(text),&s,100);
  assert(strstr(text,"WAITING FRAME") && strstr(text,"V --"));
  assert(ew_ld2451_parser_feed_sniff(&parser,filtered,sizeof(filtered),&sniff,&selected));
  s.ever_frame=true; s.observation_ms=100; s.observation=parser.latest_frame;
  s.observation_decision=ew_decide(&s.observation.track);
  /* A held emergency must not replace a newer, filtered 40km/h observation. */
  s.decision.level=EW_ALERT_EMERGENCY; s.decision.speed_kmh=120;
  s.updated_ms=1600;
  ew_measurement_text(text,sizeof(text),&s,200);
  assert(strstr(text,"V 40 km/h  AWAY") && strstr(text,"R 6 m"));
  snprintf(direction,sizeof(direction),"DIR %u",(unsigned)EW_DIR_AWAY);
  assert(strstr(text,"TTC --") && strstr(text,direction) && strstr(text,"FALLBACK: DIR"));
  assert(strstr(text,"LAST FRAME SOFT") && strstr(text,"ALARM EMERGENCY"));
  assert(!strstr(text,"NOW "));
  assert(strstr(text,"FRAME AGE 100 ms") && !strstr(text,"120"));
  assert(ew_measurement_state(&s,1600)==EW_MEASUREMENT_TARGET);
  ew_measurement_text(text,sizeof(text),&s,1601);
  assert(strstr(text,"STALE FRAME") && strstr(text,"V --") && !strstr(text,"V 40"));
  assert(s.decision.level==EW_ALERT_EMERGENCY);
  assert(!ew_ld2451_parser_feed_sniff(&parser,empty,sizeof(empty),&sniff,&selected));
  s.observation=parser.latest_frame; s.observation_ms=2000;
  ew_measurement_text(text,sizeof(text),&s,2001);
  assert(strstr(text,"NO TARGET") && strstr(text,"V --"));
  assert(s.decision.level==EW_ALERT_EMERGENCY);
  s.observation_ms=UINT32_MAX-99u;
  assert(ew_measurement_state(&s,100)==EW_MEASUREMENT_EMPTY);
  assert(ew_measurement_state(&s,1500)==EW_MEASUREMENT_STALE);
  s.radar_error=5;
  ew_measurement_text(text,sizeof(text),&s,100);
  assert(strstr(text,"RADAR ERROR") && strstr(text,"V --"));
  s.radar_error=0; s.observation_ms=100; s.observation.has_target=true;
  s.observation.track.valid=true; s.observation.track.approaching=true;
  s.observation.track.speed_kmh=20; s.observation.track.range_m=20;
  s.observation_decision=ew_decide(&s.observation.track);
  ew_measurement_text(text,sizeof(text),&s,100);
  assert(strstr(text,"TTC 3.60 s"));
  s.observation_decision.ttc_s=-1;
  ew_measurement_text(text,sizeof(text),&s,100);
  assert(strstr(text,"TTC -- s"));
  s.observation_decision.ttc_s=NAN;
  ew_measurement_text(text,sizeof(text),&s,100);
  assert(strstr(text,"TTC -- s"));
  /* A frame can remain readable for 1500ms after its 1000ms alarm expires.
   * Reproduce the video window with the real hold: never call it NOW. */
  {
    ew_hold_t hold;
    ew_hold_reset(&hold);
    s.observation.track.range_m=6; s.observation.track.speed_kmh=20;
    s.observation.track.approaching=true;
    s.observation.track.snr=30;
    s.observation.raw_dir=EW_DIR_APPROACH;
    s.observation_decision=ew_decide(&s.observation.track);
    s.decision=ew_hold_update(&hold,100,true,true,&s.observation.track);
    assert(s.decision.level==EW_ALERT_EMERGENCY);
    s.decision=ew_hold_update(&hold,1201,false,false,NULL);
    assert(s.decision.level==EW_ALERT_NONE);
    ew_measurement_text(text,sizeof(text),&s,1201);
    assert(strstr(text,"LAST FRAME EMERGENCY") && strstr(text,"ALARM NONE"));
    assert(strstr(text,"FRAME AGE 1101 ms") && !strstr(text,"NOW "));
    /* An explicitly active manual output must match the upper display too. */
    ew_measurement_text_for_display(text,sizeof(text),&s,1201,EW_ALERT_STRONG);
    assert(strstr(text,"LAST FRAME EMERGENCY") && strstr(text,"ALARM STRONG"));
    ew_measurement_text_for_display(text,sizeof(text),&s,1601,EW_ALERT_STRONG);
    assert(strstr(text,"STALE FRAME") && strstr(text,"ALARM STRONG"));
    assert(strstr(text,"V -- km/h") && !strstr(text,"V 20"));
  }
  ew_measurement_text(tiny,sizeof(tiny),&s,100);
  assert(tiny[sizeof(tiny)-1]=='\0');
  assert(!strcmp(ew_measurement_reason("radar_alarm_speed"),"FALLBACK: SPEED"));
  assert(!strcmp(ew_measurement_reason("radar_alarm_snr"),"FALLBACK: SNR"));
  assert(!strcmp(ew_measurement_reason("radar_alarm_out_of_threshold"),"FALLBACK: RANGE/TTC"));
  return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            cfile = path / "measurement.c"
            executable = path / ("measurement.exe" if os.name == "nt" else "measurement")
            cfile.write_text(source, encoding="utf-8")
            subprocess.run(["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                            "-I", str(SOURCE), str(cfile), str(SOURCE / "ew_ld2451.c"),
                            "-o", str(executable), "-lm"], check=True)
            subprocess.run([str(executable)], check=True, timeout=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
