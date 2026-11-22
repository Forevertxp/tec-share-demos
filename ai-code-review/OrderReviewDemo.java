import java.time.Instant;
import java.util.Objects;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;

/** Synthetic review exercise; no model, database, payment provider or real inventory. */
public class OrderReviewDemo {
    enum Status { UNPAID, PAID, CANCELLED }
    record Snapshot(Status status, String paymentId, int releases, boolean needsReview) {}
    static final Instant DEADLINE = Instant.parse("2026-01-01T00:15:00Z");
    interface Order {
        boolean expire(Instant now, Runnable afterRead);
        String paid(String paymentId);
        Snapshot snapshot();
    }
    // Deliberately flawed reference candidate, not a transcript of AI-generated code.
    static final class UnsafeOrder implements Order {
        final AtomicReference<Snapshot> state = new AtomicReference<>(new Snapshot(Status.UNPAID,null,0,false));
        public boolean expire(Instant now, Runnable afterRead) {
            Snapshot old = state.get();
            if (now.isBefore(DEADLINE) || old.status()!=Status.UNPAID) return false;
            afterRead.run();
            state.set(new Snapshot(Status.CANCELLED,null,old.releases()+1,false));
            return true;
        }
        public String paid(String id) {
            state.set(new Snapshot(Status.PAID,id,0,false)); return "PAID";
        }
        public Snapshot snapshot() { return state.get(); }
    }
    static final class GuardedOrder implements Order {
        final AtomicReference<Snapshot> state = new AtomicReference<>(new Snapshot(Status.UNPAID,null,0,false));
        public boolean expire(Instant now, Runnable afterRead) {
            if (now.isBefore(DEADLINE)) return false;
            Snapshot old = state.get();
            if (old.status()!=Status.UNPAID) return false;
            afterRead.run();
            // Status and the simulated release count move together in one local snapshot.
            return state.compareAndSet(old,new Snapshot(Status.CANCELLED,null,old.releases()+1,false));
        }
        public String paid(String id) {
            if (id==null || id.isBlank()) return "INVALID_PAYMENT_ID";
            for (;;) {
                Snapshot old=state.get();
                if (old.status()==Status.PAID && Objects.equals(old.paymentId(),id)) return "REPLAY";
                if (old.status()!=Status.UNPAID) {
                    Snapshot review=new Snapshot(old.status(),old.paymentId(),old.releases(),true);
                    if (state.compareAndSet(old,review)) return "RECONCILE";
                } else if (state.compareAndSet(old,new Snapshot(Status.PAID,id,0,false))) return "PAID";
            }
        }
        public Snapshot snapshot() { return state.get(); }
    }
    static final Runnable NOOP=()->{};
    static int checks;
    static void check(String name, boolean condition) {
        if (!condition) throw new AssertionError(name);
        checks++; System.out.println("PASS " + name);
    }
    static void await(CountDownLatch latch) {
        try { if(!latch.await(5,TimeUnit.SECONDS)) throw new AssertionError("latch deadline"); }
        catch(InterruptedException e) { Thread.currentThread().interrupt(); throw new RuntimeException(e); }
    }
    // Pause expiry after its read, commit payment, then resume the stale expiry write.
    static Snapshot paymentWinsSchedule(Order order) throws Exception {
        var read=new CountDownLatch(1); var resume=new CountDownLatch(1);
        var worker=Executors.newSingleThreadExecutor();
        try {
            Future<Boolean> expiry=worker.submit(()->order.expire(DEADLINE,()->{read.countDown(); await(resume);}));
            await(read); order.paid("PAY-1"); resume.countDown(); expiry.get(5,TimeUnit.SECONDS);
            return order.snapshot();
        } finally { resume.countDown(); worker.shutdownNow(); }
    }
    public static void main(String[] args) throws Exception {
        System.out.println("Java="+System.getProperty("java.version")+" OS="+System.getProperty("os.name"));
        if(args.length>0 && args[0].equals("--check-unsafe")) {
            Snapshot candidate=paymentWinsSchedule(new UnsafeOrder());
            System.out.println("unsafe candidate="+candidate);
            check("paid survives stale expiry",candidate.status()==Status.PAID && candidate.releases()==0);
            return;
        }
        Snapshot broken=paymentWinsSchedule(new UnsafeOrder());
        System.out.println("unsafe stale-expiry outcome="+broken);
        check("counterexample detected: unsafe overwrites paid",broken.status()==Status.CANCELLED && broken.releases()==1);
        Snapshot fixed=paymentWinsSchedule(new GuardedOrder());
        System.out.println("guarded same-schedule outcome="+fixed);
        check("paid survives stale expiry",fixed.status()==Status.PAID && fixed.releases()==0);
        var early=new GuardedOrder();
        check("not expired before deadline",!early.expire(DEADLINE.minusNanos(1),NOOP) && early.snapshot().status()==Status.UNPAID);
        var timeout=new GuardedOrder();
        check("expiry at exact deadline",timeout.expire(DEADLINE,NOOP) && timeout.snapshot().status()==Status.CANCELLED);
        check("duplicate timeout releases once",!timeout.expire(DEADLINE.plusSeconds(1),NOOP) && timeout.snapshot().releases()==1);
        check("late payment routes to review",timeout.paid("PAY-1").equals("RECONCILE") && timeout.snapshot().needsReview() && timeout.snapshot().status()==Status.CANCELLED);
        var paid=new GuardedOrder();
        check("ordinary payment accepted",paid.paid("PAY-1").equals("PAID") && paid.snapshot().status()==Status.PAID);
        check("same payment is a replay",paid.paid("PAY-1").equals("REPLAY") && !paid.snapshot().needsReview());
        check("paid order cannot timeout",!paid.expire(DEADLINE,NOOP) && paid.snapshot().releases()==0);
        check("different payment ID requires review",paid.paid("PAY-2").equals("RECONCILE") && paid.snapshot().needsReview() && paid.snapshot().paymentId().equals("PAY-1"));
        var invalid=new GuardedOrder();
        check("blank payment ID rejected",invalid.paid(" ").equals("INVALID_PAYMENT_ID") && invalid.snapshot().status()==Status.UNPAID);
        System.out.println(checks+" checks passed, including one detected unsafe counterexample. Not a throughput benchmark.");
    }
}
