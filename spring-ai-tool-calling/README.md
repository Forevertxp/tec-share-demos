# Spring AI tool-calling boundary demo — article 375

Article: https://tec-share.com/2026/10/09/spring-ai-tool-calling-java-execution/

This independent subproject uses Java 17, Maven 3.9+, Spring AI 2.0.1 and JUnit 5.11.0.
The source archive in this directory contains the POM, Java sources, all 14 tests and the captured test summary.

[Download tool-calling-boundary-demo.zip](tool-calling-boundary-demo.zip)

Extract the archive and run from the directory containing `pom.xml`:

```sh
mvn test
```

No provider API key, database or Spring Boot service is needed. Maven downloads dependencies on the first run.
The model is scripted; dispatch, argument conversion, method callbacks and the tool loop use the real Spring AI dependency.

## Executed checks

Tested November 21, 2026 with Java 17.0.21.0.2 on Windows 11 and Maven 3.9.9:

```
Tests run: 14, Failures: 0, Errors: 0, Skipped: 0
BUILD SUCCESS
```

- Framework and callback checks (8): successful two-model-call round trip with matching response ID; unknown tool; malformed JSON; blank input; another actor; another tenant; same public response for denied and missing orders; denied result passed back through the real tool loop.
- Business ledger checks (6): saved-result replay; changed-amount conflict; failure before effect followed by retry; eight concurrent duplicates with one effect; unauthorized replay; separate business requests remain separate.

The default framework converts the malformed-JSON tool execution error into a tool response in this fixture. The scripted model receives that response and supplies its fixed final text. The test asserts zero Java method entries; it does not claim that a final assistant message proves business success.

## Files

- `src/main/java/com/tecshare/OrderTools.java`: a request-scoped tool object with trusted caller context and synthetic authorization.
- `src/main/java/com/tecshare/CreditLedger.java`: a synchronized in-memory credit ledger with typed scoped keys, input conflict detection and completed-result replay.
- `src/test/java/com/tecshare/ToolBoundaryTest.java`: the 14 executable checks.
- `results/test-summary.txt`: captured test output excerpt, not a benchmark.

## Limits

The ledger uses one monitor and serializes calls in one JVM. Its data is neither durable nor crash-atomic, and the injected failure is before any business mutation. It does not prove safe retry after an external provider accepted a write, after a process crash, or across multiple service instances.

In production, persist the scoped key, request fingerprint, business mutation and result in the same database transaction when possible. For external effects, use the provider's idempotency facility and reconciliation. Recheck current authorization before replaying a saved response; choose retention and retry policies deliberately. Authentication is represented by a trusted `Caller` fixture here, not integrated with a live security filter.
