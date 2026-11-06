/**
 * The reasoning timeline — a vertically stacked, Linear-changelog-style list
 * where each `step` event is an animated entry. The node whose step arrived
 * most recently (while still running) pulses in the single teal accent; the
 * self-correction loop is visible because each evaluator/refine iteration adds
 * its own entry.
 */

import { AnimatePresence, motion } from 'motion/react';
import type { ReasoningState, StepEntry } from '../lib/reasoningReducer';
import { NODE_META } from './nodeMeta';

interface ReasoningTimelineProps {
  state: ReasoningState;
}

function StepDetail({ entry }: { entry: StepEntry }) {
  switch (entry.node) {
    case 'planner':
    case 'refine_queries':
      if (!entry.queries?.length) return null;
      return (
        <ul className="mt-2 flex flex-col gap-1">
          {entry.queries.map((q, i) => (
            <li
              key={i}
              className="flex gap-2 text-[13px] text-mist-text"
            >
              <span className="text-steel-text">·</span>
              <span className="font-mono text-[12.5px] text-mist-text">{q}</span>
            </li>
          ))}
        </ul>
      );
    case 'fetch_evidence':
      return (
        <p className="mt-1.5 text-[13px] text-fog-text">
          {entry.paperCount ?? 0} paper{entry.paperCount === 1 ? '' : 's'} retrieved
        </p>
      );
    case 'evaluator':
      return (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <Chip label={`iteration ${entry.iteration ?? '?'}`} />
          <Chip label={`${entry.studyCount ?? 0} studies`} />
          <Chip
            label={entry.isSufficient ? 'sufficient' : 'needs more evidence'}
            tone={entry.isSufficient ? 'ok' : 'warn'}
          />
        </div>
      );
    case 'synthesizer':
      return (
        <p className="mt-1.5 text-[13px] text-fog-text">
          Writing the synthesized report…
        </p>
      );
  }
}

function Chip({ label, tone }: { label: string; tone?: 'ok' | 'warn' }) {
  const toneClass =
    tone === 'ok'
      ? 'text-mist-text border-ash-border'
      : tone === 'warn'
        ? 'text-fog-text border-ash-border'
        : 'text-fog-text border-smoke';
  return (
    <span
      className={`font-w510 rounded border px-2 py-0.5 text-[11.5px] ${toneClass}`}
    >
      {label}
    </span>
  );
}

export function ReasoningTimeline({ state }: ReasoningTimelineProps) {
  const { steps, activeNode, status } = state;

  if (steps.length === 0 && status === 'idle') {
    return (
      <p className="text-[14px] text-steel-text">
        Enter a clinical topic above to watch the agent reason through the
        literature in real time.
      </p>
    );
  }

  return (
    <ol className="relative flex flex-col">
      {/* Spine */}
      <span
        className="absolute left-[11px] top-1 bottom-1 w-px bg-ash-border"
        aria-hidden="true"
      />
      <AnimatePresence initial={false}>
        {steps.map((entry, index) => {
          const meta = NODE_META[entry.node];
          const isActive = status === 'running' && index === steps.length - 1 && activeNode === entry.node;
          return (
            <motion.li
              key={entry.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.28, ease: 'easeOut' }}
              className="relative flex gap-3 pb-5 pl-0 last:pb-0"
            >
              <span
                className={[
                  'relative z-10 mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border bg-carbon',
                  isActive
                    ? 'border-teal text-teal pulse-teal'
                    : 'border-ash-border text-fog-text',
                ].join(' ')}
              >
                <meta.Icon className="h-3.5 w-3.5" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline gap-2">
                  <span
                    className={[
                      'font-w590 text-[14px]',
                      isActive ? 'text-teal-soft' : 'text-snow',
                    ].join(' ')}
                  >
                    {meta.label}
                  </span>
                </div>
                <p className="mt-0.5 text-[13px] text-fog-text">{entry.summary}</p>
                <StepDetail entry={entry} />
              </div>
            </motion.li>
          );
        })}
      </AnimatePresence>
    </ol>
  );
}
