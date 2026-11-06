# Handoff

- Last accepted: WP1.1 backlog report, tag `wp1.1-accepted-v1` (2026-11-06). Previous: WP1 `wp1-accepted-v1`; WP2/WP3 `wp2-wp3-accepted-v1` (`1b5eeb9`).
- Accepted as: a read-only, snapshot-only export; `verified` is a provenance proxy, not adjudicated ground truth (D-009, L1).
- Test results: 16 of 16 pass (`python3 -m unittest test_export.py` and `python3 test_export.py`); synthetic export runs end-to-end through `accepted/wp2-wp3/evaluate.py`.
- Accepted files: `accepted/wp1.1/`, `accepted/wp1/`, `accepted/wp2-wp3/`. Review history: `proposed/wp1.1/`, `proposed/wp1/`, `proposed/wp2-wp3/`. Decisions: D-008, D-009, D-010.
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

## WP1.1 — code accepted; human half in progress (2026-11-06)

- Code: `accepted/wp1.1/backlog.py`, 15/15, D-010, tag `wp1.1-accepted-v1`. Review history `proposed/wp1.1/` (Turns 1–4).
- Alta's steps (Mac, `python3.13`, fresh snapshot per the canonical procedure above):
  1. `python3.13 accepted/wp1.1/backlog.py --db ~/private/ledger-snapshot.db --out ~/private/backlog-<date>` → `backlog.csv` (merchant groups, `known_label` hint, `txn_ids` checklist) and `verified.csv` (the L1 adjudication queue). Private; never Git/chat.
  2. In Ledger, label the backlog merchant-by-merchant (hinted groups first), ticking the rows in `txn_ids`; adjudicate `verified.csv`.
  3. Re-snapshot, re-export with WP1, rerun WP3. Record here: unlabeled share, adjudicated count, and the new WP3 numbers (the WP4 baseline).
- Done when unlabeled share is under 10% of spending rows and the adjudication count is recorded. Then WP4 (local model on the LLM Pi behind the WP2 rules); Turn 1 drafter to be agreed.

## Informal pre-WP4 benchmark (2026-11-06, Alta, MacBook Pro M1 Pro, Ollama 0.40.14) — not a WP4 result
- Prompt: single ShopRite transaction, JSON-only answer, eight fixed categories. Warm-model numbers.
- `gemma3:1b`: correct, 22 tokens, ~0.9 s, 68 tok/s. `qwen3:1.7b --think=false`: correct, 20 tokens, 0.33 s, 74 tok/s.
- `qwen3:4b --think=false`: correct but the flag did not suppress thinking (766–2189 output tokens, 26–65 s, 29–34 tok/s; the tag likely resolves to a thinking-only 2507 build — unverified). Unusable under the 5-second budget without constrained JSON output (Ollama `format`), which WP4 should test rather than assume.
- The spare Pi turned out to be a Pi 4 B 8GB with no cooling; its benchmark was skipped as unrepresentative. The inference target remains a Pi 5 8GB (not yet purchased). Expect Pi 5 throughput at roughly a third of the Mac figures.
- Implications for WP4 scope: measure the 1B/1.7B class first; treat the 4B as a conditional candidate for unseen merchants; make schema-constrained output a first-class variable; keep-alive matters (cold load was 1.5–15 s).

## Known limitations carried forward
- `backlog.py` is coupled by path to accepted WP1 and WP2/WP3; rerun its suite whenever they change (L7). `known_label` is a hint, not a prediction (L8).
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
