# Tikpan AI Commercial Flow Acceptance

This project is no longer a static landing page. It is a commercial AI aggregation workbench with separate user, developer, and admin layers.

## User Layer

- Users see platform capabilities, not upstream providers.
- Public navigation includes:
  - `创作工作台`
  - `探索广场`
  - `控制台 / API`
  - account access through the wallet pill or avatar.
- The workspace left sidebar groups platform models by capability.
- The main workspace shows model value, use cases, prompt input, stable parameters, advanced parameters, smart routing, token estimate, task status, and saved results.
- Public task and quote responses must not expose `provider`, `provider_model`, `mapped_payload`, `attempts`, `worker`, or `internal`.
- User-facing billing uses `Tokens`.

## Developer Layer

- The developer console exposes only platform API concepts:
  - platform model ID
  - `POST /v1/tasks`
  - request body
  - task status object
  - Tokens usage
- It does not expose upstream provider names or upstream model names.

## Admin Layer

- `/admin` is a separate gated surface.
- Admin can configure:
  - platform models
  - schema fields shown to users
  - providers
  - provider models
  - model channels
  - channel parameter mappings
  - billing plans, payment providers, user subscriptions, wallets, API keys
- Admin can run route preview and channel tests, including mapped payload inspection.
- Admin monitoring exposes attempts, worker status, selected provider, upstream model, costs, revenue, refunds, and audit events.

## Backend Routing

The task dispatch flow is:

1. Validate platform model and platform schema.
2. Load enabled channels for the selected platform model.
3. Filter channels by actively selected user parameters.
4. Reject channels when a user-selected parameter would be omitted or replaced by a fixed default.
5. Score compatible channels by routing mode: balanced, quality, fast, cheap, stable.
6. Map platform parameters into upstream payload.
7. Pre-authorize Tokens.
8. Queue and process the task.
9. Settle on success or release frozen Tokens on failure/cancel.

Unsupported advanced parameters must block or reroute the task. They must not be silently dropped.

## Upstream API Integration

The backend has two provider adapter modes:

- `mock`: local verification mode, returns deterministic generated output links.
- `http`: sends mapped payloads to the configured provider `baseUrl`.

In HTTP mode, each provider uses its configured auth type:

- `bearer`: sends `Authorization: Bearer <secret>`.
- `custom_header`: sends `X-API-Key: <secret>`.

Provider secrets should be supplied through runtime configuration, not exposed to users. Users only use Tikpan platform API keys and Tokens.

## Verification Commands

Run these from `landing-page`:

```powershell
npm.cmd run build
```

Run these from `landing-page/api`:

```powershell
npm.cmd run check
npm.cmd run e2e:commercial
```

The commercial e2e script verifies:

- user registration
- payment order creation and confirmation
- quote sanitization
- task creation
- task polling to completion
- wallet pre-authorization and settlement
- incompatible advanced parameter blocking
- admin route preview with provider and mapped payload

## Local URLs

- Frontend: `http://127.0.0.1:5173`
- API: `http://127.0.0.1:8787`
