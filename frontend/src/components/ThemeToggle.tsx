/**
 * Sun / moon button. Shows the icon of the theme you would switch TO, and an
 * explicit label, so the control is understandable without seeing the icon.
 * It is a native <button>: Enter and Space work, and it has a visible focus ring.
 */
import { AnimatePresence, motion } from 'motion/react';
import type { Theme } from '../lib/theme';
import { MoonIcon, SunIcon } from './icons';

interface ThemeToggleProps {
  theme: Theme;
  onToggle: () => void;
}

export function ThemeToggle({ theme, onToggle }: ThemeToggleProps) {
  const next = theme === 'dark' ? 'light' : 'dark';
  return (
    <button
      type="button"
      onClick={onToggle}
      className="btn btn-ghost btn-icon"
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={theme}
          initial={{ opacity: 0, rotate: -50, scale: 0.8 }}
          animate={{ opacity: 1, rotate: 0, scale: 1 }}
          exit={{ opacity: 0, rotate: 50, scale: 0.8 }}
          transition={{ duration: 0.18 }}
          className="flex"
        >
          {theme === 'dark' ? <SunIcon size={19} /> : <MoonIcon size={19} />}
        </motion.span>
      </AnimatePresence>
    </button>
  );
}
