# State Machines

This document is the operational contract for task, wallet, ProviderKey, and channel states. Code changes that touch these states should update this file in the same pull request.

## Task

Public task states are intentionally small:

```text
created -> queued -> running -> succeeded
                         -> failed
                         -> canceled
                         -> refunded
```

Current API compatibility maps implementation states as follows:

| Internal state | Public state | Meaning |
|---|---|---|
| `queued` | `queued` | Task is accepted and waiting for a Worker. |
| `running` | `running` | Worker has started upstream execution. |
| `saving_media` | `running` | Result is being transferred or archived. |
| `completed` | `succeeded` | Generation succeeded and wallet settlement is done. |
| `failed` | `failed` | Generation failed and frozen balance is released. |
| `cancelled` | `canceled` | User or operator canceled the task and frozen balance is released. |
| `expired` | `failed` | Task exceeded its allowed lifetime and must be released. |

Rules:

- A task must not enter `queued` unless wallet pre-authorization succeeded.
- A task must not enter `succeeded` unless output persistence and wallet settlement both succeed.
- A task must not enter `failed` or `canceled` unless frozen balance release is attempted idempotently.
- Terminal states are `succeeded`, `failed`, `canceled`, and `refunded`; Workers must not execute terminal tasks.
- Retries create a new task. They do not mutate a terminal task back to `queued`.

## Wallet

Wallet state is represented by ledger entries, not by a large status enum:

```text
pre_authorized -> settled
               -> released
settled        -> refunded
```

Rules:

- `pre_authorize` reserves funds before a task can be queued.
- `settle` consumes frozen funds after a successful task.
- `release` returns frozen funds after failure, cancellation, or expiry.
- `refund` returns already settled funds after an operator-approved refund.
- The same task can have at most one ledger entry for each of `pre_authorize`, `settle`, `release`, and `refund`.
- Wallet mutations must run under a database transaction in PostgreSQL mode.

## ProviderKey

ProviderKey runtime state is derived from status, lease, and cooldown fields:

```text
available -> leased -> available
leased -> cooling -> available
available -> disabled
cooling -> disabled
```

Definitions:

| Derived state | Condition |
|---|---|
| `available` | `status=active`, not cooling, not over RPM/TPM, and `currentConcurrency < concurrency`. |
| `leased` | At least one active lease exists and has not expired. |
| `cooling` | `coolingUntil` is in the future. |
| `disabled` | `status=disabled`. |
| `exhausted` | Active, not cooling, but concurrency or RPM/TPM is exhausted. |

Rules:

- Key acquisition must be atomic.
- Every key acquisition creates a lease with `leaseId` and `expiresAt`.
- Successful completion releases the lease and records success metrics.
- Retryable provider failures release the lease, record failure metrics, and may set `coolingUntil`.
- User input errors and content rejections must not cool down the key.
- Expired leases must be reclaimable without the original Worker.

## ModelChannel

ModelChannel state represents route health before selecting a ProviderKey:

```text
healthy -> degraded -> disabled
```

Current compatibility maps:

| Channel status | Route behavior |
|---|---|
| `active` | Eligible for routing. |
| `degraded` | Eligible with score penalty and reduced retry budget. |
| `disabled` | Not eligible. |

Rules:

- Routing excludes disabled channels before ProviderKey selection.
- Degraded channels may be used when no healthier route scores better.
- A channel can be unhealthy even if individual ProviderKeys are available.
- Channel health should aggregate task attempt success rate, latency, and upstream error rate.
