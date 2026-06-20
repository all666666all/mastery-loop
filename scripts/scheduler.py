#!/usr/bin/env python3
"""
mastery-loop scheduler — the deterministic spaced-repetition engine.

Why this exists
---------------
The single biggest failure mode of AI "study" tools is that they GENERATE
material and then leave the actual remembering to the user. Remembering is the
hard part, and it is governed by the forgetting curve, not by how good the notes
look. This script owns timing and state so the language model never has to guess
"have they forgotten this yet?" — a question LLMs answer unreliably and
inconsistently across sessions.

Division of labour (copied from the best agent-maintained KBs):
  * This SCRIPT does every structural / numeric mutation: due dates, ease,
    intervals, lapses, interleaving, mastery, calibration, and a timestamped
    record of each session's distillation. Deterministic and testable.
  * The MODEL does only prose + judgement: writing items, grading open answers,
    explaining errors, adapting tone.

Algorithm: SM-2 ("SuperMemo 2", the classic Anki algorithm) with three
evidence-based additions:
  1. Exam-horizon scaling  — intervals are capped/compressed so every item gets
     at least one more spaced review before the exam date, and a due date is
     never placed past the exam (Cepeda et al. 2008: the optimal gap is a
     shrinking fraction of the retention interval; err long not short, but never
     overshoot the test).
  2. Confident-error flag  — a wrong answer given with high confidence is
     "hypercorrection gold" (Butterfield & Metcalfe 2001): re-tested tomorrow AND
     flagged so the model rephrases it instead of re-showing the same prompt.
  3. Interleaving          — the daily review queue is spread across topics so
     consecutive items can't be solved by the same procedure (Rohrer & Taylor
     2007). Uses an optimal greedy (largest bucket first) that minimises
     same-topic adjacency.

FSRS (the newer, ~20-30% more efficient scheduler) is a drop-in upgrade; see
references/scheduler.md. SM-2 is the default because it is simple, robust, and
verifiable without trained parameters — "大道至简" where reliability matters.

Storage: a single JSON file (default .mastery/items.json). Plain text, the user
owns it, Obsidian/Anki can read it. Python stdlib only, no dependencies.

Commands:
  init     create the store (optionally with an exam date / target retention)
  config   update meta (exam date, pace, max reviews/day, target retention)
  add      append items from a JSON array (file or stdin); de-duplicates
  due      print today's queue: interleaved reviews + a capped batch of new items
  grade    record an attempt (grade 0-5, optional confidence 1-5); reschedules
  distill  record that this session updated the learner profile / constraints
  stats    mastery per topic, calibration (predicted vs actual), streak, counts

All commands print JSON to stdout so the calling agent can parse them.
"""

import argparse
import datetime as dt
import hashlib
import heapq
import json
import os
import sys

import fsrs  # local module (same scripts/ dir): FSRS-5 scheduling math

DEFAULT_STORE = os.path.join(".mastery", "items.json")
EASE_FLOOR = 1.3
EASE_START = 2.5
VALID_TYPES = ("recall", "cloze", "problem", "concept")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def today(date_str=None):
    return dt.date.fromisoformat(date_str) if date_str else dt.date.today()


def iso_now():
    return dt.datetime.now().isoformat(timespec="seconds")


def round_half_up(x):
    """Predictable rounding (Python's round() is half-to-even, which makes
    interval growth subtly non-monotonic)."""
    return int(x + 0.5)


def content_id(topic, front):
    h = hashlib.sha1(f"{topic.strip().lower()}|{front.strip().lower()}".encode("utf-8"))
    return h.hexdigest()[:8]


def load_store(path):
    if not os.path.exists(path):
        die(f"store not found: {path}  (run `init` first)")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_store(path, store):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)  # atomic write — never leave a half-written store


def die(msg):
    print(json.dumps({"ok": False, "error": msg}, ensure_ascii=False))
    sys.exit(1)


