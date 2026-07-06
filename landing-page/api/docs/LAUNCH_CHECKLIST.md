# Launch Checklist

Use this checklist before opening Tikpan to paying users. The target rollout is small-scale commercial operation first, not full-volume launch.

## Required Gates

- [ ] `npm run check` passes.
- [ ] `npm run smoke:provider-keys` passes against the target environment.
- [ ] `/health` returns `ok`.
- [ ] `/health/readiness` returns `ready` in PostgreSQL mode.
- [ ] User-facing task responses do not expose attempts, provider keys, raw provider errors, or mapped payloads.
- [ ] `/admin/api-keys` returns 404.
- [ ] `/admin/webhook-endpoints` returns 404.
- [ ] Payment webhook signature verification is enabled.
- [ ] Payment order callbacks are idempotent.

## Infrastructure

- [ ] PostgreSQL is reachable from API and Worker hosts.
- [ ] PostgreSQL automated backup is enabled.
- [ ] Backup restore has been tested at least once.
- [ ] Object storage bucket exists and API credentials work.
- [ ] CDN/public asset base URL is configured.
- [ ] Worker process is supervised by systemd, PM2, Docker, or another process manager.
- [ ] Logs are persisted outside the process.
- [ ] Log search is available for task id, user id, provider id, provider key id, and order id.
- [ ] Server CPU, memory, disk, and network metrics are visible.
- [ ] Database connection count and slow queries are visible.

## Secrets

- [ ] `DATABASE_URL` is stored as a deployment secret.
- [ ] `TIKPAN_ADMIN_TOKEN` is set in production.
- [ ] `TIKPAN_SECRETS_ENCRYPTION_KEY` is set and backed up securely.
- [ ] Provider keys are stored as encrypted `enc:v1:` values or injected via secrets.
- [ ] Logs do not include `Authorization` headers or raw provider keys.
- [ ] Object storage secret keys are not printed in logs.

## Business Safety

- [ ] Wallet `pre_authorize`, `settle`, `release`, and `refund` are idempotent.
- [ ] Failed tasks release frozen balance.
- [ ] Canceled tasks release frozen balance.
- [ ] Refunded tasks cannot be refunded twice.
- [ ] ProviderKey lease expiry can be reclaimed.
- [ ] ProviderKey concurrency returns to 0 after smoke tests.
- [ ] User subscription concurrency limits are set deliberately.
- [ ] Initial recharge limits are conservative.

## Provider Operations

- [ ] At least one ProviderKey exists for each enabled channel.
- [ ] ProviderKey RPM and concurrency are below upstream limits.
- [ ] ProviderKey `coolingUntil` and last error are visible in admin.
- [ ] Disabled ProviderKeys are not selected.
- [ ] Degraded channels are penalized by routing.
- [ ] Channel fallback works for retryable provider errors.

## Alerts

- [ ] `alerts.json` has been reviewed for production thresholds.
- [ ] `node scripts/check-alerts.mjs` passes.
- [ ] Alert delivery channel is configured.
- [ ] Test alert has reached an operator.
- [ ] Runbooks are reachable from alert messages.
- [ ] At minimum, alerts cover provider key auth failure, consecutive provider failures, queue backlog, settlement failure, database readiness, and refund rate.

## Compliance And User Trust

- [ ] User agreement is published.
- [ ] Privacy policy is published.
- [ ] Recharge and refund rules are published.
- [ ] Content policy or content rejection messaging is published.
- [ ] Supplier terms have been checked for the planned use case.
- [ ] Manual customer support path exists for failed paid tasks.

## Go / No-Go

Do not launch if any of these are true:

- Wallet settlement or refund has unknown behavior.
- Provider keys are stored or logged in plaintext.
- Payment callback idempotency is unverified.
- Database backups are missing.
- No operator can receive alerts.
- No rollback plan exists for the current release.
