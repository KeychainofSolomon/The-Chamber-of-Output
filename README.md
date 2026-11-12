# The Chamber of Output

The narrator's side of a two-part system for running the people of a roleplay world.

- **The engine** lives in its own repository. It
  decides who people are, what happened to them today, how they react and why, how they change,
  what they think. It is all numbers, rules and tables.
- **The Chamber of Output** (this repository) is what the roleplaying AI actually reads. It drives
  the engine and hands back plain briefs: how each person comes across, what shows, what's left in
  the world to notice. No numbers, no traits, no workings.

The narrating agent installs only the chamber. It never sees how the engine works, so it can't
let the workings slip into the story, and it can't peek into what's meant to stay unknowable,
such as where a character's thoughts come from.

## How the separation works

```
engine repository (rules, tables, sealed thought box)
        │   tools/sync_engine.py seals one pinned version of the engine script
        ▼
chamber/engine.bin + engine.lock     the engine, compressed and pinned; no documentation comes across
        │
chamber/chamber.py                   runs the engine, translates every result into plain words
        │
narrating agent                      reads chamber/SKILL.md (meta instructions only) and the briefs
```

- **Pinned.** The chamber carries one exact engine version, recorded in `engine.lock` with a
  checksum. An engine update never reaches a running campaign by surprise. To move to a newer
  engine, run `python tools/sync_engine.py --source <engine checkout> --commit <sha>` (or `--repo <git url>`) and commit the result.
- **Sealed, not secret.** The engine travels compressed, and the skill tells the agent never to
  open it. Its documentation never comes across. This is informational isolation: it keeps the
  narrator from reading the workings by accident, and keeps the workings out of its context. It is
  **not** cryptographic security. Anyone, or any agent that deliberately decodes `engine.bin`, can
  recover the full engine source, so treat it as readable code, never as a place for secrets.
- **Checked, not authenticated.** The checksum in `engine.lock` catches corruption and accidental
  edits. It does not prove who published the engine: someone who replaces both files gets a
  matching pair. To check a pinned engine independently, rebuild it from the engine's own source:
  `python tools/sync_engine.py --verify --source <engine checkout>` (or `--repo <git url>`). Add
  `--require-signed` to refuse any engine commit whose signature git can't verify, which works
  once engine releases are signed and you hold the signer's key.
- **Translated.** Every engine result passes through a plain-language layer. Internal names
  (trait names, need names, manner labels, scores) are turned into portrayal, or dropped.

## What the agent does with it

```
python chamber/chamber.py setting 1,1,2,1,2,1,1
python chamber/chamber.py place "Kilbrack harbour" --add "sound:the gulls" "smell:tar" "taste:salt"
python chamber/chamber.py new "Mairead Coyle"
python chamber/chamber.py tie "Mairead Coyle" --to "Joren Coyle" --role spouse --loyalty 6
python chamber/chamber.py day
python chamber/chamber.py round "Mairead Coyle" "Tomas Coyle" "Fenwick" --place "Kilbrack harbour" --approach deference --solemn --public
python chamber/chamber.py event "Mairead Coyle" loss --about "Joren Coyle"
```

`round` works out a whole room in one call, in the right order: the scene, who leads, how
their mood carries to the easily moved, then everyone else, each toward the player, and then how
the people present treat each other. Conditions and the player's approach can be set for the whole
room or per person (`--as "Tomas Coyle:drunk"`, `--treat "Fenwick:pressure"`), with home ground,
the symbol a victim stood for, and a look-only mode. A brief looks
like this:

```
Fenwick holds the room; the others take their lead from them, or set themselves against them.
Tomas Coyle toward you: cool; sad, gentle, faraway.
  Colour: a stillness at the edges; keeps vigil; the old words, the old motions; low voices, set forms; weighed down.
  Speech: trailing, hushed.
  A thought has come to them: to beat a dependency. They notice it. It shows as: a name, or a word,
  under the breath. If they wonder where it came from, they'd guess: salt on the wind. Never narrate the thought itself.
  Their day so far: supplies ran short for their dependant (it may or may not come up).
Offscreen, for Fenwick: an old urge or hunger has flared. Let it show in what they do; never explain it.
```

The agent turns that into prose under the laws in `chamber/SKILL.md`: nothing leaks, all five
senses, no quests unless `ask` allows one, thoughts shown only by their ripple.

## Commands

