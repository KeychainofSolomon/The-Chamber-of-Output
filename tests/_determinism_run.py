# Run a long, varied campaign with a fixed seed; print the final state fingerprint.
import sys, os, io, contextlib, random
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "chamber"))
import chamber as ch
camp = sys.argv[1]
def run(*a):
    sys.argv = ["c", "--campaign", camp] + list(a)
    with contextlib.redirect_stdout(io.StringIO()):
        try: ch.main()
        except SystemExit: pass
R = random.Random(5)   # the script's own choices: identical in every run
names = ["Ada", "Bo", "Cy", "Di", "Ed", "Flo", "Gus", "Hal"]
run("--seed", "det", "setting", "2,1,2,2,2,2,2")
run("place", "Yard", "--add", "sound:pump", "smell:tar")
for n in names: run("new", n)
for i, n in enumerate(names): run("tie", n, "--to", names[(i + 1) % 8], "--role", R.choice(ch.ROLES), "--loyalty", str(R.randint(1, 6)))
run("circle", "A", "--members", *names[:4]); run("circle", "B", "--members", *names[4:])
run("learn", "Ada", "--about", "you", "--claim", "x", "--how", "saw")
for d in range(40):
    run("day")
    pres = R.sample(names, R.randint(2, 6))
    run("round", *pres, "--place", "Yard", "--approach", R.choice(ch.APPROACHES), *(["--festive"] if R.random() < .3 else []))
    if d % 6 == 0: run("violence", *pres, "--victim", pres[0], "--attacker", pres[1], "--hurt", pres[0])
    run("event", R.choice(names), R.choice(["humiliation", "gift", "betrayal", "respect", "threat"]))
    run("spread", "--about", "you", "--among", *names, "--times", "3")
    if d % 9 == 0: run("week")
print(ch.state_hash(camp))
