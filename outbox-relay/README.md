# Outbox Relay Retry Demo

This small demo accompanies the TechShare article [Outbox Relay Retries: At-Least-Once Delivery Without Duplicate Events](https://tec-share.com/2026/10/16/outbox-relay-retries-at-least-once-delivery-without-duplicate-events/).

It focuses on the failure window between a broker publish and the database update that marks an Outbox row as sent. The demo keeps one stable `event_id`, schedules retry with exponential backoff, moves exhausted events to `DEAD`, and records processed event IDs on the consumer side.

## What is included

- `schema.sql` creates the Outbox and consumer idempotency tables.
- `src/main/java/com/tecshare/outbox/OutboxRelay.java` contains the claim, publish, retry, and dead-letter flow.
- `src/test/java/com/tecshare/outbox/OutboxRelayTest.java` exercises a publish failure, a crash after publish, and duplicate consumption.

The Java classes use small interfaces so the failure points can be replaced with a real MySQL repository and broker client without hiding the delivery semantics.

## Run the tests

```bash
mvn test
```

Requires JDK 17+ and Maven 3.9+. The compiler plugin is pinned and tests use Java 17 collection APIs.

The tests inject a crash after broker acceptance but before marking an event SENT. The claim remains PROCESSING; a new relay object sharing the in-memory store waits for the five-second lease to expire, then republishes the same event ID. A synthetic consumer applies that ID once. Another test resumes an old worker after a newer claim and verifies that the old completion cannot overwrite the newer state.

`attempts` counts claimed delivery attempts, including interrupted claims that may not reach the broker. Retry delays are 2 and 4 seconds before a third failure becomes DEAD. Test clocks are injected; timestamps are synthetic and no real waiting is required. An exhausted uncertain publish does not prove non-delivery: DEAD events need reconciliation before deliberate replay.

This is a memory-backed model. A new relay object simulates a restart while preserving the store object; an actual JVM exit would lose that data. The consumer set represents a deduplication contract, not a durable transactional ledger. No real broker, database, network timeout or process kill is tested. This poller claims all due events at once; production needs bounded batches and leases sized or renewed for processing time.

## Production notes

The sample is intentionally small. A production relay should use MySQL 8 `FOR UPDATE SKIP LOCKED`, a lease timeout, bounded exponential backoff with jitter, metrics for event age and dead rows, and a deliberate replay operation for `DEAD` events.


[Download source, schema, tests, and captured output](./outbox-relay.zip). Extract the archive and run `mvn test` in the extracted directory.
