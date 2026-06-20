#!/usr/bin/env python3
"""
Deterministic tests for scheduler.py (+ FSRS integration). No pytest needed:
run `python3 test_scheduler.py`. Exit code 0 = all passed.
"""
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCHED = os.path.join(HERE, "..", "scripts", "scheduler.py")
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import scheduler as S  # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name}")


def run(store, *args, expect_ok=True):
    out = subprocess.run([sys.executable, SCHED, "--store", store, *args],
                         capture_output=True, text=True, encoding="utf-8")
    if expect_ok:
        assert out.returncode == 0, out.stdout + out.stderr
    return out


def jrun(store, *args):
    return json.loads(run(store, *args).stdout)


def adjacency(order):
    return sum(1 for i in range(1, len(order)) if order[i] == order[i - 1])


# ---- SM-2 core (pinned to algorithm="sm2") -------------------------------- #
def test_sm2_growth():
    d = dt.date(2026, 1, 1)
    it = {"ease": 2.5, "reps": 0, "interval": 0, "lapses": 0, "history": []}
    S.reschedule(it, 5, 5, d, None, "sm2")
    check("sm2 first good recall -> 1 day", it["interval"] == 1)
    S.reschedule(it, 5, 5, d, None, "sm2")
    check("sm2 second good recall -> 6 days", it["interval"] == 6)
    S.reschedule(it, 4, 4, d, None, "sm2")
    check("sm2 third good recall -> grows (>=14d)", it["interval"] >= 14)
    check("sm2 ease stayed sane (>=1.3)", it["ease"] >= 1.3)


def test_sm2_lapse():
    d = dt.date(2026, 1, 1)
    it = {"ease": 2.5, "reps": 3, "interval": 30, "lapses": 0, "history": []}
    before = it["ease"]
    S.reschedule(it, 1, 2, d, None, "sm2")
    check("sm2 lapse -> interval back to 1", it["interval"] == 1)
    check("sm2 lapse -> reps reset", it["reps"] == 0)
    check("sm2 lapse -> ease dropped", it["ease"] < before)
    check("sm2 lapse -> lapses incremented", it["lapses"] == 1)
    check("sm2 low-confidence wrong -> not flagged", it["flag"] is None)


def test_confident_error_sm2():
    d = dt.date(2026, 1, 1)
    it = {"ease": 2.5, "reps": 2, "interval": 6, "lapses": 0, "history": []}
    S.reschedule(it, 0, 5, d, None, "sm2")  # sure (5) but wrong (0)
    check("sm2 confident error -> flagged hypercorrect", it["flag"] == "hypercorrect")
    check("sm2 confident error -> retest tomorrow", it["interval"] == 1)


def test_horizon_sm2():
    when = dt.date(2026, 1, 1)
    exam = dt.date(2026, 1, 4)  # 3 days away
    it = {"ease": 2.5, "reps": 5, "interval": 40, "lapses": 0, "history": []}
    S.reschedule(it, 5, 5, when, exam, "sm2")
    check("horizon: interval never overshoots exam", (when + dt.timedelta(days=it["interval"])) <= exam)
    check("horizon: still schedules a spaced review (>=1d)", it["interval"] >= 1)
    check("horizon: due never lands past the exam", dt.date.fromisoformat(it["due"]) <= exam)


# ---- FSRS (the default) --------------------------------------------------- #
def test_fsrs_integration():
    d = dt.date(2026, 1, 1)
    it = {"reps": 0, "interval": 0, "lapses": 0, "history": [],
          "stability": None, "difficulty": None, "ease": 2.5, "last_reviewed": None}
    S.reschedule(it, 5, 5, d, None, "fsrs", 0.9)
    check("fsrs first grade sets stability", it["stability"] is not None)
    check("fsrs first interval >= 1", it["interval"] >= 1)
    i1 = it["interval"]
    d2 = d + dt.timedelta(days=i1)
    S.reschedule(it, 4, 4, d2, None, "fsrs", 0.9)
    check("fsrs good review grows interval", it["interval"] > i1)
    s_before = it["stability"]
    d3 = d2 + dt.timedelta(days=it["interval"])
    S.reschedule(it, 1, 2, d3, None, "fsrs", 0.9)
    check("fsrs lapse reduces stability", it["stability"] < s_before)
    check("fsrs lapse increments lapses", it["lapses"] == 1)
    it2 = {"reps": 2, "interval": 6, "lapses": 0, "history": [],
           "stability": 20.0, "difficulty": 5.0, "last_reviewed": "2026-01-01"}
    S.reschedule(it2, 0, 5, dt.date(2026, 1, 20), None, "fsrs", 0.9)
    check("fsrs confident error -> retest tomorrow", it2["interval"] == 1 and it2["flag"] == "hypercorrect")


