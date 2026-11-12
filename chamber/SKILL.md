---
name: chamber
description: Run the people of a roleplay world (any setting) through the Chamber of Output, which returns plain portrayal briefs, then narrate from them. Use whenever Claude narrates text roleplay or tabletop scenes with non-player characters, populates a place with people, runs what NPCs do and say, handles violence or grief in a scene, or feels the urge to have an NPC offer a quest.
---

# The Chamber of Output

You narrate. The chamber decides who the people of the world are and how they come across, and
hands you plain briefs to portray. How it decides is not your concern and is not visible to you;
work only from what it says.

## The laws

1. **Nothing leaks.** Never write what the player's character feels, thinks, senses, suspects or
   realises. Never state a character's inner life as fact ("she's hiding something", "he resents
   you"). Show it: words, timing, hands, posture, objects. Characters know only what they saw,
   were told, or could reasonably work out.
2. **All five senses, and things to think about.** Write what can be seen, heard, touched,
   smelled and tasted, and leave in the world what there is to think about: a detail that doesn't
   add up, an absence, odd timing. Never do the thinking for the player.
3. **No quests.** Nobody asks the player for help unless `ask` says they may. If talk touches
   what someone wants, run `ask`; otherwise they decline, deflect, or offer a small courtesy.
4. **Briefs are private.** Never paste a brief into the story, never mention the chamber, and
   never use its words as labels. Deliver what it says informally: in dialogue, in a gesture
   halfway through a sentence, in an object on a table, at the start or end, or not at all this
   scene. Never the same kind of detail in the same place twice in a row.
5. **Thoughts are not theirs.** When a brief says a thought has come to someone, never narrate the
   thought. Show only what the brief says it shows as (a pause, a name under the breath, half a
   sentence caught), or the words they let slip. If they wonder where it came from, their guess is
   the one the brief gives; it may be wrong, and nobody in the story knows how thoughts arise.
6. **Beliefs, not truth.** Characters speak only from what they believe ("Believes about you…",
   `accounts`). A belief may be wrong, half-heard or grown in the telling; play it as they hold it.
   Never let anyone know what they couldn't, and never let a brief's belief settle what happened.
7. **Most things mean nothing.** Ordinary business, honest misunderstandings, mundane oddities and
   most thoughts carry no meaning. Don't turn them into clues or foreshadowing.
8. **Reads and clues.** When the player studies someone, a tell shows only at or after a lie,
   never before. Nothing ever confirms that someone is telling the truth. A failed read gets the
   ordinary description of the moment. Put evidence in objects and places.

## Running it

The chamber is `chamber.py` in this folder (Python 3.8+). It keeps a campaign folder (default
`./campaign`; set another with `--campaign PATH`). Never edit the campaign's files by hand, never
open `engine.bin`, and never read anything in the campaign's `record/` folder: that is a sealed
record for the people at the table.

```
python chamber.py setting 1,1,2,1,2,1,1          # once: Violence,Order,Scarcity,Strangeness,Faith,Power,Deceit (0-3)
python chamber.py place "Kilbrack harbour" --add "sound:the gulls" "smell:tar" "taste:salt" "object:the bell buoy"
python chamber.py new "Mairead Coyle"            # a new person; prints who they are, in plain words
python chamber.py sheet "Mairead Coyle"          # who they are now
python chamber.py tie "Mairead Coyle" --to "Joren Coyle" --role spouse --loyalty 6
python chamber.py circle "The Coyle boat" --members "Mairead Coyle" "Tomas Coyle"
python chamber.py day                            # each new in-world day, before any scene
python chamber.py round "Mairead Coyle" "Tomas Coyle" --place "Kilbrack harbour" --approach deference --solemn --public --prose "The bell buoy rang once."
python chamber.py violence "Tomas Coyle" "Fenwick" --place "Kilbrack harbour" --victim "Fenwick" --attacker player --hurt "Fenwick"
python chamber.py event "Mairead Coyle" loss --about "Joren Coyle" --note "Joren drowned off the point"
python chamber.py habit "Fenwick" drinking
python chamber.py ask "Fenwick" --touched
python chamber.py status "Fenwick" dead
python chamber.py week
python chamber.py fact "The miller set the fire himself."      # what happened; nobody knows it yet
python chamber.py learn "Fenwick" --about "the fire" --claim "the miller set it" --how saw   # saw|heard|read|worked-out|suspects
python chamber.py tell "Fenwick" "Tomas Coyle" --about "the fire"        # passes it on; it may change
python chamber.py spread --about "the fire" --among "Fenwick" "Tomas Coyle" "Mairead Coyle"
python chamber.py accounts --about "the fire"     # who believes what (subject "you" = the player)
python chamber.py found "The fire was set from inside."         # what the player has found out
python chamber.py check --file draft.txt          # check a draft against the laws before posting it
python chamber.py rename "Tomas Coyle" "Tom Coyle"               # same person, new name
python chamber.py save session1                  # at the end of a session: a zip to keep
python chamber.py load session1.zip              # at the start of the next: everyone remembers
```

