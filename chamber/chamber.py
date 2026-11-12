#!/usr/bin/env python3
"""The Chamber of Output: run a roleplay campaign's people and places, and get back plain briefs.

The engine that decides who people are and how they react is sealed inside this folder
(engine.bin, pinned by engine.lock). This program drives it and translates everything it says
into plain portrayal: how someone comes across, what shows, what is left in the world to notice.
No numbers, no workings. Python 3.8+, standard library only.
"""
import argparse, base64, hashlib, io, json, os, re, sys, types, zlib, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
FLAGS = ("solemn", "festive", "superior", "duty", "drunk", "tired", "sick", "grieving", "private")
DANGER = ["violence", "injury", "disaster", "authority", "contagion", "uncanny"]
APPROACHES = ["deference", "familiarity", "bluntness", "flattery", "haggling", "humour", "patience",
              "pressure", "generosity", "principle", "pity"]
ROLES = ["child", "parent", "sibling", "spouse", "lover", "kin", "friend", "dependant", "student", "mentor",
         "spiritual", "master", "subordinate", "follower", "comrade", "rival", "enemy", "creditor", "debtor", "symbol"]
EVENTS = ["kindness", "rescue", "gift", "respect", "betrayal", "humiliation", "threat", "lie-caught", "triumph",
          "loss", "code-broken", "fell-ill", "intoxicated", "reunion", "joy", "witnessed"]

# ---------- the sealed engine ----------
_E = None


def engine():
    global _E
    if _E is None:
        with open(os.path.join(HERE, "engine.lock")) as fh:
            lock = json.load(fh)
        with open(os.path.join(HERE, "engine.bin"), "rb") as fh:
            raw = zlib.decompress(base64.b64decode(fh.read()))
        if hashlib.sha256(raw).hexdigest() != lock["sha256"]:
            sys.exit("The sealed engine doesn't match its lock. Re-seal it with tools/sync_engine.py.")
        mod = types.ModuleType("sealed_engine")
        exec(compile(raw, "<sealed engine>", "exec"), mod.__dict__)
        _E = mod
    return _E


def quiet(fn, **kw):
    """Run an engine command without letting anything it prints through. Returns (view, refusal)."""
    E = engine()
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            fn(types.SimpleNamespace(**kw))
    except SystemExit as e:
        return {}, str(e) or "That can't be done."
    return dict(E.VIEW), None


# ---------- the campaign on disk ----------
class Campaign:
    def __init__(self, root):
        self.root = root
        for sub in ("cast", "places", "circles", "record"):
            os.makedirs(os.path.join(root, sub), exist_ok=True)

    @staticmethod
    def slug(name):
        s = re.sub(r"[^\w]+", "_", name.strip().lower(), flags=re.UNICODE).strip("_")
        return s or "unnamed"

    def person(self, name):
        return os.path.join(self.root, "cast", self.slug(name) + ".json")

    def place(self, name):
        return os.path.join(self.root, "places", self.slug(name) + ".json")

    def circle(self, name):
        return os.path.join(self.root, "circles", self.slug(name) + ".json")

    @property
    def world(self):
        return os.path.join(self.root, "world.json")

    @property
    def record(self):
        return os.path.join(self.root, "record", "thoughts.sealed.jsonl")

    def need(self, path, what):
        if not os.path.exists(path):
            sys.exit("No %s by that name in this campaign." % what)
        return path

    def dials(self):
        if os.path.exists(self.world):
            with open(self.world) as fh:
                return ",".join(str(x) for x in json.load(fh)["dials"])
        return None

    def everyone(self):
        d = os.path.join(self.root, "cast")
        return sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".json"))


def load(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def save(obj, p):
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, ensure_ascii=False)