def emit(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def new_meta(exam=None, retention=0.9, new_per_day=8, max_reviews=60, algorithm="fsrs"):
    return {
        "version": 1,
        "created": iso_now(),
        "algorithm": algorithm,   # "fsrs" (default, fewer reviews) or "sm2"
        "exam_date": exam,
        "target_retention": retention,
        "new_per_day": new_per_day,
        "max_reviews_per_day": max_reviews,
        "last_distilled": None,   # set by `distill`; surfaced so skipping is visible
        "distill_log": [],
    }


def days_since(iso_date, when):
    return (when - dt.date.fromisoformat(iso_date)).days if iso_date else None


# --------------------------------------------------------------------------- #
# scheduling core (SM-2 + horizon scaling + confident-error handling)
# --------------------------------------------------------------------------- #
def _finalize(item, grade, confidence, when, interval, exam_date, flag):
    """Shared tail for both algorithms: apply hypercorrection + exam-horizon
    scaling, set the due date (never past the exam), and append history."""
    if flag == "hypercorrect":
        interval = 1  # confident error -> always retest tomorrow, whatever the algorithm
    if exam_date is not None:
        days_left = (exam_date - when).days
        if days_left <= 1:
            interval = 1  # keep testing through the final stretch
        elif interval >= days_left:
            interval = max(1, round_half_up(days_left * 0.5))  # one spaced pass mid-way
    due_date = when + dt.timedelta(days=interval)
    if exam_date is not None and due_date > exam_date:
        due_date = exam_date  # never schedule the next review past the exam itself
    item["interval"] = interval
    item["last_grade"] = grade
    item["last_confidence"] = confidence
    item["last_reviewed"] = when.isoformat()
    item["flag"] = flag
    item["due"] = due_date.isoformat()
    item.setdefault("history", []).append(
        {"date": when.isoformat(), "grade": grade, "conf": confidence, "interval": interval}
    )


def reschedule_sm2(item, grade, confidence, when, exam_date):
    """Classic SM-2 (the simple, robust baseline)."""
    ease = item.get("ease", EASE_START)
    reps = item.get("reps", 0)
    interval = item.get("interval", 0)
    lapses = item.get("lapses", 0)
    flag = None
    if grade < 3:
        lapses += 1
        reps = 0
        ease = max(EASE_FLOOR, ease - 0.20)
        interval = 1
        if confidence is not None and confidence >= 4:
            flag = "hypercorrect"
    else:
        reps += 1
        if reps == 1:
            interval = 1
        elif reps == 2:
            interval = 6
        else:
            interval = max(1, round_half_up(interval * ease))
        ease = ease + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))
        ease = max(EASE_FLOOR, ease)
    item["ease"] = round(ease, 4)
    item["reps"] = reps
    item["lapses"] = lapses
    _finalize(item, grade, confidence, when, interval, exam_date, flag)


def reschedule_fsrs(item, grade, confidence, when, exam_date, target_retention):
    """FSRS-5: tracks Stability + Difficulty; fewer reviews for the same retention."""
    rating = fsrs.grade_to_rating(grade)
    last = item.get("last_reviewed")
    elapsed = (when - dt.date.fromisoformat(last)).days if last else 0
    s, d = fsrs.review(rating, elapsed, item.get("stability"), item.get("difficulty"))
    item["stability"] = round(s, 4)
    item["difficulty"] = round(d, 4)
    item["reps"] = item.get("reps", 0) + 1  # count reviews; never reset (unlike SM-2)
    if grade < 3:
        item["lapses"] = item.get("lapses", 0) + 1
    flag = "hypercorrect" if (grade < 3 and confidence is not None and confidence >= 4) else None
    interval = fsrs.interval_days(s, target_retention)
    _finalize(item, grade, confidence, when, interval, exam_date, flag)


def reschedule(item, grade, confidence, when, exam_date, algorithm="fsrs", target_retention=0.9):
    """Mutate `item` after an attempt graded `grade` (0-5). Dispatches to FSRS
    (default; fewer reviews for the same retention) or SM-2 (simpler/older)."""
    grade = max(0, min(5, int(grade)))  # defensive; cmd_grade validates loudly
    if algorithm == "sm2":
        reschedule_sm2(item, grade, confidence, when, exam_date)
    else:
        reschedule_fsrs(item, grade, confidence, when, exam_date, target_retention)
    return item


