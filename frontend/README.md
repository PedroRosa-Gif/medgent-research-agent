# MedGent — Frontend

A single-page React UI that streams and visualizes the MedGent research agent's
reasoning in real time. One screen: enter a clinical topic, watch the agent
plan → fetch → evaluate → (self-correct) → synthesize, and read the final
report with inline citations.

## Stack & choices

- **Vite + React 19 + TypeScript** — scaffolded manually (no CRA).
- **Tailwind CSS v4** — via the first-party `@tailwindcss/vite` plugin. v4 was
  chosen because it builds cleanly with the current Vite 6 toolchain and lets
  the design tokens live in a single `@theme` block in `src/index.css` with no
  `tailwind.config.js` / PostCSS pipeline.
- **Framer Motion (`motion`)** — timeline entry animations, the active-node
  pulse, report fade-in, and the studies panel expand/collapse. Reduced-motion
  is respected via a `prefers-reduced-motion` media query in CSS.
- **react-markdown + remark-gfm** — renders the synthesized report (GFM tables,
  lists). A small custom text renderer linkifies bare URLs and bracketed PMIDs.
- **Inter** — bundled offline via `@fontsource/inter` (weights 400/500/600).
  The design's half-step weights 510/590 are mapped onto the nearest static
  faces (`.font-w510` / `.font-w590`) since the static fontsource files do not
  ship variable axes.
- **npm** as the package manager.

## Design language

Primary language is **design_v2 (Linear / Changelog)**: near-black canvas,
layered gray surfaces, 1px hairline borders (no drop shadows), Inter with
negative letter-spacing and half-step weights, pill outlined buttons. Dark mode
is the only mode.

Tokens (defined in `src/index.css` `@theme`):

| Role | Token | Value |
| --- | --- | --- |
| Canvas | `--color-onyx` | `#08090a` |
| Surface 1 | `--color-carbon` | `#141516` |
| Surface 2 | `--color-graphite` | `#1c1c1f` |
| Surface 3 / hover | `--color-smoke` | `#23252a` |
| Surface 4 / pressed | `--color-iron` | `#2d2e31` |
| Border (primary) | `--color-ash-border` | `#34343a` |
| Border (inner) | `--color-ferrite-border` | `#3e3e44` |
| Text muted / tertiary | `--color-steel-text` | `#62666d` |
| Text muted | `--color-fog-text` | `#8a8f98` |
| Text secondary | `--color-mist-text` | `#d0d6e0` |
| Text primary | `--color-snow` | `#f7f8f8` |
| **Accent (teal)** | `--color-teal` | `#2dd4bf` |
| Accent (teal soft) | `--color-teal-soft` | `#5eead4` |

**Single accent = muted clinical teal.** It is used in exactly two places: the
currently-active reasoning node (pulse) and citation links. Everything else is
monochrome. No Graphite orange, no 600/700 bold headings (510/590 half-steps),
no large radii except pills, no drop shadows for separation.

## SSE consumption & EventSource lifecycle

The browser-native `EventSource` only does GET, which matches
`GET /research/stream`. Because the backend frames **named** events, the hook
registers one `addEventListener` per name (`step`, `token`, `done`, `error`) —
`onmessage` would only catch unnamed `message` events and is intentionally not
used.

Lifecycle (in `src/lib/useResearchStream.ts`): the connection is closed on the
terminal `done` event, on an `error` event (server-sent JSON error _or_ a
transport drop with no `data`), on component unmount, and whenever a new run
starts. A double-start guard ignores a submit while a run is already live.

## Pure reducer separation (testable event logic)

- `src/lib/events.ts` — event payload types mirroring the backend contract.
- `src/lib/reasoningReducer.ts` — a pure `(state, action) => state` reducer.
  No DOM, no `EventSource`, no timers. It appends step entries, concatenates
  `token` text in arrival order, finalizes on `done`, sets error state, and
  resets. This is the only place state transitions happen.
- `src/lib/useResearchStream.ts` — the thin impure shell: owns the
  `EventSource`, parses each named event's JSON, and dispatches parsed events
  into the reducer via `useReducer`.

Tests (`src/lib/reasoningReducer.test.ts`, Vitest, offline, node env, no DOM)
cover a realistic self-correction run (plan → fetch → evaluate[insufficient] →
refine → fetch → evaluate[sufficient] → tokens → done), token concatenation
order, the empty-`done.report` fallback to streamed tokens, the `error`
transition, and `reset`. No React Testing Library / component tests (out of
scope).

## Dev proxy

`vite.config.ts` proxies `/research` (which covers `/research/stream`) and
`/health` to `http://127.0.0.1:8000` (IPv4 explicitly, since uvicorn binds
`127.0.0.1` and `localhost` may resolve to IPv6 on Windows). The browser therefore talks same-origin,
so `EventSource` needs no CORS and no cross-origin handling in dev. SSE streams
pass through because the proxy keeps the connection open and does not buffer.

## Commands

```sh
npm install      # install dependencies
npm run dev       # Vite dev server (proxies to the backend on :8000)
npm run build     # tsc -b && vite build (typecheck + production build)
npm run typecheck # tsc -b --noEmit
npm run lint      # ESLint
npm run test      # Vitest (reducer tests)
npm run preview   # preview the production build
```

## Running the full stack locally

1. Start Ollama (from the repo root): `docker compose up -d`
2. Start the API: `backend/serve.ps1` (serves on `http://localhost:8000`)
3. Start this UI: `cd frontend; npm install; npm run dev`
4. Open the Vite URL (typically `http://localhost:5173`).
