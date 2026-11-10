/**
 * Run status as a small pill: an icon + a word, so state is never conveyed by
 * color alone. Accent is used for the live "Researching" state only.
 */
import type { ReactNode } from 'react';
import type { RunStatus } from '../lib/reasoningReducer';
import { AlertIcon, CheckIcon, StopIcon } from './icons';

interface StatusPillProps {
  status: RunStatus;
}

const LABEL: Record<RunStatus, string> = {
  idle: 'Ready',
  running: 'Researching',
  done: 'Complete',
  error: 'Error',
  cancelled: 'Stopped',
};

function Indicator({ status }: { status: RunStatus }): ReactNode {
  switch (status) {
    case 'running':
      return (
        <span
          className="dot-pulse inline-block h-2 w-2 rounded-full bg-accent"
          aria-hidden="true"
        />
      );
    case 'done':
      return <CheckIcon size={14} className="text-ok" />;
    case 'error':
      return <AlertIcon size={14} className="text-danger" />;
    case 'cancelled':
      return <StopIcon size={14} className="text-fg-muted" />;
    default:
      return (
        <span className="inline-block h-2 w-2 rounded-full bg-fg-subtle" aria-hidden="true" />
      );
  }
}

export function StatusPill({ status }: StatusPillProps) {
  return (
    <span
      className="glass-soft inline-flex h-8 items-center gap-2 rounded-full px-3 text-[13px] font-medium text-fg"
      role="status"
    >
      <Indicator status={status} />
      {LABEL[status]}
    </span>
  );
}
