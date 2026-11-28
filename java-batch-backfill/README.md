# Java batch backfill demo

[Read the full case study on TechShare](https://tec-share.com/2026/11/28/how-to-make-java-batch-jobs-safe-to-rerun/) for the material snapshot repair, the quantity comparison, and how the batch revisits failed records.

## Run the demo

Use JDK 17 or later. From this directory, run:

```sh
java src/BackfillDemo.java
```

The demo uses synthetic records and models the commit boundary in memory. It covers retries before and after the modeled commit, quantity-only comparison, incomplete targets, stale writes, and a failed record behind the scan cursor. Database transactions, Spring proxy behavior, and coordination across workers require separate verification.

## Captured output

The following output was recorded on JDK 17 during the publication check.

```text
PASS missing record repaired
PASS replay performs no additional commit
PASS failure before modeled commit retains old state
PASS retry repairs rolled-back attempt
PASS lost acknowledgement can hide committed success
PASS retry after lost acknowledgement skips
PASS quantity equivalence does not repair price
PASS split and reordered rows can be quantity equivalent
PASS empty target does not erase current state
PASS explicit partial target blocked by demo safeguard
PASS changed target changes result
PASS atomic replacements alone allow stale overwrite
PASS replayed additive update doubles quantity
PASS continue-on-error can leave a hole behind cursor
PASS fresh sweep repairs hole and skips successful records
ALL 15 CHECKS PASSED
```
