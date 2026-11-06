# MINERVA 0.1 — WP1.1 Turn 2 (Claude)

**Status:** Revision proposed for ChatGPT's Turn 3. Not accepted or merged. `proposed/wp1.1/` only.
**Source reviewed:** Turn 1 at `049e95a` (`backlog.py`, `test_backlog.py`, HANDOFF note), against the WP1.1 scope in `HANDOFF.md`, `accepted/wp1/export.py`, `accepted/wp2-wp3/evaluate.py::normalize`, and Ledger's `/api/activity` category filter (`evenkeel/app.py`, the route the recategorize sheet reads).
**Independent verification:** Turn 1 as submitted: 13/13, reproduced on Python 3.13.18. Turn 2: **14/14** via `python3.13 -m unittest test_backlog.py` and `python3.13 test_backlog.py`; accepted WP1 16/16 and WP2/WP3 21/21 unchanged. The new test and the updated CLI test fail against Turn 1's `backlog.py` (proven fail-first). Synthetic data only.

## Verdict on Turn 1

Keep nearly all of it. The reuse of accepted code by path (`_accepted`) is the right call and survives the move to `accepted/wp1.1/` (`parents[2]` is still the repo root there). Mask-before-normalize matches the WP1→WP3 path exactly, so `backlog.csv` groups the way the harness will see merchants. The output refusals are stricter than WP1's (symlinked output folder, dangling symlinks, `exist_ok=False`) and every one has a test. `merchant_variants` was not asked for and is useful.

## Findings (three; ranked)

1. **DESIGN — The report did not tell Alta what he already knows.** A merchant whose other rows are already labeled (e.g. `wawa` → Transport ×2, with two more rows at `Other`) appeared in `backlog.csv` with no hint. Those are the cheapest rows to label and the first ones the WP2 rules would accept once labeled; they should sort themselves out of Alta's way. **Change:** two columns — `known_label` (the single category this normalized merchant carries among WP1's labeled rows; `""` if none, `mixed` if several) and `labeled_count`. Computed from `wp1.build`'s labeled rows with the same `normalize`, so it is exactly the WP2 unanimity view, offline. It is a hint for a human; nothing is applied. stdout gains `hinted=N`. Test: `test_known_label_hint_and_txn_ids_per_group`.

2. **DESIGN — No row identifiers, so a group could not be acted on.** `HANDOFF.md` (my own line) claimed "one tap relabels all of a merchant's rows"; that is not how Ledger's recategorize sheet works — it reads `/api/activity?category=…` (optionally per month) and the user ticks rows. Without ids, Alta would re-derive each group by eye. **Change:** `txn_ids`, a JSON list of `L<id>` in date order per group, matching WP1's `txn_id` convention. The HANDOFF claim is corrected in this turn.

3. **NOTE — Coupling to accepted WP1 is intentional and should be recorded, not removed.** `backlog.py` imports `wp1.build`, `open_readonly`, `check_schema`, `LONG_DIGITS`; if WP1 revs its row keys, WP1.1 breaks loudly (ImportError/KeyError), which is the desired failure. Recorded as a limitation for the acceptance record; no code change.

Not findings, confirmed and left alone: `total_cents` sums stored cents (Ledger CHECKs `amount_cents > 0`, test covers a negative anyway); `##` doubling after masking (`SHOP #123456` → `shop ##`) is WP1's existing behaviour and the harness sees the same string; `WAWA 100` vs `WAWA# 8323` not merging is `normalize`'s conservatism (D-005, parked).

## Preserve
- `_accepted` path-pinned reuse; no second normalizer; mask before normalize.
- Filters identical to WP1 (direction `out`, not transfer, not settlement, category blank/`Other`).
- Fresh-folder-only output, all refusals, `0700`/`0600`, exclusive create; counts-only stdout.
- `verified.csv` as the L1 adjudication queue with WP1's `txn_id`, amount, and status.
- Standard library, Python 3.11+, synthetic tests only; accepted code untouched.

## Parking (unchanged)
- Normalization reach (`WAWA 100`), stable category IDs, broader redaction, bill-source rows.

## Turn 3 request
Confirm or dispute findings 1–2 and the limitation wording in 3. Full files below; code 136 lines, tests 226.

## Complete `backlog.py`

