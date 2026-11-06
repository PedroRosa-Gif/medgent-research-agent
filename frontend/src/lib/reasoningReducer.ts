/**
 * Pure state machine for the reasoning UI.
 *
 * `reasoningReducer(state, action) => state` is the single source of truth for
 * how the UI evolves as SSE events arrive. It is deliberately free of any DOM,
 * `EventSource`, timers, or other side effects so it can be unit-tested offline
 * (see `reasoningReducer.test.ts`). The thin hook `useResearchStream` owns the
 * network; this module only owns the transitions.
 *
 * Design intent per node (what the timeline renders from each step):
 *   - planner        → the planned queries
 *   - fetch_evidence → how many papers were fetched
 *   - evaluator      → iteration #, study count, sufficiency (drives the loop)
 *   - refine_queries → the refreshed queries for the next iteration
 *   - synthesizer    → marks the report is being written
 */

import type {
  DoneEvent,
  ErrorEvent,
  NodeName,
  ResearchEvent,
  StepData,
  StudySummary,
} from './events';

/** Lifecycle status of a single research run. */
export type RunStatus = 'idle' | 'running' | 'done' | 'error';

/**
 * One rendered entry on the reasoning timeline. Built from a `step` event; the
 * `detail` fields are pre-extracted from the node update so the view stays dumb.
 */
export interface StepEntry {
  /** Monotonic id for stable React keys (reducer-assigned, never from the server). */
  id: number;
  node: NodeName;
  summary: string;
  queries?: string[];
  paperCount?: number;
  studyCount?: number;
  iteration?: number;
  isSufficient?: boolean;
}

/** The complete UI state. */
export interface ReasoningState {
  status: RunStatus;
  topic: string;
  steps: StepEntry[];
  /** The report text, concatenated from `token` events (and finalized on done). */
  reportText: string;
  studies: StudySummary[];
  iterations: number;
  /** The node whose step arrived most recently — rendered with the active pulse. */
  activeNode: NodeName | null;
  error?: { name: string; detail: string };
  /** Internal counter for assigning `StepEntry.id`s. */
  nextStepId: number;
}

/**
 * Actions the hook dispatches. `start` is a UI-originated action (user hit
 * Research); `event` wraps a parsed SSE event; `reset` returns to idle.
 */
export type ReasoningAction =
  | { type: 'start'; topic: string }
  | { type: 'event'; event: ResearchEvent }
  | { type: 'reset' };

/** The pristine state, reused by `reset` and as the `useReducer` initializer. */
export function initialState(): ReasoningState {
  return {
    status: 'idle',
    topic: '',
    steps: [],
    reportText: '',
    studies: [],
    iterations: 0,
    activeNode: null,
    nextStepId: 0,
  };
}

/** Freshly-running state for `topic`, preserving the monotonic id counter. */
function runningState(topic: string, nextStepId: number): ReasoningState {
  return {
    ...initialState(),
    status: 'running',
    topic,
    nextStepId,
  };
}

/** Pull the renderable detail fields out of a node update. */
function entryFromStep(
  id: number,
  node: NodeName,
  summary: string,
  data: StepData,
): StepEntry {
  const entry: StepEntry = { id, node, summary };
  switch (node) {
    case 'planner':
    case 'refine_queries':
      entry.queries = data.queries ?? [];
      break;
    case 'fetch_evidence':
      entry.paperCount = data.evidence?.length ?? 0;
      break;
    case 'evaluator':
      entry.studyCount = data.evaluated_studies?.length ?? 0;
      entry.iteration = data.iteration;
      entry.isSufficient = data.is_sufficient;
      break;
    case 'synthesizer':
      break;
  }
  return entry;
}

function onDone(state: ReasoningState, payload: DoneEvent): ReasoningState {
  return {
    ...state,
    status: 'done',
    activeNode: null,
    // Prefer the authoritative report from the done event; fall back to the
    // text streamed via tokens if the server sent an empty final report.
    reportText: payload.report || state.reportText,
    studies: payload.studies,
    iterations: payload.iterations,
  };
}

function onError(state: ReasoningState, payload: ErrorEvent): ReasoningState {
  return {
    ...state,
    status: 'error',
    activeNode: null,
    error: { name: payload.error, detail: payload.detail },
  };
}

/** Apply one parsed SSE event to the state. */
function onEvent(state: ReasoningState, event: ResearchEvent): ReasoningState {
  switch (event.kind) {
    case 'step': {
      const { node, summary, data } = event.payload;
      const entry = entryFromStep(state.nextStepId, node, summary, data);
      const iterations =
        node === 'evaluator' && typeof data.iteration === 'number'
          ? data.iteration
          : state.iterations;
      return {
        ...state,
        steps: [...state.steps, entry],
        activeNode: node,
        iterations,
        nextStepId: state.nextStepId + 1,
      };
    }
    case 'token':
      // Append in arrival order so the report "types out" exactly as streamed.
      return { ...state, reportText: state.reportText + event.payload.text };
    case 'done':
      return onDone(state, event.payload);
    case 'error':
      return onError(state, event.payload);
  }
}

/** The pure reducer: `(state, action) => nextState`. */
export function reasoningReducer(
  state: ReasoningState,
  action: ReasoningAction,
): ReasoningState {
  switch (action.type) {
    case 'start':
      return runningState(action.topic, state.nextStepId);
    case 'reset':
      return { ...initialState(), nextStepId: state.nextStepId };
    case 'event':
      return onEvent(state, action.event);
  }
}