# ---------- plain language ----------
SHOWS = {
 "Candid": "tells the hard truth, for the other's own good", "Confiding": "shares something true and private",
 "Forgiving": "lets a slight go, openly", "Generous": "gives more than asked and waves off payment",
 "Gruff-Kind": "kind inside a gruff manner", "Hospitable": "offers food, a seat, shelter before anything else",
 "Loyal": "remembers past favours and takes their side", "Mentoring": "corrects and explains how things really work",
 "Practical": "helps without fuss, then back to work", "Protective": "steps between them and harm",
 "Respectful": "treats them as an equal worth their time", "Reverent": "treats them as someone of standing",
 "Teasing-Fond": "affection as ribbing", "Tender": "a soft voice, real concern, notices hurt",
 "Appraising": "measuring what they're worth", "Bargaining-Humour": "haggles as a game",
 "Boastful": "talks themself up and watches for the effect", "Curious": "asks questions, wants the story",
 "Distracted": "mind elsewhere", "Dutiful": "does exactly the job and nothing more",
 "Evasive": "answers questions with questions", "Flirtatious": "playful interest that may mean nothing",
 "Gossipy": "trades rumours, some true", "Indifferent": "treats them like weather",
 "Melancholic": "sad, gentle, faraway", "Mercurial": "warm words with cold eyes, or the reverse",
 "Performing": "plays to an audience, even an audience of one", "Preaching": "explains the world through what they believe",
 "Ritual": "set phrases, proper forms, protocol", "Testing": "pokes to see how they react",
 "Transactional": "everything has a price, stated plainly", "Wary": "polite, watching their hands",
 "Withdrawn": "short answers, eyes elsewhere, a body that wants to leave", "Cold Refusal": "a closed door: no",
 "Contempt": "not worth their anger", "Envy/Spite": "resents what they have; small cruelties",
 "Fear-Aggression": "lashes out from fear", "Grudge": "holds something against them, or people like them",
 "Manipulation": "friendly on the surface, working an angle (show only the surface)",
 "Mockery": "laughs at them, plays to the room", "Obstruction": "rules, forms and delays, never a raised voice",
 "Predatory": "sizing them up as prey, mark or tool (in looks, not words)",
 "Reproach": "wounded accusation; makes them feel the debt", "Righteous Wrath": "certain a principle has been offended",
 "Sabotage": "agrees readily (whatever fails, fails later and unseen)", "Suspicion": "assumes the worst of them",
 "Territorial": "wants them away from this place and these people", "Toying": "cruelty as play, in no hurry",
 "Violent Outburst": "a sudden threat or blow, perhaps regretted",
 "Wounded-Selfless": "asks after someone else before themself",
 "Wounded-Panic": "pleads, bargains, calls for someone; breath and words break",
 "Wounded-Stoic": "quiet and practical about their own wound; asks for cloth, water, light",
 "Wounded-Shock": "looks at the wound as if it belonged to someone else; says something ordinary",
 "Wounded-Betrayed": "looks at the one who did it; asks why",
}
FEEL = {"Hostile": "hostile", "Cool": "cool", "Neutral": "neither warm nor cold", "Warm": "warm", "Kind": "kind"}
PLAN = {"Overwhelm": "if it comes to opposition, they'd confront openly, or toy with them",
        "Press": "if it comes to opposition, they'd press: demand terms, show strength",
        "Wait": "if it comes to opposition, they'd wait and probe, test, look for allies",
        "Avoid": "if it comes to opposition, they'd avoid open conflict: appear to comply, strike where it isn't expected",
        "Yield": "if it comes to opposition, they'd yield, slip away, or turn to someone stronger"}
STATION = {"Head": "runs something", "Warden": "holds and defends a place or thing", "Steward": "keeps goods or services for others",
           "Herald": "carries word and knows things", "Threshold": "keeps a gate, a desk, a way through",
           "Hand": "makes and works", "Sworn": "is bound by a loyalty and gives only within it", "Unmoored": "belongs nowhere fixed"}
OFFICE = {"Teaches": "teach a skill or art", "Reveals": "reveal secrets or the past", "Finds": "find what is lost",
          "Reconciles": "mend feuds and broker deals", "Kindles": "stir love, courage or desire", "Carries": "carry people or goods",
          "Builds": "build", "Ruins": "break and unmake", "Companions": "lend an ally, animal or helper",
          "Transforms": "change things or people", "Mends": "heal or repair", "Forecasts": "read what's coming"}
CREED = {"Strength": "strength", "Gain": "gain", "Excellence": "excellence, the work done well", "Pleasure": "pleasure",
         "Thrill": "the thrill of it", "Freedom": "freedom", "Mercy": "mercy", "Justice": "justice", "Kin": "their own people",
         "Faith": "faith", "Order": "order", "Security": "safety", "Nothing": "nothing at all"}
LEANS = [  # trait index, low phrase, high phrase
 (0, "slippery with the truth", "honest to a fault"), (1, "hard to rattle", "feels everything"),
 (2, "reserved", "outgoing"), (3, "cold", "warm"), (4, "careless of rules", "orderly and dutiful"),
 (5, "conventional", "curious and unconventional"), (6, "yielding", "commanding")]
SHIFT = {("Candour", 1): "more honest", ("Candour", -1): "less honest", ("Volatility", 1): "more easily shaken",
         ("Volatility", -1): "steadier", ("Energy", 1): "more outgoing", ("Energy", -1): "more withdrawn",
         ("Warmth", 1): "warmer", ("Warmth", -1): "colder", ("Discipline", 1): "more disciplined",
         ("Discipline", -1): "less disciplined", ("Openness", 1): "more open", ("Openness", -1): "more closed",
         ("Dominance", 1): "more forceful", ("Dominance", -1): "less forceful"}
HUNGER = {"Survival": "food, warmth, health", "Safety": "safety", "Means": "money, work, tools", "Comfort": "rest and ease",
          "Belonging": "belonging", "Standing": "respect", "Selfhood": "being their own person", "Meaning": "meaning"}
PROCESS = {"Numb": "go numb and feel it later", "Expressive": "show it at once", "Devotional": "turn to the old words and rites",
           "Action": "do something about it", "Contained": "hold it in and keep working", "Caretaking": "look after others",
           "Intellectual": "think it through", "Bargaining": "tell themself it can still be undone", "Performed": "perform the right feelings"}
MASK = {"Masked": "shows the world a chosen face", "Borrowed": "wears a self copied from someone else",
        "Shifting": "shows a different face to each audience", "Hollow": "performs feelings without having them",
        "Unanchored": "is certain of a past that may not be theirs"}
