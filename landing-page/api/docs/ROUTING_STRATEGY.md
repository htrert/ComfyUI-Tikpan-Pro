# Routing Strategy

Tikpan exposes PlatformModels to users and routes them internally to ProviderModels through ModelChannels and ProviderKeys.

```text
PlatformModel
→ ModelChannel
→ ProviderModel
→ ProviderKey
→ upstream provider
```

## Route Selection Order

1. Validate user input against the PlatformModel schema.
2. List ModelChannels for the selected PlatformModel.
3. Exclude disabled channels and disabled/testing providers.
4. Validate user-provided fields against channel support and parameter mappings.
5. Score eligible channels by route mode.
6. Acquire a ProviderKey for the selected provider and provider model.
7. Call upstream.
8. On retryable failure, release/cool the key and attempt the next eligible channel.

## Route Modes

| Mode | Preference |
|---|---|
| `balanced` | Mix quality, speed, cost, and stability. |
| `quality` | Prefer primary/quality channels with higher success. |
| `fast` | Prefer lower latency channels. |
| `cheap` | Prefer lower cost channels. |
| `stable` | Prefer higher success rate and non-degraded providers. |

## Channel Health

Channel status:

| Status | Behavior |
|---|---|
| `active` | Eligible for normal routing. |
| `degraded` | Eligible with score penalty. |
| `disabled` | Excluded. |

Recommended health inputs:

```text
attempt success rate
p95 latency
provider 429/5xx rate
storage transfer failure rate
manual operator override
```

Channel health is separate from ProviderKey health. If all keys under a channel are healthy but the upstream model endpoint fails, mark the channel degraded or disabled.

## ProviderKey Selection

ProviderKey selection filters by:

```text
provider_id
provider_model_id support
status active/degraded
cooling_until
current_concurrency < concurrency
RPM window
TPM window
priority
weight
```

PostgreSQL mode uses row locks and leases for MVP to small production. High-throughput deployments should move RPM/TPM windows to Redis Lua or Redis Cell while preserving the same repository interface.

## Parameter Capability Validation

Every channel must declare which PlatformModel fields it can carry:

```text
PlatformModel schema
→ ProviderModel raw capabilities
→ ModelChannel supports
→ ChannelParameterMapping
→ mapped upstream payload
```

Rules:

- Required platform fields must have a mapping or be directly supported.
- Optional user-provided fields must either be mapped or explicitly rejected.
- `omit` is allowed only for fields that are not user intent or are documented as unsupported.
- Silent dropping of user-provided fields should be treated as a validation error.
- Admin channel creation may infer `supports` from ProviderModel capabilities, but operators should review it before enabling the channel.

Suggested capability flags:

```text
supports_seed
supports_negative_prompt
supports_reference_image
supports_cfg_scale
supports_duration
supports_resolution
supports_mask
supports_stream
supports_async_poll
```

## Fallback Policy

Fallback is allowed when:

- Provider timeout, rate limit, network error, 5xx, or provider async failure occurs.
- The next channel supports the user-requested parameters.
- The next channel has an available ProviderKey.

Fallback is not allowed when:

- User input is invalid.
- Content is rejected by policy.
- The failure is caused by a missing required field.
- All remaining channels would silently drop user-provided parameters.

## Admin Operations

Keep high-risk operations explicit and audited:

```text
disable ProviderKey
clear ProviderKey cooldown
adjust ProviderKey limits
adjust channel priority/weight
adjust model/channel pricing
disable/degrade channel
manual refund
manual task state correction
```
