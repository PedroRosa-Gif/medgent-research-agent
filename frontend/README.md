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

Calm, minimalist "dusk" look: a deep desaturated navy canvas with a faint violet
undertone, glass surfaces, a faint blueprint grid and a very low-alpha
indigo/violet haze. Dark is the default theme; light is a soft lavender-tinted
off-white. No neon: one soft periwinkle accent and a muted lavender secondary.

Colors are semantic tokens (raw CSS variables per theme in `src/index.css`,
exposed to Tailwind as `bg-canvas`, `text-fg`, `text-accent-text`, ...). Change
values there, not in components. `npm run check:contrast` reads those variables
and verifies WCAG AA (4.5:1) for text on every surface, over the worst-case
orb backdrops, in both themes.

| Role | Token | Dark | Light |
| --- | --- | --- | --- |
| Canvas | `--canvas` | `#0c0e1b` | `#f5f6fb` |
| Surface / surface 2 | `--surface`, `--surface-2` | `#12152a` / `#1a1e38` | `#ffffff` / `#eceef8` |
| Text / muted | `--fg`, `--fg-muted` | `#e6e8f5` / `#a2a8c6` | `#14172b` / `#4a4f6b` |
| Accent (rings, dots) | `--accent` | `#8087e0` | `#6a71d6` |
| Accent text / links | `--accent-text` | `#aab0f0` | `#4349ae` |
| Filled button | `--accent-strong` | `#5a60c8` | `#4f55c4` |
| Secondary (lavender) | `--violet` | `#a99be0` | `#8a78d0` |

The brand mark (`src/components/Logo.tsx`, `public/favicon.svg`) is a thin-stroke
medical cross with one small accent dot. Keep the two in sync.

## UX features

Post-run action bar (New research / Run again / Copy report / Download `.md`), a
Stop control while running, keyboard shortcuts (`Enter` to submit, `Esc` to stop,
`/` or `Ctrl/Cmd+K` to focus the composer), example-topic chips, a collapsible
Sources panel, and a centered layout that auto-scrolls to follow the active step.
Accessibility: landmarks, visible focus, an `aria-live` region for the narration,
and full `prefers-reduced-motion` support.

> **Note:** Stop closes the `EventSource` so the UI stops listening, but the backend
> run continues in its worker thread until it finishes (see `roadmap.md`).

## SSE consumption & EventSource lifecycle

The browser-native `EventSource` only does GET, which matches
`GET /research/stream`. Because the backend frames **named** events, the hook
registers one `addEventListener` per name (`node_start`, `step`, `token`, `done`,
`error`) — `onmessage` would only catch unnamed `message` events and is
intentionally not used. `node_start` drives the per-node "thinking" line; `step`
carries the finished result that the reducer narrates.

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
