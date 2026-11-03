# JOIN vs EXISTS: paginate orders, not child rows

Companion to [TechShare article 346](https://tec-share.com/2026/10/12/join-vs-exists-in-sql-filter-orders-without-breaking-pagination/).

`verify.py` is standalone: Python 3.10+ and its standard library only. It includes the seven-order fixture, all query definitions, seven regression tests, a deterministic scale-data generator, and an optional MySQL plan exporter.

```sh
python sql/join-exists/verify.py
python sql/join-exists/verify.py --benchmark --sizes 1000 10000 100000 --repeats 9 --output results/join-exists-sqlite.json --export-mysql results/join-exists-mysql.sql
```

Tests use fresh in-memory SQLite databases. The first command performs no file writes. The second creates or overwrites the specified report/export files; it does not connect to an existing database. A failed correctness check exits unsuccessfully before publication of timing data.

## Pagination regression

| Query | First 3 rows | Next 3 rows |
|---|---|---|
| Raw JOIN | 7, 7, 7 | 7, 6, 6 |
| EXISTS | 7, 6, 5 | 1 |
| JOIN DISTINCT on order columns | 7, 6, 5 | 1 |

Removing repeated order IDs after LIMIT cannot restore a full parent page. DISTINCT works here because it selects only order identity and sort values. Adding varying child IDs changes that property.

The seven tests cover raw JOIN duplication, correct parent pagination/count, DISTINCT equivalence, a cursor across tied timestamps, exclusion after a new processing refund, same-payment predicates, and NULL in a NOT IN subquery. The last case uses a separate nullable test relation, not the fixture's NOT NULL refund key. The single-payment test uses amount >= 100; the article uses > 100. This fixture has no payment exactly at 100, so those checks give the same demonstrated counterexample but the predicates are not interchangeable in general.

## Captured local scale experiment

Captured on 2026-11-03 with Python 3.12.10 / SQLite 3.49.1 on Windows 11. All seven tests passed first. These are indexed, in-memory, warm-cache LIMIT 20 queries. There are 3 payments and 4 items per generated order, with deterministic status/product filtering. The scale fixture omits refunds and is distinct from the seven-order semantic fixture. It models repeated child matches, not a production data distribution.

The expected first 20 order IDs are computed independently and checked before timing the two valid alternatives. One explicit warmup follows correctness and plan capture; order is shuffled using seed 346 for every repetition; fetching all result rows is timed. Schema/data loading, index creation and ANALYZE are excluded. This is a small local experiment, not a capacity test or general proof that EXISTS is faster.

| Orders | Payments | Items | EXISTS median ms | JOIN DISTINCT median ms |
|---:|---:|---:|---:|---:|
| 1000 | 3000 | 4000 | 0.014800 | 0.029600 |
| 10000 | 30000 | 40000 | 0.014800 | 0.029300 |
| 100000 | 300000 | 400000 | 0.016500 | 0.029700 |

The raw JOIN is also captured as an intentionally incorrect baseline. Its faster timing is not an equivalent optimization: it returns a different order page. Similar medians across sizes are possible because appropriate indexes satisfy the same small top-of-order LIMIT; they say little about a full scan, deep offsets, cold disk or concurrent writes. Interpret the per-query plans and all samples below before generalizing.

## Actual MySQL verification is separate

The exporter writes the seven-order schema/data, lookup indexes, and three MySQL 8.0.18+ EXPLAIN ANALYZE queries. Python does not execute MySQL. Run the generated script once in a newly created disposable schema:

```sh
mysql --login-path=local-demo --table fresh_demo < results/join-exists-mysql.sql
```

Configure the login path separately. Tables must be fresh; none are dropped. Capture the actual server version and output before making MySQL-specific optimizer, DECIMAL, or performance claims. SQLite plans cannot establish MySQL's chosen semijoin strategy.

<details>
<summary>Full captured SQLite report: SQL, indexes reflected in plans, result IDs and all timing samples</summary>

```json
{
  "captured_at_utc": "2026-11-03T01:24:18.961985+00:00",
  "engine": "SQLite",
  "sqlite_version": "3.49.1",
  "python": "3.12.10",
  "platform": "Windows-11-10.0.26200-SP0",
  "scope": "in-memory, warm cache, indexed LIMIT 20; fetch included; loading and ANALYZE excluded; scale fixture omits refunds",
  "seed": 346,
  "repeats": 9,
  "workloads": [
    {
      "orders": 1000,
      "payments": 3000,
      "items": 4000,
      "expected_ids": [
        999,
        998,
        997,
        996,
        993,
        992,
        991,
        989,
        988,
        986,
        984,
        983,
        982,
        981,
        979,
        978,
        977,
        976,
        974,
        972
      ],
      "queries": {
        "exists": {
          "sql": "SELECT o.id FROM bench_orders o WHERE EXISTS\n      (SELECT 1 FROM bench_payments p WHERE p.order_id=o.id AND p.status='SUCCEEDED')\n      AND EXISTS (SELECT 1 FROM bench_items i WHERE i.order_id=o.id AND i.code='A')\n      ORDER BY o.created_at DESC,o.id DESC LIMIT 20",
          "ids": [
            999,
            998,
            997,
            996,
            993,
            992,
            991,
            989,
            988,
            986,
            984,
            983,
            982,
            981,
            979,
            978,
            977,
            976,
            974,
            972
          ],
          "correct_order_page": true,
          "plan": [
            [
              4,
              0,
              118,
              "SCAN o USING COVERING INDEX bench_order_sort"
            ],
            [
              7,
              0,
              0,
              "CORRELATED SCALAR SUBQUERY 1"
            ],
            [
              11,
              7,
              44,
              "SEARCH p USING COVERING INDEX bench_payment_filter (order_id=? AND status=?)"
            ],
            [
              22,
              0,
              0,
              "CORRELATED SCALAR SUBQUERY 2"
            ],
            [
              26,
              22,
              46,
              "SEARCH i USING COVERING INDEX bench_item_filter (order_id=? AND code=?)"
            ]
          ],
          "samples_ms": [
            0.0158,
            0.0149,
            0.0148,
            0.0149,
            0.0146,
            0.0152,
            0.0147,
            0.0146,
            0.0147
          ],
          "median_ms": 0.0148,
          "min_ms": 0.0146,
          "max_ms": 0.0158
        },
        "join_distinct": {
          "sql": "SELECT DISTINCT o.id,o.created_at FROM bench_orders o\n      JOIN bench_payments p ON p.order_id=o.id AND p.status='SUCCEEDED'\n      JOIN bench_items i ON i.order_id=o.id AND i.code='A'\n      ORDER BY o.created_at DESC,o.id DESC LIMIT 20",
          "ids": [
            999,
            998,
            997,
            996,
            993,
            992,
            991,
            989,
            988,
            986,
            984,
            983,
            982,
            981,
            979,
            978,
            977,
            976,
            974,
            972
          ],
          "correct_order_page": true,
          "plan": [
            [
              7,
              0,
              118,
              "SCAN o USING COVERING INDEX bench_order_sort"
            ],
            [
              9,
              0,
              44,
              "SEARCH p USING COVERING INDEX bench_payment_filter (order_id=? AND status=?)"
            ],
            [
              14,
              0,
              46,
              "SEARCH i USING COVERING INDEX bench_item_filter (order_id=? AND code=?)"
            ]
          ],
          "samples_ms": [
            0.0321,
            0.0305,
            0.0296,
            0.0295,
            0.0298,
            0.0315,
            0.0292,
            0.0292,
            0.0295
          ],
          "median_ms": 0.0296,
          "min_ms": 0.0292,
          "max_ms": 0.0321
        },
        "raw_join_wrong_page": {
          "sql": "SELECT o.id FROM bench_orders o\n      JOIN bench_payments p ON p.order_id=o.id AND p.status='SUCCEEDED'\n      JOIN bench_items i ON i.order_id=o.id AND i.code='A'\n      ORDER BY o.created_at DESC,o.id DESC LIMIT 20",
          "ids": [
            999,
            999,
            999,
            999,
            999,
            999,
            999,
            999,
            999,
            999,
            999,
            999,
            998,
            998,
            998,
            998,
            998,
            998,
            998,
            998
          ],
          "correct_order_page": false,
          "plan": [
            [
              6,
              0,
              118,
              "SCAN o USING COVERING INDEX bench_order_sort"
            ],
            [
              8,
              0,
              44,
              "SEARCH p USING COVERING INDEX bench_payment_filter (order_id=? AND status=?)"
            ],
            [
              13,
              0,
              46,
              "SEARCH i USING COVERING INDEX bench_item_filter (order_id=? AND code=?)"
            ]
          ],
          "samples_ms": [
            0.0086,
            0.0082,
            0.0081,
            0.0085,
            0.008,
            0.0084,
            0.0082,
            0.0082,
            0.0082
          ],
          "median_ms": 0.0082,
          "min_ms": 0.008,
          "max_ms": 0.0086
        }
      }
    },
    {
      "orders": 10000,
      "payments": 30000,
      "items": 40000,
      "expected_ids": [
        9999,
        9998,
        9997,
        9994,
        9993,
        9992,
        9991,
        9988,
        9987,
        9986,
        9984,
        9983,
        9981,
        9979,
        9978,
        9977,
        9976,
        9974,
        9973,
        9972
      ],
      "queries": {
        "exists": {
          "sql": "SELECT o.id FROM bench_orders o WHERE EXISTS\n      (SELECT 1 FROM bench_payments p WHERE p.order_id=o.id AND p.status='SUCCEEDED')\n      AND EXISTS (SELECT 1 FROM bench_items i WHERE i.order_id=o.id AND i.code='A')\n      ORDER BY o.created_at DESC,o.id DESC LIMIT 20",
          "ids": [
            9999,
            9998,
            9997,
            9994,
            9993,
            9992,
            9991,
            9988,
            9987,
            9986,
            9984,
            9983,
            9981,
            9979,
            9978,
            9977,
            9976,
            9974,
            9973,
            9972
          ],
          "correct_order_page": true,
          "plan": [
            [
              4,
              0,
              151,
              "SCAN o USING COVERING INDEX bench_order_sort"
            ],
            [
              7,
              0,
              0,
              "CORRELATED SCALAR SUBQUERY 1"
            ],
            [
              11,
              7,
              46,
              "SEARCH p USING COVERING INDEX bench_payment_filter (order_id=? AND status=?)"
            ],
            [
              22,
              0,
              0,
              "CORRELATED SCALAR SUBQUERY 2"
            ],
            [
              26,
              22,
              48,
              "SEARCH i USING COVERING INDEX bench_item_filter (order_id=? AND code=?)"
            ]
          ],
          "samples_ms": [
            0.0158,
            0.015,
            0.0148,
            0.0151,
            0.0149,
            0.0145,
            0.0146,
            0.0148,
            0.0148
          ],
          "median_ms": 0.0148,
          "min_ms": 0.0145,
          "max_ms": 0.0158
        },
        "join_distinct": {
          "sql": "SELECT DISTINCT o.id,o.created_at FROM bench_orders o\n      JOIN bench_payments p ON p.order_id=o.id AND p.status='SUCCEEDED'\n      JOIN bench_items i ON i.order_id=o.id AND i.code='A'\n      ORDER BY o.created_at DESC,o.id DESC LIMIT 20",
          "ids": [
            9999,
            9998,
            9997,
            9994,
            9993,
            9992,
            9991,
            9988,
            9987,
            9986,
            9984,
            9983,
            9981,
            9979,
            9978,
            9977,
            9976,
            9974,
            9973,
            9972
          ],
          "correct_order_page": true,
          "plan": [
            [
              7,
              0,
              151,
              "SCAN o USING COVERING INDEX bench_order_sort"
            ],
            [
              9,
              0,
              46,
              "SEARCH p USING COVERING INDEX bench_payment_filter (order_id=? AND status=?)"
            ],
            [
              14,
              0,
              48,
              "SEARCH i USING COVERING INDEX bench_item_filter (order_id=? AND code=?)"
            ]
          ],
          "samples_ms": [
            0.0311,
            0.03,
            0.0296,
            0.0292,
            0.0293,
            0.029,
            0.0289,
            0.0289,
            0.0308
          ],
          "median_ms": 0.0293,
          "min_ms": 0.0289,
          "max_ms": 0.0311
        },
        "raw_join_wrong_page": {
          "sql": "SELECT o.id FROM bench_orders o\n      JOIN bench_payments p ON p.order_id=o.id AND p.status='SUCCEEDED'\n      JOIN bench_items i ON i.order_id=o.id AND i.code='A'\n      ORDER BY o.created_at DESC,o.id DESC LIMIT 20",
          "ids": [
            9999,
            9999,
            9999,
            9999,
            9999,
            9999,
            9999,
            9999,
            9999,
            9999,
            9999,
            9999,
            9998,
            9998,
            9998,
            9998,
            9998,
            9998,
            9998,
            9998
          ],
          "correct_order_page": false,
          "plan": [
            [
              6,
              0,
              151,
              "SCAN o USING COVERING INDEX bench_order_sort"
            ],
            [
              8,
              0,
              46,
              "SEARCH p USING COVERING INDEX bench_payment_filter (order_id=? AND status=?)"
            ],
            [
              13,
              0,
              48,
              "SEARCH i USING COVERING INDEX bench_item_filter (order_id=? AND code=?)"
            ]
          ],
          "samples_ms": [
            0.0084,
            0.0082,
            0.0081,
            0.008,
            0.008,
            0.0081,
            0.0079,
            0.0079,
            0.0081
          ],
          "median_ms": 0.0081,
          "min_ms": 0.0079,
          "max_ms": 0.0084
        }
      }
    },
    {
      "orders": 100000,
      "payments": 300000,
      "items": 400000,
      "expected_ids": [
        99999,
        99998,
        99997,
        99996,
        99994,
        99993,
        99992,
        99991,
        99989,
        99987,
        99986,
        99984,
        99983,
        99982,
        99979,
        99978,
        99977,
        99976,
        99973,
        99972
      ],
      "queries": {
        "exists": {
          "sql": "SELECT o.id FROM bench_orders o WHERE EXISTS\n      (SELECT 1 FROM bench_payments p WHERE p.order_id=o.id AND p.status='SUCCEEDED')\n      AND EXISTS (SELECT 1 FROM bench_items i WHERE i.order_id=o.id AND i.code='A')\n      ORDER BY o.created_at DESC,o.id DESC LIMIT 20",
          "ids": [
            99999,
            99998,
            99997,
            99996,
            99994,
            99993,
            99992,
            99991,
            99989,
            99987,
            99986,
            99984,
            99983,
            99982,
            99979,
            99978,
            99977,
            99976,
            99973,
            99972
          ],
          "correct_order_page": true,
          "plan": [
            [
              4,
              0,
              185,
              "SCAN o USING COVERING INDEX bench_order_sort"
            ],
            [
              7,
              0,
              0,
              "CORRELATED SCALAR SUBQUERY 1"
            ],
            [
              11,
              7,
              48,
              "SEARCH p USING COVERING INDEX bench_payment_filter (order_id=? AND status=?)"
            ],
            [
              22,
              0,
              0,
              "CORRELATED SCALAR SUBQUERY 2"
            ],
            [
              26,
              22,
              49,
              "SEARCH i USING COVERING INDEX bench_item_filter (order_id=? AND code=?)"
            ]
          ],
          "samples_ms": [
            0.0172,
            0.0168,
            0.0165,
            0.0166,
            0.0165,
            0.0162,
            0.0162,
            0.0162,
            0.0161
          ],
          "median_ms": 0.0165,
          "min_ms": 0.0161,
          "max_ms": 0.0172
        },
        "join_distinct": {
          "sql": "SELECT DISTINCT o.id,o.created_at FROM bench_orders o\n      JOIN bench_payments p ON p.order_id=o.id AND p.status='SUCCEEDED'\n      JOIN bench_items i ON i.order_id=o.id AND i.code='A'\n      ORDER BY o.created_at DESC,o.id DESC LIMIT 20",
          "ids": [
            99999,
            99998,
            99997,
            99996,
            99994,
            99993,
            99992,
            99991,
            99989,
            99987,
            99986,
            99984,
            99983,
            99982,
            99979,
            99978,
            99977,
            99976,
            99973,
            99972
          ],
          "correct_order_page": true,
          "plan": [
            [
              7,
              0,
              185,
              "SCAN o USING COVERING INDEX bench_order_sort"
            ],
            [
              9,
              0,
              48,
              "SEARCH p USING COVERING INDEX bench_payment_filter (order_id=? AND status=?)"
            ],
            [
              14,
              0,
              49,
              "SEARCH i USING COVERING INDEX bench_item_filter (order_id=? AND code=?)"
            ]
          ],
          "samples_ms": [
            0.0312,
            0.0305,
            0.0299,
            0.0299,
            0.0295,
            0.0294,
            0.0295,
            0.0296,
            0.0297
          ],
          "median_ms": 0.0297,
          "min_ms": 0.0294,
          "max_ms": 0.0312
        },
        "raw_join_wrong_page": {
          "sql": "SELECT o.id FROM bench_orders o\n      JOIN bench_payments p ON p.order_id=o.id AND p.status='SUCCEEDED'\n      JOIN bench_items i ON i.order_id=o.id AND i.code='A'\n      ORDER BY o.created_at DESC,o.id DESC LIMIT 20",
          "ids": [
            99999,
            99999,
            99999,
            99999,
            99999,
            99999,
            99999,
            99999,
            99999,
            99999,
            99999,
            99999,
            99998,
            99998,
            99998,
            99998,
            99998,
            99998,
            99998,
            99998
          ],
          "correct_order_page": false,
          "plan": [
            [
              6,
              0,
              185,
              "SCAN o USING COVERING INDEX bench_order_sort"
            ],
            [
              8,
              0,
              48,
              "SEARCH p USING COVERING INDEX bench_payment_filter (order_id=? AND status=?)"
            ],
            [
              13,
              0,
              49,
              "SEARCH i USING COVERING INDEX bench_item_filter (order_id=? AND code=?)"
            ]
          ],
          "samples_ms": [
            0.0087,
            0.0084,
            0.0084,
            0.0083,
            0.0081,
            0.0082,
            0.0082,
            0.0082,
            0.0083
          ],
          "median_ms": 0.0083,
          "min_ms": 0.0081,
          "max_ms": 0.0087
        }
      }
    }
  ]
}
```

</details>