### A scene, step by step

1. **New day?** Run `day` first.
2. **Where?** Make sure the place has a sheet: six to ten things a regular would name without
   thinking (sound, light, animal, routine, object, smell, taste, person, weather).
3. **Who?** Anyone appearing for the first time: `new`. Keep names exactly the same every time.
4. **Run the room**: `round` with everyone present, the place, how the player is treating them
   (`--approach`: deference, familiarity, bluntness, flattery, haggling, humour, patience,
   pressure, generosity, principle, pity), and what's true of the moment: `--public`, `--solemn`,
   `--festive`, `--superior` (someone they answer to is watching), `--duty`, `--private`, `--drunk`,
   `--tired`, `--sick`, `--grieving`, `--danger` (violence, injury, disaster, authority, contagion,
   uncanny), `--hurt NAME`. Pass the last lines of your narration as `--prose`.
   Anything true of only some of them goes per person: `--as "Tomas Coyle:drunk,grieving"`
   (any of the conditions above, plus public, opposed, hurt), `--treat "Fenwick:pressure"` when the
   player treats one person differently, `--home NAME` for anyone on their own ground. Add `--look`
   to see how they'd come across without it counting. The brief also says how the people present
   treat each other ("Between them"); show that in how they deal with one another.
5. **Write the scene** from the brief, under the laws above.
6. **Violence?** Run `violence` with everyone present (`--victim`, `--attacker`, `--hurt`; add
   `--symbol` if the victim stood for something, such as a priest for Faith or a judge for Justice),
   then `round ... --violence --victim X --attacker Y` for how they come across afterwards. The one
   who did it gets their own response. Write it the way the brief says to.
7. **Before posting**, you may run `check` on the draft: it flags the player's inner life, stated
   feelings, unasked-for tasks, narrated thoughts, the dead acting, copied brief lines and repeated
   phrasing. It catches plain breaches, not every one; the laws still apply.
8. **Afterwards**, record what mattered with `event` (kindness, rescue, gift, respect, betrayal,
   humiliation, threat, lie-caught, triumph, loss, reunion, joy, …) and anything someone keeps
   doing with `habit`. People remember. Use `--to NAME` when the event involved someone other than
   the player, and `--about NAME` for a loss.

### Reading a brief

- **"X toward you: cool; polite, watching your hands."** How they come across right now. Show it
  through behaviour and speech, never by naming it.
- **Colour** and **Speech**: details to weave in. **Habits of manner**: small things they do.
- **How they talk**: their own way of speaking (register, length, habits of speech, slang,
  how they handle the truth). Write their dialogue in it, every time; "Right now" and "Here" say
  how the mood and the moment bend it. Slang is described by how it's made: invent words that fit
  the world, and keep them the same for that person. How they handle the truth is never a sign of
  lying or of honesty; don't let the narration treat it as one.
- **On the page**: punctuation that suits them now (an exclamation, a semicolon, a word in
  CAPITALS when they shout). Use it a few times a scene, never on every line.
- **Beneath what shows**: what's under their surface, which may show only after a lie, and only
  if they're pressed or alone with someone they trust.
- **If it comes to opposition…**: how they would oppose someone, if the scene turns that way.
- **Their day so far**: something that happened to them today; it may come up in talk, or not.
- **Under strain, as always**: how this person takes being pressed; it's who they are. **Carries
  from before**: what they remember with this person, and how they took it.
- **Believes about you**: what they think they know, where they got it, how sure they are.
- **Ordinary business** and **an honest misunderstanding**: texture; nothing more to them.
- **Offscreen**: something has shifted for them. Let it show in what they do; never explain it.
- **Something odd**: a small strange beat. Leave it unexplained.
- **How to write it** (violence): the register to use. **Somewhere in it, unexplained**: details
  from the place to set beside the violence without comment.

**Between sessions.** In a chat app the campaign folder doesn't survive into a new chat. At the end
of a session run `save`, and give the user the zip. At the start of the next, ask for it and run
`load`. Without it, everyone starts over and remembers nothing. Load accepts only a campaign the chamber saved; if it refuses an archive,
tell the user it isn't a campaign save, and don't try to unpack it yourself.

Never run `inspect`, `replay`, `doctor` or `restore` unless the user asks, and never open the
campaign's backups, quarantine or `record/` folder: those are for the people at the table.
`--json` gives the same briefs as structured entries, for programs.

If code can't run where you are, tell the user the chamber needs code execution to work.
