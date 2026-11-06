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
  - Code section (four-turn review, read-only over a snapshot, standard library): `backlog.py` groups the unlabeled spending rows by conservatively normalized merchant with count, total cents, and date span, so Alta labels merchant-by-merchant in Ledger's recategorize sheet (one tap relabels all of a merchant's rows via the existing `edit_transaction` verb); it also lists the `verified` rows for the L1 adjudication pass. Output is a private report outside Git; the six-digit mask applies; no Ledger code or schema changes.
  - Human section (Alta, in Ledger): label the backlog merchant-by-merchant; adjudicate the 77 verified rows.
  - Done when: a fresh WP1 export shows unlabeled share under 10% of spending rows and the adjudication is recorded as a count in this file; then WP3 reruns and its numbers become the baseline WP4 must beat.
- After WP1.1: WP4 local model (Ollama on the LLM Pi) behind the WP2 rules.

## WP1.1 Turn 1 — proposed (2026-11-06)

- Draft: `proposed/wp1.1/backlog.py` and `test_backlog.py`; pending Claude's Turn 2 review. No accepted checkpoint or decision record yet.
- Reuses `accepted/wp1/export.py` for read-only snapshot opening, schema checks, and the exact verified provenance selection, and `accepted/wp2-wp3/evaluate.py::normalize` for grouping. No production access or real financial data used.
- `backlog.csv`: unlabeled spending only (stripped category blank/`Other`, direction `out`, no transfer or settlement), grouped after WP1's six-digit mask, sorted count descending then normalized merchant. Columns: normalized merchant, count, sum of stored integer cents, first/last date, JSON list of masked merchant variants for merge review. Stored cent signs are preserved.
- `verified.csv`: WP1's labeled spending rows marked `verified`, with transaction ID, date, masked merchant, WP1's negative decimal amount, masked category name, and provenance status. This is the L1 adjudication queue, not adjudicated ground truth.
- Output: fresh folder only, outside Git/worktrees, directory mode 0700 and files 0600. Refuses `finance.db` (including resolved aliases), symlink output directories, existing output folders/files, and dangling output symlinks; exclusive file creation. Standard library, Python 3.11+; prints only schema and counts.
- Validation: Python 3.13.18, 13/13 synthetic WP1.1 tests pass via both `python3.13 -m unittest -v test_backlog.py` and `python3.13 test_backlog.py` in `proposed/wp1.1`; accepted WP1 16/16 and WP2/WP3 21/21 regression tests pass. Accepted WP1 tests emit existing unclosed-fixture-connection ResourceWarnings under 3.13; accepted code/tests were not changed.
- Invocation for Alta on a consistent offline snapshot: `python3.13 proposed/wp1.1/backlog.py --db ~/private/ledger-snapshot.db --out ~/private/backlog-<fresh-name>`. Creating/copying the snapshot and all Ledger labeling/adjudication remain Alta's steps.
- Handoff to Alta: Turn 1 is one local commit and is **not pushed**. Alta must push before relaying to Claude for Turn 2; the other AI cannot see an unpushed turn. The existing WP1.1 completion criteria and baseline remain unchanged.

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
