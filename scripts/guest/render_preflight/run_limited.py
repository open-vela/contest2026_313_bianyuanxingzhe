#!/usr/bin/env python3
"""Execute prepared fixtures inside an externally enforced cgroup scope."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

p = argparse.ArgumentParser()
p.add_argument('--repo', type=Path, required=True)
p.add_argument('--build', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--cpu-percent', type=int, required=True)
a = p.parse_args()
group = next(line.split(':', 2)[2] for line in Path('/proc/self/cgroup').read_text().splitlines()
             if line.startswith('0::'))
cg = Path('/sys/fs/cgroup') / group.lstrip('/')
cpu_max = (cg/'cpu.max').read_text().strip()
memory_max = (cg/'memory.max').read_text().strip()
quota, period = cpu_max.split()
assert quota != 'max' and int(quota) * 100 == int(period) * a.cpu_percent, cpu_max
assert int(memory_max) == 64*1024*1024, memory_max
assert len(os.sched_getaffinity(0)) == 1
before = (cg/'cpu.stat').read_text()
results = []
commands = [
    ('headless_lvgl', [str(a.build/'render_bench')]),
    ('production_radar_regression', [str(a.build/'host_smoke')]),
    ('production_snapshot_regression', ['python3', str(a.repo/'scripts/host/test_snapshot.py')]),
]
for name, cmd in commands:
    start = time.monotonic()
    try:
        r = subprocess.run(cmd, cwd=a.repo, text=True, capture_output=True, timeout=120)
        row = dict(name=name, returncode=r.returncode, wall_seconds=time.monotonic()-start,
                   stdout=r.stdout, stderr=r.stderr)
    except subprocess.TimeoutExpired as exc:
        row = dict(name=name, returncode=124, wall_seconds=time.monotonic()-start,
                   error='resource-constrained fixture exceeded 120s; not a board measurement')
    results.append(row)
    print(json.dumps(row), flush=True)
report = dict(scope='vmware_linux_cgroup_preflight', board_equivalent=False,
              calibrated_against_board=False, epic_hardware_emulated=False,
              cpu_percent_of_one_vm_vcpu=a.cpu_percent,
              cpu_affinity=sorted(os.sched_getaffinity(0)), cpu_max=cpu_max,
              process_tree_memory_max_bytes=int(memory_max),
              memory_note='process-tree cap includes Linux/Python; LVGL fixture separately caps its heap at 512KiB',
              cpu_stat_before=before, cpu_stat_after=(cg/'cpu.stat').read_text(),
              memory_peak_bytes=(cg/'memory.peak').read_text().strip(),
              memory_events=(cg/'memory.events').read_text(), results=results,
              passed=all(r['returncode'] == 0 for r in results))
a.out.write_text(json.dumps(report, indent=2)+'\n')
raise SystemExit(0 if report['passed'] else 1)
