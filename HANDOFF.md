# Handoff

- Last accepted: WP1 dataset export, tag `wp1-accepted-v1` (2026-11-06). Previous: WP2/WP3, tag `wp2-wp3-accepted-v1`, commit `1b5eeb9`.
- Accepted as: a read-only, snapshot-only export; `verified` is a provenance proxy, not adjudicated ground truth (D-009, L1).
- Test results: 16 of 16 pass (`python3 -m unittest test_export.py` and `python3 test_export.py`); synthetic export runs end-to-end through `accepted/wp2-wp3/evaluate.py`.
- Accepted files: `accepted/wp1/`, `accepted/wp2-wp3/`. Review history: `proposed/wp1/`, `proposed/wp2-wp3/`. Decisions: D-008, D-009.
- First real-data run (2026-11-06, Alta, Mac, `python3.13`): `schema_version=22`, 15 categories, **89 labeled spending rows** (77 verified, 12 imported); skipped 42 inflows, 9 settlements, **227 unlabeled (`Other`)**. 72% of spending rows carry no label. WP3 harness result (`python3.13`, MIN_HISTORY=3, TEST_FRACTION=0.3): temporal split train=53/test=24 — accepted 3/24 (coverage 12.5%), precision 100% (95% Wilson 43.9–100%), false acceptance 0%; abstentions: 12 unseen merchants, 9 insufficient history. Merchant-grouped split train=66/test=11 — 0 accepted (all test merchants unseen by construction). Three normalization merges flagged for Alta's review (case/store-number variants). Test true labels are dining-heavy (15/24). **This is the baseline WP4 must beat.**
- Canonical snapshot procedure (Pi has no `sqlite3` CLI; macOS SQLite refuses a read-only open of a WAL-flagged copy):
  1. On the Pi: `python3 -c "import sqlite3; s=sqlite3.connect('/home/altamash/pifinance/finance.db'); d=sqlite3.connect('/home/altamash/private/ledger-snapshot.db'); s.backup(d); d.execute('PRAGMA journal_mode=DELETE'); d.close(); s.close()"`
  2. `scp` it to `~/private/` on the Mac (outside any Git worktree).
  3. `python3.13 accepted/wp1/export.py --db ~/private/ledger-snapshot.db --out ~/private/export-<date>` then `python3.13 accepted/wp2-wp3/evaluate.py --data ~/private/export-<date> --out ~/private/results-<date>`. Apple's `python3` is 3.9 and cannot run the accepted code.
- **Next work package: WP1.1 — label the backlog** (approved by Alta 2026-11-06; before any WP4 model work). The bottleneck is labels, not models: 89 rows across 15 categories is ~6 per class, below what WP2's `MIN_HISTORY = 3` can use for most merchants.
  - Code section (four-turn review, read-only over a snapshot, standard library): `backlog.py` groups the unlabeled spending rows by conservatively normalized merchant with count, total cents, and date span, so Alta labels merchant-by-merchant in Ledger (the recategorize sheet reads `/api/activity?category=Other`; each group's `txn_ids` is the checklist); it also lists the `verified` rows for the L1 adjudication pass. Output is a private report outside Git; the six-digit mask applies; no Ledger code or schema changes.
  - Human section (Alta, in Ledger): label the backlog merchant-by-merchant; adjudicate the 77 verified rows.
  - Done when: a fresh WP1 export shows unlabeled share under 10% of spending rows and the adjudication is recorded as a count in this file; then WP3 reruns and its numbers become the baseline WP4 must beat.
- After WP1.1: WP4 local model (Ollama on the LLM Pi) behind the WP2 rules.

## WP1.1 in review (2026-11-06)

- Turn 1 (ChatGPT, `049e95a`): `proposed/wp1.1/backlog.py` + `test_backlog.py` — grouped backlog + verified adjudication queue, reusing `accepted/wp1/export.py` and `accepted/wp2-wp3/evaluate.py::normalize`; 13/13.
- Turn 2 (Claude): `proposed/wp1.1/TURN2-wp1.1-for-chatgpt.md`. Keeps the design; adds `known_label` / `labeled_count` (the category a merchant already carries among labeled rows — a hint, never applied) and `txn_ids` per group (L-prefixed, so each group is a checklist); corrects the HANDOFF claim about one-tap relabeling. 14/14 on Python 3.13.18 via both invocations; accepted WP1 16/16 and WP2/WP3 21/21 unchanged; new tests proven to fail against Turn 1.
- Turn 3 (ChatGPT, reviewing `ee3afe6`): `proposed/wp1.1/TURN3-wp1.1-for-claude.md` contains the reply and both full files. Keep the human hint over all WP1 labeled spending and the per-group transaction IDs. A unanimous category named `mixed` now counts as a hint. Conflicting labels produce a blank `known_label` with positive `labeled_count`; blank with zero means no labeled history. IDs are ordered by date, then numeric Ledger ID. The accepted WP1 dependency is intentional and requires rechecking when WP1 changes.
- Synthetic verification on Python 3.13.18: WP1.1 15/15 under both test invocations, WP1 16/16, WP2/WP3 21/21. Next: Alta pushes the local Turn 3 commit and relays it to Claude for Turn 4 consensus, followed by Alta's sign-off.
- Invocation on a consistent offline snapshot (unchanged): `python3.13 proposed/wp1.1/backlog.py --db ~/private/ledger-snapshot.db --out ~/private/backlog-<fresh-name>`.

## Known limitations carried forward
- `verified` means "set under a human UI session or manual entry", which includes Ask-tab agent writes the user confirmed (L1). Adjudicate before quoting a real accuracy number.
- `merge_category` relabels without per-row audit (L2); category IDs change on rename (L5).
- Six-digit masking is partial; real exports never enter Git, chat, or fixtures (L3).
- Small samples can give single-class merchant-grouped test sets; read sample metrics as plumbing checks only.

## Parking list (out of scope)
- Stable category IDs across renames (ID table or rename-aware mapping).
- Broader PII redaction of `merchant_raw`.
- Treating `source="bill"` rows as human-labeled.
- Incremental exports; additional category classes; snapshot tooling.
- Effect of six-digit masking on merchant normalization (track in WP4/WP5).
- Threshold sweep for MIN_HISTORY; three-way split; more normalization rules; Txn composition over inheritance.
