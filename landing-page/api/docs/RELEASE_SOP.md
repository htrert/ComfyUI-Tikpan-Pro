# Commercial Release SOP

This SOP is for production releases of the internal AI workspace API. It assumes small-scale commercial rollout first, followed by gradual expansion.

## Release Stages

```text
feature branch
→ local verification
→ test environment
→ staging / pre-production
→ production canary
→ monitored rollout
→ full release
```

## 1. Prepare The Change

Record:

- Release owner.
- Release date and window.
- Summary of changes.
- Risk category.
- Database migrations.
- Feature flags or kill switches.
- Rollback plan.

Risk categories:

| Category | Examples | Required rollout |
|---|---|---|
| Normal feature | New model, UI copy, new category | Test then production |
| Core logic | ProviderKey scheduling, wallet, task state, routing | Staging and canary |
| Infrastructure | Database, Redis, storage, Worker scaling | Maintenance window |

## 2. Local Verification

Run:

```bash
npm run check
npm run smoke:provider-keys
```

If payment code changed, also verify:

```text
create order
payment callback success
duplicate callback
wrong amount callback
cancelled order callback
wallet top-up ledger
```

If ProviderKey or routing changed, verify:

```text
multiple tasks
fallback path
rate limited provider
disabled key
cooling key
admin attempts contain provider_key_id
```

## 3. Database Migration Rules

Safe migration pattern:

```text
add nullable field / table
deploy code that writes both old and new fields
verify production data
switch reads to new field
remove old field in a later release
```

Rules:

- Avoid destructive migrations in the same release as logic changes.
- Avoid long table locks during business hours.
- Back up before schema changes.
- Keep migrations backward-compatible with the previous app version whenever possible.
- Test rollback before production if the migration touches wallet, tasks, ProviderKey, or payments.

## 4. Staging Verification

Deploy to staging and verify:

- API boot.
- Worker boot.
- `/health`.
- `/health/readiness`.
- Task creation and completion.
- ProviderKey lease acquire/release.
- Wallet pre-authorize and settle.
- Failure release path.
- Admin task attempt visibility.
- Alerts can be emitted.

## 5. Production Canary

Start with one of:

```text
small user allowlist
low recharge cap
limited model catalog
limited Worker concurrency
single region / single instance
```

Canary observation window:

```text
30-60 minutes for small code changes
1-3 days for payment, wallet, ProviderKey, routing, or storage changes
```

Watch:

- Task success rate.
- Task queue depth.
- ProviderKey current concurrency.
- ProviderKey 429/401/5xx/timeout count.
- Channel success rate.
- Wallet settlement failures.
- Refund rate.
- Payment callback failures.
- Database CPU, locks, and connection count.
- Worker restarts.
- Object storage errors.

## 6. Rollout

Increase traffic only if:

- Error rate is stable.
- Refund rate is expected.
- No wallet settlement failures.
- No ProviderKey lease leakage.
- No database connection saturation.
- Support queue is manageable.

Suggested rollout:

```text
5 users
→ 20 users
→ 50 users
→ 20% traffic
→ 50% traffic
→ full traffic
```

## 7. Post-Release

After rollout:

- Record release notes.
- Record migration IDs.
- Save smoke test output.
- Review alerts after the observation window.
- Review top provider/channel errors.
- Review refund and settlement ledger.
- Update runbooks if an operator needed undocumented steps.

## Emergency Stop

Use emergency stop if:

- Duplicate billing is suspected.
- Provider keys are leaking.
- Payment callbacks are incorrectly crediting wallets.
- ProviderKey leases are not releasing.
- Database migration caused data corruption.

Immediate actions:

```text
disable affected ProviderKey or channel
pause Worker
disable recharge provider if payment is affected
preserve logs
restore previous app version
run wallet/task reconciliation
notify affected users if money or results are impacted
```
