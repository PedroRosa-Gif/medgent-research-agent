/**
 * Unit tests for the pure reasoning reducer (decision 3a: event logic only).
 *
 * These are offline and DOM-free — they exercise `(state, action) => state`
 * directly, never `EventSource` or React. The headline test walks a realistic
 * self-correction run: plan → fetch → evaluate(insufficient) → refine → fetch →
 * evaluate(sufficient) → tokens → done.
 */

import { describe, expect, it } from 'vitest';
import type {
  DoneEvent,
  ErrorEvent,
  NodeName,
  ResearchEvent,
  StepData,
  StudySummary,
} from './events';
import {
  initialState,
  reasoningReducer,
  THINKING_LABELS,
  type ReasoningState,
} from './reasoningReducer';

/** Build a `node_start` event action for `node`. */
function nodeStart(node: NodeName): ResearchEvent {
  return { kind: 'node_start', payload: { node } };
}

/** Build a `step` event action for `node` with the given update `data`. */
function step(node: NodeName, summary: string, data: StepData): ResearchEvent {
  return { kind: 'step', payload: { node, summary, keys: Object.keys(data), data } };
}

function token(text: string): ResearchEvent {
  return { kind: 'token', payload: { node: 'synthesizer', text } };
}

function done(payload: DoneEvent): ResearchEvent {
  return { kind: 'done', payload };
}

function errorEvent(payload: ErrorEvent): ResearchEvent {
  return { kind: 'error', payload };
}

/** Reduce a list of actions over a starting state. */
function run(
  start: ReasoningState,
  events: ResearchEvent[],
): ReasoningState {
  return events.reduce(
    (state, event) => reasoningReducer(state, { type: 'event', event }),
    start,
  );
}

const STUDIES: StudySummary[] = [
  { identifier: 'PMID:111', study_type: 'rct', quality_score: 0.9 },
  { identifier: 'PMID:222', study_type: 'meta_analysis', quality_score: 0.95 },
];

