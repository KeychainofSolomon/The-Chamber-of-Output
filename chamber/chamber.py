#!/usr/bin/env python3
"""The Chamber of Output: run a roleplay campaign's people and places, and get back plain briefs.

The engine that decides who people are and how they react is sealed inside this folder
(engine.bin, pinned by engine.lock). This program drives it and translates everything it says
into plain portrayal: how someone comes across, what shows, what is left in the world to notice.
No numbers, no workings. Python 3.8+, standard library only.
"""
import argparse, base64, hashlib, io, json, os, random, re, sys, types, zlib, contextlib

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


_READONLY = [False]


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
    if _READONLY[0]:
        return
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
            line += " If they wonder where it came from, they'd guess: %s." % ("you" if th["guess"] == "player" else th["guess"])
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
    if view.get("under_strain"):
        out.append("  Under strain, as always: " + view["under_strain"] + ".")
    for c in view.get("carried") or []:
        out.append("  Carries from before with %s: %s%s." % (who, EVENT_WORDS.get(c["event"], c["event"]),
                   ("; at the time, " + E_STRAIN().get(c["took"], "")) if c.get("took") else ""))
    for b in view.get("believes") or []:
        out.append("  Believes about %s: %s Speak only from this; it may be wrong." % (who, b))
    if view.get("business"):
        out.append("  Ordinary business, meaning nothing: " + view["business"] + ".")
    if view.get("mishear"):
        out.append("  An honest misunderstanding this scene: " + view["mishear"] + ". It can be cleared up; nothing more to it.")
    if view.get("today"):
        out.append("  Their day so far: %s (it may or may not come up)." % view["today"])
    return out


def E_STRAIN():
    return engine().STRAIN_WAYS


EVENT_WORDS = {"kindness": "a kindness", "rescue": "being rescued", "gift": "a gift", "respect": "being shown respect",
               "betrayal": "a betrayal", "humiliation": "a humiliation", "threat": "a threat",
               "lie-caught": "a lie they caught", "triumph": "a triumph", "loss": "a loss", "code-broken": "a line they crossed",
               "fell-ill": "an illness", "intoxicated": "a night's drinking", "reunion": "a reunion", "joy": "a good time",
               "witnessed": "something they saw"}


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
    w["schema"] = CHAMBER_SCHEMA
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


INVERSE_ROLE = {"child": "parent", "parent": "child", "sibling": "sibling", "spouse": "spouse", "lover": "lover",
                "kin": "kin", "friend": "friend", "student": "mentor", "mentor": "student", "master": "subordinate",
                "subordinate": "master", "comrade": "comrade", "rival": "rival", "enemy": "enemy",
                "creditor": "debtor", "debtor": "creditor"}


