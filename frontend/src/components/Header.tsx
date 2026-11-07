/**
 * App header (a real <header> landmark). On the idle hero it is transparent and
 * only carries the theme toggle; once a run is active it becomes a sticky,
 * translucent blurred bar with the brand on the left and status + elapsed time
 * + theme toggle on the right.
 */
import { AnimatePresence, motion } from 'motion/react';
import { formatElapsed } from '../lib/format';
import type { RunStatus } from '../lib/reasoningReducer';
import type { Theme } from '../lib/theme';
import { Logo } from './Logo';
import { StatusPill } from './StatusPill';
import { ThemeToggle } from './ThemeToggle';

interface HeaderProps {
  compact: boolean;
  status: RunStatus;
  elapsedMs: number;
  theme: Theme;
  onToggleTheme: () => void;
}

export function Header({ compact, status, elapsedMs, theme, onToggleTheme }: HeaderProps) {
  return (
    <header
      className={[
        'sticky top-0 z-30 transition-[background-color,border-color,box-shadow] duration-300',
        compact ? 'glass-bar' : 'border-b border-transparent',
      ].join(' ')}
    >
      <div className="mx-auto flex h-16 w-full max-w-[780px] items-center justify-between gap-3 px-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-2.5">
          <AnimatePresence initial={false}>
            {compact && (
              <motion.div
                key="brand"
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -8 }}
                transition={{ duration: 0.25 }}
                className="flex items-center gap-2.5"
              >
                <Logo size={30} />
                <span className="text-gradient text-lg font-semibold tracking-tight">MedGent</span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="flex items-center gap-2.5">
          {compact && (
            <>
              <StatusPill status={status} />
              <span
                className="hidden min-w-[3.5rem] text-right font-mono text-[13px] tabular-nums text-fg-muted sm:inline"
                title="Elapsed time"
              >
                {formatElapsed(elapsedMs)}
              </span>
            </>
          )}
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        </div>
      </div>
    </header>
  );
}
