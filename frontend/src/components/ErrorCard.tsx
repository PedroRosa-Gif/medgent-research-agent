/**
 * Glass card for `error` events: icon + title (never color alone), the error
 * name and backend detail, and a hint about the most common cause. A transport
 * failure (`ConnectionError`) points at the backend / Ollama not running.
 */
import { motion } from 'motion/react';
import { AlertIcon } from './icons';

interface ErrorCardProps {
  name: string;
  detail: string;
}

export function ErrorCard({ name, detail }: ErrorCardProps) {
  const isConnection = name === 'ConnectionError';
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      role="alert"
      className="glass flex gap-3.5 border-l-[3px] border-l-danger-edge px-5 py-4"
    >
      <span className="mt-0.5 text-danger">
        <AlertIcon size={22} />
      </span>
      <div className="min-w-0">
        <h2 className="text-base font-semibold tracking-tight text-fg">
          {isConnection ? 'Can’t reach the research backend' : 'Run interrupted'}
        </h2>
        <p className="mt-1 text-sm text-fg-muted">
          <span className="font-mono text-[13px] text-danger">{name}</span>
          {detail ? <span className="break-words"> — {detail}</span> : null}
        </p>
        <p className="mt-2 text-[13px] text-fg-subtle">
          {isConnection
            ? 'The backend (port 8000) or Ollama may not be running. Start them, then choose Run again.'
            : 'Check the backend logs, and that Ollama is running if you use the local model. You can run again or start a new topic.'}
        </p>
      </div>
    </motion.div>
  );
}