TURN = [("news reached them", "news has reached them, by a route they could really have"),
        ("something happened with", "something has happened with someone or something of theirs, offscreen"),
        ("a decision about their drive", "a decision has ripened in them"),
        ("a compulsion or old hunger", "an old urge or hunger has flared"),
        ("they are trying out the other side", "they're trying out the other side of themself"),
        ("something no table covers", "something has shifted in them that will make sense later")]
NUM = re.compile(r"\s*\([^)]*\d[^)]*\)|[+-]?\d+(\.\d+)?%?")


def clean(text):
    return re.sub(r"\s{2,}", " ", NUM.sub("", text or "")).strip(" ;,.")


def thing(x):
    """A habit, urge or thought in plain words (habits can be named after a manner)."""
    if x in SHOWS:
        return SHOWS[x]
    low = {k.lower(): v for k, v in SHOWS.items()}
    return low.get((x or "").lower(), x)


def lower1(t):
    return t[:1].lower() + t[1:] if t else t


def feel_phrase(view):
    word = FEEL.get(view.get("band"), "")
    inten = view.get("intensity")
    return ("%s %s" % (inten, word)).strip() if inten else word


def quirk_phrase(q):
    if q.endswith("(not now)"):
        return None
    if q.endswith("(surfaces)"):
        return "it shows now: " + q[:-len(" (surfaces)")]
    if q.endswith("(more than usual)"):
        return q[:-len(" (more than usual)")] + ", more than usual"
    return q


def person_lines(view, n):
    """How one person comes across, in plain portrayal."""
    out = []
    form = view.get("form")
    shows = SHOWS.get(form, (form or "").lower())
    who = "you" if view.get("who") == "player" else view.get("who")
    out.append("%s toward %s: %s." % (n["name"], who, (feel_phrase(view) + "; " if feel_phrase(view) else "") + shows))
    col = []
    for c in view.get("colour", []):
        if not c:
            continue
        if c.startswith("with a trace of "):
            f2 = c[len("with a trace of "):]
            c = "with a trace of something else: " + SHOWS.get(f2, f2.lower())
        elif c.startswith("a pull toward "):
            f2 = c[len("a pull toward "):]
            c = "a pull toward " + SHOWS.get(f2, f2.lower())
        col.append(clean(c))
    if col:
        out.append("  Colour: " + "; ".join(col) + ".")
    if view.get("speech"):
        out.append("  Speech: " + ", ".join(view["speech"]) + ".")
    if view.get("punctuation"):
        out.append("  On the page: " + "; ".join(view["punctuation"]) + ".")
    tk = view.get("talk")
    if tk:
        out.append("  How they talk: %s; %s, %s." % (tk["keys"], tk["register"], tk["length"]))
        out.append("    Habits of speech: " + "; ".join(tk["habits"]) + ".")
        if tk.get("tone"):
            out.append("    Right now: " + tk["tone"] + ".")
        if tk.get("slang"):
            out.append("    Their slang: " + "; ".join(tk["slang"]) + ". Invent the words to suit the world.")
        for h in tk.get("here", []):
            out.append("    Here: " + h + ".")
        out.append("    With the truth: " + tk["bend"] + ". Never a tell by itself.")
    qs = [x for x in (quirk_phrase(q) for q in view.get("quirks", [])) if x]
    if qs:
        out.append("  Habits of manner: " + "; ".join(qs) + ".")
    th = view.get("thought")
    if th:
        line = "  A thought has come to them: %s. %s. It shows as: %s." % (", and somehow ".join(
            thing(part) for part in th["text"].split(", and somehow ")), th["hold"][0].upper() + th["hold"][1:], th["ripple"])
        if th.get("guess"):
            line += " If they wonder where it came from, they'd guess: %s." % th["guess"]
        out.append(line + " Never narrate the thought itself.")
    if view.get("face") and view.get("core"):
        out.append("  Beneath what shows: %s. Only at or after a lie, and only if pressed or alone with someone they trust."
                   % SHOWS.get(view["core"], view["core"].lower()))
    elif view.get("face_dropped"):
        out.append("  Whatever face they usually wear has dropped.")
    if view.get("violence_steady"):
        out.append("  Violence doesn't change how they come across; it's already part of who they are.")
    if view.get("danger_beat"):
        out.append("  The danger stirs something old in them: a moment of %s." % SHOWS.get(view["danger_beat"], view["danger_beat"].lower()))
    if view.get("stratagem"):
        key = view["stratagem"].split(":")[0].split()[0]
        txt = PLAN.get(key, "")
        if "deception" in view["stratagem"]:
            txt += ", preferring deceit"
        if txt:
            out.append("  " + txt[0].upper() + txt[1:] + ".")
    if view.get("today"):
        out.append("  Their day so far: %s (it may or may not come up)." % view["today"])
    return out


