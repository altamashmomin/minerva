# MINERVA 0.1 — WP1 Turn 4 (consensus)

**Status:** Consensus reached between ChatGPT and Claude. Awaiting Alta's sign-off.
Candidate stays in `proposed/wp1/` until then. Nothing in `accepted/` changes.

## ChatGPT's Turn 4 (Nov 6, 2026, relayed by Alta)
- Independently ran Turn 3: 15/15 via both invocations; synthetic export loads in the
  accepted WP3 loader; no real data accessed.
- All six Turn 2 findings accepted with the documented limitations on label
  provenance and sensitive exports.
- Item 1: the file attached to ChatGPT was the WP2/WP3 review, not the WP1 Turn 3
  record — asked that the correct record be preserved.
- Item 2: the exporter could overwrite existing output files; before any real data,
  refuse existing files and require a fresh private destination. No architecture change.
- `verified` must stay documented as a provenance proxy. Final consensus; no restart.

## Claude's response (Turn 4 close)
- Item 1: an attachment mix-up outside the repo. The correct record has been at
  `proposed/wp1/TURN3-wp1-for-chatgpt.md` since commit `6ddb48d`; unchanged.
- Item 2: Agree. `write()` now refuses any existing `labeled.csv` / `categories.csv`
  (symlink or regular) and opens both with mode `x`. New test
  `test_refuses_to_overwrite_existing_export`. Suite 16/16 via both invocations.

## Per-finding acceptance
| Finding | Status |
|---|---|
| T2 #1 stale UI edits | Agree |
| T2 #2 exports in Git | Agree |
| T2 #3 symlink / URI | Agree |
| T2 #4 schema validation | Agree |
| T2 #5 `ui:` is not independent review | Agree with limitation (L1) |
| T2 #6 snapshot integrity external | Agree with limitation (L4) |
| T3 #1 no-op category resubmit | Agree |
| T3 #2 real audit shape only | Agree |
| T3 #3 two-decimal amounts | Agree |
| T4 #2 refuse overwrite | Agree |

Limitations L1–L6 as written in the Turn 3 draft record carry over unchanged.

## For Alta's sign-off
On approval: copy `export.py` + `test_export.py` to `accepted/wp1/`, commit, tag
`wp1-accepted-v1`, add `decisions/D-009-wp1-accepted.md` + a `DECISIONS.md` line,
update `HANDOFF.md`. Until then, nothing moves.
