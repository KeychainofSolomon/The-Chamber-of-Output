# The Chamber of Output

The narrator's side of a two-part system for running the people of a roleplay world.

- **[RP-Instructional](https://github.com/KeychainofSolomon/RP-Instructional)** is the engine. It
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
RP-Instructional (engine, rules, tables, sealed thought box)
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
  engine, run `python tools/sync_engine.py --commit <sha>` and commit the result.
- **Sealed.** The engine travels compressed, and the skill tells the agent never to open it. Its
  documentation never comes across. (This is a separation, not encryption: an agent that
  deliberately decoded the file could read it. It is never told how, or given a reason to.)
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
their mood carries to the easily moved, then everyone else, each toward the player. A brief looks
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

Campaigns live in a folder (`--campaign PATH`, default `./campaign`). Its `record/` folder holds
a sealed record of how thoughts arose, for the people at the table, never for the narrator.

## Tests

```
python tests/run_tests.py --days 120 --seed 7
```

Runs a long random campaign through every command and option and fails on any crash, any digit
in a brief, or any of the engine's internal words (trait names, need names, manner labels, terms
like mood or band). Run with nine seeds (3, 7, 11, 23, 31, 47, 59, 73, 89): 7,946
commands over 1,080 simulated days, all passing on the shipped code. The engine has its own audit in RP-Instructional.

## Install

Download `chamber.skill` and upload it under Skills in Claude's settings, or copy the `chamber/`
folder into your skills directory. Python 3.8 or later, nothing else.
