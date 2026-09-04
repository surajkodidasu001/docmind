# DocMind frontend (React + Vite)

A real React frontend for DocMind, built to replace the Streamlit MVP once
streaming + citation highlighting needed a proper UI. Talks to the same
FastAPI backend (`/api/*`) as the Streamlit app — both can run side by side.

## What it does that Streamlit couldn't

- **Clickable citation highlighting**: `[n]` markers in the answer are
  rendered as clickable badges that scroll to and highlight the matching
  source in the sidebar, and turn red if that claim was flagged as
  possibly unsupported by the backend's citation verifier.
- **True token-by-token streaming** via the SSE endpoint, using a raw
  `fetch` + `ReadableStream` reader (not `EventSource`, since that only
  supports GET and this endpoint is a POST).
- Upload, delete, and reset documents; toggle the vision fallback for
  scanned PDFs; see computable CSV tables; per-session conversation memory;
  cache stats; full pipeline trace, all from one screen instead of
  Streamlit's rerun-per-interaction model.

## Design notes

Deliberately not the default "SaaS card kit" look — no rounded-card grid,
no gradient washes, no tracked-out ALL-CAPS labels. Citation badges and
trace data use a monospace face (footnote/manuscript-annotation feel);
headings use a serif; body text uses a plain sans-serif. Amber for
citations/medium-confidence, teal for high-confidence, rust/red for
low-confidence and flagged claims.

## Running it

```bash
npm install
cp .env.example .env   # points at your FastAPI backend
npm run dev
```

Requires the FastAPI backend running separately (`uvicorn app.main:app`
from the repo root) — this is a pure frontend, no server-side code here.

## Testing

```bash
npm test    # 16 vitest tests: citation-marker parsing, flagged-claim detection, SSE buffer parsing
npm run build   # production build — verified clean in this repo
npm run lint    # oxlint — 0 errors
```

The 16 tests cover the pieces of genuinely trip-up-able logic in this app — regex-based
citation marker parsing (multi-index citations like `[2,3]`, repeated-call safety),
flagged-claim-to-citation matching, and SSE stream buffering (events split across
chunk boundaries, partial trailing events) — all extracted into pure functions
(`src/lib/citationParser.js`, `src/lib/sseParser.js`) specifically so they could be
tested without a browser or a running backend. Two real bugs were caught and fixed
during development this way: a shared module-level regex with the `g` flag carrying
stale `lastIndex` state across renders (unsafe under React StrictMode), and an
impure render-time mutation of a loop variable that the linter correctly flagged
and that a rewrite to an immutable `reduce` fixed.

**Not verified in this sandbox**: actual browser rendering. Playwright's
browser binary couldn't be downloaded here (network-restricted sandbox),
so nothing in this README claims the UI was visually inspected — only that
it builds cleanly, lints cleanly, and its extracted logic is unit-tested.
Run `npm run dev` yourself and look at it before trusting the visual design.
