"""Article 344: SQL fixture, regression tests and real SQLite query plans.

Run from the repository root with Python 3.10+ (standard library only):
python sql/sum-distinct/verify.py --plans results/sum-distinct-sqlite.json
Add --export-mysql results/sum-distinct-mysql.sql to generate a MySQL
8.0.18+ EXPLAIN ANALYZE script for a fresh disposable schema.
All records are synthetic. SQLite output is not a MySQL measurement.
Companion article: https://tec-share.com/2026/08/26/sum-distinct-vs-record-deduplication/
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sqlite3
import unittest

SQLS = {
    '01-setup.sql': """-- Use a fresh disposable database. No existing tables are dropped.
CREATE TABLE sd_orders (
    id BIGINT PRIMARY KEY
);
CREATE TABLE sd_payments (
    id BIGINT PRIMARY KEY,
    order_id BIGINT NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES sd_orders(id)
);
CREATE TABLE sd_order_tags (
    id BIGINT PRIMARY KEY,
    order_id BIGINT NOT NULL,
    tag_code VARCHAR(30) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES sd_orders(id)
);
INSERT INTO sd_orders VALUES (1);
INSERT INTO sd_payments VALUES
    (101, 1, 50.00), (102, 1, 50.00), (103, 1, 80.00);
INSERT INTO sd_order_tags VALUES
    (201, 1, 'MEMBER'), (202, 1, 'COURSE');
""",
    '02-joined-rows.sql': """SELECT p.id AS payment_id, p.order_id, p.amount,
       t.id AS tag_id
FROM sd_payments AS p
JOIN sd_order_tags AS t ON t.order_id = p.order_id
ORDER BY p.id, t.id;
""",
    '03-value-distinct.sql': """SELECT p.order_id,
       SUM(p.amount) AS joined_total,
       SUM(DISTINCT p.amount) AS distinct_value_total
FROM sd_payments AS p
JOIN sd_order_tags AS t ON t.order_id = p.order_id
GROUP BY p.order_id;
""",
    '04-wrong-projection.sql': """SELECT DISTINCT p.order_id, p.amount
FROM sd_payments AS p
JOIN sd_order_tags AS t ON t.order_id = p.order_id
ORDER BY p.order_id, p.amount;
""",
    '05-payment-set.sql': """SELECT DISTINCT p.id AS payment_id, p.order_id, p.amount
FROM sd_payments AS p
JOIN sd_order_tags AS t ON t.order_id = p.order_id
ORDER BY p.id;
""",
    '06-tag-projection.sql': """SELECT DISTINCT p.id AS payment_id, p.order_id, p.amount,
       t.id AS tag_id
FROM sd_payments AS p
JOIN sd_order_tags AS t ON t.order_id = p.order_id
ORDER BY p.id, t.id;
""",
    '07-fixed-by-identity.sql': """SELECT x.order_id, SUM(x.amount) AS paid_amount
FROM (
    SELECT DISTINCT p.id AS payment_id, p.order_id, p.amount
    FROM sd_payments AS p
    JOIN sd_order_tags AS t ON t.order_id = p.order_id
) AS x
GROUP BY x.order_id
ORDER BY x.order_id;
""",
    '08-fixed-with-exists.sql': """SELECT p.order_id, SUM(p.amount) AS paid_amount
FROM sd_payments AS p
WHERE EXISTS (
    SELECT 1
    FROM sd_order_tags AS t
    WHERE t.order_id = p.order_id
)
GROUP BY p.order_id
ORDER BY p.order_id;
""",
    '09-extra-order.sql': """-- Run once after the initial examples.
-- This order has a valid payment but no tags.
INSERT INTO sd_orders VALUES (2);
INSERT INTO sd_payments VALUES (104, 2, 25.00);
""",
    '10-all-orders.sql': """SELECT o.id AS order_id,
       COALESCE(p.paid_amount, 0) AS paid_amount