def cmd_tie(a, C):
    """Name a relationship. Kinship, marriage, friendship and the like run both ways unless --one-way:
    the other person gets the matching tie, with their own loyalty rolled if none is given."""
    me = C.need(C.person(a.name), "person")
    if C.slug(a.name) == C.slug(a.to):
        sys.exit("Someone can't be tied to themself.")
    v, err = quiet(engine().cmd_tie, file=me, to=a.to, role=a.role, loyalty=a.loyalty, reach=None, relabel=None)
    if err:
        sys.exit(err)
    msg = "%s: %s is their %s." % (a.name, a.to, a.role)
    other = C.person(a.to)
    inv = INVERSE_ROLE.get(a.role)
    if inv and not a.one_way and os.path.exists(other):
        n2 = load(other)
        if not any((t.get("who") or "").lower() == a.name.lower() for t in n2["ties"]):
            quiet(engine().cmd_tie, file=other, to=load(me)["name"], role=inv, loyalty=None, reach=None, relabel=None)
            msg += " And %s is %s's %s." % (a.name, n2["name"], inv)
    print(msg)


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
    m = re.match(r"an old memory came back to them today: the ([\w-]+)(, on its anniversary)?", x)
    if m:
        return "an old memory came back to them today: %s%s" % (EVENT_WORDS.get(m.group(1), "something from before"),
                                                               ", on its anniversary" if m.group(2) else "")
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
    seen_, present = set(), []
    for x in a.present:
        if C.slug(x) not in seen_:
            seen_.add(C.slug(x)); present.append(x)
    paths = [C.need(C.person(x), "person") for x in present]
    to = a.to or "player"
    place = C.need(C.place(a.place), "place") if a.place else None
    circle = C.need(C.circle(a.circle), "circle") if a.circle else None
    sv, err = quiet(E.cmd_scene, files=paths, world=C.world if os.path.exists(C.world) else None, place=place,
                    circle=circle, present=[to] + (a.others or []), danger=a.danger or [], prose=a.prose or "",
                    seal=None if a.look else C.record)
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
    gone = ["%s (%s)" % (load(p)["name"], load(p)["condition"]) for p in paths if p not in live]
    if gone:
        lines.append("Not taking part: %s. Nobody present can see or hear them act." % ", ".join(gone))
    elif sv.get("absent"):
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
        od = sv["oddity"]
        lines.append("Something odd, from %s: %s. %s" % (od["name"], od["what"], "It has an ordinary reason nobody will mention; don't build on it."
                                                         if od.get("mundane") else "Leave it unexplained."))
    print("\n".join(lines))
    if not a.look:
        bp = os.path.join(C.root, "record", "briefs.jsonl")
        kept = _lines(bp)[-19:] + [{"text": "\n".join(lines)}]
        with open(bp, "w", encoding="utf-8") as fh:
            fh.write("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in kept))


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
    paths = list(dict.fromkeys(C.need(C.person(x), "person") for x in a.present))
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
    took = engine().VIEW.get("took_text")
    L = ["%s will remember this." % load(p)["name"]]
    if took:
        L.append("How they take it, as they always do: %s." % took)
    for (ax, sg), word in SHIFT.items():
        if "%s shifts %+d" % (ax, sg) in text:
            L.append("It has changed them: %s." % word)
    for phrase, plain in (("refuses charity", "They won't take charity; a fair trade would have landed."),
                          ("takes it as owed", "They take it as owed."),
                          ("resents being helped", "They accept it, and resent being helped."),
                          ("performs gratitude", "They perform gratitude."),
                          ("grieving for", "They are grieving."), ("numb: grief arrives", "They seem to carry on as if nothing happened, for now."),
                          ("an enemy gone", "No grief: whatever they show about it, they show plainly."),
                          ("not a grief of their own", "No grief of their own: they're sobered for a while, no more."),
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
    _append(os.path.join(C.root, "record", "asks.jsonl"), {"name": nm, "result": v.get("result")})
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


# ---------- carrying a campaign between sessions ----------
# A campaign archive may only hold the campaign's own files, in its own layout, within size limits,
# with no links, and with every file readable as what it claims to be. Loading builds the new
# campaign aside and swaps it in whole; nothing of the old one survives a replace, and a bad archive
# changes nothing.
ARCHIVE_MAX = 50 * 1024 * 1024          # the archive itself
UNPACKED_MAX = 200 * 1024 * 1024        # everything in it, unpacked
FILE_MAX = 10 * 1024 * 1024             # any one file, unpacked
FILES_MAX = 5000
RATIO_MAX = 200                         # unpacked size over packed size, per file
MEMBER = re.compile(r"^(world\.json|(cast|places|circles)/[\w-]{1,120}\.json|record/[\w.-]{1,120}\.jsonl)$")


def _campaign_files(root):
    """The campaign's own files: right layout, regular files, never links, never outside the folder."""
    real_root = os.path.realpath(root)
    keep, skipped = [], 0
    for dirpath, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(dirpath, d))]
        for f in files:
            full = os.path.join(dirpath, f)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if (os.path.islink(full) or not os.path.isfile(full) or not MEMBER.match(rel)
                    or os.path.commonpath([real_root, os.path.realpath(full)]) != real_root):
                skipped += 1
                continue
            keep.append((full, rel))
    return keep, skipped


def cmd_save(a, C):
    import zipfile
    out = a.file if a.file.endswith(".zip") else a.file + ".zip"
    real_root = os.path.realpath(C.root)
    if os.path.commonpath([real_root, os.path.realpath(os.path.abspath(out))]) == real_root:
        sys.exit("Save it somewhere outside the campaign folder.")
    keep, skipped = _campaign_files(C.root)
    if len(keep) > FILES_MAX or sum(os.path.getsize(f) for f, _ in keep) > UNPACKED_MAX:
        sys.exit("This campaign is too large to save as one archive.")
    tmp = out + ".partial"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for full, rel in keep:
            with open(full, "rb") as fh:
                z.writestr(rel, fh.read())
    os.replace(tmp, out)
    print("Campaign saved to %s. Keep it; load it next time to carry on.%s" % (
        out, " (Left out some files that aren't part of a campaign.)" if skipped else ""))


def _valid(rel, data):
    """Each file must be what its place in the layout says it is."""
    try:
        text = data.decode("utf-8")
        if rel.endswith(".jsonl"):
            for line in text.splitlines():
                if line.strip() and not isinstance(json.loads(line), dict):
                    return False
            return True
        obj = json.loads(text)
    except (UnicodeDecodeError, ValueError):
        return False
    if not isinstance(obj, dict):
        return False
    if rel == "world.json":
        dl = obj.get("dials")
        return isinstance(dl, list) and len(dl) == 7 and all(isinstance(x, int) and 0 <= x <= 3 for x in dl)
    if rel.startswith("cast/"):
        ax = obj.get("axes")
        return (isinstance(obj.get("name"), str) and isinstance(ax, list) and len(ax) == 7
                and all(isinstance(x, int) and -3 <= x <= 3 for x in ax)
                and isinstance(obj.get("voices"), list) and obj["voices"]
                and isinstance(obj.get("needs"), dict) and isinstance(obj.get("condition"), str))
    return isinstance(obj.get("name"), str)