def sheet(n):
    """A character sheet in plain words."""
    E = engine()
    L = ["%s" % n["name"]]
    sk = "; ".join(lower1(E.SBY[v["style"]]["sketch"].rstrip(".")) for v in sorted(n["voices"], key=lambda v: -v["frac"])[:2])
    L.append("  What they're like: " + sk + ".")
    leans = [hi if n["axes"][i] >= 2 else lo for i, lo, hi in LEANS if abs(n["axes"][i]) >= 2]
    if leans:
        L.append("  Noticeably: " + ", ".join(leans) + ".")
    L.append("  In the world: %s; could, if they chose, %s." % (
        STATION.get(n["station"], ""), " or ".join(OFFICE.get(o, o) for o in n["office"])))
    L.append("  Holds above all: %s." % CREED.get(n["creed"], n["creed"]))
    au = n["authenticity"]
    if au["kind"] != "Genuine":
        L.append("  " + MASK.get(au["kind"], "") + (": " + ", ".join(
            E.SBY[f["style"]]["sketch"].rstrip(".").lower() for f in au["faces"]) if au["faces"] else "") + ".")
    dr = n["drive"]
    want = dr["text"]
    want = ("Wants " + want) if not want.startswith("for ") else ("Wants " + want[4:].replace(" to ", " to ", 1))
    if dr["type"] == "Still":
        L.append("  Wants nothing in particular.")
    elif dr["type"] == "Inward":
        L.append("  %s. No outsider could give them this; they'd never ask." % want)
    else:
        L.append("  %s. An outsider could help, %s, but they'd rarely say so." % (
            want, "only in part" if dr.get("shape") != "Full" else "perhaps fully"))
    hungry = [HUNGER[r] for r, v in n["needs"]["state"].items() if v < 0]
    if hungry:
        L.append("  Going without: " + ", ".join(hungry) + ".")
    for t in n["ties"]:
        L.append("  Tied to: %s%s." % (t.get("who") or t["label"], (" (their %s)" % t["role"]) if t.get("role") else ""))
    for c in n["codes"]:
        L.append("  Won't break: %s." % c["code"])
    for c in n["compulsions"]:
        L.append("  A pull toward: %s." % thing(c["urge"]))
    L.append("  When things go wrong, they %s." % PROCESS.get(E.processing(n), "carry on"))
    sp = E.speech_of(n)
    m = E.SPEECH[sp["main"]]
    L.append("  How they talk: %s%s; %s, %s." % (m["keys"], (", with something " + E.SPEECH[sp["side"]]["keys"].split(",")[0]
             + " in it") if sp["side"] else "", E.REG_WORD[sp["reg"]], E.LEN_WORD[m["len"]]))
    L.append("    Habits of speech: " + "; ".join(m["dev"]) + ".")
    if sp["slang"]:
        L.append("    Their slang: " + "; ".join(E.SLANG[x] for x in sp["slang"]) + "." +
                 (" Drops it in front of authority." if sp["switches"] else ""))
    L.append("    With the truth: " + E.BEND[sp["bend"]]["base"] + ".")
    L.append("  Small things: " + "; ".join(n["quirks"]) + ".")
    pair = n["contradiction"]["pair"].split("/")
    L.append("  Torn between: %s and %s." % (pair[0].lower(), pair[1].lower()))
    if n["condition"] != "present":
        L.append("  Now: %s." % n["condition"])
    return "\n".join(L)


# ---------- commands ----------
def cmd_new(a, C):
    E = engine()
    p = C.person(a.name)
    if os.path.exists(p):
        sys.exit("Someone by that name is already in this campaign.")
    dials = E.parse_dials(a.setting or C.dials())
    n = E.build(dials, a.name)
    save(n, p)
    print(sheet(n))


def cmd_sheet(a, C):
    print(sheet(load(C.need(C.person(a.name), "person"))))


def cmd_setting(a, C):
    E = engine()
    w = load(C.world) if os.path.exists(C.world) else {"week": 0, "history": []}
    w["dials"] = E.parse_dials(a.dials)
    save(w, C.world)
    print("The setting is fixed.")


def cmd_week(a, C):
    if not os.path.exists(C.world):
        sys.exit("Fix the setting first (`setting`).")
    v, err = quiet(engine().cmd_tide, world=C.world, dials=None)
    print(err or "A week passes. The times shift a little, or hold.")


def cmd_place(a, C):
    v, err = quiet(engine().cmd_place, file=C.place(a.name), name=a.name, dials=a.setting or C.dials(), add=a.add)
    if err:
        sys.exit(err)
    pl = load(C.place(a.name))
    print("%s: %s" % (pl["name"], "; ".join(f["text"] for f in pl["fixtures"]) or "nothing recorded yet"))
    if pl.get("marks"):
        print("  Since then: " + "; ".join(pl["marks"]))


def cmd_circle(a, C):
    v, err = quiet(engine().cmd_circle, name=a.name, members=[C.need(C.person(m), "person") for m in a.members] or None,
                   dials=C.dials(), save=C.circle(a.name))
    if err:
        sys.exit(err)
    print("%s is formed." % a.name)


def cmd_tie(a, C):
    v, err = quiet(engine().cmd_tie, file=C.need(C.person(a.name), "person"), to=a.to, role=a.role,
                   loyalty=a.loyalty, reach=None, relabel=None)
    print(err or "%s: %s is their %s." % (a.name, a.to, a.role))


