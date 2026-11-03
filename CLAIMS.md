# CLAIMS

One row per claim. Update after every leg. Never delete a row. If a claim is later refuted, change its status and explain in notes.

Status values:
- **supported**: CI of the effect excludes 0, in the predicted direction.
- **not distinguished**: CI includes 0.
- **refuted**: CI excludes 0, in the opposite direction.

| ID | Statement | Leg | Run IDs | Effect size + 95% CI | Status | Closest prior work | Notes |
|---|---|---|---|---|---|---|---|
| C0.0 | (example) Loop 4 GPQA accuracy minus loop 1, same items, per_loop | 1 | `20261103-1400_gpqa_l1`, `20261103-1800_gpqa_l4` | +2.9 pts [+0.4, +5.3] | supported | Dory card | Example row, delete when the first real claim lands |
