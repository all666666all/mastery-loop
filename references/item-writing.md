# Writing items that actually teach

An "item" is one unit of active recall. Item quality decides whether the whole
loop works — the scheduler will faithfully drill whatever you give it, including
garbage. Write items the learner has to *think* to answer, grounded in their
materials.

## The four types
- **recall** — a direct question with a short, checkable answer.
  Front: "What does a hash function map keys to?" Back: "A fixed-size index/bucket."
- **cloze** — a sentence with one key piece blanked out (`{{...}}`).
  Front: "Average-case lookup in a hash table is {{O(1)}}." Back: "O(1)".
- **problem** — a small task to *perform* (the heart of procedural mastery).
  Front: "Write the base case for a function that sums a linked list." Back: model
  answer + the invariant it relies on.
- **concept** — explain/contrast in their own words (graded on understanding).
  Front: "In your own words, why does recursion need a base case?" Back: the key
  points a good answer must hit.

For procedural subjects (math, algorithms, code), favour **problem** items and make
several variants per idea so interleaving can force method-selection. For
vocabulary/terminology, **cloze** and **recall**. For deep ideas, **concept**.

## Six rules (from card-craft + cognitive load research)
1. **Atomic — one fact or step per item.** If the answer has an "and," split it.
   Big items fail in vague ways and the scheduler can't tell what was forgotten.
2. **Demand retrieval, not recognition.** No yes/no, no multiple choice in the
   front, nothing that can be pattern-matched. The learner should have to *produce*.
3. **No give-aways.** The front must not contain (or rhyme with) its answer.
4. **Unambiguous answer.** You must be able to grade it consistently. If two
   answers are both "right," the item is too loose — tighten it.
5. **Context-light but self-contained.** Don't require remembering which lecture it
   came from; do include enough to stand alone.
6. **Minimum information principle.** Prefer many small precise items over one
   sprawling one. (Wozniak's classic "20 rules" is the deeper reference.)

## Bloom ladder — climb it as mastery grows
Start at remember/understand (recall, cloze, simple concept). As a topic goes
🟡→🟢, add apply/analyze items (problem, contrast, "when would you NOT use this?").
Mastery isn't reciting a definition; it's using and discriminating the idea.

## Good vs bad
- BAD (not atomic, give-away): Front "A hash table has O(1) average lookup and O(n)
  worst case — true?" → yes/no, contains the answer.
- GOOD: two items. (1) "Average-case lookup cost of a hash table?" → "O(1)".
  (2) "When does hash-table lookup degrade to O(n), and why?" → "All keys collide
  into one bucket; it becomes a linear scan."

- BAD (ambiguous): "Explain recursion." → ungradeable.
- GOOD (concept, scoped): "Name the two parts every recursive function needs, and
  what each does." → "Base case (stops it) + recursive case (shrinks toward the
  base)."

## The VERIFY GATE (run before every `add`)
Re-read each drafted item against the source with the single goal of *finding
faults*. Reject or fix any item that:
- states a fact not supported by the materials (or mark it clearly as your
  addition, not the source's);
- bundles more than one fact/step (split it);
- can be answered by recognition or from cues in the front;
- has an ambiguous or unverifiable answer.

A wrong item is worse than no item: the scheduler would rehearse the error for
weeks. When in doubt, cut it.

## JSON shape to pipe into `scheduler.py add`
A JSON array; `topic` and `front` are required, the rest optional:
```json
[
  {"topic": "hashing", "type": "recall",
   "front": "Average-case lookup cost of a hash table?",
   "back": "O(1).",
   "source": "Lecture 5, slide 12"},
  {"topic": "recursion", "type": "problem",
   "front": "Write the base case for summing a linked list.",
   "back": "if (head == NULL) return 0;  // empty list contributes 0",
   "source": "Lecture 3"}
]
```
`topic` is a stable English slug (used for interleaving and mastery). `front`/`back`
are in the **learner's language**. Identical `topic`+`front` is de-duplicated
automatically, so re-running `add` is safe.