describe('reasoningReducer', () => {
  it('starts a run from idle', () => {
    const state = reasoningReducer(initialState(), {
      type: 'start',
      topic: 'metformin efficacy',
    });
    expect(state.status).toBe('running');
    expect(state.topic).toBe('metformin efficacy');
    expect(state.steps).toHaveLength(0);
    expect(state.reportText).toBe('');
  });

  it('node_start pushes a thinking entry with the node thinking label', () => {
    let state = reasoningReducer(initialState(), { type: 'start', topic: 't' });
    state = run(state, [nodeStart('planner')]);

    expect(state.steps).toHaveLength(1);
    const entry = state.steps[0];
    expect(entry.node).toBe('planner');
    expect(entry.status).toBe('thinking');
    expect(entry.thinkingLabel).toBe(THINKING_LABELS.planner);
    expect(entry.narration).toBeUndefined();
    expect(state.activeNode).toBe('planner');
  });

  it('a step flips the matching thinking entry to done with narration', () => {
    let state = reasoningReducer(initialState(), { type: 'start', topic: 't' });
    state = run(state, [
      nodeStart('planner'),
      step('planner', 'Planned 3 queries', { queries: ['a', 'b', 'c'] }),
    ]);

    // Still one entry — the step did not append a second; it flipped the first.
    expect(state.steps).toHaveLength(1);
    const entry = state.steps[0];
    expect(entry.status).toBe('done');
    expect(entry.queries).toEqual(['a', 'b', 'c']);
    expect(entry.narration).toBe('Broke the topic into 3 lines of inquiry:');
  });

  it('a step with no preceding node_start still produces a done entry', () => {
    let state = reasoningReducer(initialState(), { type: 'start', topic: 't' });
    state = run(state, [
      step('fetch_evidence', 'Fetched 2 papers', { evidence: [1, 2] }),
    ]);

    expect(state.steps).toHaveLength(1);
    expect(state.steps[0].status).toBe('done');
    expect(state.steps[0].paperCount).toBe(2);
    expect(state.steps[0].narration).toBe('Found 2 studies across PubMed and the web.');
  });

  it('walks a full self-correction run and ends done', () => {
    let state = reasoningReducer(initialState(), {
      type: 'start',
      topic: 'metformin efficacy',
    });

    // Each node starts (thinking) then finishes (step flips it to done), as the
    // real SSE stream delivers: node_start precedes each matching step.
    const sequence: ResearchEvent[] = [
      nodeStart('planner'),
      step('planner', 'Planned 2 queries', { queries: ['q1', 'q2'] }),
      nodeStart('fetch_evidence'),
      step('fetch_evidence', 'Fetched 5 papers', { evidence: [1, 2, 3, 4, 5] }),
      nodeStart('evaluator'),
      step('evaluator', 'Evaluated 3 studies (iteration 1, sufficient=False)', {
        evaluated_studies: STUDIES.slice(0, 1),
        is_sufficient: false,
        iteration: 1,
      }),
      nodeStart('refine_queries'),
      step('refine_queries', 'Refined into 2 new queries', {
        queries: ['q3', 'q4'],
      }),
      nodeStart('fetch_evidence'),
      step('fetch_evidence', 'Fetched 8 papers', {
        evidence: [1, 2, 3, 4, 5, 6, 7, 8],
      }),
      nodeStart('evaluator'),
      step('evaluator', 'Evaluated 2 studies (iteration 2, sufficient=True)', {
        evaluated_studies: STUDIES,
        is_sufficient: true,
        iteration: 2,
      }),
    ];
    state = run(state, sequence);

    // Step entries accumulate in arrival order — one per node_start, not doubled.
    expect(state.steps.map((s) => s.node)).toEqual([
      'planner',
      'fetch_evidence',
      'evaluator',
      'refine_queries',
      'fetch_evidence',
      'evaluator',
    ]);
    // All entries are done (each step flipped its thinking entry).
    expect(state.steps.every((s) => s.status === 'done')).toBe(true);
    // Per-node detail extraction + rich narration (no raw JSON).
    expect(state.steps[0].queries).toEqual(['q1', 'q2']);
    expect(state.steps[0].narration).toBe('Broke the topic into 2 lines of inquiry:');
    expect(state.steps[1].paperCount).toBe(5);
    expect(state.steps[1].narration).toBe('Found 5 studies across PubMed and the web.');
    expect(state.steps[2].isSufficient).toBe(false);
    expect(state.steps[2].iteration).toBe(1);
    expect(state.steps[2].passingCount).toBe(1); // STUDIES[0] has quality 0.9 >= 0.6
    expect(state.steps[2].narration).toBe(
      'Appraised 1 study — 1 passed the quality bar (iteration 1). Evidence insufficient, continuing.',
    );
    expect(state.steps[3].queries).toEqual(['q3', 'q4']);
    expect(state.steps[3].narration).toBe('Refined into 2 new queries:');
    expect(state.steps[4].paperCount).toBe(8);
    expect(state.steps[5].isSufficient).toBe(true);
    expect(state.steps[5].passingCount).toBe(2);
    expect(state.steps[5].narration).toBe(
      'Appraised 2 studies — 2 passed the quality bar (iteration 2). Evidence sufficient.',
    );
    // Loop visibility: iteration tracks the latest evaluator.
    expect(state.iterations).toBe(2);
    // Active node is the most recent step; still running.
    expect(state.activeNode).toBe('evaluator');
    expect(state.status).toBe('running');
    // Monotonic ids, unique and ordered (one id per node_start).
    expect(state.steps.map((s) => s.id)).toEqual([0, 1, 2, 3, 4, 5]);

    // Report types out: tokens concatenate in order.
    state = run(state, [
      token('## Summary\n'),
      token('Metformin is '),
      token('effective. [111]'),
    ]);
    expect(state.reportText).toBe('## Summary\nMetformin is effective. [111]');

    // Terminal done: status flips, studies populate, report present.
    state = reasoningReducer(state, {
      type: 'event',
      event: done({
        topic: 'metformin efficacy',
        report: '## Summary\nMetformin is effective. [111]',
        iterations: 2,
        studies: STUDIES,
      }),
    });
    expect(state.status).toBe('done');
    expect(state.activeNode).toBeNull();
    expect(state.studies).toEqual(STUDIES);
    expect(state.iterations).toBe(2);
    expect(state.reportText).toContain('Metformin is effective');
  });

  it('concatenates tokens strictly in arrival order', () => {
    let state = reasoningReducer(initialState(), {
      type: 'start',
      topic: 't',
    });
    state = run(state, ['a', 'b', 'c', 'd'].map(token));
    expect(state.reportText).toBe('abcd');
  });

  it('falls back to streamed tokens when done.report is empty', () => {
    let state = reasoningReducer(initialState(), { type: 'start', topic: 't' });
    state = run(state, [token('streamed body')]);
    state = reasoningReducer(state, {
      type: 'event',
      event: done({ topic: 't', report: '', iterations: 1, studies: [] }),
    });
    expect(state.reportText).toBe('streamed body');
  });

  it('sets error status with detail on an error event', () => {
    let state = reasoningReducer(initialState(), {
      type: 'start',
      topic: 'boom',
    });
    state = run(state, [step('planner', 'Planned 1 queries', { queries: ['q'] })]);
    state = reasoningReducer(state, {
      type: 'event',
      event: errorEvent({ error: 'RuntimeError', detail: 'LLM timed out' }),
    });
    expect(state.status).toBe('error');
    expect(state.error).toEqual({ name: 'RuntimeError', detail: 'LLM timed out' });
    expect(state.activeNode).toBeNull();
    // Steps collected before the failure are retained.
    expect(state.steps).toHaveLength(1);
  });

  it('resets to a clean state for a new run', () => {
    let state = reasoningReducer(initialState(), {
      type: 'start',
      topic: 'first',
    });
    state = run(state, [
      step('planner', 'Planned 1 queries', { queries: ['q'] }),
      token('partial'),
    ]);
    state = reasoningReducer(state, { type: 'reset' });

    expect(state.status).toBe('idle');
    expect(state.topic).toBe('');
    expect(state.steps).toHaveLength(0);
    expect(state.reportText).toBe('');
    expect(state.studies).toHaveLength(0);
    expect(state.error).toBeUndefined();

    // A fresh run after reset starts clean.
    state = reasoningReducer(state, { type: 'start', topic: 'second' });
    expect(state.status).toBe('running');
    expect(state.topic).toBe('second');
    expect(state.steps).toHaveLength(0);
  });
});
