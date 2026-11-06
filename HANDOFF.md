# Handoff

- Last accepted: WP1 dataset export, tag `wp1-accepted-v1` (2026-11-06). Previous: WP2/WP3, tag `wp2-wp3-accepted-v1`, commit `1b5eeb9`.
- Accepted as: a read-only, snapshot-only export; `verified` is a provenance proxy, not adjudicated ground truth (D-009, L1).
- Test results: 16 of 16 pass (`python3 -m unittest test_export.py` and `python3 test_export.py`); synthetic export runs end-to-end through `accepted/wp2-wp3/evaluate.py`.
- Accepted files: `accepted/wp1/`, `accepted/wp2-wp3/`. Review history: `proposed/wp1/`, `proposed/wp2-wp3/`. Decisions: D-008, D-009.
- Next action (Alta, operational, not a work package): on the Ledger Pi make a consistent snapshot (`sqlite3 finance.db ".backup /private/ledger-snapshot.db"`), copy it to a private folder OUTSIDE any Git worktree, run `python3 accepted/wp1/export.py --db <snapshot> --out <fresh private folder>`, then `python3 accepted/wp2-wp3/evaluate.py --data <that folder> --out <private results>`. Share only the counts and metrics, never the CSVs.
- Next work package: to be agreed after the first real-data run. Candidates: WP4 local model (Ollama on the LLM Pi) behind the WP2 rules; WP1.1 manual adjudication pass on the `verified` set (L1).

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