def day_lines(view, n):
    out = ["%s, today: %s." % (n["name"], view.get("cause"))]
    states = [k for k in (view.get("lasting") or {}) if k in ("grieving", "sick", "intoxicated", "exhausted")]
    if states:
        out.append("  Carrying: " + ", ".join(states) + ".")
    if view.get("trailing"):
        out.append("  Trails off now and then today (%s)." % view["trailing"])
    for x in view.get("notes", []):
        x2 = day_note(x)
        if x2:
            out.append("  " + x2[0].upper() + x2[1:] + ".")
    return out


def day_note(x):
    """Translate one of the engine's day notes into plain words, or drop it."""
    for (ax, sg), word in SHIFT.items():
        if x.startswith(ax + " shifts"):
            return "something in them has changed: " + word
    m = re.match(r"three weeks starved of (\w+)", x)
    if m:
        return "going without %s for weeks has made it matter more to them" % HUNGER.get(m.group(1), "something")
    m = re.match(r"compulsion '(.+)' at threshold", x)
    if m:
        return "the pull of %s will win at the next real chance" % thing(m.group(1))
    m = re.match(r"code '(.+)' at risk", x)
    if m:
        return "their rule (%s) could break, if it came to it" % m.group(1)
    m = re.match(r"craving (.+): three days without it", x)
    if m:
        return "craving %s: three days without it" % thing(m.group(1))
    if x.startswith("craving "):
        return clean(x)
    if x.startswith("what they didn't feel at the time arrives now"):
        return "what they didn't feel at the time arrives now"
    if x.startswith("clarity"):
        return "a moment of clarity: unusually clear and unhurried for a few days"
    if x.startswith("authenticity drifted"):
        return "something has changed in how they present themselves"
    if "has become part of who they are" in x:
        return "a change in them has settled into who they are"
    if "has become a habit" in x:
        return "something they keep doing has become a habit"
    if "has become a compulsion" in x or "grows stronger" in x:
        return "a habit has a hold on them now"
    return None


def cmd_day(a, C):
    E = engine()
    people = [C.need(C.person(x), "person") for x in a.names] if a.names else C.everyone()
    circles = {}
    for p in people:
        n = load(p)
        if n["condition"] == "dead":
            continue
        circ = None
        for cf in os.listdir(os.path.join(C.root, "circles")):
            cp = os.path.join(C.root, "circles", cf)
            if n["name"] in load(cp).get("members", []):
                circ = cp
                if cp not in circles:
                    quiet(E.cmd_day, file=cp, world=C.world if os.path.exists(C.world) else None, circle=None)
                    circles[cp] = True
                break
        v, err = quiet(E.cmd_day, file=p, world=C.world if os.path.exists(C.world) else None, circle=circ)
        if err:
            print(err)
            continue
        print("\n".join(day_lines(v, load(p))))


def band_attitude(band):
    return "warm" if band in ("Warm", "Kind") else "hostile" if band in ("Cool", "Hostile") else None


