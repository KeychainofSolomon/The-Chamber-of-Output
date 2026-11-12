#!/usr/bin/env python3
"""Seal a specific version of the engine into the chamber.

    python tools/sync_engine.py --source /path/to/engine-checkout --commit <sha>
    python tools/sync_engine.py --repo <git url> --commit <sha>    # clones it into a temp folder

    python tools/sync_engine.py --verify --source <checkout>       # check the sealed engine against the source
    python tools/sync_engine.py --verify --require-signed ...      # ...and require a valid signed commit

The engine's location can also come from the environment: CHAMBER_ENGINE_REPO (a git url) or
CHAMBER_ENGINE_SOURCE (a local checkout). The engine script is found inside the checkout by name.

Only the engine script is taken, compressed into chamber/engine.bin, with its version recorded in
chamber/engine.lock. None of the engine's documentation comes across: the narrator who reads this
repository never sees how the engine works. Update deliberately; a running campaign keeps the
version it was pinned to until someone runs this again.
"""
import argparse, base64, hashlib, json, os, subprocess, sys, tempfile, zlib

SCRIPT = "forge.py"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "chamber")


def git(*args, cwd=None):
    return subprocess.run(["git"] + list(args), cwd=cwd, check=True, capture_output=True).stdout


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source", default=os.environ.get("CHAMBER_ENGINE_SOURCE"), help="a local checkout of the engine")
    ap.add_argument("--repo", default=os.environ.get("CHAMBER_ENGINE_REPO"), help="the engine's git url, to clone")
    ap.add_argument("--commit", help="the engine version to seal (default: the checkout's HEAD)")
    ap.add_argument("--verify", action="store_true",
                    help="seal nothing; rebuild the engine from the source at the locked commit and compare")
    ap.add_argument("--require-signed", action="store_true",
                    help="refuse a commit whose signature git cannot verify (needs the signer's key)")
    a = ap.parse_args()
    if a.verify:
        with open(os.path.join(OUT, "engine.lock")) as fh:
            lock = json.load(fh)
        with open(os.path.join(OUT, "engine.bin"), "rb") as fh:
            sealed = zlib.decompress(base64.b64decode(fh.read()))
        a.commit = lock["commit"]
    tmp = None
    src = a.source
    if not src:
        if not a.repo:
            sys.exit("Say where the engine is: --source <checkout> or --repo <git url>.")
        tmp = tempfile.mkdtemp()
        git("clone", "--quiet", a.repo, tmp)
        src = tmp
    commit = a.commit or git("rev-parse", "HEAD", cwd=src).decode().strip()
    found = [f for f in git("ls-tree", "-r", "--name-only", commit, cwd=src).decode().splitlines()
             if os.path.basename(f) == SCRIPT]
    if len(found) != 1:
        sys.exit("Expected one %s in that checkout at %s, found %d." % (SCRIPT, commit[:7], len(found)))
    raw = git("show", "%s:%s" % (commit, found[0]), cwd=src)
    commit = git("rev-parse", commit, cwd=src).decode().strip()
    if a.require_signed:
        r = subprocess.run(["git", "verify-commit", commit], cwd=src, capture_output=True)
        if r.returncode:
            sys.exit("Commit %s has no signature git can verify: %s" % (commit[:7], r.stderr.decode().strip()[:200]))
    if a.verify:
        digest = hashlib.sha256(raw).hexdigest()
        ok = digest == lock["sha256"] == hashlib.sha256(sealed).hexdigest()
        if tmp:
            subprocess.run(["rm", "-rf", tmp])
        print(("Verified: the sealed engine is exactly %s of the engine source." if ok else
               "MISMATCH: the sealed engine is not what %s of the engine source produces.") % commit[:7])
        sys.exit(0 if ok else 1)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "engine.bin"), "wb") as fh:
        fh.write(base64.b64encode(zlib.compress(raw, 9)))
    with open(os.path.join(OUT, "engine.lock"), "w") as fh:
        json.dump({"commit": commit, "sha256": hashlib.sha256(raw).hexdigest()}, fh, indent=1)
    print("Sealed engine %s (%d bytes) into chamber/engine.bin" % (commit[:7], len(raw)))
    if tmp:
        subprocess.run(["rm", "-rf", tmp])


if __name__ == "__main__":
    main()
