# MINERVA 0.1, WP1 dataset export: Turn 1 (Claude)

Status: proposed, not accepted. Turn 2 is ChatGPT's review.

## What it does
`export.py` reads a snapshot copy of the Ledger (evenkeel) SQLite database and writes `labeled.csv` and `categories.csv` in the format the accepted WP3 harness (`accepted/wp2-wp3/evaluate.py`) loads.

- Read-only: opens `file:<path>?mode=ro` with `uri=True`. Refuses a file named `finance.db` so it can't be pointed at the live database; it runs on a copy only. Making the snapshot is Alta's step and is not in the code.
- Checks the schema first: required columns on `transactions`, presence of `audit_log`, and reports `MAX(schema_version.version)`.
- Exports spending rows only. Skipped and counted: inflows (`direction != 'out'`), transfers, settlements (source `settlement` or category `Settlement`), and unlabeled rows (empty or `Other`, the Ledger default).
- `review_status` on every row: `verified` when an `edit_transaction` audit row with a `ui:` actor changed the category, or the row was entered manually (`source = 'manual'`); everything else is `imported`.
- Integer cents become decimal strings, spending negative (675 becomes `-6.75`).
- `merchant_raw` is the description with whitespace collapsed and digit runs of 6 or more masked as `#` (card and reference numbers). `description_redacted` is left empty.
- Category ids are slugs of the free-text tag; two tags that slug to the same id is an error, not a silent merge.
- Prints only the schema version and counts, never row contents.

## Tests
`test_export.py`, 8 of 8 pass (`python3 -m unittest test_export` and `python3 test_export.py`), all on a synthetic database:
filters and counts; review_status from audit and source (5 cases); negative decimal amount; digit masking; slug collision rejected; refuses finance.db name and a missing column; connection is read-only; output loads in the accepted harness.

## Open assumptions for review
1. Shape of `edit_transaction` `detail_json`: the code accepts either a `changed` list/dict or `before`/`after` objects. Needs checking against `actions.py`.
2. Only `ui:` actors count as human. The Ask (Haiku) loop and MCP actors count as imported. Is that right?
3. `merge_category` relabels don't change status.
4. Bill-generated rows are imported, since their category comes from the bill.
5. Mask threshold of 6 digits.
6. `txn_id` prefixed `L` to keep Ledger ids distinct from synthetic ones.

## Parking list (out of scope for WP1)
- Real description redaction beyond digit masking.
- Exporting inflows or a second label set for income.
- Incremental exports.

## Privacy
The real export never goes into a chat. Reviews use the synthetic fixtures in the tests.

## Code