| Command | What it does |
|---|---|
| `setting` | The world's settings: Violence, Order, Scarcity, Strangeness, Faith, Power, Deceit (0–3). |
| `week` | Let the times move on a week. |
| `place` | Make or add to a place: what is always there. |
| `new`, `sheet` | Make a person; see who they are now, in plain words. |
| `tie` | Name a relationship. |
| `circle` | Make a group from members. |
| `day` | Roll a new in-world day for everyone (or named people). |
| `round` | Run a whole room toward the player, with everything true of the moment. |
| `violence` | How to write a violent moment, and how each person present responds. |
| `event`, `habit` | Record what happened to someone, or what they did again. |
| `ask` | Whether someone would ask for help, and with what. |
| `status` | Dead, comatose, amnesiac, or back. |
| `save`, `load` | Carry a campaign between chats as a zip; everyone remembers where they were. |
| `fact`, `learn`, `tell`, `spread`, `accounts`, `found` | What happened; what each person believes and where they got it; rumours; what the player has found out. Four domains, never mixed. |
| `rename` | A new name for the same person; their identity and everyone's memory of them carry over. |
| `check` | Check a narration draft against the laws (inner life, stated feelings, unasked quests, narrated thoughts, the dead acting, copied or repeated phrasing). |
| `migrate`, `doctor`, `backups`, `restore` | Bring old campaigns forward; find and set aside damage; automatic backups before big changes. |
| `replay` | Rebuild the campaign from its seed and journal (optionally from a save) and confirm every step comes out the same. |
| `inspect` | A local HTML page of the whole campaign, numbers and truth included, for you, never the narrator. |

**Every action is reproducible.** A campaign has one seed, fixed when it starts (`--seed` to choose
it). Every action that changes the world is journalled with a fingerprint of the state before and
after, and each action draws its randomness from the seed and its place in the journal. `replay`
rebuilds the campaign from scratch, or from a save, and checks each step lands exactly where it did;
when a character does something strange, you can rerun the moment and look. Looking never changes
anything: `sheet`, `round --look`, `ask`, `accounts`, `check --dry`, `inspect` and `doctor` leave
the world exactly as it was, and the tests prove it.

**Structured output.** Add `--json` to any command for the same plain content as entries with
their details, plus whether it was refused, for programs that drive or validate the chamber.

**Identity and schema.** Everyone has an id from birth that never changes; `rename` changes the name
and carries every tie, memory and belief across. Files carry a schema version; `migrate` brings
older campaigns forward without changing who anyone is, `doctor` finds damaged or conflicting files
(and with `--fix` sets them aside), and automatic backups are kept beside the campaign before
every day, migration, rename, status change, load and restore.

**Saving and loading are strict.** `save` writes only the campaign's own files (the world, people,
places, circles and the sealed record), never links or anything outside the folder, and never into
the campaign folder itself. `load` accepts only those files, in that layout, within size limits (a
50 MB archive, 10 MB per file, 200 MB unpacked, 5,000 files, no runaway compression), and checks
that each one reads as what it claims to be before anything changes. The new campaign is built
aside and swapped in whole: with `--replace` nothing of the old campaign survives, and a bad
archive leaves the current campaign untouched.

Campaigns live in a folder (`--campaign PATH`, default `./campaign`). Its `record/` folder holds
a sealed record of how thoughts arose, for the people at the table, never for the narrator.

## Tests

```
python tests/run_tests.py --days 120 --seed 7
```

`python tests/test_archive.py --engine-source <engine checkout>` checks saving and loading against
hostile archives (path tricks, links, stray or oversized files, broken or wrong-shaped JSON,
too many files), that `--replace` leaves nothing of the old campaign, that a failed load changes
nothing, and that a replaced engine-and-lock pair is caught by `--verify`.

`python tests/test_integrity.py` checks that looking changes nothing, replay reproduces every step
and notices divergence, rename and migrate keep identity, doctor finds and sets aside damage,
restore works, `--json` is valid, beliefs stay beliefs, and `check` catches plain breaches while
passing clean prose.

`run_tests.py` runs a long random campaign through every command and option and fails on any crash, any digit
in a brief, or any of the engine's internal words (trait names, need names, manner labels, terms
like mood or band). Run with nine seeds (3, 7, 11, 23, 31, 47, 59, 73, 89): about 8,000
commands over 1,080 simulated days, all passing on the shipped code. The engine has its own audit in its own repository.

## Install

Download `chamber.skill` and upload it under Skills in Claude's settings, or copy the `chamber/`
folder into your skills directory. Python 3.8 or later, nothing else.
