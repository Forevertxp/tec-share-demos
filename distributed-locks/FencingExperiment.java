package com.tecshare.locks;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Article 33: controlled in-memory coordination and resource-side fencing.
 * JDK 17+; no dependencies. From the repository root:
 * java distributed-locks/FencingExperiment.java
 * All five checks throw on failure without requiring -ea.
 * This is not a Redis/Redisson implementation or production incident log.
 */
public final class FencingExperiment {
    public record Lease(String owner, long token, long expiresAt) {}
    public static final class Coordinator {
        private final AtomicLong clock;
        private Lease current;
        private long sequence;
        public Coordinator(AtomicLong clock) { this.clock = clock; }
        public synchronized Lease acquire(String owner, long ttl) {
            if (ttl <= 0) throw new IllegalArgumentException("ttl must be positive");
            if (current != null && clock.get() < current.expiresAt()) return null;
            current = new Lease(owner, ++sequence, clock.get() + ttl);
            return current;
        }
        public synchronized boolean release(Lease lease) {
            if (current == null || !current.equals(lease)) return false;
            current = null;
            return true;
        }
        public synchronized Lease current() { return current; }
    }
    public static final class Resource {
        private long highestToken;
        private String value;
        private final boolean enforceFencing;
        public Resource(boolean enforceFencing) { this.enforceFencing = enforceFencing; }
        public synchronized boolean write(long token, String value) {
            // Atomic with the protected effect; no separate check-then-write window.
            if (enforceFencing && token < highestToken) return false;
            highestToken = Math.max(highestToken, token);
            this.value = value;
            return true;
        }
        public synchronized String value() { return value; }
    }
    public record Outcome(String value, boolean staleAccepted, boolean oldUnlockSucceeded,
                          boolean newLeaseSurvived, List<String> trace) {}

    public static Outcome run(boolean fenced) throws Exception {
        AtomicLong clock = new AtomicLong(0);
        Coordinator coordinator = new Coordinator(clock);
        Resource resource = new Resource(fenced);
        CountDownLatch acquired = new CountDownLatch(1), newerWritten = new CountDownLatch(1);
        List<String> trace = new ArrayList<>();
        ExecutorService workers = Executors.newFixedThreadPool(2);
        try {
            Future<boolean[]> a = workers.submit(() -> {
                Lease lease = coordinator.acquire("A", 100);
                if (lease == null) throw new IllegalStateException("A did not acquire");
                synchronized (trace) { trace.add("logical_ms=0 A acquired token=" + lease.token()); }
                acquired.countDown();
                if (!newerWritten.await(5, TimeUnit.SECONDS)) throw new IllegalStateException("B stalled");
                boolean written = resource.write(lease.token(), "A-old");
                boolean unlocked = coordinator.release(lease);
                synchronized (trace) { trace.add("logical_ms=101 A resumed stale_write=" + written + " unlock=" + unlocked); }
                return new boolean[]{written, unlocked};
            });
            Future<Lease> b = workers.submit(() -> {
                if (!acquired.await(5, TimeUnit.SECONDS)) throw new IllegalStateException("A stalled");
                clock.set(101); // Advance the injected clock; no sleep-based expiry race.
                Lease lease = coordinator.acquire("B", 100);
                if (lease == null || !resource.write(lease.token(), "B-new")) throw new IllegalStateException("B failed");
                synchronized (trace) { trace.add("logical_ms=101 B acquired token=" + lease.token() + " wrote=B-new"); }
                newerWritten.countDown();
                return lease; // Deliberately keep B's lease while A tries to release.
            });
            Lease bLease = b.get(7, TimeUnit.SECONDS);
            boolean[] aResult = a.get(7, TimeUnit.SECONDS);
            return new Outcome(resource.value(), aResult[0], aResult[1], bLease.equals(coordinator.current()), List.copyOf(trace));
        } finally {
            workers.shutdownNow();
            if (!workers.awaitTermination(5, TimeUnit.SECONDS)) throw new IllegalStateException("Workers did not stop");
        }
    }
    private static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    private static void checkLeaseBoundary() {
        AtomicLong clock = new AtomicLong(10);
        Coordinator coordinator = new Coordinator(clock);
        Lease first = coordinator.acquire("A", 100);
        check(first != null, "First lease missing");
        check(coordinator.acquire("B", 100) == null, "Unexpired lease allowed takeover");
        clock.set(110);
        Lease second = coordinator.acquire("B", 100);
        check(second != null && second.token() > first.token(), "Expiry did not advance ownership");
        check(!coordinator.release(first), "Old owner released new lease");
        check(coordinator.release(second), "New owner could not release its lease");
        System.out.println("PASS lease_boundary_and_owner_safe_release");
    }

    private static void checkTokenBoundary() {
        Resource resource = new Resource(true);
        check(resource.write(1, "first"), "First token rejected");
        check(resource.write(1, "same epoch"), "Same epoch unexpectedly rejected");
        check(resource.write(2, "new epoch"), "New token rejected");
        check(!resource.write(1, "stale"), "Old token accepted after newer write");
        check("new epoch".equals(resource.value()), "Stale effect replaced new value");
        System.out.println("PASS same_epoch_is_not_business_idempotency");
    }

    private static void checkInvalidLease() {
        Coordinator coordinator = new Coordinator(new AtomicLong());
        boolean rejected = false;
        try { coordinator.acquire("A", 0); }
        catch (IllegalArgumentException expected) { rejected = true; }
        check(rejected, "Zero lease duration accepted");
        System.out.println("PASS invalid_lease_rejected");
    }

    public static void main(String[] args) throws Exception {
        checkLeaseBoundary();
        checkTokenBoundary();
        checkInvalidLease();
        for (boolean fenced : new boolean[]{false, true}) {
            Outcome result = run(fenced);
            System.out.println("mode=" + (fenced ? "resource-fencing" : "owner-safe-unlock-only"));
            result.trace().forEach(System.out::println);
            System.out.println("final_value=" + result.value() + " new_lease_survived=" + result.newLeaseSurvived());
            if (result.staleAccepted() == fenced || result.oldUnlockSucceeded() || !result.newLeaseSurvived()
                    || !(fenced ? "B-new" : "A-old").equals(result.value())) {
                throw new AssertionError("Unexpected fencing outcome");
            }
        }
        System.out.println("PASS: 5 checks; two worker interleavings and three boundary checks");
    }
}
