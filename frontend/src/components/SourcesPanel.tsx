/**
 * "Sources & evidence": the evaluated studies from the terminal `done` event as
 * a collapsible grid of glass cards. Each card has a study-type badge, a link to
 * PubMed (or the web page), and a quality meter with its numeric score and tier.
 */
import { AnimatePresence, motion } from 'motion/react';
import { useState } from 'react';
import { sourceLink } from '../lib/citations';
import { qualityTier, scorePercent, studyTypeLabel, type QualityTier } from '../lib/format';
import type { StudySummary } from '../lib/events';
import { BookIcon, ChevronDownIcon, ExternalLinkIcon } from './icons';

interface SourcesPanelProps {
  studies: StudySummary[];
}

const TIER_LABEL: Record<QualityTier, string> = {
  high: 'High quality',
  moderate: 'Moderate quality',
  low: 'Low quality',
};

const TIER_BAR: Record<QualityTier, string> = {
  high: 'bg-accent',
  moderate: 'bg-warn',
  low: 'bg-fg-subtle',
};

function SourceCard({ study }: { study: StudySummary }) {
  const link = sourceLink(study.identifier);
  const tier = qualityTier(study.quality_score);
  const percent = scorePercent(study.quality_score);

  return (
    <li className="glass-soft glass-interactive flex flex-col gap-3 px-4 py-3.5">
      <div className="flex items-start justify-between gap-2">
        <span className="rounded-full border border-violet/35 bg-violet/10 px-2.5 py-1 text-xs font-medium text-violet-text">
          {studyTypeLabel(study.study_type)}
        </span>
        {link ? (
          <a
            href={link.href}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-8 min-w-0 items-center gap-1 font-mono text-xs text-accent-text hover:underline"
            title={study.identifier}
          >
            <span className="truncate">{link.label}</span>
            <ExternalLinkIcon size={13} className="shrink-0" />
            <span className="sr-only">
              {link.kind === 'pubmed' ? '(opens PubMed in a new tab)' : '(opens in a new tab)'}
            </span>
          </a>
        ) : (
          <span className="min-w-0 truncate font-mono text-xs text-fg-muted" title={study.identifier}>
            {study.identifier}
          </span>
        )}
      </div>

      <div>
        <div className="mb-1.5 flex items-baseline justify-between text-xs">
          <span className="text-fg-muted">{TIER_LABEL[tier]}</span>
          <span className="font-mono tabular-nums text-fg">{study.quality_score.toFixed(2)}</span>
        </div>
        <div
          role="meter"
          aria-label="Quality score"
          aria-valuemin={0}
          aria-valuemax={1}
          aria-valuenow={Number(study.quality_score.toFixed(2))}
          aria-valuetext={`${study.quality_score.toFixed(2)}, ${TIER_LABEL[tier].toLowerCase()}`}
          className="h-1.5 w-full overflow-hidden rounded-full bg-surface-2 ring-1 ring-border"
        >
          <div
            className={`h-full rounded-full ${TIER_BAR[tier]}`}
            style={{ width: `${percent}%` }}
          />
        </div>
      </div>
    </li>
  );
}

export function SourcesPanel({ studies }: SourcesPanelProps) {
  // The parent keys this component by run, so each run starts expanded.
  const [open, setOpen] = useState(true);
  if (studies.length === 0) return null;

  return (
    <motion.section
      aria-labelledby="sources-heading"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
      className="glass"
    >
      <h2 id="sources-heading" className="m-0">
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          aria-controls="sources-list"
          className="flex min-h-14 w-full items-center gap-3 rounded-2xl px-5 py-3 text-left"
        >
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent/12 text-accent-text">
            <BookIcon size={17} />
          </span>
          <span className="flex-1 text-base font-semibold tracking-tight text-fg">
            Sources &amp; evidence
            <span className="ml-2 rounded-full bg-surface-2 px-2 py-0.5 font-mono text-xs font-medium text-fg-muted">
              {studies.length}
            </span>
          </span>
          <span
            className={`flex text-fg-muted transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
          >
            <ChevronDownIcon size={18} />
          </span>
        </button>
      </h2>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id="sources-list"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.26, ease: 'easeOut' }}
            className="overflow-hidden"
          >
            <ul className="m-0 grid list-none grid-cols-1 gap-3 px-4 pb-4 pt-1 sm:grid-cols-2 sm:px-5 sm:pb-5">
              {studies.map((study, index) => (
                <SourceCard key={`${study.identifier}-${index}`} study={study} />
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.section>
  );
}
