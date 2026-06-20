# mastery-loop

*English · [中文说明](README.zh-CN.md)*

**Turn any study material into a spaced-repetition system that actually makes you
remember it — not just a pile of pretty notes.**

`mastery-loop` is a portable AI *skill* (one `SKILL.md` + a tiny, tested Python
engine). Point it at lecture slides, a textbook PDF, your notes, or a whole course
folder. It builds a learnable map, then runs a short **daily active-recall loop**
backed by a real forgetting-curve scheduler — with interleaving, Feynman checks,
calibration, and error-driven review — and it adapts to how *you* learn. Built for
total beginners with zero background.

> The honest promise: not "10× faster," but **far more durable learning per hour**,
> by making the six things that actually work the easy path.

---

## Why this exists

Open-source AI study tools split cleanly into two camps, and memory dies in the gap
between them:

| Camp | Examples | What they nail | What they miss |
|---|---|---|---|
| **Generators** | book-to-skill, ko-lesson, NotebookLM clones, PDF→Anki tools | turning material into notes/cards/quizzes | no scheduler, no recall loop — "made study material" ≠ "learned it" |
| **Schedulers** | Anki, Obsidian-Spaced-Repetition | real SM-2/FSRS forgetting-curve review | no AI — you hand-write every card |

Almost nothing does **both**, in plain files you own, as a drop-in skill.
`mastery-loop` is that bridge: AI generation **and** a real scheduler, closed into
one daily loop.

## How it works

You only ever do two things, in your own language:

1. **"Help me learn ‹topic›"** → it ingests your material, builds a map (easy →
   hard), writes active-recall items for the first unit (each checked by a
   *verify gate* so no wrong fact gets drilled), and teaches the first piece.
2. **"Today"** (~15–30 min/day) → it pulls today's **interleaved** queue from the
   scheduler, asks you each question *before* showing the answer, grades you, fixes
   errors on the spot (confident mistakes get special treatment), adds a small dose
   of new material, shows you where your confidence was wrong, and **distills what
   it learned about you** so tomorrow is sharper.

You never touch files, scripts, JSON, or Obsidian. It all happens in chat. Your
knowledge base is plain Markdown + JSON you fully own (Obsidian-compatible, but
Obsidian is optional).

## Install (platform-agnostic)

`mastery-loop` is a standard skill folder. Put it where your agent looks for skills:

- **Claude Code:** `git clone https://github.com/<you>/mastery-loop ~/.claude/skills/mastery-loop`
- **Codex:** `git clone https://github.com/<you>/mastery-loop ~/.codex/skills/mastery-loop`
- **Claude Cowork / desktop:** install the `mastery-loop.skill` bundle from the
  releases, or drop the folder into your skills directory.

Then just say: *"use mastery-loop to help me learn ‹your subject›."*

Requirements: `python3` (standard library only for the scheduler). To ingest
binary formats, install a reader for what your material is in: `pip install pypdf`
(PDF), `python-pptx` (slides), `ebooklib` (EPUB). PPTX/EPUB/TXT have
dependency-free fallbacks; **PDF needs one of pdftotext / pypdf / pdfminer**. If
extraction fails, the agent just reads the file directly instead — it's a
convenience, not a gate.

## What's in the box

```
mastery-loop/
├── SKILL.md                  # the skill: the loop, in full
├── scripts/
│   ├── scheduler.py          # the SRS engine (SM-2 + horizon scaling, stdlib only)
│   └── extract.py            # material → text (PDF / PPTX / EPUB / TXT, with fallbacks)
├── references/
│   ├── pedagogy.md           # the six mechanisms + the science (read first)
│   ├── item-writing.md       # how to write items that actually teach
│   └── scheduler.md          # full scheduler command reference
├── templates/                # map / learner-profile / constraints / session-log
└── tests/
    └── test_scheduler.py     # run it: `python3 tests/test_scheduler.py`
```

## The engine

`scheduler.py` owns all timing and state so the model never has to guess "have they
forgotten this?" (a question LLMs answer inconsistently across sessions). It runs
**FSRS-5 by default** — the modern scheduler that hits the same retention with
~20–30% fewer reviews than SM-2 by modelling memory *stability* and *difficulty*
(SM-2 stays selectable with `--algorithm sm2`) — plus three evidence-based
additions:

- **exam-horizon scaling** — compresses intervals toward a deadline so every item
  still gets a spaced review before the test (never a cram-dump);
- **confident-error handling** — a sure-but-wrong answer is the most fixable kind
  (hypercorrection); it's re-tested fast and rephrased;
- **interleaving** — the daily queue mixes topics so you practice *choosing* a
  method, not just executing a familiar one.

It's deterministic and unit-tested (`tests/test_scheduler.py`). FSRS is a
documented drop-in upgrade.

## Design principles

- **Chat is the interface; files are the storage.** A beginner shouldn't have to
  learn Obsidian to study. The loop runs in conversation; files are just durable,
  portable state you own.
- **A daily loop, never a "generate everything" dump.** Full pre-generation feels
  productive and produces cramming. Refused by design.
- **A verify gate before anything is saved.** A wrong item would be drilled for
  weeks, so generated items are refuted against the source before they enter the
  bank.
- **The system compounds.** Every session updates a learner profile and a
  constraints file (distilled rules from real mistakes) that load automatically
  next time — so it gets better at teaching *you* the more you use it.
- **Honest pedagogy.** Retrieval, spacing, interleaving, explanation, feedback,
  error-correction — the techniques with real evidence. No "learning styles," no
  magic-speed claims.

## Credits & inspiration

Stands on the shoulders of three excellent open-source projects — and fills the one
gap all three share (no retention loop):
[ko-lesson](https://github.com/Liunian06/ko-lesson) (source-attribution discipline,
feedback loop), [book-to-skill](https://github.com/virgiliojr94/book-to-skill)
(extract-then-synthesize, on-demand reference files, token budgets), and
[knowledge-wiki-template](https://github.com/CatChen/knowledge-wiki-template)
(deterministic-engine / LLM-judgment split, incremental state, maintenance skills).

Pedagogy grounded in Roediger & Karpicke (2006), Karpicke & Roediger (2008),
Dunlosky et al. (2013), Cepeda et al. (2006/2008), Rohrer & Taylor (2007), Bjork &
Bjork (2011), Metcalfe (hypercorrection), and Wilson et al. (2019). See
`references/pedagogy.md`.

## License

MIT — see [LICENSE](LICENSE).
