/**
 * Pure state machine for the reasoning UI.
 *
 * `reasoningReducer(state, action) => state` is the single source of truth for
 * how the UI evolves as SSE events arrive. It is deliberately free of any DOM,
 * `EventSource`, timers, clocks, or other side effects so it can be unit-tested
 * offline (see `reasoningReducer.test.ts`). The thin hook `useResearchStream`
 * owns the network and the clock; this module only owns the transitions.
 *
 * Time: the reducer never reads the clock. The hook stamps actions with an
 * optional `at` (epoch ms); when present, the state records run/step timings so
 * the UI can show elapsed time and per-step durations.
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

/**
 * Lifecycle status of a single research run. `cancelled` means the user pressed
 * Stop: the UI stopped listening, and any partial timeline/report is kept.
 */
export type RunStatus = 'idle' | 'running' | 'done' | 'error' | 'cancelled';

/** Status of one timeline entry: a node is `thinking` until its step arrives. */
export type StepStatus = 'thinking' | 'done';

/**
 * The agent-style "thinking" line shown while a node is running, before it has
 * produced output. One per node; the self-correction loop reuses the same label
 * each time a node runs again.
 */
export const THINKING_LABELS: Record<NodeName, string> = {
  planner: 'Planning the search strategy…',
  fetch_evidence: 'Searching PubMed and the web…',
  evaluator: 'Appraising study quality…',
  refine_queries: 'Refining the queries…',
  synthesizer: 'Writing the report…',
};

/**
 * One rendered entry on the reasoning timeline. A `node_start` event pushes an
 * entry in the `thinking` status (just a node + its thinking label); the
 * matching `step` event flips it to `done` and fills the narration fields below,
 * pre-extracted from the node update so the view stays dumb.
 *
 * If the run ends (error / cancel) while an entry is still `thinking`, the
 * entry is left as-is; the view renders it as interrupted because the run
 * status is no longer `running`.
 */
export interface StepEntry {
  /** Monotonic id for stable React keys (reducer-assigned, never from the server). */
  id: number;
  node: NodeName;
  /** `thinking` while the node runs; `done` once its step arrives. */
  status: StepStatus;
  /** The "thinking" line shown while `status === 'thinking'`. */
  thinkingLabel: string;
  /** Human narration of the finished step (filled on `done`). */
  narration?: string;
  summary?: string;
  queries?: string[];
  paperCount?: number;
  studyCount?: number;
  passingCount?: number;
  iteration?: number;
  isSufficient?: boolean;
  /** Epoch ms when the node started (only if the action carried `at`). */
  startedAt?: number;
  /** How long the node took, once done (needs both a start and a step `at`). */
  durationMs?: number;
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
  /** Epoch ms when the run started (from the `start` action's `at`). */
  startedAt?: number;
  /** Epoch ms when the run ended: done, error, or cancelled. */
  endedAt?: number;
  /** Internal counter for assigning `StepEntry.id`s. */
  nextStepId: number;
}

/**
 * Actions the hook dispatches. `start` is a UI-originated action (user hit
 * Research); `event` wraps a parsed SSE event; `cancel` is the user pressing
 * Stop; `reset` returns to idle. `at` is the caller's clock reading (epoch ms).
 */
export type ReasoningAction =
  | { type: 'start'; topic: string; at?: number }
  | { type: 'event'; event: ResearchEvent; at?: number }
  | { type: 'cancel'; at?: number }
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
function runningState(topic: string, nextStepId: number, at?: number): ReasoningState {
  return {
    ...initialState(),
    status: 'running',
    topic,
    startedAt: at,
    nextStepId,
  };
}

/** Pluralize a count: `n thing(s)`. */
function plural(count: number, singular: string, pluralForm?: string): string {
  return `${count} ${count === 1 ? singular : (pluralForm ?? `${singular}s`)}`;
}

/** Count how many evaluated studies cleared the quality bar. */
function countPassing(studies: StudySummary[], threshold = 0.6): number {
  return studies.filter((s) => s.quality_score >= threshold).length;
}

/**
 * A fresh `thinking` entry for a node that just started. The narration fields
 * are left unset until the matching `step` flips it to `done`.
 */
function startEntry(id: number, node: NodeName, at?: number): StepEntry {
  return {
    id,
    node,
    status: 'thinking',
    thinkingLabel: THINKING_LABELS[node],
    startedAt: at,
  };
}

/**
 * Flip a `thinking` entry to `done`, extracting the renderable detail fields and
 * composing the rich, human narration for that node (never raw JSON).
 */
