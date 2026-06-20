# scheduler.py — command reference

The deterministic spaced-repetition engine. The agent calls it; the learner never
does. Always pass `--store <workspace>/items.json`. All output is JSON on stdout.

## Commands

### init — create the store
```
python3 scheduler.py --store WS/items.json init [--exam YYYY-MM-DD] \
        [--retention 0.9] [--new-per-day 8] [--max-reviews 60] [--algorithm fsrs|sm2] [--force]
```
Creates an empty store. Set `--exam` if a deadline is known; the scheduler will
compress intervals toward it. `--force` overwrites an existing store.

### config — update meta later
```
python3 scheduler.py --store WS/items.json config [--exam YYYY-MM-DD] \
        [--retention 0.9] [--new-per-day 10] [--max-reviews 60] [--algorithm fsrs|sm2]
```
Pass `--exam ""` (empty) to clear a deadline.

### add — append items (de-duplicated)
```
# Preferred: write items to a UTF-8 (no BOM) .json file — name it _add.json,
# distinct from the engine-owned items.json — then:
python3 scheduler.py --store WS/items.json add --json _add.json
# Alternative (stdin) — fine on Unix shells, unreliable for non-ASCII on PowerShell:
echo '[{"topic":"hashing","front":"...","back":"...","type":"recall"}]' \
  | python3 scheduler.py --store WS/items.json add --json -
```
Accepts a JSON array (or single object). Required per item: `topic`, `front`.
Optional: `back`, `type` (recall|cloze|problem|concept, default recall), `source`.
Identical `topic`+`front` (case/space-insensitive) is skipped, so re-running is
safe. Returns counts of added vs skipped. Write the JSON as UTF-8 **without a BOM**
— a leading BOM makes the parser reject the file.

### due — today's queue
```
python3 scheduler.py --store WS/items.json due [--max 60] [--new 8] [--date YYYY-MM-DD]
```
Returns `review` (items whose due date has arrived, **interleaved across topics**)
and `new` (a capped batch of never-seen items). Present `front` only, get the
answer, then reveal `back` and grade. Do not regroup by topic — the interleaving
is deliberate. `--date` is for testing.

### grade — record an attempt and reschedule
```
python3 scheduler.py --store WS/items.json grade --id <id> --grade <0-5> [--confidence <1-5>]
```
This is the only way item state changes. Returns the new interval, next due date,
ease, reps, lapses, and any `flag`.

**Grade scale (0-5, map the learner's answer to it):**
- 0 — blank / no idea
- 1 — wrong; only recognized it on reveal
- 2 — wrong or major gaps
- 3 — correct, but with real effort / hesitation / a small slip
- 4 — correct, minor hesitation
- 5 — correct, immediate, effortless

Grades 0-2 are lapses (interval resets to 1 day, ease drops). Grades 3-5 advance
the item (1 day → 6 days → ×ease …).

**Confidence (1-5):** 1 = pure guess, 5 = certain. A grade < 3 with confidence ≥ 4
is a *confident error* → flagged `hypercorrect`, re-tested tomorrow; rephrase it
next time. Always pass confidence when you have it — it powers calibration. Only
confidence ≥4 (high) and ≤2 (low) move the calibration numbers; 3 is neutral. A
grade or confidence outside its range is **rejected with an error, not silently
clamped**, so a mis-call is loud rather than corrupting state.

### distill — record session learning (owner of the self-improving loop)
```
python3 scheduler.py --store WS/items.json distill \
        --learner "one line for learner.md" --constraint "one rule for constraints.md"
```
Call at the END of every session, after updating `learner.md` and `constraints.md`.
It timestamps the distillation so `due` and `stats` can report `days_since_distill`
— making a skipped (non-improving) session visible instead of silent. The script
can't write the judgement for you; it makes *not* doing it observable.

### stats — mastery, calibration, streak
```
python3 scheduler.py --store WS/items.json stats
```
Returns per-topic mastery (score + 🔴/🟡/🟢 + counts), calibration
(overconfidence/underconfidence rates), study streak, and due/new/total counts.
Use it to update `map.md` markers and to show the learner their calibration gap.

## Item state (engine-owned — never hand-edit items.json)
`id` (hash of topic+front), `topic`, `type`, `front`, `back`, `source`, `due`,
`interval` (days), `reps`, `lapses`, `last_grade`, `last_confidence`,
`last_reviewed`, `flag`, `suspended`, `history[]`, plus algorithm state:
`stability` & `difficulty` (FSRS) or `ease` (≥1.3, starts 2.5; SM-2). "New" =
`last_reviewed` is null; once reviewed, an item is a "review" (so a lapse never
re-counts as new).

## Algorithms: FSRS (default) and SM-2
Two schedulers are built in; choose per store with `--algorithm` (default `fsrs`):

- **FSRS-5 (default)** — models memory as **Stability** (days until recall
  probability drops to 90%) and **Difficulty**, fit to hundreds of millions of real
  reviews. Reaches the same retention with ~20–30% fewer reviews than SM-2 — the
  "fewer reviews / 省复习量" win. Implemented in `scripts/fsrs.py` (FSRS-5 default
  parameters, decay −0.5; same-day/short-term steps omitted since reviews are
  daily). Items carry `stability` + `difficulty`; the next interval is computed from
  `target_retention` (lower it, e.g. 0.85, for even fewer reviews; raise it for
  tighter retention). Run `python3 fsrs.py` for its self-check.
- **SM-2** — classic Anki: one `ease` factor, intervals 1 → 6 → ×ease. Simpler and
  fully transparent; choose with `--algorithm sm2`.

Both share **exam-horizon scaling** (never schedule past the exam; guarantee a
spaced pass before it), the **confident-error / hypercorrection** flag (retest
tomorrow + rephrase), and **interleaving** in `due`. See the docstrings in
`scripts/scheduler.py` / `scripts/fsrs.py` and `references/pedagogy.md`.
