# Docker Release Guide

Use this guide when shipping the Tikpan API with Docker or Docker Compose. The recommended production path is immutable image release, not editing source files on the server.

## Release Flow

```text
local code change
→ local tests
→ build versioned image
→ push image registry
→ server pulls image
→ run migrations
→ restart API / Worker
→ verify production
→ keep previous image for rollback
```

## Image Tagging

Prefer versioned tags:

```text
registry.example.com/tikpan/api:2026.07.05-1
registry.example.com/tikpan/api:v1.2.3
registry.example.com/tikpan/api:git-abcdef1
```

Avoid relying on `latest` for production because it makes rollback and audit harder.

## Local Build

From `landing-page/api`:

```bash
npm run check
docker build -t registry.example.com/tikpan/api:2026.07.05-1 .
```

Optional local run:

```bash
docker run --rm -p 8787:8787 \
  -e TIKPAN_STORE=memory \
  -e TIKPAN_PROVIDER_ADAPTER=mock \
  registry.example.com/tikpan/api:2026.07.05-1
```

Verify:

```bash
curl http://localhost:8787/health
```

## Push Image

```bash
docker push registry.example.com/tikpan/api:2026.07.05-1
```

Record the pushed image tag in release notes.

## Server Environment

Create a production `.env` beside `docker-compose.prod.yml`:

```text
TIKPAN_API_IMAGE=registry.example.com/tikpan/api:2026.07.05-1
TIKPAN_API_PORT=8787

POSTGRES_DB=tikpan
POSTGRES_USER=tikpan
POSTGRES_PASSWORD=replace-me

TIKPAN_ADMIN_TOKEN=replace-me
TIKPAN_SECRETS_ENCRYPTION_KEY=replace-me
TIKPAN_PROVIDER_ADAPTER=http
TIKPAN_PROVIDER_SECRETS={"pkey-cangyuan-main":"sk-..."}

TIKPAN_STORAGE_ADAPTER=s3
OBJECT_STORAGE_ENDPOINT=https://...
OBJECT_STORAGE_BUCKET=tikpan-assets
OBJECT_STORAGE_ACCESS_KEY_ID=...
OBJECT_STORAGE_SECRET_ACCESS_KEY=...
OBJECT_STORAGE_REGION=auto
OBJECT_STORAGE_FORCE_PATH_STYLE=true
CDN_PUBLIC_BASE_URL=https://cdn.example.com
```

Do not commit this `.env`.

## First Deploy

Copy the example compose file:

```bash
cp docker-compose.prod.example.yml docker-compose.prod.yml
```

Start database first:

```bash
docker compose -f docker-compose.prod.yml up -d postgres
docker compose -f docker-compose.prod.yml ps
```

Apply database migrations with your migration runner or psql process. If using raw SQL files, run them in order against the target database before starting API/Worker.

Start services:

```bash
docker compose -f docker-compose.prod.yml pull api worker
docker compose -f docker-compose.prod.yml up -d api worker
```

Verify:

```bash
curl http://localhost:8787/health
curl http://localhost:8787/health/readiness
npm run smoke:provider-keys
```

For remote smoke tests:

```bash
TIKPAN_API_BASE_URL=https://api.example.com npm run smoke:provider-keys
```

## Normal Update

On the server:

```bash
export NEW_IMAGE=registry.example.com/tikpan/api:2026.07.05-2
cp .env .env.backup.$(date +%Y%m%d%H%M%S)
sed -i "s#^TIKPAN_API_IMAGE=.*#TIKPAN_API_IMAGE=$NEW_IMAGE#" .env
docker compose -f docker-compose.prod.yml pull api worker
docker compose -f docker-compose.prod.yml up -d api worker
docker compose -f docker-compose.prod.yml ps
```

Verify:

```bash
curl http://localhost:8787/health/readiness
TIKPAN_API_BASE_URL=https://api.example.com npm run smoke:provider-keys
```

Observe for 30-60 minutes:

```text
task success rate
queue depth
wallet settlement failures
refund rate
ProviderKey failures
ProviderKey current concurrency
database connections
worker restarts
```

## Updating With Database Migrations

Safe order:

```text
backup database
apply backward-compatible migration
deploy new image
run smoke tests
observe
```

Avoid destructive migrations in the same release as business logic changes.

## Rollback

Set the previous image tag:

```bash
export PREVIOUS_IMAGE=registry.example.com/tikpan/api:2026.07.05-1
sed -i "s#^TIKPAN_API_IMAGE=.*#TIKPAN_API_IMAGE=$PREVIOUS_IMAGE#" .env
docker compose -f docker-compose.prod.yml pull api worker
docker compose -f docker-compose.prod.yml up -d api worker
```

Verify:

```bash
curl http://localhost:8787/health/readiness
TIKPAN_API_BASE_URL=https://api.example.com npm run smoke:provider-keys
```

If database migration is not backward-compatible, stop and follow `docs/UPDATE_AND_ROLLBACK.md` before reverting the app image.

## Emergency Operations

Pause Worker:

```bash
docker compose -f docker-compose.prod.yml stop worker
```

Resume Worker:

```bash
docker compose -f docker-compose.prod.yml up -d worker
```

Restart API:

```bash
docker compose -f docker-compose.prod.yml restart api
```

View logs:

```bash
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f worker
```

Disable a broken route through admin:

```text
set ProviderKey status disabled
or set ModelChannel status disabled
```

Then confirm no new attempts use the disabled resource.
