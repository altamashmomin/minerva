# Decisions

One entry per decision. Status: Agree, Agree with limitation, Disagree (Alta decided), Deferred.
Each completed four-turn review adds a record under `decisions/` and a line here.

| ID | Date | Decision | Status | Rationale |
|----|------|----------|--------|-----------|
| D-001 | 2026-11-05 | Ledger-mind becomes MINERVA 0.1 | Agree | One roadmap, Ledger as first workload |
| D-002 | 2026-11-05 | Rules first, local model second, Haiku fallback; Ledger owns acceptance | Agree | Cheap, explainable, safe rollout |
| D-003 | 2026-11-05 | No leakage: lookups from train only; both splits for every method | Agree | Honest comparison |
| D-004 | 2026-11-05 | FAR = wrong/accepted; report wrong/all; oracle bound labeled | Agree | Precise metrics |
| D-005 | 2026-11-05 | Unanimity with MIN_HISTORY = 3; conservative normalization | Agree | Prefer abstaining over guessing |
| D-006 | 2026-11-05 | No pandas, scikit-learn, Pydantic or Ollama in WP2/WP3 | Agree | Small, typeable, standard library |
| D-007 | 2026-11-06 | GitHub repo is the source of truth; proposed code kept apart from accepted | Agree | No dependence on AI chat memory |
| D-008 | 2026-11-06 | WP2/WP3 accepted as synthetic-data evaluation baseline (`wp2-wp3-accepted-v1`) | Agree with limitation | Turn 4 consensus; see decisions/D-008 |
| D-009 | 2026-11-06 | WP1 dataset export accepted; `verified` is a provenance proxy (`wp1-accepted-v1`) | Agree with limitation | Turn 4 consensus, Alta approved; see decisions/D-009 |
| D-010 | 2026-11-06 | WP1.1 backlog report accepted; `known_label` is a human hint, never applied (`wp1.1-accepted-v1`) | Agree with limitation | Turn 4 consensus, Alta approved; see decisions/D-010 |

## Open
- Handling of ambiguous merchants beyond abstention (parked).
- Stable category IDs across renames (parked, L5).
- Broader PII redaction of `merchant_raw` (parked, L3).
