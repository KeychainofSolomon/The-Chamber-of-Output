#!/usr/bin/env python3
"""Check that saving and loading a campaign is strict and atomic, and that a tampered engine pair
is caught by verification.

    python tests/test_archive.py [--engine-source PATH]
"""
import argparse, base64, contextlib, hashlib, io, json, os, shutil, stat, subprocess, sys, tempfile, zipfile, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "chamber"))
import chamber as ch  # noqa: E402

FAILS = []


def run(campaign, *argv):
    out = io.StringIO()
    sys.argv = ["chamber.py", "--campaign", campaign] + list(argv)
    try:
        with contextlib.redirect_stdout(out):
            ch.main()
        return out.getvalue(), None
    except SystemExit as e:
        return out.getvalue(), str(e)


def check(cond, what):
    print(("ok    " if cond else "FAIL  ") + what)
    if not cond:
        FAILS.append(what)


def snapshot(root):
    got = {}
    for d, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(d, f)
            with open(p, "rb") as fh:
                got[os.path.relpath(p, root)] = fh.read()
    return got


def make_zip(path, members, symlink=None):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in members.items():
            z.writestr(name, data)
        if symlink:
            info = zipfile.ZipInfo(symlink[0])
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(info, symlink[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine-source", help="a local checkout of the engine, to test --verify")
    a = ap.parse_args()
    work = tempfile.mkdtemp()
    A, B = os.path.join(work, "a"), os.path.join(work, "b")
    run(A, "setting", "1,1,1,0,1,1,1")
    for n in ("Ilse", "Joren"):
        run(A, "new", n)
    run(A, "place", "Quay", "--add", "sound:gulls")
    run(A, "circle", "Crew", "--members", "Ilse", "Joren")
    save_a = os.path.join(work, "a_save")
    _, err = run(A, "save", save_a)
    check(err is None, "a normal campaign saves")
    run(B, "setting", "2,2,2,2,2,2,2")
    for n in ("Mara", "Tobias", "Wren"):
        run(B, "new", n)
    run(B, "place", "Old Mill", "--add", "smell:flour")
    run(B, "circle", "Millers", "--members", "Mara", "Tobias")

    # B: replace leaves nothing of the old campaign
    _, err = run(B, "load", save_a + ".zip")
    check(err and "--replace" in err, "load refuses to overwrite without --replace")
    _, err = run(B, "load", save_a + ".zip", "--replace")
    files = set(snapshot(B))
    check(err is None and files == set(snapshot(A)), "--replace leaves exactly the loaded campaign, nothing old")
    check(not any(x for x in os.listdir(work) if x.startswith((".incoming-", ".outgoing-"))), "no leftover temp folders")

    # C: hostile archives change nothing
    good = snapshot(B)
    with open(os.path.join(B, "cast", "ilse.json"), "rb") as fh:
        person = fh.read()
    world = b'{"dials":[1,1,1,0,1,1,1],"week":0,"history":[]}'
    bad = {
        "path traversal": {"../evil.json": person},
        "absolute path": {"/etc/evil.json": person},
        "unexpected file": {"cast/ilse.json": person, "run_me.py": b"print(1)"},
        "nested folder": {"cast/sub/ilse.json": person},
        "broken JSON": {"world.json": world, "cast/ilse.json": b"{not json"},
        "wrong shape": {"world.json": world, "cast/ilse.json": b'{"name": 3}'},
        "bad settings": {"world.json": b'{"dials":[9,9,9]}', "cast/ilse.json": person},
        "file too large": {"world.json": world, "cast/big.json": b"{" + b" " * (ch.FILE_MAX + 10) + b"}"},
        "empty archive": {},
        "too many files": dict(("record/r%d.jsonl" % i, b"") for i in range(ch.FILES_MAX + 1)),
    }
    for what, members in bad.items():
        z = os.path.join(work, "bad.zip")
        make_zip(z, members)
        _, err = run(B, "load", z, "--replace")
        check(err is not None and snapshot(B) == good, "refused, campaign untouched: " + what)
    z = os.path.join(work, "link.zip")
    make_zip(z, {"world.json": world}, symlink=("cast/ilse.json", "/etc/passwd"))
    _, err = run(B, "load", z, "--replace")
    check(err is not None and snapshot(B) == good, "refused, campaign untouched: symlink entry")
    z = os.path.join(work, "notzip.zip")
    with open(z, "wb") as fh:
        fh.write(b"not a zip at all")
    _, err = run(B, "load", z, "--replace")
    check(err is not None and snapshot(B) == good, "refused, campaign untouched: not a zip")

    # C: save never follows links or takes stray files
    secret = os.path.join(work, "secret.txt")
    with open(secret, "w") as fh:
        fh.write("outside the campaign")
    try:
        os.symlink(secret, os.path.join(B, "cast", "leak.json"))
        os.symlink(work, os.path.join(B, "places", "linkdir"))
        linked = True
    except (OSError, NotImplementedError):
        linked = False
    with open(os.path.join(B, "notes.txt"), "w") as fh:
        fh.write("stray")
    out_zip = os.path.join(work, "b_save")
    out, err = run(B, "save", out_zip)
    with zipfile.ZipFile(out_zip + ".zip") as zz:
        names = zz.namelist()
        blob = b"".join(zz.read(n) for n in names)
    check(err is None and "notes.txt" not in names and b"outside the campaign" not in blob,
          "save leaves out stray files%s" % (" and links" if linked else " (links not testable here)"))
    if linked:
        check("cast/leak.json" not in names and not any(n.startswith("places/linkdir") for n in names),
              "save never follows a link to a file or a folder")
    _, err = run(B, "save", os.path.join(B, "inside"))
    check(err is not None, "save refuses to write into the campaign folder")

    # A: a tampered engine pair passes the checksum but fails verification
    if a.engine_source:
        ver = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "sync_engine.py"), "--verify",
                              "--source", a.engine_source], capture_output=True, text=True)
        check(ver.returncode == 0, "the shipped engine verifies against its source")
        fake = os.path.join(work, "fakeroot")
        shutil.copytree(ROOT, fake, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        cdir = os.path.join(fake, "chamber")
        with open(os.path.join(cdir, "engine.bin"), "rb") as fh:
            raw = zlib.decompress(base64.b64decode(fh.read())) + b"\n# tampered\n"
        with open(os.path.join(cdir, "engine.bin"), "wb") as fh:
            fh.write(base64.b64encode(zlib.compress(raw, 9)))
        with open(os.path.join(cdir, "engine.lock")) as fh:
            lock = json.load(fh)
        lock["sha256"] = hashlib.sha256(raw).hexdigest()
        with open(os.path.join(cdir, "engine.lock"), "w") as fh:
            json.dump(lock, fh)
        ver = subprocess.run([sys.executable, os.path.join(fake, "tools", "sync_engine.py"), "--verify",
                              "--source", a.engine_source], capture_output=True, text=True)
        check(ver.returncode == 1 and "MISMATCH" in ver.stdout, "a replaced engine and lock pair is caught by --verify")

    shutil.rmtree(work, ignore_errors=True)
    print("Archive test: %d failed." % len(FAILS) if FAILS else "Archive test: all passed.")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
