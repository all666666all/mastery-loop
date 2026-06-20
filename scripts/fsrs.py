#!/usr/bin/env python3
"""
fsrs.py — FSRS-5 scheduling math (the "free spaced repetition scheduler").

Why this is here
----------------
SM-2 (the classic Anki algorithm) is robust and simple, but it tracks a single
"ease" number per card and is conservative: it tends to ask for more reviews than
needed to hit a target retention. FSRS models memory as two latent variables —
**Stability** (how many days until recall probability falls to 90%) and
**Difficulty** (how hard the item is for this learner) — fit to hundreds of
millions of real reviews. In published benchmarks it reaches the same retention
with roughly 20-30% fewer reviews. That is exactly the "省复习量 / fewer reviews"
win we want.

This module is pure math (stdlib only) so it can be unit-tested in isolation and
dropped into scheduler.py. Parameters are the FSRS-5 published defaults; the decay
is fixed at -0.5. Same-day ("short-term") scheduling is intentionally omitted —
mastery-loop reviews on a daily granularity, so intervals are always >= 1 day.

Forgetting curve:   R(t, S) = (1 + FACTOR * t / S) ** DECAY
Interval for target retention r:   t = (S / FACTOR) * (r ** (1/DECAY) - 1)
(At r = 0.9 this gives t = S, by construction.)

References: Jarrett Ye / open-spaced-repetition (FSRS-5); Anki FAQ on FSRS.
"""

import math

# FSRS-5 default parameters (19 weights). Indices:
#  0-3  initial stability for ratings Again/Hard/Good/Easy
#  4-5  initial difficulty
#  6    difficulty change per rating
#  7    difficulty mean-reversion strength
#  8-10 stability growth on successful recall
#  11-14 stability after a lapse (forgetting)
#  15   "hard" penalty   16  "easy" bonus   17-18 short-term (unused here)
W = [0.40255, 1.18385, 3.173, 15.69105, 7.1949, 0.5345, 1.4604, 0.0046,
     1.54575, 0.1192, 1.01925, 1.9395, 0.11, 0.29605, 2.2698, 0.2315,
     2.9898, 0.51655, 0.6621]

DECAY = -0.5
FACTOR = 0.9 ** (1.0 / DECAY) - 1.0  # ≈ 0.2345679
S_MIN = 0.1
D_MIN, D_MAX = 1.0, 10.0
DEFAULT_RETENTION = 0.9
MAX_INTERVAL = 36500  # 100 years; the horizon cap in scheduler.py handles exams


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


# rating: 1=Again (forgot), 2=Hard, 3=Good, 4=Easy
def init_difficulty(rating):
    return _clamp(W[4] - math.exp(W[5] * (rating - 1)) + 1.0, D_MIN, D_MAX)


def init_stability(rating):
    return max(W[rating - 1], S_MIN)


def retrievability(elapsed_days, stability):
    """Predicted probability of recall right now."""
    return (1.0 + FACTOR * max(elapsed_days, 0) / stability) ** DECAY


def interval_days(stability, request_retention=DEFAULT_RETENTION, max_interval=MAX_INTERVAL):
    ivl = (stability / FACTOR) * (request_retention ** (1.0 / DECAY) - 1.0)
    return int(_clamp(int(ivl + 0.5), 1, max_interval))


def _next_difficulty(difficulty, rating):
    delta = -W[6] * (rating - 3)
    damped = difficulty + delta * (10.0 - difficulty) / 9.0  # linear damping (FSRS-5)
    reverted = W[7] * init_difficulty(4) + (1.0 - W[7]) * damped  # mean-revert toward Easy
    return _clamp(reverted, D_MIN, D_MAX)


def _recall_stability(difficulty, stability, r, rating):
    hard = W[15] if rating == 2 else 1.0
    easy = W[16] if rating == 4 else 1.0
    growth = (math.exp(W[8]) * (11.0 - difficulty) * (stability ** -W[9])
              * (math.exp(W[10] * (1.0 - r)) - 1.0) * hard * easy)
    return stability * (1.0 + growth)


def _forget_stability(difficulty, stability, r):
    s = (W[11] * (difficulty ** -W[12]) * (((stability + 1.0) ** W[13]) - 1.0)
         * math.exp(W[14] * (1.0 - r)))
    # A lapse must never *raise* stability; cap at the prior value.
    return min(s, stability)


def review(rating, elapsed_days, stability=None, difficulty=None):
    """Return (new_stability, new_difficulty) after a review.

    First review (stability/difficulty are None): seed from the rating.
    Later reviews: update from elapsed time and current state.
    rating is 1..4 (Again/Hard/Good/Easy) — use grade_to_rating() to map a 0-5 grade.
    """
    if stability is None or difficulty is None:
        return max(init_stability(rating), S_MIN), init_difficulty(rating)
    r = retrievability(elapsed_days, stability)
    new_d = _next_difficulty(difficulty, rating)
    if rating == 1:  # Again -> forgot
        new_s = _forget_stability(difficulty, stability, r)
    else:
        new_s = _recall_stability(difficulty, stability, r, rating)
    return max(new_s, S_MIN), new_d


def grade_to_rating(grade):
    """Map mastery-loop's 0-5 grade to FSRS 1-4. 0-2 = lapse (Again);
    3 = shaky (Hard); 4 = good (Good); 5 = effortless (Easy)."""
    if grade <= 2:
        return 1
    if grade == 3:
        return 2
    if grade == 4:
        return 3
    return 4


# --------------------------------------------------------------------------- #
# self-check: `python3 fsrs.py` runs assertions + prints a sample progression
# --------------------------------------------------------------------------- #
def _selfcheck():
    ok = True

    def expect(name, cond):
        nonlocal ok
        ok = ok and cond
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")

    # interval == stability at retention 0.9 (definitional)
    expect("interval(S=10, r=0.9) ≈ 10", interval_days(10.0, 0.9) in (9, 10, 11))
    # higher target retention => shorter interval (more reviews)
    expect("higher retention -> shorter interval", interval_days(10, 0.95) < interval_days(10, 0.9))

    # a first "Good" seeds reasonable state
    s, d = review(grade_to_rating(4), 0)  # grade 4 -> Good
    expect("first Good seeds stability>0", s > 0 and D_MIN <= d <= D_MAX)

    # repeated good recalls grow stability and interval
    s, d = review(3, 0)  # first, Good
    prev_ivl = interval_days(s)
    grew = True
    for _ in range(4):
        s, d = review(3, prev_ivl, s, d)  # review right at the due interval
        ivl = interval_days(s)
        grew = grew and ivl >= prev_ivl
        prev_ivl = ivl
    expect("successive Good recalls -> non-decreasing intervals", grew)

    # a lapse reduces stability
    s_before, d0 = review(3, 0)
    s_before, d0 = review(3, interval_days(s_before), s_before, d0)
    s_after, _ = review(1, interval_days(s_before), s_before, d0)  # Again
    expect("lapse reduces stability", s_after < s_before)

    # difficulty rises on Again, falls on Easy
    _, d_again = review(1, 5, 10.0, 5.0)
    _, d_easy = review(4, 5, 10.0, 5.0)
    expect("Again raises difficulty vs Easy", d_again > d_easy)

    print("\nSample progression (all 'Good'), reviewing at each due interval:")
    s = d = None
    t = 0
    for i in range(6):
        s, d = review(3, t, s, d)
        t = interval_days(s)
        print(f"  rep {i+1}: stability={s:6.2f}  difficulty={d:4.2f}  next_interval={t}d")

    print("\nALL PASS" if ok else "\nSOME FAILED")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selfcheck() else 1)
