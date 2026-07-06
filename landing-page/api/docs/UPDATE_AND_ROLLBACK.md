# Update And Rollback Guide

This guide defines how future changes should be shipped and reverted.

## Branch Model

Recommended:

```text
main      = production-ready
dev       = integration branch
feature/* = feature work
hotfix/*  = urgent production fixes
```

Rules:

- Do not develop directly on production.
- Keep risky changes isolated in feature branches.
- Merge core logic changes only after smoke tests pass.
- Keep release notes for every production deployment.

## Change Types

### 1. Normal Feature

Examples:

- New model.
- New category.
- New admin statistic.
- Minor UI/API field addition.

Process:

```text
feature branch
→ npm run check
→ staging
→ production
```

Rollback:

```text
revert application version
disable new model/channel if needed
```

### 2. Core Logic

Examples:

- ProviderKey scheduling.
- Wallet settlement.
- Task state machine.
- Routing strategy.
- Error mapping.
- Refund behavior.

Process:

```text
feature branch
→ unit/smoke tests
→ staging
→ production canary
→ observe
→ gradual rollout
```

Required checks:

- Duplicate Worker execution is idempotent.
- Failed task releases frozen funds.
- Succeeded task settles exactly once.
- Refunded task refunds exactly once.
- ProviderKey lease expires and reclaims.
- User-facing errors do not leak provider internals.

Rollback:

```text
pause Worker
disable affected ProviderKey/channel
restore previous app version
run task reconciliation
run wallet ledger reconciliation
resume Worker after consistency check
```

### 3. Infrastructure

Examples:

- PostgreSQL migration.
- Redis introduction.
- Object storage migration.
- Worker scaling.
- Queue engine replacement.

Process:

```text
maintenance window
→ backup
→ staged migration
→ smoke test
→ canary Worker
→ monitor
→ expand
```

Rollback:

```text
stop writes if data consistency is at risk
restore previous infrastructure config
restore app version
restore database backup only if forward repair is unsafe
```

## Migration Compatibility

Use expand/contract:

```text
expand schema
deploy compatible writer
backfill data
switch readers
wait one release
contract old schema
```

Avoid:

- Dropping columns used by the current or previous app version.
- Renaming columns without compatibility views or dual reads.
- Combining destructive migration and major code changes.
- Changing wallet/task semantics without reconciliation scripts.

## Rollback Decision Tree

Rollback immediately when:

- Money movement is wrong.
- Provider keys are exposed.
- Payment callback idempotency fails.
- Tasks are being marked succeeded without stored results.
- Database errors affect writes.

Prefer feature disable over full rollback when:

- Only one ProviderKey is failing.
- Only one channel is degraded.
- Only one model has incorrect parameters.
- Only one payment provider is failing and can be disabled.

Prefer forward fix when:

- A migration has already written valid data in a new format.
- Rollback would lose user results.
- The issue is a display or admin-only bug.

## Reconciliation

After rollback or incident, reconcile:

```text
tasks in running/queued for too long
tasks succeeded without settle
tasks failed/canceled without release
wallet ledger duplicate attempts
provider key leases unreleased past expiresAt
payment orders paid but wallet not topped up
media assets missing for succeeded tasks
```

## Kill Switches

Operational kill switches should exist for:

```text
Worker enabled/disabled
ProviderKey enabled/disabled
ModelChannel active/degraded/disabled
PlatformModel visible/hidden
PaymentProvider active/testing/disabled
```

## Release Notes Template

```text
Version:
Date:
Owner:
Risk category:
Changes:
Migrations:
Validation:
Canary scope:
Rollback plan:
Post-release observations:
```