# ---- interleaving --------------------------------------------------------- #
def test_interleave_balanced():
    items = [{"topic": "a", "due": "2026-01-01", "lapses": 0} for _ in range(3)]
    items += [{"topic": "b", "due": "2026-01-01", "lapses": 0} for _ in range(3)]
    order = [it["topic"] for it in S.interleave(items)]
    check("balanced interleave -> zero adjacency", adjacency(order) == 0)


def test_interleave_dominant():
    items = [{"topic": "a", "due": "2026-01-01", "lapses": 0} for _ in range(5)]
    items += [{"topic": "b", "due": "2026-01-01", "lapses": 0}]
    order = [it["topic"] for it in S.interleave(items)]
    check("dominant interleave -> minimal adjacency (<=3, beats naive 4)", adjacency(order) <= 3)
    check("dominant interleave -> minority item used to break the run", order.count("b") == 1)


def test_content_id_stable():
    a = S.content_id("Recursion", "what is a base case?")
    b = S.content_id("recursion ", "What is a Base Case? ")
    check("content id is case/space-insensitive (dedup works)", a == b)


# ---- integration: the CLI end to end (default = FSRS) --------------------- #
def test_cli_flow():
    with tempfile.TemporaryDirectory() as tmp:
        store = os.path.join(tmp, "items.json")
        r = jrun(store, "init", "--exam", "2026-12-01", "--new-per-day", "5")
        check("init ok", r["ok"] and r["meta"]["exam_date"] == "2026-12-01")
        check("init defaults to fsrs", r["meta"]["algorithm"] == "fsrs")

        items = [
            {"topic": "recursion", "type": "concept", "front": "What is a base case?", "back": "the stop"},
            {"topic": "recursion", "type": "concept", "front": "What is a base case?", "back": "dup"},
            {"topic": "hashing", "type": "recall", "front": "Average lookup cost?", "back": "O(1)"},
        ]
        p = subprocess.run([sys.executable, SCHED, "--store", store, "add", "--json", "-"],
                           input=json.dumps(items), capture_output=True, text=True, encoding="utf-8")
        radd = json.loads(p.stdout)
        check("add dedups identical front", radd["added"] == 2 and radd["skipped_duplicates_or_invalid"] == 1)

        due = jrun(store, "due")
        check("new items appear in queue", due["counts"]["new"] == 2)
        check("nothing in review pool yet", due["counts"]["due_reviews"] == 0)

        first = due["new"][0]["id"]
        rg = jrun(store, "grade", "--id", first, "--grade", "5", "--confidence", "5")
        check("grading moves item out to >=1 day", rg["new_interval_days"] >= 1)
        check("fsrs grade returns stability", "stability" in rg)

        bad = run(store, "grade", "--id", first, "--grade", "7", expect_ok=False)
        check("out-of-range grade is rejected", bad.returncode != 0 and not json.loads(bad.stdout)["ok"])

        jrun(store, "distill", "--learner", "fast on recursion", "--constraint", "contrast base vs recursive")
        st = jrun(store, "stats")
        check("distill recorded (visible in stats)", st["last_distilled"] is not None and st["days_since_distill"] == 0)
        check("stats returns mastery by topic", "recursion" in st["mastery_by_topic"])
        check("stats counts the graded attempt", st["totals"]["reviews_done"] == 1)
        check("graded item left the new pool", st["totals"]["new_available"] == 1)


def main():
    for fn in [test_sm2_growth, test_sm2_lapse, test_confident_error_sm2, test_horizon_sm2,
               test_fsrs_integration, test_interleave_balanced, test_interleave_dominant,
               test_content_id_stable, test_cli_flow]:
        print(fn.__name__)
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