def interleave(items):
    """Spread items so the same topic is as non-adjacent as possible.

    Greedy "reorganise so equal items are k apart": always emit from the largest
    remaining topic bucket whose topic != the one just emitted. This is provably
    optimal at minimising adjacency. Perfect zero-adjacency is impossible when one
    topic holds more than half the queue (e.g. 5 of 6) — then we still break the
    run up as much as the counts allow, instead of dumping the topic in one block.
    """
    buckets = {}
    for it in items:
        buckets.setdefault(it["topic"], []).append(it)
    # Within a topic: most overdue first, then most-lapsed (struggling) first.
    for t in buckets:
        buckets[t].sort(key=lambda x: (x["due"], -x.get("lapses", 0)))
    # Max-heap on remaining count; tie-break alphabetically for determinism.
    heap = [(-len(v), t) for t, v in buckets.items()]
    heapq.heapify(heap)
    out, held = [], None  # `held` = bucket used last step, withheld one round
    while heap or held:
        if not heap:                       # only the held topic remains
            cnt, t = held
            held = None
        else:
            cnt, t = heapq.heappop(heap)
            if held is not None:
                heapq.heappush(heap, held)
                held = None
        out.append(buckets[t].pop(0))
        cnt += 1                            # consumed one (counts are negative)
        if cnt < 0:
            held = (cnt, t)                 # hold so we don't reuse it next step
    return out


# --------------------------------------------------------------------------- #
# mastery + calibration (for stats)
# --------------------------------------------------------------------------- #
def item_strength(it):
    if not it.get("last_reviewed"):
        return 0.0
    if it.get("stability") is not None:        # FSRS: stability is the real signal
        base = min(it["stability"], 60.0) / 60.0
    else:                                       # SM-2: fall back to interval
        base = min(it.get("interval", 0), 30) / 30.0
    penalty = min(it.get("lapses", 0) * 0.1, 0.4)
    return max(0.0, base - penalty)


def topic_mastery(items):
    by_topic = {}
    for it in items:
        by_topic.setdefault(it["topic"], []).append(it)
    out = {}
    for topic, its in sorted(by_topic.items()):
        score = sum(item_strength(i) for i in its) / len(its)
        emoji = "🔴" if score < 0.34 else ("🟡" if score < 0.67 else "🟢")
        out[topic] = {"score": round(score, 2), "status": emoji, "items": len(its),
                      "mature": sum(1 for i in its if i.get("interval", 0) >= 21)}
    return out


def calibration(items):
    """Compare confidence (prediction) with grade (reality) to expose the
    fluency illusion. Only confidence>=4 (high) and <=2 (low) are scored; 3 is
    neutral. Returns None rates until there is enough history to be meaningful."""
    hi_total = hi_wrong = lo_total = lo_right = n = 0
    for it in items:
        for h in it.get("history", []):
            conf, grade = h.get("conf"), h.get("grade")
            if conf is None or grade is None:
                continue
            n += 1
            correct = grade >= 3
            if conf >= 4:
                hi_total += 1
                hi_wrong += 0 if correct else 1
            elif conf <= 2:
                lo_total += 1
                lo_right += 1 if correct else 0
    return {
        "graded_attempts": n,
        "enough_data": n >= 5,  # below this, don't surface to the learner
        "overconfidence_rate": round(hi_wrong / hi_total, 2) if hi_total else None,
        "underconfidence_rate": round(lo_right / lo_total, 2) if lo_total else None,
        "note": "overconfidence = sure-but-wrong (the illusion); top priority to fix.",
    }


def streak(items):
    days = {h["date"] for it in items for h in it.get("history", [])}
    if not days:
        return 0
    s, cur = 0, today()
    while cur.isoformat() in days:
        s += 1
        cur -= dt.timedelta(days=1)
    return s


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def cmd_init(args):
    if os.path.exists(args.store) and not args.force:
        die(f"store already exists: {args.store}  (use --force to overwrite)")
    store = {"meta": new_meta(args.exam, args.retention, args.new_per_day, args.max_reviews,
                              args.algorithm), "items": []}
    save_store(args.store, store)
    emit({"ok": True, "created": args.store, "meta": store["meta"]})


def cmd_config(args):
    store = load_store(args.store)
    m = store["meta"]
    if args.exam is not None:
        m["exam_date"] = args.exam or None
    if args.retention is not None:
        m["target_retention"] = args.retention
    if args.new_per_day is not None:
        m["new_per_day"] = args.new_per_day
    if args.max_reviews is not None:
        m["max_reviews_per_day"] = args.max_reviews
    if args.algorithm is not None:
        m["algorithm"] = args.algorithm
    save_store(args.store, store)
    emit({"ok": True, "meta": m})


