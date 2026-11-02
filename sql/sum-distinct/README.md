# SUM(DISTINCT) versus payment identity

Companion to [TechShare article 344](https://tec-share.com/2026/08/26/sum-distinct-vs-record-deduplication/).

`verify.py` includes the original ten SQL examples, the complete schema and synthetic data, four additional regression tests, and SQLite plan capture. It uses Python 3.10+ and the standard library only. From the repository root:

```sh
python sql/sum-distinct/verify.py --plans results/sum-distinct-sqlite.json --export-mysql results/sum-distinct-mysql.sql
```

Each test has its own in-memory SQLite database. The script does not connect to an existing database. Repeating the command creates a fresh fixture and replaces the requested output files.

| Independent fixture change | Raw joined SUM | SUM(DISTINCT amount) | Payment identity / EXISTS |
|---|---:|---:|---:|
| Original: payments 50, 50, 80; two tags | 360 | 130 | 180 |
| Add payment 104 for order 1, amount 50 | 460 | 130 | 230 |
| Add a third tag instead | 540 | 130 | 180 |

The fourth test verifies the difference between tagged-order and all-order reports: an untagged order with a 25 payment is excluded by the eligibility queries, while the all-order report retains it and an order without payments. Changes in the table above are separate test cases, not cumulative inserts. In the original extra-order example payment 104 belongs to order 2; do not combine that insert with the independent payment-104 regression.

## What the plan capture means

A local run on 2026-11-02 with Python 3.12.10 / SQLite 3.49.1 passed all four tests. With indexes on payments(order_id) and tags(order_id), the captured plan for the amount-distinct aggregate includes `USE TEMP B-TREE FOR sum(DISTINCT)`. The identity subquery includes `USE TEMP B-TREE FOR DISTINCT` and the outer query includes `USE TEMP B-TREE FOR GROUP BY`. The EXISTS plan includes `CORRELATED SCALAR SUBQUERY 1` and an indexed tag lookup. The script records full SQL, result rows, engine version and every plan row in the JSON output.

Those observations explain this SQLite plan; they do not establish which query is fastest. There are three payments and two tags, no production load, and no validated MySQL DECIMAL rounding behavior. Do not report these as MySQL plans or performance measurements.

The `--export-mysql` option generates a separate script containing the initial fixture, indexes and three EXPLAIN ANALYZE statements. It is **not executed** by Python. With MySQL 8.0.18+ installed, run it once against a newly created disposable schema:

```sh
mysql --login-path=local-demo --table fresh_demo < results/sum-distinct-mysql.sql
```

Configure the local login path separately. The schema must be fresh; the script does not drop tables. Record the actual server version, cardinalities, indexes and output before making MySQL-specific claims.
