/** Inline notice shown after the user stops a run. */
import { motion } from 'motion/react';
import { StopIcon } from './icons';

export function StoppedNotice() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      role="status"
      className="glass-soft flex items-start gap-3 px-4 py-3 text-sm"
    >
      <span className="mt-0.5 text-fg-muted">
        <StopIcon size={16} />
      </span>
      <p className="text-fg-muted">
        <span className="font-medium text-fg">Research stopped.</span> What arrived before you
        stopped is shown below. The server may still finish the run in the background.
      </p>
    </motion.div>
  );
}
