# Fenix Mini App

React + TypeScript + Vite. Messenger APIs are reached only through `src/platform/`
(Telegram today, MAX later), so components never import a messenger SDK directly.

```bash
npm install
npm run dev     # http://127.0.0.1:5173, /api is proxied to the backend on :8000
npm run lint
npm run build
npm run gen:api # regenerate src/api/schema.d.ts from the backend's OpenAPI schema (needs uv)
```

API calls go only through the typed client in `src/api/client.ts` (`api.GET('/api/health')`).
Its types in `src/api/schema.d.ts` are generated, never edited by hand; CI regenerates them and
fails if the committed file is stale, so run `npm run gen:api` after changing backend routes.
