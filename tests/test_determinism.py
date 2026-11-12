#!/usr/bin/env python3
"""Same seed, same actions, same world, whatever order Python happens to hash things in.

Runs a 40-day campaign (circles, violence, rumours, events) in separate processes under
different hash seeds and checks that every run ends in exactly the same state.

    python tests/test_determinism.py
"""
import os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
work = tempfile.mkdtemp()
seen = set()
for hs in ("0", "1", "2", "3"):
    camp = os.path.join(work, "c" + hs)
    env = dict(os.environ, PYTHONHASHSEED=hs)
    out = subprocess.run([sys.executable, os.path.join(HERE, "_determinism_run.py"), camp],
                         capture_output=True, text=True, env=env)
    seen.add(out.stdout.strip())
    print("hash seed %s: %s" % (hs, out.stdout.strip() or out.stderr.strip()[-200:]))
for d in os.listdir(work):
    shutil.rmtree(os.path.join(work, d), ignore_errors=True)
shutil.rmtree(work, ignore_errors=True)
ok = len(seen) == 1 and "" not in seen
print("Determinism test: %s" % ("all passed." if ok else "FAILED: runs disagree."))
sys.exit(0 if ok else 1)