def cmd_load(a, C):
    import shutil, stat, tempfile, zipfile
    if not os.path.isfile(a.file):
        sys.exit("No such file: %s" % a.file)
    if os.path.getsize(a.file) > ARCHIVE_MAX:
        sys.exit("That archive is too large to be a campaign.")
    if not zipfile.is_zipfile(a.file):
        sys.exit("That archive isn't a campaign.")
    has_state = os.path.exists(C.world) or any(os.listdir(os.path.join(C.root, d)) for d in ("cast", "places", "circles"))
    if has_state and not a.replace:
        sys.exit("This campaign folder already has people in it. Use --replace to overwrite it.")
    files, total = {}, 0
    with zipfile.ZipFile(a.file) as z:
        infos = z.infolist()
        if len(infos) > FILES_MAX:
            sys.exit("That archive has too many files to be a campaign.")
        for info in infos:
            name = info.filename
            if info.is_dir():
                continue
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode) or not MEMBER.match(name) or name in files:
                sys.exit("That archive isn't a campaign.")
            if info.file_size > FILE_MAX or (info.compress_size and info.file_size / info.compress_size > RATIO_MAX
                                             and info.file_size > 1024 * 1024):
                sys.exit("That archive holds a file too large to be part of a campaign.")
            with z.open(info) as fh:
                data = fh.read(FILE_MAX + 1)
            total += len(data)
            if len(data) > FILE_MAX or total > UNPACKED_MAX:
                sys.exit("That archive is too large to be a campaign.")
            if not _valid(name, data):
                sys.exit("That archive isn't a campaign: %s doesn't read as one." % name)
            files[name] = data
    if not any(n.startswith("cast/") for n in files) and "world.json" not in files:
        sys.exit("That archive isn't a campaign: there's nobody in it.")
    root = os.path.abspath(C.root)
    parent = os.path.dirname(root)
    fresh = tempfile.mkdtemp(prefix=".incoming-", dir=parent)
    try:
        for sub in ("cast", "places", "circles", "record"):
            os.makedirs(os.path.join(fresh, sub))
        for name, data in files.items():
            with open(os.path.join(fresh, *name.split("/")), "wb") as fh:
                fh.write(data)
        old = None
        if os.path.exists(root):
            old = tempfile.mkdtemp(prefix=".outgoing-", dir=parent)
            os.rmdir(old)
            os.rename(root, old)
        try:
            os.rename(fresh, root)
        except OSError:
            if old:
                os.rename(old, root)
            raise
        fresh = None
        if old:
            shutil.rmtree(old, ignore_errors=True)
    finally:
        if fresh:
            shutil.rmtree(fresh, ignore_errors=True)
    print("Campaign loaded. Everyone remembers where they were.")



# ---------- schema, identity, backups, recovery ----------
CHAMBER_SCHEMA = 2
NOT_STATE = ("record/journal.jsonl", "record/narration.jsonl", "record/briefs.jsonl", "record/asks.jsonl")


def state_hash(root):
    """A fingerprint of the campaign's simulated state (not the journal or the narration log)."""
    h = hashlib.sha256()
    for full, rel in sorted(_campaign_files(root)[0], key=lambda x: x[1]):
        if rel in NOT_STATE:
            continue
        h.update(rel.encode())
        with open(full, "rb") as fh:
            h.update(fh.read())
    return h.hexdigest()[:16]


def write_archive(root, out):
    import zipfile
    keep, skipped = _campaign_files(root)
    tmp = out + ".partial"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for full, rel in keep:
            with open(full, "rb") as fh:
                z.writestr(rel, fh.read())
    os.replace(tmp, out)
    return skipped


def backups_dir(C):
    return os.path.abspath(C.root).rstrip(os.sep) + ".backups"