### export.py
```python
#!/usr/bin/env python3
"""MINERVA 0.1, WP1: read-only export of Ledger spending rows to the WP3 CSVs.

Turn 1 draft (Claude). Standard library only, Python 3.11+, deterministic.
Run on a SNAPSHOT copy of Ledger's database, never on the live finance.db:
    python3 export.py --db ledger-snapshot.db --out data
Writes labeled.csv and categories.csv; prints counts only, never row contents.
"""
import argparse, csv, json, re, sqlite3, sys
from decimal import Decimal
from pathlib import Path

NEEDED = {"id", "txn_date", "amount_cents", "description", "category",
          "source", "direction", "is_transfer"}
UNLABELED = {"Other"}            # Ledger's default category: not a real label
SYSTEM = {"Settlement"}          # settle_up rows: bookkeeping, not spending
HUMAN_ACTOR = "ui:"              # audit actors: 'ui:<member>' | 'sync' | 'mcp:<label>'
LONG_DIGITS = re.compile(r"\d{6,}")   # card/reference numbers; keeps '#1234', '7-ELEVEN'
COLUMNS = ("txn_id", "date", "merchant_raw", "amount", "description_redacted",
           "label", "review_status")


def open_readonly(path):
    p = Path(path)
    if p.name == "finance.db":
        sys.exit("refusing to read finance.db directly; export from a snapshot copy")
    if not p.is_file():
        sys.exit(f"{p}: no such database file")
    conn = sqlite3.connect(f"file:{p.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def check_schema(conn):
    have = {r["name"] for r in conn.execute("PRAGMA table_info(transactions)")}
    missing = NEEDED - have
    if missing:
        raise ValueError(f"transactions table lacks columns {sorted(missing)}")
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='audit_log'").fetchone():
        raise ValueError("audit_log table missing")
    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    return row[0]


def human_categorized(conn):
    """Transaction ids whose category a person set in the app, from audit_log."""
    ids = set()
    rows = conn.execute("SELECT target, detail_json FROM audit_log "
                        "WHERE action = 'edit_transaction' AND actor LIKE ?",
                        (HUMAN_ACTOR + "%",))
    for r in rows:
        target = r["target"] or ""
        if not target.startswith("transaction:"):
            continue
        try:
            detail = json.loads(r["detail_json"])
        except (TypeError, ValueError):
            continue
        if touches_category(detail):
            ids.add(int(target.split(":", 1)[1]))
    return ids


def touches_category(detail):
    if not isinstance(detail, dict):
        return False
    changed = detail.get("changed")
    if isinstance(changed, (list, dict)) and "category" in changed:
        return True
    before, after = detail.get("before"), detail.get("after")
    return (isinstance(before, dict) and isinstance(after, dict)
            and before.get("category") != after.get("category"))


def slug(name):
    s = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    if not s:
        raise ValueError(f"category {name!r} has no usable id")
    return s


def build(conn):
    """Returns (rows, categories, counts). Rows are dicts in COLUMNS order."""
    human = human_categorized(conn)
    rows, cats, counts = [], {}, {}
    def skip(reason):
        counts[reason] = counts.get(reason, 0) + 1
    for t in conn.execute("SELECT * FROM transactions ORDER BY txn_date, id"):
        category = (t["category"] or "").strip()
        if t["direction"] != "out":
            skip("skipped_inflow"); continue
        if t["is_transfer"]:
            skip("skipped_transfer"); continue
        if t["source"] == "settlement" or category in SYSTEM:
            skip("skipped_settlement"); continue
        if not category or category in UNLABELED:
            skip("skipped_unlabeled"); continue
        cid = slug(category)
        if cats.setdefault(cid, category) != category:
            raise ValueError(f"categories {cats[cid]!r} and {category!r} share id {cid!r}")
        status = "verified" if (t["id"] in human or t["source"] == "manual") else "imported"
        skip(f"exported_{status}")
        rows.append({
            "txn_id": f"L{t['id']}",
            "date": t["txn_date"],
            "merchant_raw": LONG_DIGITS.sub("#", " ".join(t["description"].split())),
            "amount": str(-Decimal(t["amount_cents"]) / 100),
            "description_redacted": "",
            "label": cid,
            "review_status": status,
        })
    return rows, cats, counts


def write(out_dir, rows, cats):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "labeled.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    with open(out / "categories.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["category_id", "name"])
        w.writerows(sorted(cats.items()))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True, help="snapshot copy of Ledger's database")
    ap.add_argument("--out", required=True, help="folder for labeled.csv, categories.csv")
    args = ap.parse_args(argv)
    conn = open_readonly(args.db)
    try:
        version = check_schema(conn)
        rows, cats, counts = build(conn)
    finally:
        conn.close()
    write(args.out, rows, cats)
    print(f"schema_version={version} categories={len(cats)} rows={len(rows)}")
    for key in sorted(counts):
        print(f"  {key}={counts[key]}")


if __name__ == "__main__":
    main()
```

