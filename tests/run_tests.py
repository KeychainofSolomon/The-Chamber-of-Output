#!/usr/bin/env python3
"""Run the chamber through long random campaigns and fail on any crash or any leak of workings.

    python tests/run_tests.py [--days 60] [--seed 1]
"""
import argparse, contextlib, io, os, random, re, shutil, sys, tempfile, traceback, types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "chamber"))
import chamber as ch  # noqa: E402

E = ch.engine()
STYLE_NAMES = [s["name"] for s in E.STYLES]
FORBIDDEN = re.compile(r"\b(" + "|".join([
    "mood", "guard", "axes", "axis", "band", "tetrad", "circumstances?", "seed", "black box", "engine",
    "sealed", "stratagem", "inclination", "compulsion", "drive", "rung", "processing", "pressure", "anchor",
    "glow", "fuse", "nerve", "agency", "bedrock", "surface trust", "audit", "VIEW", "dials?",
    "Candour", "Volatility", "Energy", "Warmth", "Discipline", "Openness", "Dominance",
    "Survival", "Safety", "Means", "Comfort", "Belonging", "Standing", "Selfhood", "Meaning",
    "Hostile", "Cool", "Neutral", "Warm", "Kind", "Wounded-\\w+", "Fear-Aggression", "Righteous Wrath",
    "Cold Refusal", "Envy/Spite", "Teasing-Fond", "Gruff-Kind", "Bargaining-Humour"] + STYLE_NAMES) + r")\b")
DIGIT = re.compile(r"\d")
NAMES = ["Ada Brenn", "Corin Vale", "Isolde", "Marek Holm", "Nell Ashby", "Oswin Grey", "Petra Lind",
         "Quill", "Rosalind Fenn", "Sorrel", "Tamsin Hale", "Ulric", "Vesna Kord", "Wren Talley"]
APPROACHES = ch.APPROACHES + [None]


