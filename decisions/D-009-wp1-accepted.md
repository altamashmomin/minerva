# D-009: WP1 dataset export accepted (2026-11-06)

- Outcome: Turn 4 consensus (ChatGPT, Claude), approved by Alta. All ten findings across Turns 2–4 accepted: eight Agree, two Agree with limitation (T2 #5 provenance, T2 #6 snapshot).
- Accepted as: a read-only, snapshot-only export whose `verified` flag is a **provenance proxy** (last real category change made under a human UI session, or a never-relabeled manual entry), not an independently adjudicated ground-truth label.
- Code: `accepted/wp1/` (export.py, test_export.py), tag `wp1-accepted-v1`.
- Verification: 16/16 tests pass via `python3 -m unittest test_export.py` and `python3 test_export.py`; synthetic export runs end-to-end through `accepted/wp2-wp3/evaluate.py`; output files mode 0600; refuses Git worktrees, symlinks, existing files, and `finance.db`.
- Limitations accepted:
  - L1. `ui:` includes Ask-tab agent writes confirmed by the user in-session; Alta must manually adjudicate the final ground-truth set before any real accuracy number is called authoritative.
  - L2. `merge_category` relabels in bulk with no per-row audit; a manual-source row keeps `verified` under its new name.
  - L3. Six-digit masking is partial, not de-identification; real exports never enter Git, chat, or test fixtures.
  - L4. Snapshot consistency (`sqlite3 finance.db ".backup snap.db"` or `VACUUM INTO`) is Alta's operational step, outside WP1.
  - L5. Category IDs are slugs of current names; a rename via `merge_category` changes IDs between exports.
  - L6. `review_status` uses two of the three harness-accepted values; `unverified` is intentionally unused.
- History: Turn 1 Claude, Turn 2 ChatGPT, Turn 3 Claude, Turn 4 consensus. Review files in `proposed/wp1/`.
