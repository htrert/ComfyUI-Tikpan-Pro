# Failure Handling

This document defines how the platform handles provider, task, wallet, and storage failures. User-facing responses must stay friendly; raw provider details belong in admin logs and task attempts.

## Public Error Contract

Users should see product-level messages:

| Scenario | Public message |
|---|---|
| Provider timeout | 当前服务繁忙，冻结额度已释放，请稍后重试。 |
| Provider rate limited | 当前服务繁忙，已自动切换或释放额度，请稍后重试。 |
| Invalid input | 输入内容不符合当前模型要求，请调整后再试。 |
| Content rejected | 内容未通过安全检查，请修改提示词后再试。 |
| No route available | 当前能力暂时不可用，请稍后再试或切换其他能力。 |
| Storage failure | 结果整理失败，冻结额度已释放，请稍后重试。 |

Do not expose upstream HTTP status, provider key identifiers, raw payloads, Authorization headers, stack traces, or provider account messages to users.

## Provider Error Policy

| Error code | Retry | Fallback channel | Cool ProviderKey | Suggested cooldown | Refund/release |
|---|---:|---:|---:|---:|---:|
| `PROVIDER_RATE_LIMITED` | yes | yes | yes | 60s | release if all attempts fail |
| `PROVIDER_AUTH_FAILED` | no | yes | yes | 10m or disable | release |
| `PROVIDER_5XX` | yes | yes | yes | 15s | release if all attempts fail |
| `PROVIDER_TIMEOUT` | yes | yes | yes after failure | 15s | release if all attempts fail |
| `PROVIDER_NETWORK_ERROR` | yes | yes | optional | 15s | release if all attempts fail |
| `PROVIDER_TASK_FAILED` | no | yes | optional | 15s | release if all attempts fail |
| `VALIDATION_ERROR` | no | no | no | none | no task or release |
| `INVALID_IMAGE_INPUT` | no | no | no | none | no task or release |
| `CONTENT_REJECTED` | no | no | no | none | release |
| `PROVIDER_KEY_EXHAUSTED` | no | yes | no | none | remain queued or release by timeout policy |

## Wallet Failure Policy

Rules:

- If pre-authorization fails, the task must not be queued.
- If task creation fails after pre-authorization, release must be attempted with the same `taskId`.
- If settlement fails after provider success, the task must remain non-terminal or enter an operator-visible compensation state. Do not mark it succeeded until settlement is durable.
- If release fails after provider failure, the task must remain operator-visible and retry release idempotently.
- Duplicate Worker execution must not duplicate `settle`, `release`, or `refund`.

## ProviderKey Lease Failure Policy

Rules:

- A Worker must release ProviderKey leases in success and failure paths.
- Expired leases are reclaimed by repository cleanup and should also be scanned by a scheduled maintenance job.
- Reclaimed leases set `PROVIDER_KEY_LEASE_EXPIRED` in ProviderKey metrics.
- A reclaimed lease should not directly mark a task failed; task recovery is handled by task lock expiry and queue retry/timeout policy.

## Storage Failure Policy

Rules:

- User uploads should go directly to object storage when possible.
- Provider output should be copied to object storage before the task is public-succeeded.
- If output transfer fails, keep raw provider output in admin attempt logs only when it contains no secrets.
- Media archive metadata must include object key, content type, size, checksum when available, and retention class.

## Alert Triggers

Alert when:

- ProviderKey consecutive failures reach threshold.
- Channel success rate drops below threshold.
- Queue depth exceeds threshold.
- Refund/release rate spikes.
- Settlement failures occur.
- Database readiness fails.
- Expired ProviderKey leases are reclaimed.