def cmd_add(args):
    store = load_store(args.store)
    raw = sys.stdin.read() if args.json in (None, "-") else open(args.json, encoding="utf-8").read()
    try:
        incoming = json.loads(raw)
    except json.JSONDecodeError as e:
        die(f"invalid JSON for add: {e}")
    if isinstance(incoming, dict):
        incoming = [incoming]
    existing = {it["id"] for it in store["items"]}
    when = today(args.date)
    added, skipped = 0, 0
    for rec in incoming:
        topic = str(rec.get("topic", "")).strip()
        front = str(rec.get("front", "")).strip()
        back = str(rec.get("back", "")).strip()
        typ = str(rec.get("type", "recall")).strip() or "recall"
        if not topic or not front:
            skipped += 1
            continue
        if typ not in VALID_TYPES:
            typ = "recall"
        iid = content_id(topic, front)
        if iid in existing:
            skipped += 1
            continue
        existing.add(iid)
        store["items"].append({
            "id": iid, "topic": topic, "type": typ, "front": front, "back": back,
            "source": str(rec.get("source", "")).strip(),
            "created": iso_now(), "due": when.isoformat(),
            "interval": 0, "ease": EASE_START, "reps": 0, "lapses": 0,
            "stability": None, "difficulty": None,  # set on first FSRS review
            "last_grade": None, "last_confidence": None, "last_reviewed": None,
            "flag": None, "suspended": False, "history": [],
        })
        added += 1
    save_store(args.store, store)
    emit({"ok": True, "added": added, "skipped_duplicates_or_invalid": skipped,
          "total_items": len(store["items"])})


def cmd_due(args):
    store = load_store(args.store)
    m = store["meta"]
    when = today(args.date)
    items = [it for it in store["items"] if not it.get("suspended")]

    reviews = [it for it in items if it.get("last_reviewed") and it["due"] <= when.isoformat()]
    reviews = interleave(reviews)
    max_rev = args.max if args.max is not None else m.get("max_reviews_per_day", 60)
    reviews = reviews[:max_rev]

    new_cap = args.new if args.new is not None else m.get("new_per_day", 8)
    new_items = [it for it in items if not it.get("last_reviewed") and it["due"] <= when.isoformat()]
    new_items.sort(key=lambda x: x["created"])
    new_items = new_items[:new_cap]

    def view(it):
        return {"id": it["id"], "topic": it["topic"], "type": it["type"],
                "front": it["front"], "back": it["back"], "source": it.get("source", ""),
                "flag": it.get("flag"), "reps": it.get("reps", 0), "lapses": it.get("lapses", 0)}

    emit({
        "ok": True, "date": when.isoformat(), "exam_date": m.get("exam_date"),
        "last_distilled": m.get("last_distilled"),
        "days_since_distill": days_since(m.get("last_distilled"), when),
        "counts": {"due_reviews": len(reviews), "new": len(new_items),
                   "total_items": len(store["items"])},
        "review": [view(it) for it in reviews],
        "new": [view(it) for it in new_items],
        "guidance": "Show `front` only; get the learner's answer FIRST; then reveal `back` and grade. "
                    "Interleaved on purpose — do not regroup by topic. "
                    "End the session by calling `distill` to record what you learned about the learner.",
    })


def cmd_grade(args):
    if not (0 <= args.grade <= 5):
        die("grade must be 0-5 (0-2 = lapse/reset, 3-5 = pass)")
    if args.confidence is not None and not (1 <= args.confidence <= 5):
        die("confidence must be 1-5")
    store = load_store(args.store)
    when = today(args.date)
    exam = dt.date.fromisoformat(store["meta"]["exam_date"]) if store["meta"].get("exam_date") else None
    target = next((it for it in store["items"] if it["id"] == args.id), None)
    if target is None:
        die(f"item not found: {args.id}")
    reschedule(target, args.grade, args.confidence, when, exam,
               store["meta"].get("algorithm", "fsrs"), store["meta"].get("target_retention", 0.9))
    save_store(args.store, store)
    out = {"ok": True, "id": target["id"], "topic": target["topic"],
           "new_interval_days": target["interval"], "next_due": target["due"],
           "reps": target["reps"], "lapses": target["lapses"], "flag": target["flag"]}
    if target.get("stability") is not None:
        out["stability"], out["difficulty"] = target["stability"], target["difficulty"]
    else:
        out["ease"] = target.get("ease")
    emit(out)