FROM sd_orders AS o
LEFT JOIN (
    SELECT order_id, SUM(amount) AS paid_amount
    FROM sd_payments
    GROUP BY order_id
) AS p ON p.order_id = o.id
ORDER BY o.id;
""",
}

class AmountIdentityTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(SQLS["01-setup.sql"])
        self.addCleanup(self.db.close)

    def query(self, name):
        return self.db.execute(SQLS[name]).fetchall()

    def test_join_multiplies_rows_and_value_distinct_loses_payment(self):
        self.assertEqual(len(self.query("02-joined-rows.sql")), 6)
        self.assertEqual(self.query("03-value-distinct.sql"), [(1, 360, 130)])
        self.assertEqual(self.query("07-fixed-by-identity.sql"), [(1, 180)])
        self.assertEqual(self.query("08-fixed-with-exists.sql"), [(1, 180)])

    def test_unrelated_tag_does_not_change_identity_total(self):
        self.db.execute("INSERT INTO sd_order_tags VALUES (203,1,'VIP')")
        self.assertEqual(self.query("03-value-distinct.sql"), [(1, 540, 130)])
        self.assertEqual(self.query("07-fixed-by-identity.sql"), [(1, 180)])

    def test_another_payment_with_same_amount_is_a_real_payment(self):
        self.db.execute("INSERT INTO sd_payments VALUES (104,1,50)")
        self.assertEqual(self.query("08-fixed-with-exists.sql"), [(1, 230)])
        self.assertEqual(self.query("07-fixed-by-identity.sql"), [(1, 230)])
        self.assertEqual(self.query("03-value-distinct.sql"), [(1, 460, 130)])

    def test_untagged_and_payment_free_orders_have_explicit_report_semantics(self):
        self.db.executescript(SQLS["09-extra-order.sql"])
        self.db.execute("INSERT INTO sd_orders VALUES (3)")
        self.assertEqual(self.query("08-fixed-with-exists.sql"), [(1, 180)])
        self.assertEqual(self.query("10-all-orders.sql"), [(1, 180), (2, 25), (3, 0)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plans', type=Path)
    parser.add_argument('--export-mysql', type=Path)
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AmountIdentityTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    with sqlite3.connect(':memory:') as db:
        db.execute('PRAGMA foreign_keys=ON')
        db.executescript(SQLS['01-setup.sql'])
        db.executescript('CREATE INDEX sd_payment_order ON sd_payments(order_id); CREATE INDEX sd_tag_order ON sd_order_tags(order_id); ANALYZE;')
        report = {'engine': 'SQLite', 'sqlite_version': sqlite3.sqlite_version,
                  'python': platform.python_version(), 'captured_at_utc': datetime.now(timezone.utc).isoformat(),
                  'scope': 'tiny indexed fixture; semantic results and plans, no performance claim', 'queries': {}}
        names = ['03-value-distinct.sql', '07-fixed-by-identity.sql', '08-fixed-with-exists.sql']
        for name in names:
            query = SQLS[name]
            rows = db.execute(query).fetchall()
            plan = db.execute('EXPLAIN QUERY PLAN ' + query).fetchall()
            report['queries'][name] = {'sql': query, 'rows': rows, 'plan': plan}
            print(name, rows)
            for row in plan:
                print('  SQLite plan:', row[3])
        if args.plans:
            args.plans.parent.mkdir(parents=True, exist_ok=True)
            args.plans.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    if args.export_mysql:
        sql = '-- Generated for MySQL 8.0.18+. Use a new disposable schema. No tables are dropped.\nSELECT VERSION();\n'
        sql += SQLS['01-setup.sql'] + '\nCREATE INDEX sd_payment_order ON sd_payments(order_id);\nCREATE INDEX sd_tag_order ON sd_order_tags(order_id);\n'
        sql += '\n'.join('EXPLAIN ANALYZE\n' + SQLS[name] for name in names)
        args.export_mysql.parent.mkdir(parents=True, exist_ok=True)
        args.export_mysql.write_text(sql, encoding='utf-8')
        print('Exported MySQL script; NOT executed:', args.export_mysql)
    print('PASS: 4 regression tests. SQLite output only; no MySQL or DECIMAL rounding validation.')

if __name__ == '__main__':
    main()
