/**
 * Shown once a run has ended (done, stopped, or failed): start over, re-run the
 * same topic, and (when there is report text) copy or download it as Markdown.
 * Copy confirmation is a small non-blocking toast plus a polite live region.
 */
import { AnimatePresence, motion } from 'motion/react';
import { CheckIcon, CopyIcon, DownloadIcon, PlusIcon, RefreshIcon } from './icons';

interface ActionBarProps {
  hasReport: boolean;
  copied: boolean;
  copyFailed: boolean;
  onNewResearch: () => void;
  onRunAgain: () => void;
  onCopy: () => void;
  onDownload: () => void;
}

export function ActionBar({
  hasReport,
  copied,
  copyFailed,
  onNewResearch,
  onRunAgain,
  onCopy,
  onDownload,
}: ActionBarProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      role="group"
      aria-label="Next actions"
      className="flex flex-wrap items-center gap-2.5"
    >
      <button type="button" onClick={onNewResearch} className="btn btn-primary">
        <PlusIcon size={16} />
        New research
      </button>
      <button type="button" onClick={onRunAgain} className="btn btn-ghost">
        <RefreshIcon size={16} />
        Run again
      </button>

      {hasReport && (
        <>
          <span className="mx-1 hidden h-6 w-px bg-border sm:block" aria-hidden="true" />
          <button type="button" onClick={onCopy} className="btn btn-ghost">
            {copied ? <CheckIcon size={16} className="text-ok" /> : <CopyIcon size={16} />}
            {copied ? 'Copied' : 'Copy report'}
          </button>
          <button type="button" onClick={onDownload} className="btn btn-ghost">
            <DownloadIcon size={16} />
            Download .md
          </button>
        </>
      )}

      {/* Screen-reader confirmation; the visible toast is below. */}
      <span role="status" className="sr-only">
        {copied ? 'Report copied to clipboard' : copyFailed ? 'Could not copy the report' : ''}
      </span>

      <AnimatePresence>
        {(copied || copyFailed) && (
          <motion.div
            key={copyFailed ? 'failed' : 'copied'}
            initial={{ opacity: 0, y: 12, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8 }}
            transition={{ duration: 0.2 }}
            aria-hidden="true"
            className="glass-strong pointer-events-none fixed bottom-6 left-1/2 z-40 flex -translate-x-1/2 items-center gap-2 rounded-full px-4 py-2.5 text-sm font-medium text-fg"
          >
            {copied ? (
              <>
                <CheckIcon size={16} className="text-ok" />
                Copied to clipboard
              </>
            ) : (
              'Copy failed. Select the text manually.'
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