def run(argv, campaign):
    out = io.StringIO()
    sys.argv = ["chamber.py", "--campaign", campaign] + argv
    try:
        with contextlib.redirect_stdout(out):
            ch.main()
        return out.getvalue(), None, None
    except SystemExit as e:
        return out.getvalue(), str(e), None
    except Exception:
        return out.getvalue(), None, traceback.format_exc()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    random.seed(a.seed)
    camp = tempfile.mkdtemp()
    crashes, leaks, refusals, outputs = [], [], 0, 0

    def go(argv, user_text=()):
        nonlocal refusals, outputs
        text, refused, tb = run(argv, camp)
        outputs += 1
        if tb:
            crashes.append((argv, tb.splitlines()[-1]))
        if refused:
            refusals += 1
        body = text
        for t in user_text:
            body = body.replace(t, "")
        for line in body.splitlines():
            m = FORBIDDEN.search(line) or DIGIT.search(line)
            if m:
                leaks.append((argv[0], m.group(0), line.strip()[:120]))
        return text

    go(["setting", ",".join(str(random.randint(0, 3)) for _ in range(7))])
    places = {"The yard": ["sound:the pump", "smell:tar", "taste:salt", "object:a clock", "light:low sun", "person:the porter"],
              "The chapel": ["sound:the bell", "smell:wax and damp", "light:coloured glass", "routine:vespers"]}
    for p, fx in places.items():
        go(["place", p, "--add"] + fx, user_text=fx + [p])
    for nm in NAMES:
        go(["new", nm], user_text=[nm])
    for i, nm in enumerate(NAMES):
        to = NAMES[(i + 1) % len(NAMES)]
        go(["tie", nm, "--to", to, "--role", random.choice(ch.ROLES), "--loyalty", str(random.randint(1, 6))],
           user_text=[nm, to])
    go(["circle", "The crew", "--members"] + NAMES[:4], user_text=["The crew"] + NAMES[:4])
    for day in range(a.days):
        go(["day"], user_text=NAMES)
        for _ in range(2):
            present = random.sample(NAMES, random.randint(1, 5))
            argv = ["round"] + present + ["--place", random.choice(list(places))]
            app = random.choice(APPROACHES)
            if app: argv += ["--approach", app]
            for fl in ch.FLAGS + ("public",):
                if random.random() < 0.12: argv.append("--" + fl)
            if random.random() < 0.3: argv += ["--danger"] + random.sample(ch.DANGER, random.randint(1, 2))
            if random.random() < 0.1: argv += ["--hurt", present[0]]
            if random.random() < 0.15: argv += ["--violence", "--victim", present[0], "--attacker", "player"]
            if random.random() < 0.5: argv += ["--prose", "The pump creaked and the bell rang twice."]
            if random.random() < 0.4:
                argv += ["--as"] + ["%s:%s" % (p_, ",".join(random.sample(list(ch.FLAGS) + ["public", "opposed", "hurt"], random.randint(1, 3))))
                                    for p_ in random.sample(present, random.randint(1, len(present)))]
            if random.random() < 0.4:
                argv += ["--treat"] + ["%s:%s" % (p_, random.choice(ch.APPROACHES)) for p_ in random.sample(present, random.randint(1, len(present)))]
            if random.random() < 0.2: argv += ["--home", present[-1]]
            if random.random() < 0.15: argv += ["--symbol", random.choice(["Justice", "Faith", "Kin", "Order"])]
            if random.random() < 0.1: argv.append("--look")
            if random.random() < 0.1: argv.append("--no-between")
            go(argv, user_text=NAMES + ["The pump creaked and the bell rang twice."] + sum(places.values(), []))
        if day % 5 == 0:
            present = random.sample(NAMES, random.randint(1, 4))
            attacker = random.choice(["player"] + present[1:]) if len(present) > 1 else "player"
            argv = ["violence"] + present + ["--place", random.choice(list(places)), "--victim", present[0],
                                             "--attacker", attacker, "--hurt", present[0]]
            if random.random() < 0.3: argv += ["--symbol", random.choice(["Justice", "Faith", "Kin"])]
            go(argv, user_text=NAMES + sum(places.values(), []))
        if day == a.days // 3:
            sp_ = os.path.join(camp, "..", "chamber_test_save")
            go(["save", sp_], user_text=[sp_ + ".zip"])
            go(["load", sp_ + ".zip", "--replace"], user_text=[sp_ + ".zip"])
        for nm in random.sample(NAMES, 3):
            kind = random.choice(ch.EVENTS)
            argv = ["event", nm, kind]
            if kind == "loss": argv += ["--about", random.choice(NAMES)]
            if random.random() < 0.3: argv.append("--big")
            go(argv, user_text=NAMES)
        if random.random() < 0.3:
            go(["habit", random.choice(NAMES), random.choice(["drinking", "praying", "fighting", "whittling"])], user_text=NAMES)
        if random.random() < 0.3:
            go(["ask", random.choice(NAMES), "--touched"], user_text=NAMES)
        if day % 7 == 0:
            go(["week"])
        if day == a.days // 2:
            go(["status", NAMES[-1], "dead"], user_text=NAMES)
    for nm in NAMES:
        go(["sheet", nm], user_text=NAMES)
    shutil.rmtree(camp, ignore_errors=True)
    print("Chamber test: %d commands over %d days, %d clean refusals." % (outputs, a.days, refusals))
    seen = set()
    for c in crashes:
        if c[1] not in seen:
            seen.add(c[1]); print("CRASH", c)
    seen = set()
    for l in leaks:
        if l[:2] not in seen:
            seen.add(l[:2]); print("LEAK", l)
    if crashes or leaks:
        print("FAILED: %d crashes, %d leaking lines" % (len(crashes), len(leaks)))
        sys.exit(1)
    print("Passed: no crashes, no numbers, no workings in any brief.")


if __name__ == "__main__":
    main()
