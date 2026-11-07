/**
 * The synthesized report as a glass "document" card. While `token` events
 * stream in, `reportText` grows and the view re-renders so the report types out,
 * with a blinking caret at the end of the last block (CSS `.report-typing`).
 *
 * The Markdown renderer is lazy-loaded; until it arrives (or if it is slow) the
 * raw text is shown so nothing is ever blank.
 */
import { motion } from 'motion/react';
import { lazy, Suspense } from 'react';
import type { ReasoningState } from '../lib/reasoningReducer';
import { DocumentIcon } from './icons';

const ReportMarkdown = lazy(() => import('./ReportMarkdown'));

interface ReportViewProps {
  state: ReasoningState;
}

function headerNote(status: ReasoningState['status'], hasText: boolean): string | null {
  if (status === 'running') return hasText ? 'Writing…' : 'Waiting for evidence…';
  if (status === 'cancelled' && hasText) return 'Partial report (stopped)';
  return null;
}

export function ReportView({ state }: ReportViewProps) {
  const { reportText, status } = state;
  const typing = status === 'running' && reportText.length > 0;
  const note = headerNote(status, reportText.length > 0);

  return (
    <motion.section
      aria-labelledby="report-heading"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
      className="glass px-5 py-6 sm:px-9 sm:py-8"
    >
      <div className="mb-5 flex items-center justify-between gap-3 border-b border-border pb-4">
        <h2
          id="report-heading"
          className="flex items-center gap-2.5 text-base font-semibold tracking-tight text-fg"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-accent/12 text-accent-text">
            <DocumentIcon size={17} />
          </span>
          Report
        </h2>
        {note && <span className="text-xs font-medium text-fg-muted">{note}</span>}
      </div>

      {reportText ? (
        <div className={typing ? 'report report-typing' : 'report'}>
          <Suspense fallback={<p className="whitespace-pre-wrap">{reportText}</p>}>
            <ReportMarkdown text={reportText} />
          </Suspense>
        </div>
      ) : (
        <p className="text-sm text-fg-muted">
          {status === 'done'
            ? 'The run finished without producing a report.'
            : 'The synthesized report will appear here once the agent has gathered sufficient evidence.'}
        </p>
      )}
    </motion.section>
  );
}