def cmd_round(a, C):
    """A whole room, worked out in order: the scene, the one who leads, how their mood carries,
    then everyone else."""
    E = engine()
    paths = [C.need(C.person(x), "person") for x in a.present]
    to = a.to or "player"
    place = C.need(C.place(a.place), "place") if a.place else None
    circle = C.need(C.circle(a.circle), "circle") if a.circle else None
    sv, err = quiet(E.cmd_scene, files=paths, world=C.world if os.path.exists(C.world) else None, place=place,
                    circle=circle, present=[to] + (a.others or []), danger=a.danger or [], prose=a.prose or "",
                    seal=C.record)
    if err:
        sys.exit(err)
    live = [p for p in paths if load(p)["condition"] not in ("dead", "comatose")]
    names = {p: load(p)["name"] for p in live}
    by_name = {v: k for k, v in names.items()}
    lead, loud = sv.get("lead"), sv.get("loud")
    spread = set(sv.get("spread_to") or [])
    hurt = set(h.lower() for h in (a.hurt or []))
    per_flags, per_app = parse_per_person(a)
    lines = []
    if a.prose is None and place:
        pl = load(place)
        lines.append("The place: " + "; ".join(f["text"] for f in pl.get("fixtures", [])[:6]) +
                     (("; and since then, " + "; ".join(pl["marks"][-3:])) if pl.get("marks") else "") + ".")

    def meet(path, lead_att=None, rival=False, contagion=None, who=None, look=False):
        n = load(path)
        mine = per_flags.get(n["name"].lower(), set())
        kw = dict(file=path, who=who or to, approach=None if who else per_app.get(n["name"].lower(), a.approach),
                  creed=None if who else a.creed, lead=lead_att, rival_of_lead=rival,
                  contagion=contagion, danger=a.danger or [], audience=a.public or "public" in mine,
                  opposed=(a.opposed or "opposed" in mine) and not who, their_strength=a.their_strength,
                  ground=1 if (n["name"].lower() in home) else 0,
                  hurt=n["name"].lower() in hurt or "hurt" in mine, violence=a.violence,
                  victim=a.victim, attacker=a.attacker, symbol=a.symbol, circle=circle, dry_run=look or a.look)
        for fl in FLAGS:
            kw[fl] = getattr(a, fl, False) or fl in mine
        return quiet(E.cmd_meet, **kw)

    home = set(h.lower() for h in (a.home or []))

    results = {}
    if lead in by_name:
        results[lead] = meet(by_name[lead])
    att = band_attitude(results.get(lead, ({}, None))[0].get("band")) if lead in results else None
    if loud in by_name and loud not in results:
        results[loud] = meet(by_name[loud], att, rival=is_rival(load(by_name[loud]), lead))
    cont = None
    if loud in results:
        b = results[loud][0].get("band")
        cont = 1 if b in ("Warm", "Kind") else -1 if b in ("Cool", "Hostile") else None
    for p in live:
        nm = names[p]
        if nm in results:
            continue
        results[nm] = meet(p, att, rival=is_rival(load(p), lead), contagion=cont if nm in spread else None)
    if sv.get("absent"):
        lines.append("Not taking part: %s." % ", ".join(sv["absent"]))
    if lead and len(live) > 1:
        lines.append("%s holds the room; the others take their lead from them, or set themselves against them." % lead)
    for p in live:
        nm = names[p]
        v, e = results.get(nm, ({}, None))
        if e:
            lines.append("%s: %s" % (nm, e))
            continue
        lines += person_lines(v, load(p))
    if len(live) > 1 and not a.no_between:
        between = []
        pairs = [(p1, p2) for p1 in live for p2 in live if p1 != p2][:a.max_pairs]
        for p1, p2 in pairs:
            n1, n2 = load(p1), load(p2)
            if n2["name"] not in n1["trust"]:
                rv, _ = quiet(E.cmd_affinity, a=p1, b=p2, tie=tie_role(n1, n2["name"]))
                n1["trust"][n2["name"]] = {"bedrock": clamp(rv.get("regard", 0), -5, 5), "surface": 0}
                save(n1, p1)
            v2, e2 = meet(p1, who=n2["name"], look=True)
            if not e2 and v2:
                between.append("  %s toward %s: %s." % (n1["name"], n2["name"],
                               (feel_phrase(v2) + "; " if feel_phrase(v2) else "") + thing(v2.get("form", ""))))
        if between:
            lines.append("Between them (show it in how they deal with each other, never say it):")
            lines += between
    ht = sv.get("hidden_turn")
    if ht:
        what = next((plain for key, plain in TURN if ht["what"].startswith(key)), "something has shifted in them")
        lines.append("Offscreen, for %s: %s. Let it show in what they do; never explain it." % (ht["name"], what))
    for s in sv.get("slips") or []:
        lines.append("If %s is pressed, or alone with someone they trust, and only after a lie: what's beneath may show for a moment." % s)
    if sv.get("oddity"):
        lines.append("Something odd, from %s: %s. Leave it unexplained." % (sv["oddity"]["name"], sv["oddity"]["what"]))
    print("\n".join(lines))


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def tie_role(n, other):
    for t in n["ties"]:
        if (t.get("who") or "") == other and t.get("role") in ("kin", "lover", "friend", "mentor", "rival", "enemy",
                                                                 "creditor", "debtor", "master", "dependant"):
            return t["role"]
    for t in n["ties"]:
        if (t.get("who") or "") == other:
            return {"child": "kin", "parent": "kin", "sibling": "kin", "spouse": "lover", "student": "dependant",
                    "subordinate": "dependant", "follower": "dependant", "spiritual": "mentor"}.get(t.get("role"))
    return None


def parse_per_person(a):
    flags, apps = {}, {}
    ok = set(FLAGS) | {"public", "opposed", "hurt"}
    for item in a.as_ or []:
        name, _, rest = item.rpartition(":")
        if not name:
            sys.exit('--as takes "Name:flag,flag" (flags: %s)' % ", ".join(sorted(ok)))
        fs = set(x.strip().lower() for x in rest.split(",") if x.strip())
        bad = fs - ok
        if bad:
            sys.exit("Unknown condition for %s: %s. Use: %s" % (name, ", ".join(sorted(bad)), ", ".join(sorted(ok))))
        flags.setdefault(name.strip().lower(), set()).update(fs)
    for item in a.treat or []:
        name, _, app = item.rpartition(":")
        app = app.strip().lower()
        if not name or app not in APPROACHES:
            sys.exit('--treat takes "Name:approach" (approaches: %s)' % ", ".join(APPROACHES))
        apps[name.strip().lower()] = app
    return flags, apps


def is_rival(n, lead):
    return bool(lead) and any((t.get("who") or "") == lead and t.get("role") in ("rival", "enemy") for t in n["ties"])


