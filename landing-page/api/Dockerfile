# syntax=docker/dockerfile:1.7

FROM node:24.16.0-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

FROM node:24.16.0-slim AS runtime
ENV NODE_ENV=production
WORKDIR /app

RUN groupadd --system tikpan && useradd --system --gid tikpan --home-dir /app tikpan

COPY --from=deps /app/node_modules ./node_modules
COPY package.json package-lock.json ./
COPY src ./src
COPY scripts ./scripts
COPY db ./db
COPY alerts.json ./alerts.json

USER tikpan
EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:' + (process.env.PORT || 8787) + '/health').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"

CMD ["node", "src/server.mjs"]
