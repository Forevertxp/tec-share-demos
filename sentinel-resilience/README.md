# Article 41: actual Sentinel rules, synthetic downstream

This uses `sentinel-core` 1.8.8 directly. It is a command-line experiment, not a Spring Boot or HTTP server benchmark. The synthetic downstream sleeps for 10 ms and fails every third offered request. There is no network dependency or genuine timeout injection. Closed-loop workers issue the next request after the previous one completes, so a fast block can greatly increase total completion rate.

```sh
mvn verify
java -jar target/sentinel-resilience-1.0.0.jar off 100 8
java -jar target/sentinel-resilience-1.0.0.jar flow 100 8
java -jar target/sentinel-resilience-1.0.0.jar circuit 100 8
```

Run each mode in a fresh JVM. Flow mode admits about 20 requests per second according to Sentinel's rolling-window rules, not an exact fixed-window quota. Circuit mode uses error ratio 0.3, minimum 10 requests, 1000-ms statistics window and 1-second open period. Tests cover block-before-downstream, traced errors, open-state rejection and recovery through a successful probe. Rule changes and core metrics are process-global; tests run sequentially.

`SUCCESS`, `FAILED` and `BLOCKED` counts must sum to requests. P95 is a nearest-rank latency within each outcome, never a merged success+fast-fallback percentile. `completed_per_second` includes rejected requests: it is **not successful business QPS**. Fallback text describes an unavailable/error result; it does not turn a blocked request into a completed business operation. Repeated console runs vary with the machine and rolling-window boundaries.

This is a short failure drill, not a warmed-up steady-state capacity test. Protected modes may admit only a handful of downstream calls; their P95 is therefore a coarse small-sample observation. Do not size a production limit from this percentile.

Core logs are under `target/sentinel-logs`, and embedded EagleEye logs are under `target/eagleeye-logs`; state changes go to stderr. Tests set workspace-local log directories for both loggers. There is no automatic retry, stale-cache fallback or billing/payment write in this demo.

References: [Sentinel flow control](https://sentinelguard.io/en-us/docs/flow-control.html), [circuit breaking](https://sentinelguard.io/en-us/docs/circuit-breaking.html).


Companion article: [Sentinel rate limiting and circuit breaking](https://tec-share.com/2026/08/25/java-sentinel-rate-limiting-circuit-breaking-degradation/). Captured output and test summaries are under results/.


[Download source, tests, and captured results](./sentinel-resilience.zip). Extract the archive and run the commands above in the extracted directory.
