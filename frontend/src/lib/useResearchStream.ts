/**
 * Thin SSE client hook. This is the ONLY module that touches `EventSource`;
 * all state transitions live in the pure `reasoningReducer`.
 *
 * EventSource specifics that shape this code:
 *   - It only does GET, which matches our `GET /research/stream` endpoint.
 *   - The backend frames *named* events (`step`/`token`/`done`/`error`). Named
 *     events are delivered via `addEventListener(name, ...)`, NOT `onmessage`
 *     (which only fires for unnamed `message` events). So we register one
 *     listener per name.
 *   - Lifecycle: we close the connection on `done`, on an `error` *event*, on a
 *     transport-level failure (`onerror` with no reconnect wanted), on unmount,
 *     and whenever a new run starts. EventSource would otherwise auto-reconnect
 *     after the stream ends, which we do not want for a one-shot run.
 */

import { useCallback, useEffect, useReducer, useRef } from 'react';
import type {
  DoneEvent,
  ErrorEvent,
  NodeStartEvent,
  ResearchEvent,
  StepEvent,
  TokenEvent,
} from './events';
import {
  initialState,
  reasoningReducer,
  type ReasoningState,
} from './reasoningReducer';

export interface UseResearchStream {
  state: ReasoningState;
  /** Open a stream for `topic`. No-op if a run is already in progress. */
  start: (topic: string, maxIterations?: number) => void;
  /**
   * Stop listening to the current run (Esc / Stop button) and mark it cancelled.
   * Only closes the browser side: see the note in the implementation.
   */
  cancel: () => void;
  /** Close any open stream and return to idle. */
  reset: () => void;
}

/** Safely parse an SSE `data` string; returns `null` on malformed JSON. */
function parseData<T>(raw: string): T | null {
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export function useResearchStream(): UseResearchStream {
  const [state, dispatch] = useReducer(reasoningReducer, undefined, initialState);
  const sourceRef = useRef<EventSource | null>(null);

  const closeSource = useCallback(() => {
    sourceRef.current?.close();
    sourceRef.current = null;
  }, []);

  // The reducer is pure and never reads the clock; we stamp each action here.
  const dispatchEvent = useCallback((event: ResearchEvent) => {
    dispatch({ type: 'event', event, at: Date.now() });
  }, []);

  const start = useCallback(
    (topic: string, maxIterations?: number) => {
      const trimmed = topic.trim();
      // Guard: ignore empty topics and double-starts while a run is live.
      if (!trimmed || sourceRef.current) return;

      dispatch({ type: 'start', topic: trimmed, at: Date.now() });

      const params = new URLSearchParams({ topic: trimmed });
      if (maxIterations != null) {
        params.set('max_iterations', String(maxIterations));
      }
      const source = new EventSource(`/research/stream?${params.toString()}`);
      sourceRef.current = source;

      source.addEventListener('node_start', (e) => {
        const payload = parseData<NodeStartEvent>((e as MessageEvent).data);
        if (payload) dispatchEvent({ kind: 'node_start', payload });
      });
      source.addEventListener('step', (e) => {
        const payload = parseData<StepEvent>((e as MessageEvent).data);
        if (payload) dispatchEvent({ kind: 'step', payload });
      });
      source.addEventListener('token', (e) => {
        const payload = parseData<TokenEvent>((e as MessageEvent).data);
        if (payload) dispatchEvent({ kind: 'token', payload });
      });
      source.addEventListener('done', (e) => {
        const payload = parseData<DoneEvent>((e as MessageEvent).data);
        if (payload) dispatchEvent({ kind: 'done', payload });
        // Terminal event: close so EventSource does not auto-reconnect.
        closeSource();
      });
      source.addEventListener('error', (e) => {
        // Two failure shapes land here:
        //  1. A server `error` *event* carrying JSON detail (has `.data`).
        //  2. A transport-level failure (connection dropped, no `.data`).
        const raw = (e as MessageEvent).data;
        if (typeof raw === 'string' && raw.length > 0) {
          const payload = parseData<ErrorEvent>(raw);
          if (payload) dispatchEvent({ kind: 'error', payload });
        } else {
          dispatchEvent({
            kind: 'error',
            payload: {
              error: 'ConnectionError',
              detail:
                'Lost connection to the research stream. Is the backend running on :8000?',
            },
          });
        }
        closeSource();
      });
    },
    [closeSource, dispatchEvent],
  );

  const cancel = useCallback(() => {
    // NOTE: this only closes the browser's EventSource. The backend run keeps
    // going in its worker thread until the graph finishes on its own; the UI
    // simply stops listening and discards any further output. (The reducer
    // ignores events after `cancel`, and we also remove the listeners by closing.)
    closeSource();
    dispatch({ type: 'cancel', at: Date.now() });
  }, [closeSource]);

  const reset = useCallback(() => {
    closeSource();
    dispatch({ type: 'reset' });
  }, [closeSource]);

  // Close the stream if the component using the hook unmounts mid-run.
  useEffect(() => closeSource, [closeSource]);

  return { state, start, cancel, reset };
}
