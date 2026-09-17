# Pramaan — web app

The product front end: Next.js 16 (App Router), Tailwind CSS 4, TypeScript. It is a thin
client of the FastAPI service in `src/analyst/api.py` — every answer, citation and trace
comes from that API.

| Route | What it is |
|---|---|
| `/` | Product page. Its answer cards are real API responses saved in `lib/showcase.json`. |
| `/analyst` | The workspace. `?q=` makes each answer a shareable link. |
| `/coverage` | Indexed companies and filing years, live from `/api/v1/companies`. |
| `/methodology` | Pipeline, decisions, measured results, limitations. |
| `/api/*` | Server-side proxy to FastAPI (`lib/api.ts`). |

**Why a proxy:** the browser only talks to this app, so the API needs no CORS and its
address (`API_URL`, server-only) never reaches the client bundle.

## Run

```bash
npm install
npm run dev -- -p 3300      # needs the API on :8400 (or set API_URL)
```

In Docker, `docker compose up -d` from the repo root builds this image (`Dockerfile`,
standalone output) and serves it on http://localhost:3300.

| Env | Default | Used for |
|---|---|---|
| `API_URL` | `http://localhost:8400` | where the proxy sends requests (compose: `http://api:8400`) |
| `SITE_URL` | `http://localhost:3300` | absolute URLs in share cards (read at build time: `/` is static) |

## Where things live

- `app/` — pages, route handlers, the share image (`opengraph-image.tsx`) and icon.
- `components/answer/` — the answer card, evidence, source drawer and pipeline trace.
- `lib/` — API types (mirroring the Python models), measured metrics, demo questions,
  and the product name (`site.ts`).
