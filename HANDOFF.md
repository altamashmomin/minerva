# Handoff

- Last accepted: WP2 rules baseline + WP3 evaluation harness, tag `wp2-wp3-accepted-v1`, commit `1b5eeb9` (2026-11-06).
- Accepted as: a synthetic-data evaluation baseline, not validated production classification software.
- Test results: 21 of 21 pass (`python3 -m unittest test_evaluate.py` and `python3 test_evaluate.py`); end-to-end sample report runs on both splits.
- Accepted files: `accepted/wp2-wp3/`. Review history: `proposed/wp2-wp3/`. Decision: D-008.
- Next work package: WP1 dataset export (read-only export of labeled Ledger transactions to the WP3 CSV format), pending Alta's go-ahead. Turn 1 drafter to be agreed.
- WP1 in review: Turn 1 Claude, Turn 2 ChatGPT, Turn 3 Claude (`proposed/wp1/TURN3-wp1-for-chatgpt.md`, 15/15 tests). Next action: ChatGPT Turn 4 consensus, then Alta's sign-off before anything moves to `accepted/wp1/`.

## Known limitations carried forward
- WP1 export must give every row an explicit review_status (verified, imported, unverified) when the column exists.
- Small samples can give single-class merchant-grouped test sets; read sample metrics as plumbing checks only.

## Parking list (out of scope)
- Threshold sweep for MIN_HISTORY.
- Three-way train/validation/test split.
- More merchant normalization rules.
- Txn composition instead of inheritance from Features.
