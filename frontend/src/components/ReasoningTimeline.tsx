/**
 * The reasoning timeline: a vertical rail of connected nodes, each with a glass
 * card. A node is
 *   - thinking:    animated accent ring + shimmering label (the live step),
 *   - done:        its icon with a check badge, the narration, and a duration,
 *   - interrupted: dashed ring (the run ended - stopped or errored - mid-step).
 * State is always carried by an icon/text too, never by color alone.
 *
 * Once a run has finished, the header row doubles as a one-line summary that
 * collapses/expands the rail ("Reasoned in 1m 12s · 2 iterations · 12 studies").
 */
import { AnimatePresence, motion } from 'motion/react';
import { useState, type ReactNode } from 'react';
import { formatElapsed, formatStepDuration } from '../lib/format';
import type { ReasoningState, StepEntry } from '../lib/reasoningReducer';
import { AlertIcon, CheckIcon, ChevronDownIcon, SparkleIcon } from './icons';
import { NODE_META } from './nodeMeta';

interface ReasoningSectionProps {
  state: ReasoningState;
  /** Elapsed run time in ms (live while running, final once ended). */
  elapsedMs: number;
}

function plural(count: number, singular: string, pluralForm = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : pluralForm}`;
}

/** One-line summary shown on the section header. */
function summaryLine(state: ReasoningState, elapsedMs: number): string {
  const time = formatElapsed(elapsedMs);
  switch (state.status) {
    case 'running':
      return 'Reasoning…';
    case 'done': {
      const parts = [`Reasoned in ${time}`];
      if (state.iterations > 0) parts.push(plural(state.iterations, 'iteration'));
      parts.push(plural(state.studies.length, 'study', 'studies'));
      return parts.join(' · ');
    }
    case 'cancelled':
      return `Stopped after ${time} · ${plural(state.steps.length, 'step')}`;
    case 'error':
      return `Interrupted after ${time} · ${plural(state.steps.length, 'step')}`;
    default:
      return 'Reasoning';
  }
}

function Chip({
  tone = 'neutral',
  icon,
  children,
}: {
  tone?: 'neutral' | 'ok' | 'warn';
  icon?: ReactNode;
  children: ReactNode;
}) {
  const toneClass =
    tone === 'ok'
      ? 'border-ok/35 bg-ok/10 text-ok'
      : tone === 'warn'
        ? 'border-warn/35 bg-warn/10 text-warn'
        : 'border-border bg-surface-2/60 text-fg-muted';
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium ${toneClass}`}
    >
      {icon}
      {children}
    </span>
  );
}

/** Planner / refine queries as wrapping mono chips. */
function QueryList({ queries }: { queries: string[] }) {
  if (!queries.length) return null;
  return (
    <ul className="mt-2.5 flex flex-wrap gap-1.5">
      {queries.map((query, index) => (
        <li
          key={`${index}-${query}`}
          className="max-w-full break-words rounded-lg border border-border bg-surface-2/60 px-2.5 py-1.5 font-mono text-xs leading-snug text-fg"
        >
          {query}
        </li>
      ))}
    </ul>
  );
}

function StepDetail({ entry }: { entry: StepEntry }) {
  return (
    <>
      {entry.narration && (
        <p className="text-[13.5px] leading-relaxed text-fg-muted">{entry.narration}</p>
      )}
      {entry.node === 'fetch_evidence' && entry.paperCount !== undefined && (
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          <Chip>{plural(entry.paperCount, 'paper')}</Chip>
        </div>
      )}
      {(entry.node === 'planner' || entry.node === 'refine_queries') && (
        <QueryList queries={entry.queries ?? []} />
      )}
      {entry.node === 'evaluator' && (
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          <Chip>iteration {entry.iteration ?? '?'}</Chip>
          <Chip>
            {entry.passingCount ?? 0}/{entry.studyCount ?? 0} passed
          </Chip>
          {entry.isSufficient ? (
            <Chip tone="ok" icon={<CheckIcon size={12} />}>
              sufficient
            </Chip>
          ) : (
            <Chip tone="warn" icon={<AlertIcon size={12} />}>
              needs more evidence
            </Chip>
          )}
        </div>
      )}
    </>
  );
}

type NodeState = 'thinking' | 'done' | 'interrupted';

