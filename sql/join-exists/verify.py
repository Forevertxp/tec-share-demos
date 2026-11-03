"""Article 346: isolated pagination regressions and optional SQLite scale experiment.

Python 3.10+, standard library only. From the repository root:
python sql/join-exists/verify.py
python sql/join-exists/verify.py --benchmark --output results/join-exists-sqlite.json
Optional --export-mysql PATH writes the tiny fixture and MySQL 8.0.18+
EXPLAIN ANALYZE statements for a fresh schema. It does not run MySQL.
Article: https://tec-share.com/2026/10/12/join-vs-exists-in-sql-filter-orders-without-breaking-pagination/
"""
import sqlite3
import unittest

FIXTURE = """-- Run once in a fresh disposable database.
CREATE TABLE ep_orders (
 id BIGINT PRIMARY KEY, created_at DATETIME NOT NULL
);
CREATE TABLE ep_payments (
 id BIGINT PRIMARY KEY, order_id BIGINT NOT NULL,
 status VARCHAR(20) NOT NULL, method VARCHAR(20) NOT NULL,
 amount DECIMAL(12,2) NOT NULL,
 FOREIGN KEY (order_id) REFERENCES ep_orders(id)
);
CREATE TABLE ep_refunds (
 id BIGINT PRIMARY KEY, order_id BIGINT NOT NULL,
 status VARCHAR(20) NOT NULL,
 FOREIGN KEY (order_id) REFERENCES ep_orders(id)
);
CREATE TABLE ep_items (
 id BIGINT PRIMARY KEY, order_id BIGINT NOT NULL,
 product_code VARCHAR(30) NOT NULL,
 FOREIGN KEY (order_id) REFERENCES ep_orders(id)
);
INSERT INTO ep_orders VALUES
 (1,'2026-07-01 09:00:00'), (2,'2026-07-02 09:00:00'),
 (3,'2026-07-03 09:00:00'), (4,'2026-07-04 09:00:00'),
 (5,'2026-07-05 09:00:00'), (6,'2026-07-06 09:00:00'),
 (7,'2026-07-06 09:00:00');
INSERT INTO ep_payments VALUES
 (11,1,'SUCCEEDED','CARD',150),
 (21,2,'SUCCEEDED','CARD',150),
 (31,3,'FAILED','CARD',200),
 (41,4,'SUCCEEDED','CARD',150),
 (51,5,'SUCCEEDED','BANK',120),
 (52,5,'SUCCEEDED','CARD',20),
 (61,6,'SUCCEEDED','CARD',60),
 (62,6,'SUCCEEDED','CARD',70),
 (71,7,'SUCCEEDED','CARD',150),
 (72,7,'SUCCEEDED','BANK',10);
INSERT INTO ep_refunds VALUES
 (201,2,'PROCESSING'), (202,2,'COMPLETED'),
 (501,5,'COMPLETED');
INSERT INTO ep_items VALUES
 (101,1,'COURSE-A'), (201,2,'COURSE-A'),
 (301,3,'COURSE-A'), (401,4,'COURSE-B'),
 (501,5,'COURSE-A'), (601,6,'COURSE-A'),
 (701,7,'COURSE-A'), (702,7,'COURSE-A');"""

ELIGIBLE = """
EXISTS (SELECT 1 FROM ep_payments p
        WHERE p.order_id=o.id AND p.status='SUCCEEDED')
AND NOT EXISTS (SELECT 1 FROM ep_refunds r
        WHERE r.order_id=o.id AND r.status='PROCESSING')
AND EXISTS (SELECT 1 FROM ep_items i
        WHERE i.order_id=o.id AND i.product_code='COURSE-A')
"""
EXISTS_BASE = "SELECT o.id FROM ep_orders o WHERE " + ELIGIBLE
ORDER = " ORDER BY o.created_at DESC, o.id DESC"
JOIN_BASE = """
SELECT o.id, o.created_at FROM ep_orders o
JOIN ep_payments p ON p.order_id=o.id AND p.status='SUCCEEDED'
JOIN ep_items i ON i.order_id=o.id AND i.product_code='COURSE-A'
WHERE NOT EXISTS (SELECT 1 FROM ep_refunds r
 WHERE r.order_id=o.id AND r.status='PROCESSING')
"""

def pagination_db():
    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(FIXTURE)
    return db

def ids(db, query):
    return [row[0] for row in db.execute(query)]

