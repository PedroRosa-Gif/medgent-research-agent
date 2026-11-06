/**
 * Non-alarming hairline card for `error` events. No red fills — separation via
 * gray value and a 1px border, matching the Linear restraint. Shows the error
 * name and the detail text from the backend.
 */

import { motion } from 'motion/react';

interface ErrorCardProps {
  name: string;
  detail: string;
}

export function ErrorCard({ name, detail }: ErrorCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      role="alert"
      className="rounded-lg border border-ferrite-border bg-graphite px-4 py-3"
    >
      <p className="font-w590 text-[14px] text-snow">Run interrupted</p>
      <p className="mt-1 text-[13px] text-mist-text">
        <span className="font-mono text-[12.5px] text-fog-text">{name}</span>
        {detail ? ` — ${detail}` : ''}
      </p>
      <p className="mt-1.5 text-[12.5px] text-steel-text">
        You can edit the topic and start a new run.
      </p>
    </motion.div>
  );
}
