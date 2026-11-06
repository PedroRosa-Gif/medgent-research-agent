/**
 * Expandable panel listing the evaluated studies from the terminal `done`
 * event. Compact list with hairline row borders; starts expanded when studies
 * are present so the evidence is visible without an extra click.
 */

import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useState } from 'react';
import type { StudySummary } from '../lib/events';

interface StudiesPanelProps {
  studies: StudySummary[];
}

function scoreTone(score: number): string {
  if (score >= 0.75) return 'text-mist-text';
  if (score >= 0.5) return 'text-fog-text';
  return 'text-steel-text';
}

export function StudiesPanel({ studies }: StudiesPanelProps) {
  const [open, setOpen] = useState(true);

  // Re-expand when a new set of studies arrives.
  useEffect(() => {
    if (studies.length > 0) setOpen(true);
  }, [studies]);

  if (studies.length === 0) return null;

  return (
    <div className="rounded-lg border border-ash-border bg-carbon">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <span className="font-w590 text-[14px] text-snow">
          Evaluated studies
          <span className="font-w510 ml-2 text-fog-text">{studies.length}</span>
        </span>
        <span
          className={`text-fog-text transition-transform ${open ? 'rotate-180' : ''}`}
          aria-hidden="true"
        >
          <svg
            viewBox="0 0 24 24"
            width="16"
            height="16"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="m6 9 6 6 6-6" />
          </svg>
        </span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: 'easeOut' }}
            className="overflow-hidden"
          >
            <div className="border-t border-smoke">
              <div className="font-w510 grid grid-cols-[1fr_auto_auto] gap-x-4 px-4 py-2 text-[11.5px] uppercase tracking-wide text-steel-text">
                <span>Identifier</span>
                <span>Type</span>
                <span className="text-right">Quality</span>
              </div>
              <ul>
                {studies.map((study, i) => (
                  <li
                    key={`${study.identifier}-${i}`}
                    className="grid grid-cols-[1fr_auto_auto] items-center gap-x-4 border-t border-smoke px-4 py-2.5 text-[13.5px]"
                  >
                    <span className="truncate font-mono text-[12.5px] text-mist-text">
                      {study.identifier}
                    </span>
                    <span className="text-fog-text">
                      {study.study_type.replace(/_/g, ' ')}
                    </span>
                    <span className={`text-right tabular-nums ${scoreTone(study.quality_score)}`}>
                      {study.quality_score.toFixed(2)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
