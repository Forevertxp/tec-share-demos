# TechShare article demos

Reproducible examples for [TechShare](https://tec-share.com), organized as independent subprojects. Future article demos will be added to this repository under topic-specific directories.

## Java performance — article 279

[Read the article](https://tec-share.com/2026/08/01/java-performance-unnecessary-work/) · [Source and instructions](java-performance) · [Raw JMH results](results/jmh.json)

Requires JDK 17+ and Maven 3.9+. From the repository root:

```sh
mvn -pl java-performance -am verify
mkdir -p results
java -jar java-performance/target/benchmarks.jar MembershipBenchmark -p studentsCount=100,10000 -p selectedCount=10,1000 -p hitPercent=50 -wi 3 -i 5 -w 1s -r 1s -f 2 -foe true -prof gc -rf json -rff results/jmh.json
```

The six correctness tests preserve ordered results, repeated input IDs and null membership. Measurements use synthetic repeated import records and a 50% hit rate. They are microseconds per complete request, not production latency. The captured results do not consistently rank the two Set variants; wide intervals require further profiling before making finer claims. Raw allocation metrics exclude the retained setup cost of a prebuilt Set.

Previously published standalone repositories remain available: [Outbox relay](https://github.com/Forevertxp/outbox-relay-demo) and [AI workout plan demo](https://github.com/Forevertxp/ai-workout-plan-java-demo).