def cmd_violence(a, C):
    E = engine()
    paths = [C.need(C.person(x), "person") for x in a.present]
    place = C.need(C.place(a.place), "place") if a.place else None
    v, err = quiet(E.cmd_violence, files=paths, world=C.world if os.path.exists(C.world) else None, dials=None,
                   hurt=a.hurt or [], place=place, victim=a.victim, attacker=a.attacker, symbol=a.symbol,
                   circle=C.circle(a.circle) if a.circle else None, record=True)
    if err:
        sys.exit(err)
    L = ["How to write it: " + E.REGISTERS[v["register"]]]
    for d_ in v["dissonance"]:
        L.append("Somewhere in it, unexplained: " + d_ + ".")
    L.append("After: " + v["aftermath"] + ".")
    if v.get("keeps"):
        L.append("The place will keep: " + v["keeps"] + ".")
    for r in v["responses"]:
        rel = ("; " + "; ".join(r["relations"])) if r["relations"] else ""
        L.append("%s%s: %s.%s" % (r["name"], rel, r["desc"], " Outwardly they stay as they were." if r["steady"]
                                   else " This changes how they come across for the rest of the day."))
    if v.get("absent"):
        L.append("Not responding: %s." % ", ".join(v["absent"]))
    L.append("Show all of it through the senses. Name no one's feelings.")
    print("\n".join(L))


def cmd_event(a, C):
    E = engine()
    p = C.need(C.person(a.name), "person")
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            E.cmd_event(types.SimpleNamespace(file=p, kind=a.kind, who=a.to or "player", size=2 if a.big else None,
                                              trade=a.trade, note=a.note, about=a.about))
    except SystemExit as e:
        sys.exit(str(e))
    text = out.getvalue()
    L = ["%s will remember this." % load(p)["name"]]
    for (ax, sg), word in SHIFT.items():
        if "%s shifts %+d" % (ax, sg) in text:
            L.append("It has changed them: %s." % word)
    for phrase, plain in (("refuses charity", "They won't take charity; a fair trade would have landed."),
                          ("takes it as owed", "They take it as owed."),
                          ("resents being helped", "They accept it, and resent being helped."),
                          ("performs gratitude", "They perform gratitude."),
                          ("grieving for", "They are grieving."), ("numb: grief arrives", "They seem to carry on as if nothing happened, for now."),
                          ("an enemy gone", "No grief: whatever they show about it, they show plainly."),
                          ("used to", "They're used to this by now; it lands lighter than it once did."),
                          ("clarity", "They are unusually clear for a while.")):
        if phrase in text:
            L.append(plain)
    print(" ".join(L))


def cmd_habit(a, C):
    E = engine()
    p = C.need(C.person(a.name), "person")
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            E.cmd_habit(types.SimpleNamespace(file=p, act=a.act, times=a.times))
    except SystemExit as e:
        sys.exit(str(e))
    t = out.getvalue()
    L = ["Noted."]
    if "has become a habit" in t: L.append("It has become a habit of theirs.")
    if "has become a compulsion" in t or "grows stronger" in t: L.append("It has a hold on them now.")
    if "satisfies less" in t: L.append("It satisfies them less than it did; they reach for more.")
    for (ax, sg), word in SHIFT.items():
        if "%s shifts %+d" % (ax, sg) in t:
            L.append("It has changed them: %s." % word)
    print(" ".join(L))


def cmd_ask(a, C):
    E = engine()
    v, err = quiet(E.cmd_ask, file=C.need(C.person(a.name), "person"), who=a.to or "player", touched=a.touched,
                   asked=a.already)
    if err:
        sys.exit(err)
    nm = load(C.person(a.name))["name"]
    if v.get("result") == "may":
        print("%s may ask for help with this: %s.%s Pride or a principle may still stop them." % (
            nm, v["text"], " Only part of it is anyone else's to do." if v.get("shape") != "Full" else ""))
    elif v.get("result") == "hint":
        print("%s won't ask, but may let slip an oblique remark touching on: %s." % (nm, v["text"]))
    else:
        print("%s won't ask anything of anyone now." % nm)


def cmd_status(a, C):
    v, err = quiet(engine().cmd_status, file=C.need(C.person(a.name), "person"), condition=a.condition, restore=a.restore)
    print(err or "%s is now %s." % (a.name, a.condition))


def cmd_save(a, C):
    import zipfile
    out = a.file if a.file.endswith(".zip") else a.file + ".zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(C.root):
            for f in files:
                full = os.path.join(root, f)
                z.write(full, os.path.relpath(full, C.root))
    print("Campaign saved to %s. Keep it; load it next time to carry on." % out)


def cmd_load(a, C):
    import zipfile
    if not os.path.exists(a.file):
        sys.exit("No such file: %s" % a.file)
    with zipfile.ZipFile(a.file) as z:
        for m in z.namelist():
            if m.startswith("/") or ".." in m.split("/"):
                sys.exit("That archive isn't a campaign.")
        if any(os.listdir(os.path.join(C.root, d)) for d in ("cast", "places", "circles")) and not a.replace:
            sys.exit("This campaign folder already has people in it. Use --replace to overwrite it.")
        z.extractall(C.root)
    print("Campaign loaded. Everyone remembers where they were.")


