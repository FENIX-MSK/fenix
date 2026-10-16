# Review — adversarial pairs (inline)

Pairs of units that obey every AD yet diverge, and the fix applied:

1. **high** Cart vs catalog price change: one story stores prices in the cart, another recomputes — totals differ. Fix: AD-6 — cart stores only selections; price computed on every read.
2. **high** Daily order number: two concurrent checkouts both read the counter and issue #047. Fix: AD-3 — number issued atomically in the create transaction (per-location, per-business-day counter row lock).
3. **high** Notifications vs ordering: notifications cannot import ordering (dependency direction), so one story renders messages from event payload, another tries to fetch the order. Fix: AD-4 — event payload carries everything subscribers need; subscribers never call back the emitter.
4. **medium** Birthday discount vs automatic promo: one story stacks them, another picks max. Fix: AD-6 — staff-verified promo competes per item with automatic promos; one promo per item, the largest.
5. **low** Payment success retried after order already moved to `new` → conflict on transition. Covered by AD-4 idempotency; made explicit in AD-9.