def auto_backup(C, why, rotate=True):
    if not (os.path.exists(C.world) or C.everyone()):
        return
    import time
    d = backups_dir(C)
    os.makedirs(d, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    seq = 1 + max([int(f.split("-", 1)[0]) for f in os.listdir(d) if f.endswith(".zip") and f.split("-", 1)[0].isdigit()] or [0])
    out = os.path.join(d, "%06d-%s-%s.zip" % (seq, stamp, why))   # numbered first, so order never depends on the clock
    write_archive(C.root, out)
    old = sorted(f for f in os.listdir(d) if f.endswith(".zip")) if rotate else []
    for f in old[:-8]:
        os.remove(os.path.join(d, f))


def cmd_backups(a, C):
    d = backups_dir(C)
    fs = sorted(f for f in os.listdir(d) if f.endswith(".zip")) if os.path.isdir(d) else []
    print("\n".join(fs) if fs else "No automatic backups yet.")


def cmd_restore(a, C):
    d = backups_dir(C)
    fs = sorted(f for f in os.listdir(d) if f.endswith(".zip")) if os.path.isdir(d) else []
    if not fs:
        sys.exit("No automatic backups to restore.")
    pick = a.which or fs[-1]
    if pick not in fs:
        sys.exit("No backup by that name. Run `backups` to see them.")
    a.file, a.replace = os.path.join(d, pick), True
    cmd_load(a, C)
    print("Restored from %s." % pick)


def cmd_rename(a, C):
    """A new name, the same person: the id never changes, and everyone's memory follows."""
    E = engine()
    src = C.need(C.person(a.old), "person")
    dst = C.person(a.new)
    if os.path.exists(dst):
        sys.exit("Someone by that name is already in this campaign.")
    n = load(src)
    old = n["name"]
    n["name"] = a.new
    E.migrate(n)
    save(n, dst)
    os.remove(src)
    for p in C.everyone() + [os.path.join(C.root, "circles", f) for f in os.listdir(os.path.join(C.root, "circles"))]:
        x = load(p)
        changed = False
        for t in x.get("ties", []):
            if t.get("who") == old:
                t["who"] = a.new; changed = True
        if old in x.get("trust", {}):
            x["trust"][a.new] = x["trust"].pop(old); changed = True
        for m in x.get("memory", []):
            if m.get("with") == old:
                m["with"] = a.new; changed = True
        for b in x.get("knows", []):
            if b.get("from") == old:
                b["from"] = a.new; changed = True
            if b.get("subject") == old:
                b["subject"] = a.new; changed = True
            if old in b.get("also_from", []):
                b["also_from"] = [a.new if y == old else y for y in b["also_from"]]; changed = True
        if old in x.get("members", []):
            x["members"] = [a.new if y == old else y for y in x["members"]]; changed = True
        if changed:
            save(x, p)
    print("%s is now known as %s; the same person, remembered by everyone as such." % (old, a.new))


def cmd_migrate(a, C):
    E = engine()
    k = 0
    for p in C.everyone() + [os.path.join(C.root, "circles", f) for f in os.listdir(os.path.join(C.root, "circles"))]:
        x = load(p)
        before = json.dumps(x, sort_keys=True)
        E.migrate(x)
        if json.dumps(x, sort_keys=True) != before:
            save(x, p); k += 1
    if os.path.exists(C.world):
        w = load(C.world)
        if w.get("schema") != CHAMBER_SCHEMA:
            w["schema"] = CHAMBER_SCHEMA; save(w, C.world); k += 1
    print("Campaign is up to date%s." % (" (%d files brought forward; nobody changed who they are)" % k if k else ""))


def cmd_doctor(a, C):
    """Check every file; with --fix, set aside what can't be read and repair what can be."""
    import shutil
    E = engine()
    problems, fixed = [], []
    keep, skipped = _campaign_files(C.root)
    ids = {}
    names = set()
    for full, rel in keep:
        with open(full, "rb") as fh:
            data = fh.read()
        if not _valid(rel, data):
            problems.append("%s can't be read as part of a campaign" % rel)
            if a.fix:
                q = os.path.abspath(C.root).rstrip(os.sep) + ".quarantine"
                os.makedirs(q, exist_ok=True)
                shutil.move(full, os.path.join(q, rel.replace("/", "__")))
                fixed.append("set aside " + rel)
            continue
        if rel.startswith("cast/"):
            x = json.loads(data.decode("utf-8"))
            names.add(x["name"])
            pid = x.get("id")
            if pid and pid in ids:
                problems.append("%s and %s share an identity" % (ids[pid], rel))
                if a.fix:
                    x["id"] = E.new_id(); save(x, full); fixed.append("gave %s its own identity" % rel)
            ids[pid] = rel
    for p in [os.path.join(C.root, "circles", f) for f in os.listdir(os.path.join(C.root, "circles"))]:
        try:
            c = load(p)
        except ValueError:
            continue
        gone = [m for m in c.get("members", []) if m not in names]
        if gone:
            problems.append("%s lists people not in the campaign: %s" % (os.path.basename(p), ", ".join(gone)))
    if skipped:
        problems.append("%d stray file(s) in the campaign folder (left out of saves)" % skipped)
    print("\n".join(["Campaign check:"] + ["  " + x for x in problems] + ["  Fixed: " + x for x in fixed])
          if problems else "Campaign check: everything reads as it should.")


# ---------- the journal and deterministic replay ----------
MUTATING = {"setting", "week", "new", "place", "circle", "tie", "day", "round", "violence", "event", "habit",
            "status", "rename", "migrate", "fact", "learn", "tell", "spread", "found"}
BIG = {"day", "migrate", "rename", "status"}


def journal_path(C):
    return os.path.join(C.root, "record", "journal.jsonl")


def journal(C):
    p = journal_path(C)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as fh:
        return [json.loads(x) for x in fh if x.strip()]


def campaign_seed(C, fresh=None):
    j = journal(C)
    if j and "seed" in j[0]:
        return j[0]["seed"], len(j) - 1
    seed = fresh or "%016x" % random.SystemRandom().getrandbits(64)
    with open(journal_path(C), "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"seed": seed, "schema": CHAMBER_SCHEMA}) + "\n")
    return seed, 0


def cmd_replay(a, C):
    """Rebuild the campaign from a save plus the journal, and check that every step comes out the same."""
    import tempfile, shutil, zipfile
    mine = journal(C)
    if not mine:
        sys.exit("This campaign has no journal to replay.")
    work = tempfile.mkdtemp()
    try:
        T = Campaign(os.path.join(work, "c"))
        start = 0
        if a.archive:
            sub = types.SimpleNamespace(file=a.archive, replace=True)
            with contextlib.redirect_stdout(io.StringIO()):
                cmd_load(sub, T)
            theirs = journal(T)
            if not theirs or theirs[0] != mine[0] or theirs != mine[:len(theirs)]:
                sys.exit("That save isn't an earlier point of this campaign.")
            start = len(theirs) - 1
        else:
            with open(journal_path(T), "w", encoding="utf-8") as fh:
                fh.write(json.dumps(mine[0]) + "\n")
        steps = mine[1 + start:]
        for i, e in enumerate(steps, start + 1):
            if e["argv"][0] == "load":
                sys.exit("Step %d loaded a save; replay from that save instead." % i)
            before = state_hash(T.root)
            if before != e["before"]:
                sys.exit("Replay diverged before step %d (%s)." % (i, " ".join(e["argv"][:3])))
            buf = io.StringIO()
            sys.argv = ["chamber.py", "--campaign", T.root] + e["argv"]
            with contextlib.redirect_stdout(buf):
                try:
                    main(replaying=True)
                except SystemExit:
                    pass
            if state_hash(T.root) != e["after"]:
                sys.exit("Replay diverged at step %d (%s): the same seed gave a different result." % (i, " ".join(e["argv"][:3])))
        print("Replayed %d step%s exactly: same seed, same actions, same world." % (len(steps), "" if len(steps) == 1 else "s"))
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ---------- knowledge: facts, beliefs, what the player has found ----------
HOW = {"saw": "witnessed", "heard": "heard", "read": "read", "worked-out": "inferred", "suspects": "imagined"}


def _append(path, obj):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _lines(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(x) for x in fh if x.strip()]


def cmd_fact(a, C):
    p = os.path.join(C.root, "record", "facts.jsonl")
    k, fid = len(_lines(p)), ""
    while True:  # fact-a, fact-b, ... fact-aa: no digits ever reach a brief
        fid = chr(97 + k % 26) + fid
        k = k // 26 - 1
        if k < 0:
            break
    fid = a.id or "fact-" + fid
    _append(p, {"id": fid, "text": a.text})
    print("Recorded as what happened (%s). Nobody in the world knows it unless they learn it." % fid)


def cmd_learn(a, C):
    E = engine()
    v, err = quiet(E.cmd_learn, file=C.need(C.person(a.name), "person"), subject=a.about, claim=a.claim,
                   source=HOW[a.how], source_name=a.from_, reliability=None, fact=a.fact, secret=a.secret, stressed=a.stressed)
    if err:
        sys.exit(err)
    print("%s now believes, about %s" % (v["name"], v["plain"]))


def cmd_tell(a, C):
    E = engine()
    v, err = quiet(E.cmd_tell, teller=C.need(C.person(a.teller), "person"), hearer=C.need(C.person(a.hearer), "person"),
                   about=a.about)
    if err:
        sys.exit(err)
    if v.get("refused"):
        sys.exit(v["refused"])
    print("%s now believes, about %s" % (v["hearer"], v["plain"]))


def cmd_spread(a, C):
    """Let something get around a group: a few tellings between random pairs, as gossip goes."""
    E = engine()
    paths = [C.need(C.person(x), "person") for x in a.among]
    if len(paths) < 2:
        sys.exit("A rumour needs at least two people to get around.")
    told = 0
    for _ in range(a.times):
        holders = [p for p in paths if E.beliefs_about(load(p), a.about)]
        if not holders:
            break
        t = random.choice(holders)
        h = random.choice([p for p in paths if p != t])
        v, err = quiet(E.cmd_tell, teller=t, hearer=h, about=a.about)
        told += bool(v and not v.get("refused"))
    print(("Nobody passed it on." if not told else "It gets around a little." if told <= 2 else "It goes round.")
          + " Run `accounts` to see who believes what.")


def cmd_accounts(a, C):
    E = engine()
    paths = [C.need(C.person(x), "person") for x in a.names] if a.names else C.everyone()
    out = []
    for p in paths:
        n = load(p)
        for b in E.beliefs_about(n, a.about)[:2]:
            out.append("%s: %s" % (n["name"], E.belief_plain(b, subject=False)))
    print("\n".join(["What people believe about %s (beliefs only; any of it may be wrong):" % a.about] + ["  " + x for x in out])
          if out else "Nobody believes anything about %s." % a.about)


def cmd_found(a, C):
    p = os.path.join(C.root, "record", "player.jsonl")
    if a.text:
        _append(p, {"text": a.text})
        print("Noted as something the player has found out.")
    else:
        got = _lines(p)
        print("\n".join("- " + x["text"] for x in got) if got else "The player hasn't found anything out yet.")


# ---------- checking a narration draft against the contract ----------
INNER_YOU = re.compile(r"\byou (feel|felt|think|thought|realis|realiz|sense|sensed|know|knew|wonder|suspect|can tell|notice that|are sure)\w*\b|"
                       r"\byour (heart|stomach|gut|mind|instincts?) \w+|\ba (chill|shiver) (runs|ran|goes|went)\b", re.I)
INNER_THEM = r"\b{name}\b[^.!?\n]{{0,40}}?\b(feels|felt|thinks|thought|resents|fears|is hiding|was hiding|is lying|was lying|secretly|knows that|realises|realizes|wants to|is afraid)\b"
QUEST = re.compile(r"\b(would|could|can|will) you (help|find|bring|retrieve|fetch|deliver|kill|rescue|investigate|look into|recover)\b|"
                   r"\bI need (you|someone) to\b|\ba job for you\b|\byou'?ll be (paid|rewarded)\b|\breward\b", re.I)
WORKINGS = re.compile(r"\b(brief|chamber|engine|mood band|tetrad|stratagem|inclination|compulsion score|the box)\b", re.I)
SAID = r"\b{name}\b[^.!?\n]{{0,30}}?\b(says|said|asks|asked|replies|replied|nods|smiles|laughs|whispers)\b"


def _shingles(text, k=6):
    w = re.findall(r"[a-z']+", text.lower())
    return {" ".join(w[i:i + k]) for i in range(len(w) - k + 1)}


def cmd_check(a, C):
    text = a.text if a.text is not None else open(a.file, encoding="utf-8").read()
    flags = []
    sentences = re.split(r"(?<=[.!?])\s+|\n", text)

    def flag(kind, s_):
        flags.append("%s: \"%s\"" % (kind, s_.strip()[:120]))
    people = [load(p) for p in C.everyone()]
    asks = _lines(os.path.join(C.root, "record", "asks.jsonl"))
    may = {x["name"] for x in asks[-20:] if x.get("result") == "may"}
    for s_ in sentences:
        dialogue = '"' in s_ or "“" in s_
        if INNER_YOU.search(s_) and not dialogue:
            flag("narrates the player's inner life", s_)
        for n in people:
            nm = re.escape(n["name"].split()[0])
            if not dialogue and re.search(INNER_THEM.format(name=nm), s_, re.I):
                flag("states %s's inner life as fact" % n["name"], s_)
            if n["condition"] in ("dead", "comatose") and re.search(SAID.format(name=nm), s_, re.I):
                flag("%s is %s but acts" % (n["name"], n["condition"]), s_)
        if QUEST.search(s_) and not may:
            flag("an offer of a task nobody was cleared to ask for", s_)
        if WORKINGS.search(s_):
            flag("mentions the workings", s_)
    briefs = _lines(os.path.join(C.root, "record", "briefs.jsonl"))
    if briefs:
        last = briefs[-1]["text"]
        for m in re.finditer(r"A thought has come to them: (.+?)\. ", last):
            for part in m.group(1).split(", and somehow "):
                if len(part) > 6 and part.lower() in text.lower():
                    flag("narrates a thought instead of its ripple", part)
        pasted = _shingles(last, 7) & _shingles(text, 7)
        if pasted:
            flag("copies the brief word for word", sorted(pasted)[0])
    past = _lines(os.path.join(C.root, "record", "narration.jsonl"))[-10:]
    mine = _shingles(text)
    seen = set()
    for x in past:
        seen |= set(x["s"])
    rep = sorted(h for h in mine if hashlib.sha1(h.encode()).hexdigest()[:10] in seen)
    if rep:
        flag("repeats a phrase from recent scenes", rep[0])
    if not a.dry:
        _append(os.path.join(C.root, "record", "narration.jsonl"),
                {"s": sorted(hashlib.sha1(h.encode()).hexdigest()[:10] for h in mine)})
    print("\n".join(["Draft breaks the narration rules in %d place%s:" % (len(flags), "" if len(flags) == 1 else "s")]
                    + ["  " + f for f in flags]) if flags else "Draft passes the checks. (They catch plain breaches, not every one.)")
    if flags:
        sys.exit(1)


# ---------- a campaign inspector, for the people at the table, never the narrator ----------
def cmd_inspect(a, C):
    import html as H
    out = os.path.abspath(a.out)
    real_root = os.path.realpath(C.root)
    if os.path.commonpath([real_root, os.path.realpath(out)]) == real_root:
        sys.exit("Write the inspector page somewhere outside the campaign folder.")
    E = engine()
    people = [load(p) for p in C.everyone()]
    facts = _lines(os.path.join(C.root, "record", "facts.jsonl"))
    found = _lines(os.path.join(C.root, "record", "player.jsonl"))
    j = journal(C)
    e = H.escape
    rows = []
    for n in people:
        sp = E.speech_of(n); st = E.strain_of(n); tp = E.tempo_of(n)
        rows.append("<tr><td><b>%s</b><br><small>%s · %s</small></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            e(n["name"]), e(n.get("id", "")), e(n["condition"]),
            e(", ".join("%s %s" % (E.fmt_frac(v["frac"]), v["style"]) for v in n["voices"])),
            e(" ".join("%s%+d" % (E.AX[i][0], n["axes"][i]) for i in range(7))),
            e("%s%s; %s" % (sp["main"], " + " + sp["side"] if sp["side"] else "", sp["bend"])),
            e("; ".join("%s: %s" % (k, v) for k, v in st.items())),
            e("grief ×%s, fade ×%s, recall ×%s" % (tp["grief"], tp["fade"], tp["recall"]))))
    names = [n["name"] for n in people]
    import math as _m
    R, cx, cy = 230, 300, 280
    pos = {nm: (cx + R * _m.cos(2 * _m.pi * i / max(1, len(names))), cy + R * _m.sin(2 * _m.pi * i / max(1, len(names))))
           for i, nm in enumerate(names)}
    edges = []
    for n in people:
        for who, t in n.get("trust", {}).items():
            if who in pos and who != n["name"]:
                v = t.get("bedrock", 0) + t.get("surface", 0)
                col = "#2f855a" if v > 0 else "#c53030" if v < 0 else "#a0aec0"
                (x1, y1), (x2, y2) = pos[n["name"]], pos[who]
                edges.append('<line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" stroke="%s" stroke-width="%d" opacity=".6"><title>%s → %s: %+d</title></line>'
                             % (x1, y1, x2, y2, col, 1 + abs(v) // 2, e(n["name"]), e(who), v))
    nodes = "".join('<circle cx="%.0f" cy="%.0f" r="7" fill="#2b6cb0"/><text x="%.0f" y="%.0f" font-size="12" text-anchor="middle">%s</text>'
                    % (x, y, x, y - 12, e(nm)) for nm, (x, y) in pos.items())
    beliefs = []
    for n in people:
        for b in n.get("knows", []):
            beliefs.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%.2f</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                e(n["name"]), e(b["subject"]), e(b["claim"]), e(b["source"] + (" from " + b["from"] if b.get("from") else "")),
                b["confidence"], e(b["meaning"]), e(", ".join(b["distortions"])), e(b.get("fact") or "")))
    mem = []
    for n in people:
        for m in n.get("memory", [])[-10:]:
            mem.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                e(n["name"]), m.get("day", ""), e(m["event"]), e(m.get("with", "")), e(m.get("took") or "")))
    page = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Campaign inspector</title><style>
