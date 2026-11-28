import java.util.*;

/** Dependency-free model of reconciliation, not a database transaction emulator. */
public final class BackfillDemo {
    record Key(long goodsId, Long specId) {}
    record Line(Key key, int quantity, int priceCents) {}
    record Target(String version, List<Line> lines, boolean complete) {
        Target { lines = List.copyOf(lines); }
    }
    enum Result { CONSISTENT, REPAIRED, SKIPPED }
    enum Failure { NONE, BEFORE_COMMIT, AFTER_COMMIT }
    static class Store {
        Map<Long, List<Line>> records = new HashMap<>();
        int commits;
        void replace(long id, List<Line> lines, Failure failure) {
            // Construct the replacement privately. The assignment models one commit boundary.
            List<Line> prepared = List.copyOf(lines);
            if (failure == Failure.BEFORE_COMMIT) throw new IllegalStateException("before commit");
            records.put(id, prepared); commits++;
            if (failure == Failure.AFTER_COMMIT) throw new IllegalStateException("acknowledgement lost");
        }
    }
    static Map<Key, Integer> quantities(List<Line> lines) {
        Map<Key, Integer> map = new HashMap<>();
        for (Line line : lines) map.merge(line.key(), line.quantity(), Math::addExact);
        return map;
    }
    static Result reconcile(Store store, long id, Target target, Failure failure) {
        // complete is a proposed safeguard beyond the project's empty-target check.
        if (!target.complete() || target.lines().isEmpty()) return Result.SKIPPED;
        List<Line> current = store.records.getOrDefault(id, List.of());
        if (quantities(current).equals(quantities(target.lines()))) return Result.CONSISTENT;
        store.replace(id, target.lines(), failure);
        return Result.REPAIRED;
    }
    static int checks;
    static void check(boolean condition, String name) {
        if (!condition) throw new AssertionError(name);
        checks++; System.out.println("PASS " + name);
    }
    static void attempt(Runnable action) {
        try { action.run(); throw new AssertionError("expected injected failure"); }
        catch (IllegalStateException expected) { /* injected fault */ }
    }
    public static void main(String[] args) {
        Key book = new Key(10, null), band = new Key(20, 3L);
        Target v1 = new Target("v1", List.of(new Line(book, 1, 100), new Line(band, 2, 200)), true);
        Store store = new Store();
        check(reconcile(store, 1, v1, Failure.NONE) == Result.REPAIRED, "missing record repaired");
        check(reconcile(store, 1, v1, Failure.NONE) == Result.CONSISTENT && store.commits == 1, "replay performs no additional commit");
        store.records.put(2L, List.of(new Line(book, 5, 100)));
        List<Line> before = store.records.get(2L);
        attempt(() -> reconcile(store, 2, v1, Failure.BEFORE_COMMIT));
        check(store.records.get(2L).equals(before), "failure before modeled commit retains old state");
        check(reconcile(store, 2, v1, Failure.NONE) == Result.REPAIRED, "retry repairs rolled-back attempt");
        attempt(() -> reconcile(store, 3, v1, Failure.AFTER_COMMIT));
        int committed = store.commits;
        check(quantities(store.records.get(3L)).equals(quantities(v1.lines())), "lost acknowledgement can hide committed success");
        check(reconcile(store, 3, v1, Failure.NONE) == Result.CONSISTENT && store.commits == committed, "retry after lost acknowledgement skips");
        store.records.put(4L, List.of(new Line(book, 1, 999), new Line(band, 2, 999)));
        check(reconcile(store, 4, v1, Failure.NONE) == Result.CONSISTENT
                && store.records.get(4L).get(0).priceCents() == 999, "quantity equivalence does not repair price");
        store.records.put(5L, List.of(new Line(band, 1, 200), new Line(book, 1, 100), new Line(band, 1, 200)));
        check(reconcile(store, 5, v1, Failure.NONE) == Result.CONSISTENT, "split and reordered rows can be quantity equivalent");
        check(reconcile(store, 1, new Target("empty", List.of(), true), Failure.NONE) == Result.SKIPPED, "empty target does not erase current state");
        check(reconcile(store, 1, new Target("partial", List.of(new Line(book, 1, 100)), false), Failure.NONE) == Result.SKIPPED, "explicit partial target blocked by demo safeguard");
        Target v2 = new Target("v2", List.of(new Line(book, 3, 100)), true);
        reconcile(store, 1, v2, Failure.NONE);
        check(quantities(store.records.get(1L)).equals(quantities(v2.lines())), "changed target changes result");
        // Deterministic interleaving: both workers observed an old state; their targets differ.
        store.replace(6, v2.lines(), Failure.NONE); // newer worker commits first
        store.replace(6, v1.lines(), Failure.NONE); // older worker commits afterward
        check(quantities(store.records.get(6L)).equals(quantities(v1.lines())), "atomic replacements alone allow stale overwrite");
        int additive = 0; additive += 2; additive += 2;
        check(additive == 4, "replayed additive update doubles quantity");
        // First pass advances beyond a failed ID; a fresh sweep is needed to visit it again.
        Store batch = new Store(); int failed = 0;
        for (long id = 1; id <= 3; id++) {
            try { reconcile(batch, id, v1, id == 2 ? Failure.BEFORE_COMMIT : Failure.NONE); }
            catch (IllegalStateException e) { failed++; }
        }
        check(failed == 1 && !batch.records.containsKey(2L) && batch.records.containsKey(3L), "continue-on-error can leave a hole behind cursor");
        int repaired = 0, consistent = 0;
        for (long id = 1; id <= 3; id++) {
            if (reconcile(batch, id, v1, Failure.NONE) == Result.REPAIRED) repaired++; else consistent++;
        }
        check(repaired == 1 && consistent == 2, "fresh sweep repairs hole and skips successful records");
        System.out.println("ALL " + checks + " CHECKS PASSED");
    }
}