### test_export.py
```python
"""Synthetic tests for export.py. Run: python3 -m unittest test_export.py"""
import csv, json, sqlite3, sys, tempfile, unittest
from pathlib import Path

import export as ex

SCHEMA = """
CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT, description TEXT);
INSERT INTO schema_version VALUES (22, '2026-11-01', 'x');
CREATE TABLE transactions (id INTEGER PRIMARY KEY, txn_date TEXT, amount_cents INTEGER,
  description TEXT, category TEXT, paid_by INTEGER, source TEXT, external_id TEXT,
  direction TEXT, income_type TEXT, is_transfer INTEGER);
CREATE TABLE audit_log (id INTEGER PRIMARY KEY, at TEXT, actor TEXT, action TEXT,
  target TEXT, detail_json TEXT);
"""


def make_db(txns, audits=()):
    d = Path(tempfile.mkdtemp())
    p = d / "snapshot.db"
    c = sqlite3.connect(p)
    c.executescript(SCHEMA)
    for t in txns:
        c.execute("INSERT INTO transactions (id, txn_date, amount_cents, description, category,"
                  " source, direction, is_transfer) VALUES (?,?,?,?,?,?,?,?)", t)
    for a in audits:
        c.execute("INSERT INTO audit_log (actor, action, target, detail_json) VALUES (?,?,?,?)", a)
    c.commit(); c.close()
    return p


def row(i, cat="Groceries", src="simplefin", direction="out", transfer=0,
        desc="SHOPRITE #12", cents=4250):
    return (i, f"2026-09-{i:02d}", cents, desc, cat, src, direction, transfer)


def edit(i, detail, actor="ui:alta"):
    return (actor, "edit_transaction", f"transaction:{i}", json.dumps(detail))


class Export(unittest.TestCase):
    def run_build(self, txns, audits=()):
        conn = ex.open_readonly(make_db(txns, audits))
        try:
            ex.check_schema(conn)
            return ex.build(conn)
        finally:
            conn.close()

    def test_filters_and_counts(self):
        rows, cats, counts = self.run_build([
            row(1), row(2, direction="in"), row(3, transfer=1),
            row(4, cat="Settlement", src="settlement"), row(5, cat="Other")])
        self.assertEqual([r["txn_id"] for r in rows], ["L1"])
        self.assertEqual(cats, {"groceries": "Groceries"})
        self.assertEqual(counts["skipped_inflow"] + counts["skipped_transfer"]
                         + counts["skipped_settlement"] + counts["skipped_unlabeled"], 4)

    def test_review_status_from_audit_and_source(self):
        rows, _, _ = self.run_build(
            [row(1), row(2), row(3, src="manual"), row(4), row(5)],
            [edit(1, {"changed": ["category"]}),
             edit(2, {"changed": ["description"]}),
             edit(4, {"changed": ["category"]}, actor="mcp:laptop"),
             edit(5, {"before": {"category": "Other"}, "after": {"category": "Groceries"}})])
        status = {r["txn_id"]: r["review_status"] for r in rows}
        self.assertEqual(status, {"L1": "verified", "L2": "imported", "L3": "verified",
                                  "L4": "imported", "L5": "verified"})

    def test_amount_is_negative_decimal_from_cents(self):
        rows, _, _ = self.run_build([row(1, cents=675)])
        self.assertEqual(rows[0]["amount"], "-6.75")

    def test_masks_long_digit_runs_but_keeps_store_numbers(self):
        rows, _, _ = self.run_build([row(1, desc="POS 4417123456  7-ELEVEN #1234")])
        self.assertEqual(rows[0]["merchant_raw"], "POS # 7-ELEVEN #1234")

    def test_category_id_collision_rejected(self):
        with self.assertRaisesRegex(ValueError, "share id"):
            self.run_build([row(1, cat="Home Goods"), row(2, cat="home-goods")])

    def test_refuses_live_db_name_and_missing_columns(self):
        with self.assertRaises(SystemExit):
            ex.open_readonly(Path(tempfile.mkdtemp()) / "finance.db")
        p = make_db([])
        c = sqlite3.connect(p); c.execute("ALTER TABLE transactions DROP COLUMN is_transfer")
        c.commit(); c.close()
        conn = ex.open_readonly(p)
        with self.assertRaisesRegex(ValueError, "is_transfer"):
            ex.check_schema(conn)
        conn.close()

    def test_connection_is_read_only(self):
        conn = ex.open_readonly(make_db([row(1)]))
        with self.assertRaises(sqlite3.OperationalError):
            conn.execute("DELETE FROM transactions")
        conn.close()

    def test_output_loads_in_accepted_harness(self):
        harness = Path(__file__).resolve().parents[2] / "accepted" / "wp2-wp3"
        sys.path.insert(0, str(harness))
        import evaluate as ev
        out = Path(tempfile.mkdtemp())
        ex.main(["--db", str(make_db([row(1), row(2, cat="Dining", desc="SQ *BLUE BOTTLE")])),
                 "--out", str(out)])
        cats = ev.load_categories(out / "categories.csv")
        txns = ev.load_transactions(out / "labeled.csv", cats)
        self.assertEqual(cats, {"groceries", "dining"})
        self.assertEqual([t.verified for t in txns], [False, False])


if __name__ == "__main__":
    unittest.main()
```
