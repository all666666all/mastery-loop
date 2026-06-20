# Pedagogy: the six mechanisms (read this first)

This skill is opinionated because the science of durable learning is unusually
settled. The core finding of ~40 years of research: **the conditions that make
studying feel easy and fast are mostly different from the conditions that make
learning durable** (Bjork's *performance ≠ learning* / "desirable difficulties").
Beginners — and tools built for them — almost always optimize for the feeling.
This skill optimizes for the durability.

Each mechanism below maps to a step in `SKILL.md`. Understand the *why* so you can
adapt, not just obey.

## 1. Retrieval practice (active recall) — the engine
Trying to *produce* an answer from memory beats re-reading it, by a lot, and the
gap grows with time. Classic result: study-then-test vs study-then-restudy were
tied after 5 minutes but testing won decisively a week later (≈56% vs 42%), and
one study + three tests beat four studies (≈61% vs 40%) while reading the passage
a quarter as much (Roediger & Karpicke 2006). Retrieval even beats elaborate
study like concept-mapping (Karpicke & Blunt 2011). Meta-analyses put the effect
at medium-to-large (g ≈ 0.5–0.6), reliably bigger with feedback.
→ *Always show the front and get an attempt before revealing the back. Recognition
("yeah I knew that") is the trap; production is the medicine.*

## 2. Spacing — let the scheduler own time
Reviewing across spaced sessions beats massing the same minutes ("cramming");
forgetting and re-retrieving is what builds durability (spacing effect, Cepeda et
al. 2006). Practical rule from Cepeda et al. 2008: the optimal gap is a *shrinking
fraction* of how long you need to remember (~20–40% of the interval for
week-scale, falling to ~5–10% for year-scale), and **erring long is far cheaper
than erring short**. `scheduler.py` encodes this; never override its timing by
hand. When an exam date is set, it compresses gaps toward the date instead of
abandoning spacing.

## 3. Interleaving — mix, don't block
Mixing problem *types* within a session beats grouping them (Rohrer & Taylor
2007). Blocking lets the learner reuse one method on every problem and never
practice the real skill: *choosing* which method applies. Interleaving teaches
discrimination among look-alike concepts (Rohrer 2012). This matters most for
procedural subjects (math, algorithms, coding, classification).
→ *The `due` queue is interleaved on purpose. Do not regroup it by topic.* Caveat:
a brand-new type needs a tiny blocked introduction first (teach it, do 2-3), then
it joins the interleaved pool.

## 4. Elaboration & the Feynman pass — explain to find the gap
Self-explanation ("why is this true? how does it connect?") is well supported
(g ≈ 0.55, Bisra et al. 2018), and expecting-to-teach / actually teaching deepens
processing (the "protégé effect," Chase et al. 2009). The point isn't the
explanation; it's that **the place the explanation breaks is the exact gap to
target next**.
→ *One "explain it to me like I'm new" pass per session; turn the stall into a new
item.*

## 5. Calibration — break the illusion of competence
Learners' confidence is largely uncorrelated with what they'll actually recall,
and fluent re-reading inflates it (Koriat & Bjork 2005; learners in Karpicke &
Roediger 2008 couldn't predict their own results). Testing recalibrates. The
scheduler logs predicted (confidence) vs actual (grade); surfacing that gap is the
cheapest, strongest antidote to false confidence.
→ *Ask for a confidence rating; show the predicted-vs-actual gap in `stats`.*

## 6. Error-driven review & the hypercorrection effect
Errors made with **high confidence** are the *most* fixable: the surprise of being
sure-but-wrong boosts attention, and the correction sticks (Butterfield &
Metcalfe 2001). Prior testing both strengthens the right answer and blocks the
error's return.
→ *On a confident error the scheduler flags `hypercorrect`: correct it vividly now,
re-test soon, and **rephrase** the item next time so it demands retrieval, not
recall of the question.*

## The difficulty dial: aim ~85% success
Learning is fastest when practice is hard but mostly succeeds — about 85% correct
/ 15% errors (Wilson et al. 2019; treat 80–90% as a target zone, not a law). Tune
difficulty with **levers, not by changing the content**: too easy → lengthen gaps,
interleave more, switch recognition→free recall, remove cues; too hard → add a
worked example, a brief blocked warm-up, shorten the gap, add a cue.

## Honesty about "10x" / "top 1%"
The literature supports substantially **more durable learning per hour** and far
better long-term retention than cramming — not a magic speed multiplier. Don't
promise "10x." Also avoid two popular myths: matching "learning styles"
(visual/auditory/etc.) has no credible support (Pashler et al. 2008), and the
"10,000-hour rule" is a popularization — deliberate practice matters but explains
only part of skill variance (Macnamara et al. 2014). What reliably moves a
beginner toward the top of a field is doing the six mechanisms above,
consistently. This skill's whole job is to make that consistency the easy path.

## Sources
Roediger & Karpicke 2006, *Psych Science*; Karpicke & Roediger 2008, *Science*;
Karpicke & Blunt 2011, *Science*; Dunlosky et al. 2013, *PSPI* (rereading &
highlighting = low utility; testing & spacing = high); Cepeda et al. 2006 (*Psych
Bulletin*) & 2008 (*Psych Science*); Rohrer & Taylor 2007; Rohrer 2012; Bisra et
al. 2018; Chase et al. 2009; Koriat & Bjork 2005; Butterfield & Metcalfe 2001;
Wilson et al. 2019, *Nature Communications*; Pashler et al. 2008; Macnamara et al.
2014.