```python
#!/usr/bin/env python3
"""MINERVA WP1.1: private backlog and verified-row adjudication report.

Python 3.11+, standard library; run ONLY on Alta's consistent offline snapshot:
    python3.13 proposed/wp1.1/backlog.py --db ~/private/snapshot.db --out ~/private/backlog-new
Writes backlog.csv and verified.csv in a fresh private folder outside Git.
total_cents sums Ledger's stored integer cents (outflows are normally positive).
known_label is the one category this merchant already carries among WP1's
labeled rows ("" if none, "mixed" if several); it is a hint for Alta, never
applied. txn_ids are Ledger ids (L-prefixed) so each group is a checklist.
Verified is WP1's provenance proxy, NOT adjudicated ground truth. Six-digit
masking is partial, NOT anonymization. Keep real reports out of Git/cloud/chat.
"""
import argparse
import csv
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _accepted(name, relative):
    """Load the repository's accepted code, never a similarly named local module."""
    spec = importlib.util.spec_from_file_location(name, ROOT / "accepted" / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # Required by evaluate.py's dataclasses.
    spec.loader.exec_module(module)
    return module


wp1 = _accepted("_minerva_wp1", "wp1/export.py")
wp23 = _accepted("_minerva_wp23", "wp2-wp3/evaluate.py")
BACKLOG_COLUMNS = ("normalized_merchant", "count", "total_cents", "first_date",
                   "last_date", "known_label", "labeled_count", "txn_ids",
                   "merchant_variants")
VERIFIED_COLUMNS = ("txn_id", "date", "merchant_raw", "amount", "category", "review_status")


def mask(text):
    return wp1.LONG_DIGITS.sub("#", " ".join(text.split()))


def build(conn):
    """Return (merchant groups, verified rows, WP1 counts); no database writes.

    Mask BEFORE normalizing, matching WP1 export -> WP2/WP3 evaluation. Retain
    masked raw variants so Alta can review merges and find merchants in Ledger.
    """
    labeled, categories, counts = wp1.build(conn)
    known = {}  # normalized merchant -> {category name: labeled row count}
    for row in labeled:
        hits = known.setdefault(wp23.normalize(row["merchant_raw"]), {})
        name = categories[row["label"]]
        hits[name] = hits.get(name, 0) + 1
    verified = [{"txn_id": row["txn_id"], "date": row["date"],
                 "merchant_raw": row["merchant_raw"], "amount": row["amount"],
                 "category": mask(categories[row["label"]]),
                 "review_status": row["review_status"]}
                for row in labeled if row["review_status"] == "verified"]
    groups = {}
    for txn in conn.execute("SELECT * FROM transactions ORDER BY txn_date, id"):
        category = (txn["category"] or "").strip()
        if (txn["direction"] != "out" or txn["is_transfer"]
                or txn["source"] == "settlement" or category == "Settlement"):
            continue
        if category and category != "Other":
            continue
        raw = mask(txn["description"])
        key = wp23.normalize(raw)
        hits = known.get(key, {})
        group = groups.setdefault(key, {
            "normalized_merchant": key, "count": 0, "total_cents": 0,
            "first_date": txn["txn_date"], "last_date": txn["txn_date"],
            "known_label": mask(next(iter(hits))) if len(hits) == 1 else
                           ("mixed" if hits else ""),
            "labeled_count": sum(hits.values()), "txn_ids": [],
            "merchant_variants": set()})
        group["count"] += 1
        group["txn_ids"].append(f"L{txn['id']}")
        group["total_cents"] += txn["amount_cents"]
        group["first_date"] = min(group["first_date"], txn["txn_date"])
        group["last_date"] = max(group["last_date"], txn["txn_date"])
        group["merchant_variants"].add(raw)
    backlog = sorted(groups.values(), key=lambda group: (-group["count"],
                                                        group["normalized_merchant"]))
    for group in backlog:
        group["txn_ids"] = json.dumps(group["txn_ids"])
        group["merchant_variants"] = json.dumps(sorted(group["merchant_variants"]),
                                                ensure_ascii=False)
    return backlog, verified, counts


def write(out_dir, backlog, verified):
    """Refuse Git/worktrees, symlink output, and every existing output folder."""
    requested = Path(out_dir).expanduser()
    if requested.is_symlink():
        raise ValueError("refusing symlink output; use a fresh folder")
    out = requested.resolve()
    if any((parent / ".git").exists() for parent in (out, *out.parents)):
        raise ValueError("financial reports must be written outside Git repositories")
    if out.exists():
        raise ValueError("refusing existing output; use a fresh folder")
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    for name, columns, rows in (("backlog.csv", BACKLOG_COLUMNS, backlog),
                                ("verified.csv", VERIFIED_COLUMNS, verified)):
        with (out / name).open("x", newline="", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="offline SQLite snapshot, never finance.db")
    parser.add_argument("--out", required=True, help="fresh private folder OUTSIDE Git")
    args = parser.parse_args(argv)
    conn = wp1.open_readonly(args.db)
    try:
        version = wp1.check_schema(conn)
        backlog, verified, counts = build(conn)
    finally:
        conn.close()
    write(args.out, backlog, verified)
    hinted = sum(1 for group in backlog if group["known_label"] not in ("", "mixed"))
    print(f"schema_version={version} merchants={len(backlog)} hinted={hinted} "
          f"verified={len(verified)}")
    for key in sorted(counts):
        print(f"  {key}={counts[key]}")


if __name__ == "__main__":
    main()
```