:root{--bg:#fbfaf7;--fg:#1a202c;--mut:#5a6577;--line:#e2ddd3}
@media (prefers-color-scheme:dark){:root{--bg:#16181d;--fg:#e6e6e6;--mut:#9aa3b2;--line:#2d3139}}
body{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif;margin:0;padding:16px;max-width:1200px;margin:auto}
h1{font-size:22px}h2{font-size:16px;margin-top:28px;border-bottom:1px solid var(--line);padding-bottom:4px}
.warn{color:var(--mut)}table{border-collapse:collapse;width:100%%;display:block;overflow-x:auto}
td,th{border-bottom:1px solid var(--line);padding:6px 8px;vertical-align:top;text-align:left}small{color:var(--mut)}
svg{max-width:100%%;height:auto}text{fill:var(--fg)}</style></head><body>
<h1>Campaign inspector</h1><p class="warn">For the people at the table. Everything here, numbers and truth included, is what the
narrator must never see.</p>
<h2>People (%d)</h2><table><tr><th>Who</th><th>Voices</th><th>Traits</th><th>Talk</th><th>Under strain</th><th>Tempo</th></tr>%s</table>
<h2>Regard between them</h2><svg viewBox="0 0 600 560">%s%s</svg>
<h2>What happened (facts)</h2><ul>%s</ul>
<h2>What people believe</h2><table><tr><th>Who</th><th>About</th><th>Claim</th><th>Source</th><th>Sure</th><th>Meaning</th><th>Gone wrong</th><th>Fact</th></tr>%s</table>
<h2>What the player has found out</h2><ul>%s</ul>
<h2>Recent memories</h2><table><tr><th>Who</th><th>Day</th><th>Event</th><th>With</th><th>Took it by</th></tr>%s</table>
<h2>Journal</h2><p>%d recorded actions; seed %s.</p></body></html>""" % (
        len(people), "".join(rows), "".join(edges), nodes,
        "".join("<li><b>%s</b> %s</li>" % (e(f["id"]), e(f["text"])) for f in facts) or "<li>None recorded.</li>",
        "".join(beliefs), "".join("<li>%s</li>" % e(f["text"]) for f in found) or "<li>Nothing yet.</li>",
        "".join(mem), max(0, len(j) - 1), e(j[0]["seed"]) if j else "none")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(page)
    print("Inspector page written to %s (for you, not the narrator)." % out)


# ---------- structured output ----------
def as_structured(text):
    """Turn a brief into entries: each top-level line, with its indented details as label: value."""
    entries = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.startswith("  ") and entries:
            body = line.strip()
            k, sep, v = body.partition(": ")
            if sep and len(k) < 40:
                entries[-1]["details"].setdefault(k, []).append(v)
            else:
                entries[-1]["details"].setdefault("note", []).append(body)
        else:
            entries.append({"text": line.strip(), "details": {}})
    return entries


def main(replaying=False):
    ap = argparse.ArgumentParser(description="The Chamber of Output: plain briefs for roleplay narration")
    ap.add_argument("--campaign", default=os.environ.get("CHAMBER_CAMPAIGN", "campaign"))
    ap.add_argument("--json", action="store_true", help="structured output: entries with their details")
    ap.add_argument("--seed", help="the seed for a new campaign (fixed once, then kept)")
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
    x.add_argument("--one-way", action="store_true", help="the other person doesn't see it the same way, or doesn't know")
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
    x = sp.add_parser("rename"); x.add_argument("old"); x.add_argument("new"); x.set_defaults(f=cmd_rename)
    x = sp.add_parser("migrate"); x.set_defaults(f=cmd_migrate)
    x = sp.add_parser("doctor"); x.add_argument("--fix", action="store_true"); x.set_defaults(f=cmd_doctor)
    x = sp.add_parser("backups"); x.set_defaults(f=cmd_backups)
    x = sp.add_parser("restore"); x.add_argument("which", nargs="?"); x.set_defaults(f=cmd_restore)
    x = sp.add_parser("replay"); x.add_argument("archive", nargs="?"); x.set_defaults(f=cmd_replay)
    x = sp.add_parser("fact"); x.add_argument("text"); x.add_argument("--id"); x.set_defaults(f=cmd_fact)
    x = sp.add_parser("learn"); x.add_argument("name"); x.add_argument("--about", required=True)
    x.add_argument("--claim", required=True); x.add_argument("--how", required=True, choices=list(HOW))
    x.add_argument("--from", dest="from_"); x.add_argument("--secret", action="store_true")
    x.add_argument("--stressed", action="store_true"); x.add_argument("--fact"); x.set_defaults(f=cmd_learn)
    x = sp.add_parser("tell"); x.add_argument("teller"); x.add_argument("hearer"); x.add_argument("--about", required=True)
    x.set_defaults(f=cmd_tell)
    x = sp.add_parser("spread"); x.add_argument("--about", required=True); x.add_argument("--among", nargs="+", required=True)
    x.add_argument("--times", type=int, default=6); x.set_defaults(f=cmd_spread)
    x = sp.add_parser("accounts"); x.add_argument("names", nargs="*"); x.add_argument("--about", required=True)
    x.set_defaults(f=cmd_accounts)
    x = sp.add_parser("found"); x.add_argument("text", nargs="?"); x.set_defaults(f=cmd_found)
    x = sp.add_parser("check"); x.add_argument("--text"); x.add_argument("--file")
    x.add_argument("--dry", action="store_true", help="don't remember this draft for repetition checks"); x.set_defaults(f=cmd_check)
    x = sp.add_parser("inspect"); x.add_argument("--out", required=True); x.set_defaults(f=cmd_inspect)
    argv_all = sys.argv[1:]
    a = ap.parse_args()
    if not getattr(a, "f", None):
        ap.print_help(); return
    if a.cmd == "check" and a.text is None and not a.file:
        sys.exit("check needs --text or --file.")
    C = Campaign(a.campaign)
    rec, skip = [], 0
    for i, t in enumerate(argv_all):  # the action itself, without where or how it was printed
        if skip:
            skip -= 1; continue
        if t in ("--campaign", "--seed"):
            skip = 1; continue
        if t.startswith(("--campaign=", "--seed=")) or t == "--json":
            continue
        rec.append(t)
    mut = a.cmd in MUTATING and not (a.cmd == "round" and a.look)
    seed, count = campaign_seed(C, a.seed)
    outer = random.getstate()
    random.seed("%s:%d:%s" % (seed, count, a.cmd))
    if not replaying and (a.cmd in BIG or a.cmd in ("load", "restore")) or (a.cmd == "doctor" and a.fix):
        if not replaying:
            auto_backup(C, a.cmd, rotate=a.cmd != "restore")  # never rotate away the backup being restored
    before = state_hash(C.root) if mut else None
    E = engine()
    readonly = not mut and a.cmd not in ("load", "restore", "doctor", "migrate", "check", "replay", "ask", "save")
    real_save = E.save
    if readonly:
        _READONLY[0] = True
        E.save = lambda *x, **k: None
    buf = io.StringIO() if a.json else None
    refused = None
    try:
        if buf is not None:
            with contextlib.redirect_stdout(buf):
                a.f(a, C)
        else:
            a.f(a, C)
    except SystemExit as e:
        refused = e
    finally:
        _READONLY[0] = False
        E.save = real_save
        random.setstate(outer)
        if mut:
            with open(journal_path(C), "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"argv": rec, "before": before, "after": state_hash(C.root)}, ensure_ascii=False) + "\n")
    if buf is not None:
        msg = str(refused) if refused is not None and refused.code not in (0, None) else None
        print(json.dumps({"command": a.cmd, "ok": msg is None and not (refused is not None and refused.code == 1),
                          "refused": msg, "entries": as_structured(buf.getvalue())}, ensure_ascii=False, indent=1))
        if refused is not None:
            raise SystemExit(1 if refused.code else 0)
        return
    if refused is not None:
        raise refused


if __name__ == "__main__":
    main()
