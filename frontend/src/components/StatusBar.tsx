/**
 * Compact idle/running/done/error indicator. Monochrome dot + label, with the
 * single teal accent reserved for the live "running" state.
 */

import type { RunStatus } from '../lib/reasoningReducer';

interface StatusBarProps {
  status: RunStatus;
  iterations: number;
}

const COPY: Record<RunStatus, string> = {
  idle: 'Idle',
  running: 'Researching',
  done: 'Complete',
  error: 'Error',
};

export function StatusBar({ status, iterations }: StatusBarProps) {
  const running = status === 'running';
  return (
    <div className="flex items-center gap-2 text-[13px] text-fog-text">
      <span
        className={[
          'inline-block h-2 w-2 rounded-full',
          running
            ? 'bg-teal pulse-teal'
            : status === 'error'
              ? 'bg-fog-text'
              : status === 'done'
                ? 'bg-mist-text'
                : 'bg-steel-text',
        ].join(' ')}
      />
      <span className="font-w510 text-mist-text">{COPY[status]}</span>
      {iterations > 0 && (
        <span className="text-steel-text">
          · {iterations} iteration{iterations === 1 ? '' : 's'}
        </span>
      )}
    </div>
  );
}