def cmd_distill(args):
    """Mechanical owner of the self-improving loop: record that this session
    updated learner.md / constraints.md, with a timestamp, so a skipped
    distillation is visible (due/stats report `days_since_distill`)."""
    store = load_store(args.store)
    when = today(args.date)
    store["meta"]["last_distilled"] = when.isoformat()
    store["meta"].setdefault("distill_log", []).append(
        {"date": when.isoformat(), "learner": args.learner or "", "constraint": args.constraint or ""})
    save_store(args.store, store)
    emit({"ok": True, "last_distilled": when.isoformat(),
          "entries": len(store["meta"]["distill_log"])})


def cmd_stats(args):
    store = load_store(args.store)
    when = today(args.date)
    items = store["items"]
    m = store["meta"]
    due_now = sum(1 for it in items if not it.get("suspended")
                  and it.get("last_reviewed") and it["due"] <= when.isoformat())
    new_avail = sum(1 for it in items if not it.get("suspended") and not it.get("last_reviewed"))
    emit({
        "ok": True, "date": when.isoformat(), "exam_date": m.get("exam_date"),
        "last_distilled": m.get("last_distilled"),
        "days_since_distill": days_since(m.get("last_distilled"), when),
        "totals": {"items": len(items), "due_today": due_now, "new_available": new_avail,
                   "reviews_done": sum(len(it.get("history", [])) for it in items)},
        "streak_days": streak(items),
        "mastery_by_topic": topic_mastery(items),
        "calibration": calibration(items),
    })


# --------------------------------------------------------------------------- #
# arg parsing
# --------------------------------------------------------------------------- #
def build_parser():
    p = argparse.ArgumentParser(description="mastery-loop spaced-repetition scheduler")
    p.add_argument("--store", default=DEFAULT_STORE, help="path to items.json")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="create the store")
    pi.add_argument("--exam", default=None, help="exam date YYYY-MM-DD")
    pi.add_argument("--retention", type=float, default=0.9)
    pi.add_argument("--new-per-day", type=int, default=8, dest="new_per_day")
    pi.add_argument("--max-reviews", type=int, default=60, dest="max_reviews")
    pi.add_argument("--algorithm", choices=["fsrs", "sm2"], default="fsrs")
    pi.add_argument("--force", action="store_true")
    pi.set_defaults(func=cmd_init)

    pc = sub.add_parser("config", help="update exam date / pace / caps")
    pc.add_argument("--exam", default=None, help="exam date YYYY-MM-DD (empty string clears)")
    pc.add_argument("--retention", type=float, default=None)
    pc.add_argument("--new-per-day", type=int, default=None, dest="new_per_day")
    pc.add_argument("--max-reviews", type=int, default=None, dest="max_reviews")
    pc.add_argument("--algorithm", choices=["fsrs", "sm2"], default=None)
    pc.set_defaults(func=cmd_config)

    pa = sub.add_parser("add", help="append items from JSON (file or stdin)")
    pa.add_argument("--json", default="-", help="path to JSON array, or - for stdin")
    pa.add_argument("--date", default=None)
    pa.set_defaults(func=cmd_add)

    pd = sub.add_parser("due", help="today's interleaved queue")
    pd.add_argument("--date", default=None)
    pd.add_argument("--max", type=int, default=None, help="max reviews this call")
    pd.add_argument("--new", type=int, default=None, help="max new items this call")
    pd.set_defaults(func=cmd_due)

    pg = sub.add_parser("grade", help="record an attempt and reschedule")
    pg.add_argument("--id", required=True)
    pg.add_argument("--grade", type=int, required=True, help="0-5 (0-2 lapse, 3-5 pass)")
    pg.add_argument("--confidence", type=int, default=None, help="1-5 (optional)")
    pg.add_argument("--date", default=None)
    pg.set_defaults(func=cmd_grade)

    pn = sub.add_parser("distill", help="record session learning about the learner")
    pn.add_argument("--learner", default=None, help="one line added to learner.md")
    pn.add_argument("--constraint", default=None, help="one rule added to constraints.md")
    pn.add_argument("--date", default=None)
    pn.set_defaults(func=cmd_distill)

    ps = sub.add_parser("stats", help="mastery, calibration, streak")
    ps.add_argument("--date", default=None)
    ps.set_defaults(func=cmd_stats)
    return p


def main(argv=None):
    # Force UTF-8 output. The mastery emojis (🔴🟡🟢) and non-Latin item text must
    # not crash on consoles whose default codec is e.g. GBK (Chinese Windows) —
    # exactly the locale many target users have. Without this, `stats`/`due` raise
    # UnicodeEncodeError on those machines.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
