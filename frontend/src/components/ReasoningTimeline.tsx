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

/** The queries list for planner / refine, rendered as a tight mono list. */
function QueryList({ queries }: { queries: string[] }) {
  if (!queries.length) return null;
  return (
    <ul className="mt-2 flex flex-col gap-1">
      {queries.map((q, i) => (
        <li key={i} className="flex gap-2 text-[13px] text-mist-text">
          <span className="text-steel-text">·</span>
          <span className="font-mono text-[12.5px] text-mist-text">{q}</span>
        </li>
      ))}
    </ul>
  );
}

/** Rich narration shown once a step is `done` (never raw JSON). */
function StepDetail({ entry }: { entry: StepEntry }) {
  return (
    <>
      {entry.narration && (
        <p className="mt-0.5 text-[13px] leading-relaxed text-mist-text">
          {entry.narration}
        </p>
      )}
      {(entry.node === 'planner' || entry.node === 'refine_queries') && (
        <QueryList queries={entry.queries ?? []} />
      )}
      {entry.node === 'evaluator' && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <Chip label={`iteration ${entry.iteration ?? '?'}`} />
          <Chip label={`${entry.passingCount ?? 0}/${entry.studyCount ?? 0} passed`} />
          <Chip
            label={entry.isSufficient ? 'sufficient' : 'needs more evidence'}
            tone={entry.isSufficient ? 'ok' : 'warn'}
          />
        </div>
      )}
    </>
  );
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
        {steps.map((entry) => {
          const meta = NODE_META[entry.node];
          // A `thinking` entry is the live step: pulse it in teal. Once a run
          // ends (done/error) nothing is thinking, so no stale pulse remains.
          const isThinking = entry.status === 'thinking' && status === 'running';
          const isActive = isThinking && activeNode === entry.node;
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
                {isThinking ? (
                  <p className="mt-0.5 flex items-center gap-2 text-[13px] text-teal-soft">
                    <span
                      className="inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-teal pulse-teal"
                      aria-hidden="true"
                    />
                    <span className="shimmer-text">{entry.thinkingLabel}</span>
                  </p>
                ) : (
                  <StepDetail entry={entry} />
                )}
              </div>
            </motion.li>
          );
        })}
      </AnimatePresence>
    </ol>
  );
}
