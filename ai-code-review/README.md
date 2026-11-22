# AI-assisted code review: order transition exercise — article 140

Article: https://tec-share.com/2026/09/26/developer-career-ai-coding/

Requires JDK 17+. No Maven, database, network, provider credentials or external dependencies.

```sh
java OrderReviewDemo.java --check-unsafe
# Expected: AssertionError "paid survives stale expiry", nonzero exit.

java OrderReviewDemo.java
# Expected: 11 checks passed, including one detected unsafe counterexample.
```

The deliberately flawed implementation is an authored teaching candidate, not a saved AI conversation or production incident. The program uses a latch-controlled schedule: expiry reads UNPAID, payment commits PAID, expiry resumes its stale write. The unsafe candidate loses the payment state; the guarded candidate preserves it.

The 11 normal checks comprise one detected unsafe counterexample and ten guarded-order checks: paid state survives a stale expiry; no early expiry; exact-deadline expiry; duplicate expiry has one simulated release; late payment requires review; normal payment; duplicate receipt replay; paid order cannot expire; conflicting receipt requires review; blank receipt rejected.

The captured outputs below were produced on November 22, 2026 with Java 17.0.21.0.2 on Windows 11.

Scope: one JVM, an immutable snapshot in an AtomicReference, and a simulated release counter. No live inventory or payment request is executed. The test hook exists solely to control an interleaving and defaults to no action. These checks do not prove durable storage, database isolation, provider authentication, cross-process coordination or crash recovery. A late payment sets a review marker; it does not perform financial reconciliation.

The career lesson is the review artifact: explicit invariants, a counterexample, a guarded change and reproducible checks. No measured claim about AI accuracy, productivity or job outcomes is made.


## Captured normal run

```text
Java=17.0.21.0.2 OS=Windows 11
unsafe stale-expiry outcome=Snapshot[status=CANCELLED, paymentId=null, releases=1, needsReview=false]
PASS counterexample detected: unsafe overwrites paid
guarded same-schedule outcome=Snapshot[status=PAID, paymentId=PAY-1, releases=0, needsReview=false]
PASS paid survives stale expiry
PASS not expired before deadline
PASS expiry at exact deadline
PASS duplicate timeout releases once
PASS late payment routes to review
PASS ordinary payment accepted
PASS same payment is a replay
PASS paid order cannot timeout
PASS different payment ID requires review
PASS blank payment ID rejected
11 checks passed, including one detected unsafe counterexample. Not a throughput benchmark.
```

## Captured unsafe invariant failure

```text
Java=17.0.21.0.2 OS=Windows 11
unsafe candidate=Snapshot[status=CANCELLED, paymentId=null, releases=1, needsReview=false]
Exception in thread "main" java.lang.AssertionError: paid survives stale expiry
	at OrderReviewDemo.check(OrderReviewDemo.java:57)
	at OrderReviewDemo.main(OrderReviewDemo.java:79)
```