def main():
    ap = argparse.ArgumentParser(description="The Chamber of Output: plain briefs for roleplay narration")
    ap.add_argument("--campaign", default=os.environ.get("CHAMBER_CAMPAIGN", "campaign"))
    sp = ap.add_subparsers(dest="cmd")
    x = sp.add_parser("setting"); x.add_argument("dials", help="Violence,Order,Scarcity,Strangeness,Faith,Power,Deceit, 0-3 each"); x.set_defaults(f=cmd_setting)
    x = sp.add_parser("week"); x.set_defaults(f=cmd_week)
    x = sp.add_parser("new"); x.add_argument("name"); x.add_argument("--setting"); x.set_defaults(f=cmd_new)
    x = sp.add_parser("sheet"); x.add_argument("name"); x.set_defaults(f=cmd_sheet)
    x = sp.add_parser("place"); x.add_argument("name"); x.add_argument("--add", nargs="*"); x.add_argument("--setting")
    x.set_defaults(f=cmd_place)
    x = sp.add_parser("circle"); x.add_argument("name"); x.add_argument("--members", nargs="*", default=[]); x.set_defaults(f=cmd_circle)
    x = sp.add_parser("tie"); x.add_argument("name"); x.add_argument("--to", required=True)
    x.add_argument("--role", required=True, choices=ROLES); x.add_argument("--loyalty", type=int, choices=range(1, 7))
    x.set_defaults(f=cmd_tie)
    x = sp.add_parser("day"); x.add_argument("names", nargs="*"); x.set_defaults(f=cmd_day)
    x = sp.add_parser("round"); x.add_argument("present", nargs="+"); x.add_argument("--to")
    x.add_argument("--others", nargs="*"); x.add_argument("--place"); x.add_argument("--circle")
    x.add_argument("--approach", choices=APPROACHES); x.add_argument("--creed", choices=["aligned", "opposed"])
    x.add_argument("--danger", nargs="*", choices=DANGER); x.add_argument("--prose"); x.add_argument("--public", action="store_true")
    x.add_argument("--opposed", action="store_true"); x.add_argument("--their-strength", type=int, default=2)
    x.add_argument("--hurt", nargs="*"); x.add_argument("--violence", action="store_true")
    x.add_argument("--victim"); x.add_argument("--attacker")
    x.add_argument("--as", dest="as_", nargs="*", metavar="NAME:CONDITIONS",
                   help='conditions for one person only, e.g. "Tomas Coyle:drunk,grieving"')
    x.add_argument("--treat", nargs="*", metavar="NAME:APPROACH",
                   help='how the player treats one person, e.g. "Mairead Coyle:pity"')
    x.add_argument("--home", nargs="*", metavar="NAME", help="people on their own ground")
    x.add_argument("--symbol", choices=["Strength", "Gain", "Excellence", "Pleasure", "Thrill", "Freedom", "Mercy",
                                        "Justice", "Kin", "Faith", "Order", "Security"],
                   help="what the victim of violence stood for, if anything")
    x.add_argument("--look", action="store_true", help="see how they'd come across without it counting")
    x.add_argument("--no-between", action="store_true", help="leave out how they treat each other")
    x.add_argument("--max-pairs", type=int, default=12)
    for fl in FLAGS:
        x.add_argument("--" + fl, action="store_true")
    x.set_defaults(f=cmd_round)
    x = sp.add_parser("violence"); x.add_argument("present", nargs="+"); x.add_argument("--place")
    x.add_argument("--victim"); x.add_argument("--attacker"); x.add_argument("--hurt", nargs="*"); x.add_argument("--circle")
    x.add_argument("--symbol", choices=["Strength", "Gain", "Excellence", "Pleasure", "Thrill", "Freedom", "Mercy",
                                        "Justice", "Kin", "Faith", "Order", "Security"])
    x.set_defaults(f=cmd_violence)
    x = sp.add_parser("save"); x.add_argument("file"); x.set_defaults(f=cmd_save)
    x = sp.add_parser("load"); x.add_argument("file"); x.add_argument("--replace", action="store_true")
    x.set_defaults(f=cmd_load)
    x = sp.add_parser("event"); x.add_argument("name"); x.add_argument("kind", choices=EVENTS); x.add_argument("--to")
    x.add_argument("--about"); x.add_argument("--big", action="store_true"); x.add_argument("--trade", action="store_true")
    x.add_argument("--note"); x.set_defaults(f=cmd_event)
    x = sp.add_parser("habit"); x.add_argument("name"); x.add_argument("act"); x.add_argument("--times", type=int, default=1)
    x.set_defaults(f=cmd_habit)
    x = sp.add_parser("ask"); x.add_argument("name"); x.add_argument("--to"); x.add_argument("--touched", action="store_true")
    x.add_argument("--already", action="store_true"); x.set_defaults(f=cmd_ask)
    x = sp.add_parser("status"); x.add_argument("name"); x.add_argument("condition", choices=["present", "dead", "comatose", "amnesiac"])
    x.add_argument("--restore", action="store_true"); x.set_defaults(f=cmd_status)
    a = ap.parse_args()
    if not getattr(a, "f", None):
        ap.print_help(); return
    a.f(a, Campaign(a.campaign))


if __name__ == "__main__":
    main()