class PaginationTests(unittest.TestCase):
    def setUp(self):
        self.db = pagination_db()
        self.addCleanup(self.db.close)

    def test_raw_join_pages_can_repeat_one_order(self):
        first = ids(self.db, JOIN_BASE + ORDER + " LIMIT 3 OFFSET 0")
        second = ids(self.db, JOIN_BASE + ORDER + " LIMIT 3 OFFSET 3")
        self.assertEqual(first, [7, 7, 7])
        self.assertEqual(second, [7, 6, 6])
        self.assertEqual(list(dict.fromkeys(first)), [7])

    def test_exists_paginates_orders_not_detail_rows(self):
        self.assertEqual(ids(self.db, EXISTS_BASE + ORDER + " LIMIT 3"), [7, 6, 5])
        self.assertEqual(ids(self.db, EXISTS_BASE + ORDER + " LIMIT 3 OFFSET 3"), [1])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM ep_orders o WHERE " + ELIGIBLE).fetchone()[0], 4)

    def test_distinct_order_projection_matches_exists(self):
        distinct = JOIN_BASE.replace("SELECT o.id,", "SELECT DISTINCT o.id,", 1)
        self.assertEqual(ids(self.db, distinct + ORDER), ids(self.db, EXISTS_BASE + ORDER))

    def test_unique_sort_key_supports_keyset_cursor(self):
        cursor = " AND (o.created_at < '2026-07-06 09:00:00' OR (o.created_at='2026-07-06 09:00:00' AND o.id<7))"
        self.assertEqual(ids(self.db, EXISTS_BASE + cursor + ORDER + " LIMIT 3"), [6, 5, 1])

    def test_new_refund_excludes_order(self):
        self.db.execute("INSERT INTO ep_refunds VALUES (701,7,'PROCESSING')")
        self.assertEqual(ids(self.db, EXISTS_BASE + ORDER), [6, 5, 1])

    def test_predicates_must_match_the_same_payment(self):
        correct = """SELECT o.id FROM ep_orders o WHERE EXISTS
          (SELECT 1 FROM ep_payments p WHERE p.order_id=o.id
           AND p.status='SUCCEEDED' AND p.method='CARD' AND p.amount>=100)"""
        split = """SELECT o.id FROM ep_orders o WHERE EXISTS
          (SELECT 1 FROM ep_payments p WHERE p.order_id=o.id AND p.status='SUCCEEDED' AND p.method='CARD')
          AND EXISTS (SELECT 1 FROM ep_payments p WHERE p.order_id=o.id AND p.status='SUCCEEDED' AND p.amount>=100)"""
        self.assertNotIn(5, ids(self.db, correct))
        self.assertIn(5, ids(self.db, split))

    def test_not_in_with_nullable_subquery_is_not_not_exists(self):
        self.assertEqual(ids(self.db, "SELECT id FROM ep_orders WHERE id NOT IN (SELECT NULL UNION ALL SELECT 2)"), [])
        safe = """SELECT o.id FROM ep_orders o WHERE NOT EXISTS
          (SELECT 1 FROM (SELECT NULL AS order_id UNION ALL SELECT 2) r WHERE r.order_id=o.id) ORDER BY o.id"""
        self.assertEqual(ids(self.db, safe), [1, 3, 4, 5, 6, 7])


