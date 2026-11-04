# Lease expiry and resource-side fencing

Companion to [TechShare article 33](https://tec-share.com/2026/08/15/java-distributed-locks-redis-redlock-zookeeper-best-practices/).

Requires JDK 17+ only. This independent subproject needs no Maven, Redis, broker, database or third-party libraries. From the shared repository root:

```sh
java distributed-locks/FencingExperiment.java
```

Java's source-file launcher compiles the file in memory and runs its main method. Five executable checks fail with AssertionError or another exception on an unexpected outcome; no `-ea` flag is required. To compile separately instead:

```sh
javac --release 17 -d target/lock-demo distributed-locks/FencingExperiment.java
java -cp target/lock-demo com.tecshare.locks.FencingExperiment
```

## Controlled sequence

Two actual Java worker threads use CountDownLatch to control the interleaving. A obtains token 1 and waits. The test advances a shared logical clock from 0 to 101, beyond the 100-unit lease deadline. B obtains token 2 and writes `B-new`, keeping its lease. Only then does A resume and attempt `A-old` followed by owner-safe release.

| Mode | A's stale write accepted? | A releases B's lease? | Final value | B's lease survives? |
|---|---|---|---|---|
| Owner-safe unlock only | yes | no | A-old | yes |
| Resource fencing | no | no | B-new | yes |

The lease coordinator checks ownership, while the destination separately checks the fencing token and performs its mutation atomically in a synchronized method. The unfenced run demonstrates the incorrect business outcome first. Tests check the final resource value and surviving lease, not just whether lock acquisition returned successfully.

## Five checks and captured output

The checks cover an active lease and exact expiry boundary, rejection of an old owner's release, same-token versus older-token writes, a zero-duration lease, and both two-worker interleavings. The first two lease properties are checked together, and the two worker modes are separate checks, giving five executable cases in total. A same-token duplicate is intentionally accepted: fencing is not business-command deduplication.

Captured on 2026-11-04 with Microsoft OpenJDK 17.0.21.0.2 on Windows 11:

```text
PASS lease_boundary_and_owner_safe_release
PASS same_epoch_is_not_business_idempotency
PASS invalid_lease_rejected
mode=owner-safe-unlock-only
logical_ms=0 A acquired token=1
logical_ms=101 B acquired token=2 wrote=B-new
logical_ms=101 A resumed stale_write=true unlock=false
final_value=A-old new_lease_survived=true
mode=resource-fencing
logical_ms=0 A acquired token=1
logical_ms=101 B acquired token=2 wrote=B-new
logical_ms=101 A resumed stale_write=false unlock=false
final_value=B-new new_lease_survived=true
PASS: 5 checks; two worker interleavings and three boundary checks
```

`logical_ms` labels injected simulation time. It is not a measured JVM pause or Redis expiration log. Real waiting is limited to bounded latch/future safety timeouts; advancing the model's clock does not depend on Thread.sleep.

## What still needs a real integration test

This is an in-memory model, not a Redis/Redisson or ZooKeeper client. It supplies no evidence about network partitions, watchdog renewal, Redis failover, clock drift, database transactions or durable recovery of token order. The coordinator counter resets on process restart. A real destination must atomically enforce the ordering rule alongside the effect; checking the token separately before writing leaves a race.

The destination rejects an old epoch after it observes a newer token. Merely acquiring a new lease elsewhere does not notify the destination or revoke an old worker's CPU execution. Equal-token duplicate commands need an independent idempotency mechanism. If a destination cannot enforce conditional writes or fencing, sending a token field alone provides no such protection.
