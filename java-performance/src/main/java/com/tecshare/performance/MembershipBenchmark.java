package com.tecshare.performance;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Random;
import java.util.Set;
import java.util.concurrent.TimeUnit;
import org.openjdk.jmh.annotations.*;

@State(Scope.Thread)
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(value = 2, jvmArgsAppend = {"-Xms256m", "-Xmx256m", "-XX:+UseG1GC"})
public class MembershipBenchmark {
    @Param({"100", "10000"}) public int studentsCount;
    @Param({"10", "1000"}) public int selectedCount;
    @Param({"0", "50", "100"}) public int hitPercent;

    private List<Long> students;
    private List<Long> selected;
    private Set<Long> selectedSet;

    @Setup(Level.Trial)
    public void prepare() {
        selected = new ArrayList<>();
        for (int i = 0; i < selectedCount; i++) selected.add(10000L + i);
        Collections.shuffle(selected, new Random(20261102L));
        students = new ArrayList<>();
        int hitCount = studentsCount * hitPercent / 100;
        for (int i = 0; i < studentsCount; i++) {
            students.add(i < hitCount ? 10000L + i % selectedCount : 1000000L + i);
        }
        Collections.shuffle(students, new Random(346279L));
        selectedSet = new HashSet<>(selected);
        // Correctness checks run outside the timed operation.
        List<Long> baseline = Membership.listScan(students, selected);
        if (!baseline.equals(Membership.buildSetPerRequest(students, selected))
                || !baseline.equals(Membership.prebuiltSet(students, selectedSet))) {
            throw new IllegalStateException("Algorithms returned different ordered results");
        }
        if (baseline.size() != hitCount) throw new IllegalStateException("Wrong hit count");
    }

    @Benchmark public List<Long> listScan() { return Membership.listScan(students, selected); }
    @Benchmark public List<Long> buildSetPerRequest() { return Membership.buildSetPerRequest(students, selected); }
    @Benchmark public List<Long> prebuiltSet() { return Membership.prebuiltSet(students, selectedSet); }
}