function TimelineItem({
  entry,
  runStatus,
  isLast,
}: {
  entry: StepEntry;
  runStatus: ReasoningState['status'];
  isLast: boolean;
}) {
  const meta = NODE_META[entry.node];
  const running = runStatus === 'running';
  const nodeState: NodeState =
    entry.status === 'done' ? 'done' : running ? 'thinking' : 'interrupted';

  const nodeClass =
    nodeState === 'thinking'
      ? 'node-active'
      : nodeState === 'done'
        ? 'border-accent/50 text-accent-text'
        : 'border-dashed border-border-strong text-fg-subtle';

  return (
    <motion.li
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className="relative pb-3.5 pl-12 last:pb-0"
    >
      {/* Connector to the next node: accent once this step is done. */}
      {!isLast && (
        <span
          className={`absolute left-[17.5px] top-9 bottom-[-2px] w-px ${
            nodeState === 'done' ? 'bg-accent/45' : 'bg-border-strong'
          }`}
          aria-hidden="true"
        />
      )}

      <span
        className={`absolute left-0 top-0 flex h-9 w-9 items-center justify-center rounded-full border bg-surface-2/80 ${nodeClass}`}
        aria-hidden="true"
      >
        <meta.Icon className="h-[18px] w-[18px]" />
        {nodeState === 'done' && (
          <span className="absolute -bottom-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-accent-strong text-on-accent ring-2 ring-canvas">
            <CheckIcon size={10} strokeWidth={3} />
          </span>
        )}
      </span>

      <div className="glass-soft px-4 py-3">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="text-sm font-semibold tracking-tight text-fg">
            {meta.label}
            <span className="sr-only">
              {nodeState === 'done' ? ' (done)' : nodeState === 'thinking' ? ' (in progress)' : ' (interrupted)'}
            </span>
          </h3>
          {nodeState === 'done' && entry.durationMs !== undefined && (
            <span className="shrink-0 font-mono text-xs tabular-nums text-fg-subtle">
              {formatStepDuration(entry.durationMs)}
            </span>
          )}
          {nodeState === 'interrupted' && (
            <span className="shrink-0 text-xs font-medium text-fg-subtle">Interrupted</span>
          )}
        </div>

        <div className="mt-0.5">
          {nodeState === 'thinking' && (
            <p className="flex items-center gap-2 text-[13.5px]">
              <span className="shimmer-text">{entry.thinkingLabel}</span>
            </p>
          )}
          {nodeState === 'interrupted' && (
            <p className="text-[13.5px] text-fg-subtle">Stopped before this step finished.</p>
          )}
          {nodeState === 'done' && <StepDetail entry={entry} />}
        </div>
      </div>
    </motion.li>
  );
}

export function ReasoningSection({ state, elapsedMs }: ReasoningSectionProps) {
  const { steps, status } = state;
  // Collapsing is offered once the run has ended. The parent keys this component
  // by run, so every new run starts expanded.
  const [open, setOpen] = useState(true);
  const finished = status !== 'running' && status !== 'idle';
  const expanded = !finished || open;

  const heading = (
    <>
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent/12 text-accent-text">
        <SparkleIcon size={16} />
      </span>
      <span className="min-w-0 flex-1 truncate text-left text-sm font-medium text-fg">
        {summaryLine(state, elapsedMs)}
      </span>
      {finished && (
        <span
          className={`flex text-fg-muted transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
        >
          <ChevronDownIcon size={18} />
        </span>
      )}
    </>
  );

  return (
    <section aria-labelledby="reasoning-heading" className="flex flex-col gap-3">
      <h2 id="reasoning-heading" className="m-0">
        {finished ? (
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
            aria-controls="reasoning-steps"
            className="glass-soft glass-interactive flex min-h-12 w-full items-center gap-3 rounded-2xl px-3.5 py-2"
          >
            {heading}
            <span className="sr-only">{open ? 'Collapse reasoning' : 'Expand reasoning'}</span>
          </button>
        ) : (
          <div className="flex min-h-12 w-full items-center gap-3 px-1 py-2">{heading}</div>
        )}
      </h2>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            key="steps"
            id="reasoning-steps"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.28, ease: 'easeOut' }}
            // The 16px padding / negative margin pair keeps node glows and card
            // shadows inside the clipped box (and equals the page gutter, so it
            // can never cause horizontal scroll).
            className="pointer-events-none -m-4 overflow-hidden p-4"
          >
            <ol
              className="pointer-events-auto m-0 list-none p-0 pt-1"
              aria-live="polite"
              aria-relevant="additions text"
            >
              {steps.map((entry, index) => (
                <TimelineItem
                  key={entry.id}
                  entry={entry}
                  runStatus={status}
                  isLast={index === steps.length - 1}
                />
              ))}
            </ol>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
