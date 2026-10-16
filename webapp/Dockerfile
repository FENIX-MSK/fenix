# syntax=docker/dockerfile:1.7
# Build context: repository root (needs infra/caddy/Caddyfile).
FROM node:22-alpine AS build
WORKDIR /app
COPY webapp/package.json webapp/package-lock.json ./
RUN npm ci
COPY webapp/ ./
RUN npm run build

FROM caddy:2.10-alpine
COPY infra/caddy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