function finishEntry(
  entry: StepEntry,
  summary: string,
  data: StepData,
  at?: number,
): StepEntry {
  const next: StepEntry = { ...entry, status: 'done', summary };
  if (at !== undefined && entry.startedAt !== undefined) {
    next.durationMs = Math.max(0, at - entry.startedAt);
  }
  switch (entry.node) {
    case 'planner': {
      const queries = data.queries ?? [];
      next.queries = queries;
      next.narration = `Broke the topic into ${plural(queries.length, 'line')} of inquiry:`;
      break;
    }
    case 'refine_queries': {
      const queries = data.queries ?? [];
      next.queries = queries;
      next.narration = `Refined into ${plural(queries.length, 'new query', 'new queries')}:`;
      break;
    }
    case 'fetch_evidence': {
      const count = data.evidence?.length ?? 0;
      next.paperCount = count;
      next.narration = `Found ${plural(count, 'study', 'studies')} across PubMed and the web.`;
      break;
    }
    case 'evaluator': {
      const studies = data.evaluated_studies ?? [];
      const passing = countPassing(studies);
      next.studyCount = studies.length;
      next.passingCount = passing;
      next.iteration = data.iteration;
      next.isSufficient = data.is_sufficient;
      const verdict = data.is_sufficient
        ? 'Evidence sufficient.'
        : 'Evidence insufficient, continuing.';
      next.narration =
        `Appraised ${plural(studies.length, 'study', 'studies')} — ` +
        `${passing} passed the quality bar (iteration ${data.iteration ?? '?'}). ${verdict}`;
      break;
    }
    case 'synthesizer':
      next.narration = 'Report ready.';
      break;
  }
  return next;
}

function onDone(state: ReasoningState, payload: DoneEvent, at?: number): ReasoningState {
  return {
    ...state,
    status: 'done',
    activeNode: null,
    endedAt: at,
    // Prefer the authoritative report from the done event; fall back to the
    // text streamed via tokens if the server sent an empty final report.
    reportText: payload.report || state.reportText,
    studies: payload.studies,
    iterations: payload.iterations,
  };
}

function onError(state: ReasoningState, payload: ErrorEvent, at?: number): ReasoningState {
  return {
    ...state,
    status: 'error',
    activeNode: null,
    endedAt: at,
    error: { name: payload.error, detail: payload.detail },
  };
}

/**
 * Index of the latest `thinking` entry for `node`, or `-1` if none. A step
 * flips the most recent still-thinking entry for its node, which keeps the
 * self-correction loop correct (each loop pass starts a new entry, so the step
 * resolves the one that node just started rather than an earlier one).
 */
function latestThinkingIndex(steps: StepEntry[], node: NodeName): number {
  for (let i = steps.length - 1; i >= 0; i -= 1) {
    if (steps[i].node === node && steps[i].status === 'thinking') return i;
  }
  return -1;
}

/** A node began running: push a `thinking` entry and mark it the active node. */
function onNodeStart(state: ReasoningState, node: NodeName, at?: number): ReasoningState {
  return {
    ...state,
    steps: [...state.steps, startEntry(state.nextStepId, node, at)],
    activeNode: node,
    nextStepId: state.nextStepId + 1,
  };
}

/** Apply one parsed SSE event to the state. */
function onEvent(state: ReasoningState, event: ResearchEvent, at?: number): ReasoningState {
  // A run that was stopped (or already finished) ignores late events, e.g. ones
  // already in flight when the user pressed Stop.
  if (state.status !== 'running') return state;

  switch (event.kind) {
    case 'node_start':
      return onNodeStart(state, event.payload.node, at);
    case 'step': {
      const { node, summary, data } = event.payload;
      const iterations =
        node === 'evaluator' && typeof data.iteration === 'number'
          ? data.iteration
          : state.iterations;

      // Flip the matching `thinking` entry to `done`. If no node_start preceded
      // this step (defensive — the backend always emits one), append a finished
      // entry so no step is ever dropped.
      const index = latestThinkingIndex(state.steps, node);
      let steps: StepEntry[];
      let nextStepId = state.nextStepId;
      if (index === -1) {
        steps = [...state.steps, finishEntry(startEntry(nextStepId, node), summary, data, at)];
        nextStepId += 1;
      } else {
        steps = state.steps.map((entry, i) =>
          i === index ? finishEntry(entry, summary, data, at) : entry,
        );
      }

      // The active node stays the just-finished node until the next node starts,
      // so the UI keeps a sensible highlight between steps.
      return { ...state, steps, activeNode: node, iterations, nextStepId };
    }
    case 'token':
      // Append in arrival order so the report "types out" exactly as streamed.
      return { ...state, reportText: state.reportText + event.payload.text };
    case 'done':
      return onDone(state, event.payload, at);
    case 'error':
      return onError(state, event.payload, at);
  }
}

/**
 * User pressed Stop. Only meaningful while running; otherwise a no-op so a late
 * click can't turn a finished run into a "stopped" one. Partial steps and report
 * text are kept so the user can still read (and copy) what arrived.
 */
function onCancel(state: ReasoningState, at?: number): ReasoningState {
  if (state.status !== 'running') return state;
  return { ...state, status: 'cancelled', activeNode: null, endedAt: at };
}

/** The pure reducer: `(state, action) => nextState`. */
export function reasoningReducer(
  state: ReasoningState,
  action: ReasoningAction,
): ReasoningState {
  switch (action.type) {
    case 'start':
      return runningState(action.topic, state.nextStepId, action.at);
    case 'reset':
      return { ...initialState(), nextStepId: state.nextStepId };
    case 'cancel':
      return onCancel(state, action.at);
    case 'event':
      return onEvent(state, action.event, action.at);
  }
}
