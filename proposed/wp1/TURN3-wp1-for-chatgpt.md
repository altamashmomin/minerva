# MINERVA 0.1 — WP1 Turn 3 (Claude)

**Status:** Revision in reply to ChatGPT's Turn 2. Proposed, not accepted or merged. `proposed/wp1/` only.
**Sources reviewed:** `MINERVA_WP1_TURN2_REVIEW.md` (all six findings + both revised files); `accepted/wp2-wp3/evaluate.py` (the consumer contract); the live `altamashmomin/evenkeel` source at HEAD — `actions.py` (`edit_transaction`, `recategorize_transaction`, `merge_category`, `_write_audit`, `validate_txn_payload`), `app.py` (`ui_actor`, the recategorize route), `agent_write_tools.py` / `ask_loop.py` (in-process session execution), `static/app.js` (the edit form's PUT payload), `migrations/004_audit_log.sql`, `005_income.py`, `012_transfer_flag.py`, `schema_runtime.py` (`REQUIRED_SCHEMA_VERSION = 22`).
**Independent verification:** Turn 2 as submitted: 13/13 pass, reproduced. Turn 3: **15/15** pass via `python3 -m unittest test_export.py` and `python3 test_export.py` (Python 3.13; standard library only). Against Turn 2's `export.py`, the three new/changed tests fail (proven fail-first). A 112-row synthetic snapshot exported and ran end-to-end through `accepted/wp2-wp3/evaluate.py` on both splits; output files are mode `0600`. Only synthetic SQLite databases were used.

## Verdict on ChatGPT's six findings

| # | Finding | Verdict | Note |
|---|---------|---------|------|
| 1 | Stale UI edits produce false `verified` | **Agree** | Correct and kept. Turn 3 tightens it further (new finding 1 below). |
| 2 | Exports could be committed to the public repo | **Agree** | Git-worktree refusal, symlink refusal, `0600`, docs — all kept verbatim. |
| 3 | `finance.db` symlink bypass; URI special characters | **Agree** | Kept verbatim. Agree it cannot prove a renamed file is a snapshot. |
| 4 | Incomplete schema/audit validation; malformed targets crash | **Agree** | Kept verbatim. |
| 5 | `ui:` is not proof of independent human review | **Agree, and it is stronger than stated** | Verified in source: `agent_write_tools.py` executes Ask-tab writes in-process under the *user's session* (`ask_loop.py` lines 310–336), so a category the Haiku agent chose and the user merely confirmed is audited as `ui:<username>`. `verified` therefore means "set under a human session," not "chosen by a human." Carried into the acceptance record as a limitation. |
| 6 | Snapshot integrity is external to WP1 | **Agree** | The module docstring now names the two safe methods (`.backup`, `VACUUM INTO`). No code. |

## Turn 3 findings (three; ranked)

1. **BUG — Any UI edit of a transaction counted as a category-setting event.** The Ledger edit form (`static/app.js`, the `formTxn` submit handler) always sends `category: formTxn.category.value || "Other"` with every field. `validate_txn_payload` then puts `category` in `cols`, so `edit_transaction` logs `changed.category` even when the label did not change. Turn 2 treated any `changed.category` as the row's latest category event, so a user fixing a date or payer on an imported SimpleFIN row turned it `verified`. Reproduced on synthetic data. **Change:** `_category_change` compares `changed.category` against `before.category` (Ledger always writes the full before-image); an unchanged resubmit is ignored — it neither verifies nor downgrades. A no-op by `mcp:` after a real UI change therefore no longer demotes the row. Test: `test_unchanged_category_resubmit_is_not_a_category_event`.

2. **CLEANUP — Two audit shapes Ledger never writes were treated as verifying.** `_write_audit` always receives `{"before": dict(existing), "changed": cols, ...}`; there is no `before`/`after` pair and no list-valued `changed` anywhere in `actions.py`. Turn 2 accepted the `before`/`after` shape as verifying. **Change:** only the real shape verifies; everything else is non-verifying (the list shape still counts as "touched, value unknown" so it cannot establish verification). `test_review_status_from_audit_and_source` row 5 now uses the real shape; the legacy-shape case moved into the malformed-audit test with an `imported` expectation. Dead branches removed; `export.py` stays at 174 lines.

3. **CONSISTENCY — Amounts were emitted with a variable number of decimals.** `str(-Decimal(100)/100)` gives `-1`, `4250` gives `-42.5`. The accepted harness parses both, but WP3's sample fixtures and any future diff of two exports expect two decimals. **Change:** `.quantize(Decimal("0.01"))` — still exact, no float. Test: `test_amount_is_exact_negative_two_decimal`.

Also pinned, not changed: `test_merge_category_limitation_is_pinned` encodes the behaviour ChatGPT listed as deliberately unresolved (a manual-source row relabeled by `merge_category` stays `verified` under its new name; a UI-edited row whose label no longer matches its last edit downgrades) so Turn 4 can accept it knowingly and a later change cannot drift silently. A `source="bill"` row is now covered as `imported`.

## Preserve (from Turn 1 and Turn 2)

- Standard-library Python 3.11+; read-only SQLite via `mode=ro`; `finance.db` refused after `resolve()`.
- Spending-only: exclude inflows, transfers, settlement rows, blank/`Other` labels; counts-only stdout.
- Exact integer-cents → negative decimal; slug collision rejection; deterministic ordering; `L`-prefixed IDs.
- Output schema `labeled.csv` (7 columns) and `categories.csv`; every row carries an explicit `review_status`.
- Latest-category-change provenance with `ui:` actor and value match; manual-source fallback; malformed audits never verify.
- Git-worktree refusal, symlink refusal, `0600` output, six-digit partial mask with blank `description_redacted`.
- End-to-end compatibility with `accepted/wp2-wp3/evaluate.py`; synthetic-only tests; nothing installed on the Ledger Pi.

## Proposed Turn 4 acceptance record (draft for consensus — not yet a decision)

**D-009: WP1 dataset export accepted (date TBD)**

- Outcome: Turn 4 consensus pending ChatGPT's review of this Turn 3 and Alta's sign-off.
- Accepted as: a read-only, snapshot-only export whose `verified` flag is a **provenance proxy** (last real category change made under a human UI session, or a never-relabeled manual entry), not an independently reviewed gold label.
- Code: `proposed/wp1/export.py`, `proposed/wp1/test_export.py` → on acceptance copied to `accepted/wp1/`, tag `wp1-accepted-v1`.
- Verification: 15/15 via both invocations; end-to-end through `accepted/wp2-wp3/evaluate.py`.
- Per-finding status (nine items): ChatGPT T2 #1–#6 — Agree (six); Claude T3 #1 (no-op resubmit) — Agree; T3 #2 (real audit shape only) — Agree; T3 #3 (two-decimal amounts) — Agree.
- Limitations accepted:
  - L1. `ui:` includes Ask-tab agent writes confirmed by the user in-session; Alta must manually adjudicate the final ground-truth set before any real accuracy number is called authoritative.
  - L2. `merge_category` relabels in bulk without per-row audit; a manual-source row keeps `verified` under its new name.
  - L3. Six-digit masking is partial, not de-identification; real exports never enter Git, chat, or test fixtures.
  - L4. Snapshot consistency (`.backup` / `VACUUM INTO`) is Alta's operational step, outside WP1.
  - L5. Category IDs are slugs of current names; a rename via `merge_category` changes IDs between exports (ARCHITECTURE's "stable IDs" holds within one export, not across renames).
  - L6. `review_status` uses two of the three harness-accepted values; `unverified` is intentionally unused.
- History: Turn 1 Claude, Turn 2 ChatGPT, Turn 3 Claude, Turn 4 consensus.

## Parking list (unchanged scope; add to `HANDOFF.md` on acceptance)

- Stable category IDs across renames (an ID table or rename-aware mapping).
- Broader PII redaction of `merchant_raw`.
- Treating `source="bill"` rows as human-labeled (bill category is user-set at bill level).
- Incremental exports; additional category classes; snapshot tooling.
- Effect of six-digit masking on merchant normalization (track during WP4/WP5).

## Turn 4 request

Please confirm or dispute the three Turn 3 findings and the L1–L6 limitation wording, and return the per-finding acceptance statuses. No code changes unless a finding is disputed. Do not move to `accepted/` before Alta's approval.

## Complete `export.py`

```python
#!/usr/bin/env python3
"""MINERVA WP1: export a Ledger SNAPSHOT to WP3-compatible CSV files.

Standard library, Python 3.11+. Never run against the live Ledger database.
    python3 export.py --db /private/ledger-snapshot.db --out /private/export
The snapshot must be a consistent offline copy (sqlite3 finance.db
".backup snap.db" or VACUUM INTO), made by Alta on the Ledger Pi.
The output contains sensitive financial information. Keep it out of Git/cloud.
"""
import argparse
import csv
import json
import re
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path

TXN_COLUMNS = {"id", "txn_date", "amount_cents", "description", "category",
               "source", "direction", "is_transfer"}
AUDIT_COLUMNS = {"id", "actor", "action", "target", "detail_json"}
COLUMNS = ("txn_id", "date", "merchant_raw", "amount", "description_redacted",
           "label", "review_status")
LONG_DIGITS = re.compile(r"\d{6,}")  # Partial masking, NOT complete anonymization.
CENTS = Decimal("0.01")


def open_readonly(path):
    p = Path(path).expanduser().resolve()
    if p.name.casefold() == "finance.db":
        sys.exit("Refusing finance.db; use a consistent snapshot copy")
    if not p.is_file():
        sys.exit(f"{p}: snapshot file not found")
    conn = sqlite3.connect(p.as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def check_schema(conn):
    for table, required in (("transactions", TXN_COLUMNS),
                            ("audit_log", AUDIT_COLUMNS),
                            ("schema_version", {"version"})):
        have = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if required - have:
            raise ValueError(f"{table}: missing columns {sorted(required - have)}")
    version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    if version is None:
        raise ValueError("schema_version is empty")
    return version


def _category_change(detail):
    """Return (changed, new category) for Ledger's edit_transaction audit shape:
    {"before": <row>, "changed": <validated columns>}. A payload that resubmits
    the current category unchanged (the edit form always sends it) is NOT a
    category-setting event. Any other shape is non-verifying."""
    if not isinstance(detail, dict):
        return False, None
    before, changed = detail.get("before"), detail.get("changed")
    if not isinstance(changed, dict) or "category" not in changed:
        return False, None
    new = changed["category"]
    if not isinstance(new, str):
        return True, None  # Category touched but the value is unknowable.
    old = before.get("category") if isinstance(before, dict) else None
    if isinstance(old, str) and old.strip() == new.strip():
        return False, None  # No-op resubmit: neither verifies nor downgrades.
    return True, new.strip()


def category_edits(conn):
    """Latest real category change per row, by audit id: (by UI actor, value)."""
    latest = {}
    for row in conn.execute("SELECT actor, target, detail_json FROM audit_log "
                            "WHERE action='edit_transaction' ORDER BY id"):
        target = row["target"] or ""
        if not re.fullmatch(r"transaction:[0-9]+", target):
            continue  # Malformed audit targets cannot establish provenance.
        try:
            detail = json.loads(row["detail_json"])
        except (TypeError, ValueError):
            continue
        changed, new_value = _category_change(detail)
        if changed:
            latest[int(target.split(":", 1)[1])] = (
                (row["actor"] or "").startswith("ui:"), new_value)
    return latest


def slug(name):
    result = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    if not result:
        raise ValueError(f"category {name!r} has no usable ID")
    return result


def build(conn):
    """Return (CSV rows, category lookup, counts); never mutate the database."""
    edits = category_edits(conn)
    rows, categories, counts = [], {}, {}

    def count(reason):
        counts[reason] = counts.get(reason, 0) + 1

    for txn in conn.execute("SELECT * FROM transactions ORDER BY txn_date, id"):
        category = (txn["category"] or "").strip()
        if txn["direction"] != "out":
            count("skipped_inflow"); continue
        if txn["is_transfer"]:
            count("skipped_transfer"); continue
        if txn["source"] == "settlement" or category == "Settlement":
            count("skipped_settlement"); continue
        if not category or category == "Other":
            count("skipped_unlabeled"); continue
        cid = slug(category)
        if categories.setdefault(cid, category) != category:
            raise ValueError(f"categories {categories[cid]!r} and {category!r} share ID {cid!r}")

        # verified = the latest real category change was made under a UI session
        # and still matches, or a manually entered row nobody has relabeled since.
        # This is a provenance proxy, not independent human review (see HANDOFF).
        last = edits.get(txn["id"])
        verified = (last == (True, category)) if last is not None else txn["source"] == "manual"
        status = "verified" if verified else "imported"
        count(f"exported_{status}")
        rows.append({
            "txn_id": f"L{txn['id']}", "date": txn["txn_date"],
            "merchant_raw": LONG_DIGITS.sub("#", " ".join(txn["description"].split())),
            "amount": str((-Decimal(txn["amount_cents"]) / 100).quantize(CENTS)),
            "description_redacted": "", "label": cid, "review_status": status,
        })
    return rows, categories, counts


def write(out_dir, rows, categories):
    """Keep potentially sensitive exports outside any Git worktree."""
    out = Path(out_dir).expanduser().resolve()
    if any((parent / ".git").exists() for parent in (out, *out.parents)):
        raise ValueError("financial exports must be written outside Git repositories")
    for name in ("labeled.csv", "categories.csv"):
        if (out / name).is_symlink():
            raise ValueError(f"refusing symlink output {out / name}")
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(out / "labeled.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    with open(out / "categories.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["category_id", "name"])
        writer.writerows(sorted(categories.items()))
    (out / "labeled.csv").chmod(0o600)
    (out / "categories.csv").chmod(0o600)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="local SQLite snapshot, not live Ledger")
    parser.add_argument("--out", required=True, help="private folder OUTSIDE Git")
    args = parser.parse_args(argv)
    conn = open_readonly(args.db)
    try:
        version = check_schema(conn)
        rows, categories, counts = build(conn)
    finally:
        conn.close()
    write(args.out, rows, categories)
    print(f"schema_version={version} categories={len(categories)} rows={len(rows)}")
    for key in sorted(counts):
        print(f"  {key}={counts[key]}")


if __name__ == "__main__":
    main()
```

## Complete `test_export.py`

```python
"""Synthetic WP1 tests. Run: python3 -m unittest test_export.py"""
import csv
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

import export as ex

SCHEMA = """
CREATE TABLE schema_version (version INTEGER PRIMARY KEY);
INSERT INTO schema_version VALUES (22);
CREATE TABLE transactions (id INTEGER PRIMARY KEY, txn_date TEXT, amount_cents INTEGER,
  description TEXT, category TEXT, source TEXT, direction TEXT, is_transfer INTEGER);
CREATE TABLE audit_log (id INTEGER PRIMARY KEY, actor TEXT, action TEXT,
  target TEXT, detail_json TEXT);
"""


def make_db(txns, audits=()):
    p = Path(tempfile.mkdtemp()) / "snapshot.db"
    with sqlite3.connect(p) as conn:
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?)", txns)
        conn.executemany("INSERT INTO audit_log (actor, action, target, detail_json) "
                         "VALUES (?,?,?,?)", audits)
    return p


def row(i, cat="Groceries", src="simplefin", direction="out", transfer=0,
        desc="SHOPRITE #12", cents=4250):
    return i, f"2026-09-{i:02d}", cents, desc, cat, src, direction, transfer


def edit(i, detail, actor="ui:alta"):
    return actor, "edit_transaction", f"transaction:{i}", json.dumps(detail)


def ledger_edit(i, old, new, actor="ui:alta", **more):
    """Ledger's real edit_transaction shape: full before-image + validated cols."""
    return edit(i, {"before": {"id": i, "category": old, "description": "SHOPRITE #12"},
                    "changed": {"category": new, **more}}, actor)


class Export(unittest.TestCase):
    def build(self, txns, audits=()):
        conn = ex.open_readonly(make_db(txns, audits))
        try:
            self.assertEqual(ex.check_schema(conn), 22)
            return ex.build(conn)
        finally:
            conn.close()

    def statuses(self, txns, audits=()):
        return [r["review_status"] for r in self.build(txns, audits)[0]]

    def test_filters_and_counts(self):
        rows, cats, counts = self.build([
            row(1), row(2, direction="in"), row(3, transfer=1),
            row(4, cat="Settlement", src="settlement"), row(5, cat="Other")])
        self.assertEqual([r["txn_id"] for r in rows], ["L1"])
        self.assertEqual(cats, {"groceries": "Groceries"})
        self.assertEqual(sum(counts.get(k, 0) for k in (
            "skipped_inflow", "skipped_transfer", "skipped_settlement",
            "skipped_unlabeled")), 4)

    def test_review_status_from_audit_and_source(self):
        self.assertEqual(self.statuses(
            [row(1), row(2), row(3, src="manual"), row(4), row(5), row(6, src="bill")],
            [edit(1, {"changed": {"category": "Groceries"}}),
             edit(2, {"changed": {"description": "corrected"}}),
             edit(4, {"changed": {"category": "Groceries"}}, actor="mcp:laptop"),
             ledger_edit(5, "Other", "Groceries")]),
            ["verified", "imported", "verified", "imported", "verified", "imported"])

    def test_last_category_edit_determines_status(self):
        self.assertEqual(self.statuses([
            row(1, cat="Dining"), row(2, cat="Dining"), row(3, cat="Dining"),
            row(4, cat="Dining", src="manual")], [
            edit(1, {"changed": {"category": "Groceries"}}),
            edit(1, {"changed": {"category": "Dining"}}, actor="mcp:agent"),
            edit(2, {"changed": {"category": "Groceries"}}, actor="mcp:agent"),
            edit(2, {"changed": {"category": "Dining"}}),
            edit(3, {"changed": {"category": "Groceries"}}),
            edit(4, {"changed": {"category": "Dining"}}, actor="mcp:agent")]),
            ["imported", "verified", "imported", "imported"])

    def test_unchanged_category_resubmit_is_not_a_category_event(self):
        """The Ledger edit form always resubmits category; a form save that
        only fixed the description must not verify, and an mcp no-op must not
        downgrade an earlier real UI change."""
        self.assertEqual(self.statuses([row(1), row(2), row(3)], [
            ledger_edit(1, "Groceries", "Groceries", description="ShopRite"),
            ledger_edit(2, "Dining", "Groceries"),
            ledger_edit(2, "Groceries", "Groceries", actor="mcp:agent"),
            ledger_edit(3, "Groceries", " Groceries ")]),
            ["imported", "verified", "imported"])

    def test_merge_category_limitation_is_pinned(self):
        """merge_category relabels in bulk with no per-row audit. A manual row
        keeps 'verified' under its NEW name (accepted limitation); a UI-edited
        row whose label no longer matches its last edit downgrades."""
        merge = ("ui:alta", "merge_category", None,
                 json.dumps({"from_category": "Dining", "into_category": "Food"}))
        self.assertEqual(self.statuses(
            [row(1, cat="Food", src="manual"), row(2, cat="Food")],
            [ledger_edit(2, "Other", "Dining"), merge]),
            ["verified", "imported"])

    def test_legacy_ambiguous_or_malformed_audits_do_not_verify(self):
        self.assertEqual(self.statuses([row(1), row(2), row(3), row(4)], [
            edit(1, {"changed": ["category"]}),
            edit(2, {"changed": {"category": "Groceries"}}, actor="ui:alta"),
            ("ui:alta", "edit_transaction", "transaction:bad", "{}"),
            ("ui:alta", "edit_transaction", "transaction:3", "{invalid"),
            edit(4, {"before": {"category": "Other"}, "after": {"category": "Groceries"}})]),
            ["imported", "verified", "imported", "imported"])

    def test_amount_is_exact_negative_two_decimal(self):
        rows, _, _ = self.build([row(1, cents=675), row(2, cents=100), row(3, cents=5)])
        self.assertEqual([r["amount"] for r in rows], ["-6.75", "-1.00", "-0.05"])

    def test_masks_long_digits_but_is_not_full_redaction(self):
        rows, _, _ = self.build([row(1, desc="POS 4417123456 7-ELEVEN #1234")])
        self.assertEqual(rows[0]["merchant_raw"], "POS # 7-ELEVEN #1234")

    def test_slug_collision_rejected(self):
        with self.assertRaisesRegex(ValueError, "share ID"):
            self.build([row(1, cat="Home Goods"), row(2, cat="home-goods")])

    def test_refuses_live_path_even_through_symlink(self):
        p = make_db([]).with_name("finance.db")
        p.write_bytes(make_db([]).read_bytes())
        alias = p.with_name("alias.db")
        alias.symlink_to(p)
        with self.assertRaises(SystemExit):
            ex.open_readonly(alias)

    def test_readonly_and_uri_special_characters(self):
        p = make_db([row(1)])
        funny = p.with_name("snap?part#1.db")
        p.rename(funny)
        conn = ex.open_readonly(funny)
        with self.assertRaises(sqlite3.OperationalError):
            conn.execute("DELETE FROM transactions")
        conn.close()

    def test_schema_requires_transactions_columns(self):
        p = make_db([])
        with sqlite3.connect(p) as conn:
            conn.execute("ALTER TABLE transactions DROP COLUMN is_transfer")
        conn = ex.open_readonly(p)
        with self.assertRaisesRegex(ValueError, "transactions: missing columns"):
            ex.check_schema(conn)
        conn.close()

    def test_schema_requires_audit_columns(self):
        p = make_db([])
        with sqlite3.connect(p) as conn:
            conn.execute("ALTER TABLE audit_log DROP COLUMN actor")
        conn = ex.open_readonly(p)
        with self.assertRaisesRegex(ValueError, "audit_log: missing columns"):
            ex.check_schema(conn)
        conn.close()

    def test_refuses_git_worktree_and_symlink_output(self):
        root = Path(tempfile.mkdtemp())
        (root / ".git").mkdir()
        with self.assertRaisesRegex(ValueError, "outside Git"):
            ex.write(root / "exports", [], {})
        out = Path(tempfile.mkdtemp())
        (out / "labeled.csv").symlink_to(out / "target.csv")
        with self.assertRaisesRegex(ValueError, "symlink"):
            ex.write(out, [], {})

    def test_output_loads_in_accepted_harness(self):
        harness = Path(__file__).resolve().parents[2] / "accepted" / "wp2-wp3"
        sys.path.insert(0, str(harness))
        import evaluate as ev
        out = Path(tempfile.mkdtemp()) / "private-out"
        ex.main(["--db", str(make_db([row(1), row(2, cat="Dining")])),
                 "--out", str(out)])
        cats = ev.load_categories(out / "categories.csv")
        txns = ev.load_transactions(out / "labeled.csv", cats)
        self.assertEqual(cats, {"groceries", "dining"})
        self.assertEqual([t.verified for t in txns], [False, False])
        with (out / "labeled.csv").open(newline="") as f:
            self.assertEqual(len(list(csv.DictReader(f))), 2)


if __name__ == "__main__":
    unittest.main()
```