## Complete `test_backlog.py`

```python
"""Synthetic only. Run from proposed/wp1.1: python3.13 -m unittest test_backlog.py"""
import contextlib
import csv
import io
import json
import sqlite3
import stat
import tempfile
import unittest
from pathlib import Path

import backlog as bl

SCHEMA = """
CREATE TABLE schema_version (version INTEGER PRIMARY KEY);
INSERT INTO schema_version VALUES (22);
CREATE TABLE transactions (id INTEGER PRIMARY KEY, txn_date TEXT, amount_cents INTEGER,
 description TEXT, category TEXT, source TEXT, direction TEXT, is_transfer INTEGER);
CREATE TABLE audit_log (id INTEGER PRIMARY KEY, actor TEXT, action TEXT,
 target TEXT, detail_json TEXT);
"""


def row(i, cat="Other", src="simplefin", direction="out", transfer=0,
        desc="SHOPRITE #12", cents=4250, day="2026-09-01"):
    return i, day, cents, desc, cat, src, direction, transfer


def edit(i, old, new, actor="ui:alta"):
    return actor, "edit_transaction", f"transaction:{i}", json.dumps(
        {"before": {"category": old}, "changed": {"category": new}})


class Backlog(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def database(self, txns=(), audits=(), name="snapshot.db"):
        snapshot = self.root / name
        with contextlib.closing(sqlite3.connect(snapshot)) as conn, conn:
            conn.executescript(SCHEMA)
            conn.executemany("INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?)", txns)
            conn.executemany("INSERT INTO audit_log (actor,action,target,detail_json) "
                             "VALUES (?,?,?,?)", audits)
        return snapshot

    def build(self, txns, audits=()):
        with contextlib.closing(bl.wp1.open_readonly(self.database(txns, audits))) as conn:
            self.assertEqual(bl.wp1.check_schema(conn), 22)
            return bl.build(conn)

    def test_groups_exact_cents_dates_variants_and_order(self):
        groups, verified, counts = self.build([
            row(1, desc="SQ *BLUE BOTTLE", cents=5, day="2026-09-20"),
            row(2, cat=" ", desc=" Blue   Bottle #4 ", cents=675, day="2026-08-01"),
            row(3, cat=None, desc="BLUE BOTTLE #12", cents=-100, day="2026-09-01"),
            row(4, desc="ZED"), row(5, desc="ALPHA")])
        self.assertEqual([g["normalized_merchant"] for g in groups],
                         ["blue bottle", "alpha", "zed"])
        self.assertEqual((groups[0]["count"], groups[0]["total_cents"],
                          groups[0]["first_date"], groups[0]["last_date"]),
                         (3, 580, "2026-08-01", "2026-09-20"))
        self.assertEqual(json.loads(groups[0]["merchant_variants"]),
                         ["BLUE BOTTLE #12", "Blue Bottle #4", "SQ *BLUE BOTTLE"])
        self.assertEqual(verified, [])
        self.assertEqual(counts["skipped_unlabeled"], 5)

    def test_known_label_hint_and_txn_ids_per_group(self):
        groups, _, _ = self.build([
            row(1, cat="Transport", desc="WAWA #1", day="2026-08-01"),
            row(2, cat="Transport", src="manual", desc="WAWA #2", day="2026-08-02"),
            row(3, desc="WAWA #3", day="2026-09-01"), row(4, desc="WAWA #4", day="2026-09-02"),
            row(5, cat="Dining", desc="CAFE", day="2026-08-01"),
            row(6, cat="Groceries", desc="CAFE", day="2026-08-02"),
            row(7, desc="CAFE", day="2026-09-01"),
            row(8, desc="NEW PLACE", day="2026-09-01")])
        by = {g["normalized_merchant"]: g for g in groups}
        self.assertEqual((by["wawa"]["known_label"], by["wawa"]["labeled_count"]),
                         ("Transport", 2))
        self.assertEqual(json.loads(by["wawa"]["txn_ids"]), ["L3", "L4"])
        self.assertEqual((by["cafe"]["known_label"], by["cafe"]["labeled_count"]), ("mixed", 2))
        self.assertEqual((by["new place"]["known_label"], by["new place"]["labeled_count"]),
                         ("", 0))
        self.assertEqual(json.loads(by["new place"]["txn_ids"]), ["L8"])

    def test_filters_apply_before_backlog_and_verification(self):
        groups, verified, counts = self.build([
            row(1), row(2, cat="Other", direction="in"), row(3, cat="", transfer=1),
            row(4, cat="Other", src="settlement"), row(5, cat=" Settlement "),
            row(6, cat="Dining"), row(7, cat="Dining", src="manual"),
            row(8, cat="Dining", src="manual", direction="in"),
            row(9, cat="Dining", src="manual", transfer=1),
            row(10, cat="Settlement", src="manual")])
        self.assertEqual(sum(g["count"] for g in groups), 1)
        self.assertEqual([r["txn_id"] for r in verified], ["L7"])
        self.assertEqual(counts, {"skipped_unlabeled": 1, "skipped_inflow": 2,
                                 "skipped_transfer": 2, "skipped_settlement": 3,
                                 "exported_imported": 1, "exported_verified": 1})

    def test_uses_accepted_normalization_and_preserves_distinguishing_numbers(self):
        descriptions = ["TST*CAFE #1", "PAYPAL *CAFE #2", "CAFE", "7-ELEVEN",
                        "ELEVEN", "ROUTE 18 DINER", "ROUTE 19 DINER"]
        groups, _, _ = self.build([row(i, desc=d) for i, d in enumerate(descriptions, 1)])
        self.assertEqual([g["normalized_merchant"] for g in groups],
                         ["cafe", "7-eleven", "eleven", "route 18 diner", "route 19 diner"])
        self.assertEqual(groups[0]["count"], 3)

    def test_masks_before_normalization_in_both_reports(self):
        groups, verified, _ = self.build([
            row(1, desc="SHOP #123456"), row(2, desc="SHOP #654321"),
            row(3, cat="Category 123456", src="manual", desc="POS 4417123456 #1234")])
        self.assertEqual(groups[0]["normalized_merchant"], "shop ##")
        self.assertEqual(groups[0]["count"], 2)
        self.assertEqual(verified[0]["merchant_raw"], "POS # #1234")
        self.assertEqual(verified[0]["category"], "Category #")
        self.assertNotIn("123456", json.dumps([groups, verified]))
        self.assertNotIn("4417123456", json.dumps([groups, verified]))

    def test_verified_matches_accepted_provenance_not_adjudication(self):
        txns = [row(i, cat="Dining", src="manual" if i in (3, 4) else "simplefin")
                for i in range(1, 8)] + [row(8, cat="Dining", src="bill")]
        audits = [edit(1, "Other", "Dining"), edit(1, "Dining", "Dining", "mcp:agent"),
                  edit(2, "Dining", "Dining"), edit(3, "Other", "Dining", "mcp:agent"),
                  edit(5, "Other", "Dining"), edit(5, "Dining", "Groceries", "mcp:agent"),
                  edit(6, "Other", "Groceries"), edit(7, "Other", "Dining")]
        _, verified, _ = self.build(txns, audits)
        self.assertEqual([r["txn_id"] for r in verified], ["L1", "L4", "L7"])
        self.assertTrue(all(r["review_status"] == "verified" for r in verified))
        self.assertEqual(verified[0]["amount"], "-42.50")

    def test_empty_snapshot_produces_headers(self):
        groups, verified, counts = self.build([])
        self.assertEqual((groups, verified, counts), ([], [], {}))
        out = self.root / "empty-report"
        bl.write(out, groups, verified)
        for filename, columns in (("backlog.csv", bl.BACKLOG_COLUMNS),
                                  ("verified.csv", bl.VERIFIED_COLUMNS)):
            with (out / filename).open(newline="") as stream:
                self.assertEqual(list(csv.reader(stream)), [list(columns)])

    def test_readonly_special_uri_filename_and_unchanged_snapshot(self):
        snapshot = self.database([row(1)], name="snap?part#1.db")
        original = snapshot.read_bytes()
        with contextlib.closing(bl.wp1.open_readonly(snapshot)) as conn:
            with self.assertRaises(sqlite3.OperationalError):
                conn.execute("DELETE FROM transactions")
            bl.build(conn)
        self.assertEqual(snapshot.read_bytes(), original)

    def test_refuses_finance_db_direct_and_alias(self):
        snapshot = self.database(name="FiNaNcE.Db")
        alias = self.root / "alias.db"
        alias.symlink_to(snapshot)
        for candidate in (snapshot, alias):
            with self.subTest(candidate=candidate), self.assertRaises(SystemExit):
                bl.wp1.open_readonly(candidate)

    def test_missing_snapshot_is_not_created(self):
        missing = self.root / "missing.db"
        with self.assertRaises(SystemExit):
            bl.wp1.open_readonly(missing)
        self.assertFalse(missing.exists())

    def test_cli_rejects_missing_schema_before_output(self):
        snapshot = self.database()
        with contextlib.closing(sqlite3.connect(snapshot)) as conn, conn:
            conn.execute("ALTER TABLE audit_log DROP COLUMN actor")
        with self.assertRaisesRegex(ValueError, "audit_log: missing columns"):
            bl.main(["--db", str(snapshot), "--out", str(self.root / "report")])
        self.assertFalse((self.root / "report").exists())

    def test_refuses_git_directory_and_worktree_file_in_ancestors(self):
        for marker_type in ("directory", "file"):
            root = self.root / marker_type
            root.mkdir()
            marker = root / ".git"
            marker.mkdir() if marker_type == "directory" else marker.write_text("gitdir: elsewhere")
            with self.subTest(marker_type=marker_type), self.assertRaisesRegex(ValueError, "outside Git"):
                bl.write(root / "nested" / "report", [], [])
            self.assertFalse((root / "nested").exists())

    def test_refuses_existing_folder_files_and_symlinks_without_overwrite(self):
        out = self.root / "report"
        out.mkdir()
        with self.assertRaisesRegex(ValueError, "fresh folder"):
            bl.write(out, [], [])
        existing = out / "backlog.csv"
        existing.write_text("keep")
        (out / "verified.csv").symlink_to(self.root / "missing-target")
        with self.assertRaisesRegex(ValueError, "fresh folder"):
            bl.write(out, [], [])
        self.assertEqual(existing.read_text(), "keep")
        self.assertFalse((self.root / "missing-target").exists())
        for target in (out, self.root / "absent-folder"):
            alias = self.root / ("alias-" + target.name)
            alias.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "symlink"):
                bl.write(alias, [], [])
        self.assertFalse((self.root / "absent-folder").exists())

    def test_cli_private_csv_roundtrip_counts_only_and_snapshot_unchanged(self):
        snapshot = self.database([row(1, desc='CAFE, "A" 123456'),
                                  row(2, cat="Dining", src="manual", cents=5)])
        original = snapshot.read_bytes()
        out = self.root / "report"
        console = io.StringIO()
        with contextlib.redirect_stdout(console):
            bl.main(["--db", str(snapshot), "--out", str(out)])
        self.assertEqual(console.getvalue(), "schema_version=22 merchants=1 hinted=0 verified=1\n"
                         "  exported_verified=1\n  skipped_unlabeled=1\n")
        self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o700)
        for filename in ("backlog.csv", "verified.csv"):
            self.assertEqual(stat.S_IMODE((out / filename).stat().st_mode), 0o600)
        with (out / "backlog.csv").open(newline="") as stream:
            self.assertEqual(list(csv.DictReader(stream))[0]["normalized_merchant"], 'cafe, "a" #')
        with (out / "verified.csv").open(newline="") as stream:
            self.assertEqual(list(csv.DictReader(stream))[0]["category"], "Dining")
        self.assertEqual(snapshot.read_bytes(), original)
        with self.assertRaisesRegex(ValueError, "fresh folder"):
            bl.write(out, [], [])


if __name__ == "__main__":
    unittest.main()
```