"""SQLite-only, in-memory, warm-cache comparison. Never call this a MySQL plan."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import random
import sqlite3
import statistics
import time

QUERIES = {
    "exists": """SELECT o.id FROM bench_orders o WHERE EXISTS
      (SELECT 1 FROM bench_payments p WHERE p.order_id=o.id AND p.status='SUCCEEDED')
      AND EXISTS (SELECT 1 FROM bench_items i WHERE i.order_id=o.id AND i.code='A')
      ORDER BY o.created_at DESC,o.id DESC LIMIT 20""",
    "join_distinct": """SELECT DISTINCT o.id,o.created_at FROM bench_orders o
      JOIN bench_payments p ON p.order_id=o.id AND p.status='SUCCEEDED'
      JOIN bench_items i ON i.order_id=o.id AND i.code='A'
      ORDER BY o.created_at DESC,o.id DESC LIMIT 20""",
    "raw_join_wrong_page": """SELECT o.id FROM bench_orders o
      JOIN bench_payments p ON p.order_id=o.id AND p.status='SUCCEEDED'
      JOIN bench_items i ON i.order_id=o.id AND i.code='A'
      ORDER BY o.created_at DESC,o.id DESC LIMIT 20""",
}

def create_db(size):
    db = sqlite3.connect(":memory:")
    db.executescript("""
    CREATE TABLE bench_orders(id INTEGER PRIMARY KEY, created_at INTEGER NOT NULL);
    CREATE TABLE bench_payments(id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL,status TEXT NOT NULL);
    CREATE TABLE bench_items(id INTEGER PRIMARY KEY,order_id INTEGER NOT NULL,code TEXT NOT NULL);
    CREATE INDEX bench_order_sort ON bench_orders(created_at DESC,id DESC);
    CREATE INDEX bench_payment_filter ON bench_payments(order_id,status);
    CREATE INDEX bench_item_filter ON bench_items(order_id,code);
    """)
    db.executemany("INSERT INTO bench_orders VALUES (?,?)", ((i, i // 3) for i in range(1, size + 1)))
    db.executemany("INSERT INTO bench_payments VALUES (?,?,?)",
                   ((i * 3 + p, i, "FAILED" if i % 5 == 0 else "SUCCEEDED") for i in range(1, size + 1) for p in range(3)))
    db.executemany("INSERT INTO bench_items VALUES (?,?,?)",
                   ((i * 4 + p, i, "B" if i % 7 == 0 else "A") for i in range(1, size + 1) for p in range(4)))
    db.commit()
    db.execute("ANALYZE")
    return db

def run(size, repeats):
    db = create_db(size)
    try:
        expected = [i for i in range(size, 0, -1) if i % 5 != 0 and i % 7 != 0][:20]
        result = {}
        for name, query in QUERIES.items():
            rows = [r[0] for r in db.execute(query)]
            correct = rows == expected
            if name != "raw_join_wrong_page" and not correct:
                raise AssertionError((name, rows, expected))
            result[name] = {"sql": query, "ids": rows, "correct_order_page": correct,
                            "plan": [list(r) for r in db.execute("EXPLAIN QUERY PLAN " + query)], "samples_ms": []}
        # Warm every variant, then shuffle each repetition to reduce ordering bias.
        for query in QUERIES.values():
            list(db.execute(query))
        rng = random.Random(346)
        for _ in range(repeats):
            names = list(QUERIES)
            rng.shuffle(names)
            for name in names:
                started = time.perf_counter_ns()
                list(db.execute(QUERIES[name]))
                result[name]["samples_ms"].append((time.perf_counter_ns() - started) / 1e6)
        for entry in result.values():
            entry["median_ms"] = statistics.median(entry["samples_ms"])
            entry["min_ms"] = min(entry["samples_ms"])
            entry["max_ms"] = max(entry["samples_ms"])
        return {"orders": size, "payments": size * 3, "items": size * 4, "expected_ids": expected, "queries": result}
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--benchmark', action='store_true')
    parser.add_argument('--sizes', type=int, nargs='+', default=[1000, 10000, 100000])
    parser.add_argument('--repeats', type=int, default=9)
    parser.add_argument('--output', type=Path, default=Path('results/join-exists-sqlite.json'))
    parser.add_argument('--export-mysql', type=Path)
    args = parser.parse_args()
    if args.repeats < 3 or any(n < 50 for n in args.sizes):
        parser.error('At least 3 repeats and 50 orders per size are required')
    checked = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PaginationTests))
    if not checked.wasSuccessful():
        raise SystemExit(1)
    db = pagination_db()
    try:
        distinct = JOIN_BASE.replace('SELECT o.id,', 'SELECT DISTINCT o.id,', 1)
        for name, query in [('raw JOIN', JOIN_BASE), ('EXISTS', EXISTS_BASE), ('JOIN DISTINCT', distinct)]:
            print(name, 'page1=', ids(db, query + ORDER + ' LIMIT 3'),
                  'page2=', ids(db, query + ORDER + ' LIMIT 3 OFFSET 3'))
    finally:
        db.close()
    if args.export_mysql:
        indexes = '''
CREATE INDEX ep_payment_lookup ON ep_payments(order_id,status);
CREATE INDEX ep_item_lookup ON ep_items(order_id,product_code);
CREATE INDEX ep_refund_lookup ON ep_refunds(order_id,status);
CREATE INDEX ep_order_sort ON ep_orders(created_at DESC,id DESC);
'''
        sql = '-- MySQL 8.0.18+, fresh disposable schema only. Not executed by Python.\nSELECT VERSION();\n' + FIXTURE + indexes
        for query in [JOIN_BASE, EXISTS_BASE, distinct]:
            sql += '\nEXPLAIN ANALYZE\n' + query + ORDER + ' LIMIT 3;\n'
        args.export_mysql.parent.mkdir(parents=True, exist_ok=True)
        args.export_mysql.write_text(sql, encoding='utf-8')
        print('Exported MySQL script; NOT executed:', args.export_mysql)
    if args.benchmark:
        report = {'captured_at_utc': datetime.now(timezone.utc).isoformat(),
                  'engine': 'SQLite', 'sqlite_version': sqlite3.sqlite_version,
                  'python': platform.python_version(), 'platform': platform.platform(),
                  'scope': 'in-memory, warm cache, indexed LIMIT 20; fetch included; loading and ANALYZE excluded; scale fixture omits refunds',
                  'seed': 346, 'repeats': args.repeats,
                  'workloads': [run(size, args.repeats) for size in args.sizes]}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        for workload in report['workloads']:
            for name, entry in workload['queries'].items():
                print(f"orders={workload['orders']} query={name} correct={entry['correct_order_page']} median_ms={entry['median_ms']:.6f}")
        print('Raw SQLite plans and timing samples:', args.output)

if __name__ == '__main__':
    main()
