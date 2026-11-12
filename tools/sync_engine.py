#!/usr/bin/env python3
"""Seal a specific version of the RP-Instructional engine into the chamber.

    python tools/sync_engine.py --source /path/to/RP-Instructional --commit <sha>
    python tools/sync_engine.py --commit <sha>          # clones RP-Instructional into a temp folder

Only the engine script is taken, compressed into chamber/engine.bin, with its version recorded in
chamber/engine.lock. None of the engine's documentation comes across: the narrator who reads this
repository never sees how the engine works. Update deliberately; a running campaign keeps the
version it was pinned to until someone runs this again.
"""
import argparse, base64, hashlib, json, os, subprocess, sys, tempfile, zlib

REPO = "https://github.com/KeychainofSolomon/RP-Instructional"
PATH = "npc-temperament/scripts/forge.py"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "chamber")


def git(*args, cwd=None):
    return subprocess.run(["git"] + list(args), cwd=cwd, check=True, capture_output=True).stdout


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source", help="a local checkout of RP-Instructional")
    ap.add_argument("--commit", help="the engine version to seal (default: the checkout's HEAD)")
    a = ap.parse_args()
    tmp = None
    src = a.source
    if not src:
        tmp = tempfile.mkdtemp()
        git("clone", "--quiet", REPO, tmp)
        src = tmp
    commit = a.commit or git("rev-parse", "HEAD", cwd=src).decode().strip()
    raw = git("show", "%s:%s" % (commit, PATH), cwd=src)
    commit = git("rev-parse", commit, cwd=src).decode().strip()
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "engine.bin"), "wb") as fh:
        fh.write(base64.b64encode(zlib.compress(raw, 9)))
    with open(os.path.join(OUT, "engine.lock"), "w") as fh:
        json.dump({"repo": REPO, "commit": commit, "sha256": hashlib.sha256(raw).hexdigest()}, fh, indent=1)
    print("Sealed engine %s (%d bytes) into chamber/engine.bin" % (commit[:7], len(raw)))
    if tmp:
        subprocess.run(["rm", "-rf", tmp])


if __name__ == "__main__":
    main()
