# Review — verified-current technology (inline)

**Verdict:** pass. Library versions come from the project lockfiles created at stage 0 (backend/uv.lock, webapp/package-lock.json); image tags for Postgres, Redis, Caddy, Prometheus, Loki, Alloy, Grafana were checked against the Docker Hub registry API on 2026-10-16 and run on the stand; Garage v2.4.1 is the newest semver tag on Docker Hub (checked 2026-10-16). MinIO intentionally absent (images no longer published).
