# MINERVA 0.1 — WP1.1 Turn 4 (consensus)

**Status:** Consensus reached (ChatGPT Turn 3 at `7e274c5`, Claude Turn 4). Awaiting Alta's sign-off.
Candidate stays in `proposed/wp1.1/` until then. Nothing in `accepted/` changes.

## Claude's verification of Turn 3 (independent, Python 3.13.18)
- `python3 -B -W error::ResourceWarning -m unittest test_backlog.py` → 15/15; `python3 -B -W error::ResourceWarning test_backlog.py` → 15/15.
- Accepted WP1 16/16, WP2/WP3 21/21 unchanged. `__pycache__` ignored, not tracked.
- End-to-end on a synthetic snapshot: a merchant with one labeled row and two at `Other` reports `known_label=Transport, labeled_count=1, txn_ids=[L2, L3]`; an unseen merchant reports blank/0. Counts-only stdout; files 0600 in a 0700 fresh folder.

## Per-finding acceptance
| Finding | Status |
|---|---|
| T2 #1 known_label / labeled_count hint | Agree, as revised in T3 (blank + positive count = conflict; unmasked names compared; literal `mixed` category no longer collides) |
| T2 #2 txn_ids per group | Agree (date, then numeric id; tie test added in T3) |
| T2 #3 coupling to accepted WP1 | Agree with limitation (L7) |
| T3 — hint representation | Agree |
| T3 — checklist semantics vs Ledger's sheet | Agree (sheet is per-month, exact-category, one edit per checked id; report spans months and includes blank categories) |
| T3 — rerun suites when WP1 changes | Agree with limitation (L7) |

## Limitations to record (D-010 draft)
- L7. `backlog.py` imports accepted WP1 (`open_readonly`, `check_schema`, `build`, `LONG_DIGITS`) and WP2/WP3 `normalize` by path. A WP1 change that keeps row keys but alters filtering or provenance changes this report silently; rerun both synthetic suites and re-read this record whenever an accepted dependency revs.
- L8. `known_label` counts imported as well as verified labels and applies no minimum history; it is a hint for a human, never a prediction, and establishes nothing for WP3.
- L1–L6 from D-009 carry over (verified is a provenance proxy; masking partial; normalization conservative).

## Draft decision record — D-010: WP1.1 backlog report accepted (date TBD)
- Outcome: Turn 4 consensus; Alta's sign-off pending.
- Accepted as: a read-only, snapshot-only private report that organises Alta's labeling and adjudication work; it writes nothing to Ledger.
- Code: `accepted/wp1.1/` (backlog.py, test_backlog.py), tag `wp1.1-accepted-v1`.
- Verification: 15/15 via both invocations with ResourceWarning as error; accepted suites unchanged.
- Limitations: L7, L8 above; L1–L6 carried.
- History: Turn 1 ChatGPT, Turn 2 Claude, Turn 3 ChatGPT, Turn 4 consensus. Review files in `proposed/wp1.1/`.

## For Alta's sign-off
On approval: copy both files to `accepted/wp1.1/`, commit, tag `wp1.1-accepted-v1`, add `decisions/D-010-wp1.1-accepted.md` + a `DECISIONS.md` line, update `HANDOFF.md`. Then the human half of WP1.1 begins: run the report on a fresh snapshot, label the backlog in Ledger merchant-by-merchant using `txn_ids`, adjudicate `verified.csv`, re-export with WP1, rerun WP3.
