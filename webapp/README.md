# Fenix Mini App

React + TypeScript + Vite. Messenger APIs are reached only through `src/platform/`
(Telegram today, MAX later), so components never import a messenger SDK directly.

```bash
npm install
npm run dev     # http://127.0.0.1:5173, /api is proxied to the backend on :8000
npm run lint
npm run build
```
