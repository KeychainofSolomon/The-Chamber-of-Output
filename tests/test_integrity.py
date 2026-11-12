#!/usr/bin/env python3
"""Check the chamber's guarantees: looking never changes anything, the same seed and actions give the
same world, identity survives renaming and migration, damage is found and set aside, structured
output is valid, beliefs stay beliefs, and the narration check catches plain breaches.

    python tests/test_integrity.py
"""
import contextlib, io, json, os, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "chamber"))
import chamber as ch  # noqa: E402

FAILS = []


def run(camp, *argv):
    out = io.StringIO()
    sys.argv = ["chamber.py", "--campaign", camp] + list(argv)
    try:
        with contextlib.redirect_stdout(out):
            ch.main()
        return out.getvalue(), None
    except SystemExit as e:
        return out.getvalue(), str(e) if e.code not in (0, None) else None


def check(cond, what):
    print(("ok    " if cond else "FAIL  ") + what)
    if not cond:
        FAILS.append(what)


def main():
    work = tempfile.mkdtemp()
    A = os.path.join(work, "camp")
    run(A, "--seed", "fixed-seed", "setting", "1,1,2,1,1,1,2")
    people = ["Mara Voss", "Tobias Lind", "Wren", "Ilse Brand"]
    for p in people:
        run(A, "new", p)
    run(A, "place", "The yard", "--add", "sound:the pump", "smell:tar")
    run(A, "tie", "Mara Voss", "--to", "Tobias Lind", "--role", "sibling", "--loyalty", "5")
    run(A, "circle", "The yard crew", "--members", "Mara Voss", "Wren")
    for _ in range(3):
        run(A, "day")
        run(A, "round", *people, "--place", "The yard", "--approach", "pressure")
    run(A, "event", "Wren", "humiliation")
    run(A, "fact", "The miller started the fire himself.")
    run(A, "learn", "Wren", "--about", "the fire", "--claim", "the miller set it", "--how", "saw", "--stressed")
    run(A, "spread", "--about", "the fire", "--among", *people, "--times", "8")
    mid = os.path.join(work, "mid")
    run(A, "save", mid)

    # looking never changes anything
    h0 = ch.state_hash(A)
    page = os.path.join(work, "inspect.html")
    looks = [("sheet", "Wren"), ("round", *people, "--place", "The yard", "--look"), ("ask", "Wren", "--touched"),
             ("accounts", "--about", "the fire"), ("inspect", "--out", page), ("doctor",), ("found",), ("backups",),
             ("check", "--text", "The pump creaked.", "--dry"), ("save", os.path.join(work, "x"))]
    for argv in looks:
        run(A, *argv)
        check(ch.state_hash(A) == h0, "looking changes nothing: " + argv[0])

    # more play after the save, then replay
    for _ in range(3):
        run(A, "day")
        run(A, "round", *people, "--place", "The yard", "--approach", "humour")
        run(A, "tell", "Wren", "Ilse Brand", "--about", "the fire")
    run(A, "event", "Mara Voss", "betrayal")
    out, err = run(A, "replay")
    check(err is None and "exactly" in out, "replay from the start reproduces every step")
    out, err = run(A, "replay", mid + ".zip")
    check(err is None and "exactly" in out, "replay from a save reproduces the rest")
    j = ch.journal(ch.Campaign(A))
    j[-1]["after"] = "0" * 16
    with open(ch.journal_path(ch.Campaign(A)), "w") as fh:
        fh.write("".join(json.dumps(x) + "\n" for x in j))
    out, err = run(A, "replay")
    check(err is not None and "diverged" in err, "replay notices when a step comes out differently")
    j[-1]["after"] = ch.state_hash(A)
    with open(ch.journal_path(ch.Campaign(A)), "w") as fh:
        fh.write("".join(json.dumps(x) + "\n" for x in j))

    # identity: rename keeps the person and everyone's memory of them
    C = ch.Campaign(A)
    pid = ch.load(C.person("Tobias Lind"))["id"]
    out, err = run(A, "rename", "Tobias Lind", "Tobi Lind")
    t = ch.load(C.person("Tobi Lind"))
    m = ch.load(C.person("Mara Voss"))
    check(err is None and t["id"] == pid and not os.path.exists(C.person("Tobias Lind")), "rename keeps the same identity")
    check(any(x.get("who") == "Tobi Lind" for x in m["ties"]) and "Tobias Lind" not in m["trust"],
          "others' ties and regard follow the rename")
    _, err = run(A, "rename", "Wren", "Mara Voss")
    check(err is not None, "rename refuses to take someone else's name")

    # migration brings old ledgers forward without changing who anyone is
    w = ch.load(C.person("Wren"))
    keep = {k: w[k] for k in ("id", "speech", "strain", "tempo", "axes")}
    for k in ("id", "speech", "strain", "tempo", "schema"):
        w.pop(k, None)
    w["id"] = keep["id"]
    with open(C.person("Wren"), "w") as fh:
        json.dump(w, fh)
    run(A, "migrate")
    w2 = ch.load(C.person("Wren"))
    check(w2["id"] == keep["id"] and w2["axes"] == keep["axes"] and w2.get("schema"), "migrate restores missing layers, keeps identity")
    before = ch.state_hash(A)
    run(A, "migrate")
    check(ch.state_hash(A) == before, "migrate twice changes nothing the second time")

    # damage is found, set aside with --fix, and backups restore
    bad = C.person("Ilse Brand")
    with open(bad, "w") as fh:
        fh.write("{ torn")
    out, _ = run(A, "doctor")
    check("can't be read" in out, "doctor finds a damaged file")
    run(A, "doctor", "--fix")
    check(not os.path.exists(bad) and os.path.isdir(A + ".quarantine"), "doctor --fix sets the damaged file aside")
    out, _ = run(A, "backups")
    check(".zip" in out, "automatic backups are kept")
    names = [x for x in out.split() if x.endswith(".zip")]
    out, err = run(A, "restore", names[0])
    if err: print("      restore said:", err, out[-200:])
    check(err is None and os.path.exists(C.person("Ilse Brand")), "restore brings back an earlier state")

    # structured output is valid JSON with the same content
    out, err = run(A, "--json", "round", "Mara Voss", "Wren", "--place", "The yard", "--look")
    try:
        js = json.loads(out)
        good = js["command"] == "round" and js["entries"] and all("text" in e_ and "details" in e_ for e_ in js["entries"])
    except ValueError:
        good = False
    check(good, "--json gives structured entries")
    out, _ = run(A, "--json", "sheet", "Nobody Here")
    check(json.loads(out)["ok"] is False and json.loads(out)["refused"], "--json reports refusals in the structure")

    # beliefs: never truth, drift and confidence shown in words
    out, _ = run(A, "accounts", "--about", "the fire")
    check("the miller set it" in out and "may be wrong" in out and not any(c.isdigit() for c in out.replace("the fire", "")),
          "accounts show beliefs only, in words")
    check("started the fire himself" not in out, "what happened never shows up as anyone's belief by itself")
    _, err = run(A, "tell", "Mara Voss", "Wren", "--about", "a thing nobody knows")
    check(err is not None, "nobody passes on what they don't know")

    # the narration check
    bad_draft = ("You feel a chill as Mara Voss looks at you. Mara Voss is secretly afraid of the dark. "
                 "\"Could you help me find my brother?\" she asks. The brief said she was cool.")
    out, err = run(A, "check", "--text", bad_draft, "--dry")
    check(err is not None and "player's inner life" in out and "inner life as fact" in out and "task" in out
          and "workings" in out, "check catches inner life, stated feelings, unasked quests and workings")
    good_draft = "Mara wipes her hands on her apron and doesn't look up. \"Pump's been at it all morning,\" she says."
    out, err = run(A, "check", "--text", good_draft)
    check(err is None, "check passes clean narration")
    out, err = run(A, "check", "--text", good_draft)
    check(err is not None and "repeats a phrase" in out, "check notices the same phrasing scene after scene")
    run(A, "status", "Wren", "dead")
    out, err = run(A, "check", "--text", "Wren nods slowly at the pump.", "--dry")
    check(err is not None and "dead" in out, "check notices the dead acting")

    # the inspector is for the table: numbers allowed, never inside the campaign
    _, err = run(A, "inspect", "--out", os.path.join(A, "inside.html"))
    check(err is not None, "inspector refuses to write into the campaign folder")
    check(os.path.exists(page) and "Campaign inspector" in open(page).read(), "inspector page is written")

    for d in (work,):
        shutil.rmtree(d, ignore_errors=True)
    print("Integrity test: %d failed." % len(FAILS) if FAILS else "Integrity test: all passed.")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
