/**
 * SSE event payload types — a 1:1 mirror of the backend contract in
 * `backend/src/medgent/adapters/driving/api/app.py`.
 *
 * The server frames four named SSE events. `EventSource` dispatches them by
 * name (`step`/`token`/`done`/`error`) via `addEventListener`, and the hook in
 * `useResearchStream.ts` parses each event's JSON `data` into one of these
 * shapes before handing it to the pure reducer.
 *
 * Nothing in here touches the DOM or the network — these are plain data types,
 * so both the hook and the reducer tests can import them freely.
 */

/** Graph nodes that can emit a `step` event, in loop order. */
export type NodeName =
  | 'planner'
  | 'fetch_evidence'
  | 'evaluator'
  | 'refine_queries'
  | 'synthesizer';

/** One evaluated study as projected by the backend's `StudySummary`. */
export interface StudySummary {
  identifier: string;
  study_type: string;
  quality_score: number;
}

/**
 * `data` of a `step` event. `data` mirrors the graph state update for that
 * node, so its concrete keys depend on `node`; we keep it loosely typed and
 * read individual fields defensively in the reducer.
 */
export interface StepEvent {
  node: NodeName;
  summary: string;
  keys: string[];
  data: StepData;
}

/** Loosely-typed node update. Only the fields the UI reads are named. */
export interface StepData {
  queries?: string[];
  evidence?: unknown[];
  evaluated_studies?: StudySummary[];
  is_sufficient?: boolean;
  iteration?: number;
  final_report?: string;
  [key: string]: unknown;
}

/** `data` of a `token` event — one chunk of the synthesized report. */
export interface TokenEvent {
  node: 'synthesizer';
  text: string;
}

/** `data` of the terminal `done` event. */
export interface DoneEvent {
  topic: string;
  report: string;
  iterations: number;
  studies: StudySummary[];
}

/** `data` of an `error` event. */
export interface ErrorEvent {
  error: string;
  detail: string;
}

/**
 * A parsed SSE event tagged by its event name. The hook produces these from the
 * raw `MessageEvent`s; the reducer consumes them. This discriminated union is
 * the single contract between the (impure) hook and the (pure) reducer.
 */
export type ResearchEvent =
  | { kind: 'step'; payload: StepEvent }
  | { kind: 'token'; payload: TokenEvent }
  | { kind: 'done'; payload: DoneEvent }
  | { kind: 'error'; payload: ErrorEvent };
