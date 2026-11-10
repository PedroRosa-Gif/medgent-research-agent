/**
 * Idle state: display title, tagline, a two-sentence explanation of what MedGent
 * is, the composer (passed as children), keyboard hints and example-topic chips.
 * Deliberately sparse: no logo here (the header carries the small mark).
 */
import { motion } from 'motion/react';
import type { ReactNode } from 'react';
import { EXAMPLE_TOPICS } from '../lib/examples';
import { SparkleIcon } from './icons';

interface HeroProps {
  children: ReactNode;
  onPickExample: (topic: string) => void;
}

export function Hero({ children, onPickExample }: HeroProps) {
  return (
    <motion.section
      aria-labelledby="hero-title"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: 'easeOut' }}
      className="flex flex-col items-center pt-[clamp(2rem,11vh,6.5rem)] pb-10 text-center"
    >
      <h1
        id="hero-title"
        className="text-gradient text-[clamp(2.75rem,9vw,4.25rem)] font-semibold leading-none tracking-[-0.04em]"
      >
        MedGent
      </h1>
      <p className="mt-4 max-w-md text-balance text-base text-fg-muted sm:text-lg">
        Autonomous clinical-literature research agent
      </p>
      <p className="mt-3 max-w-xl text-balance text-sm leading-relaxed text-fg-subtle sm:text-[15px]">
        Give it a clinical topic and it plans the search, queries PubMed and the web, appraises the
        evidence and writes a cited report. Its reasoning is shown along the way.
      </p>

      <div className="mt-10 w-full">{children}</div>

      <p className="mt-3 hidden items-center gap-1.5 text-xs text-fg-subtle sm:flex">
        <span className="kbd">Enter</span> to research
        <span aria-hidden="true">·</span>
        <span className="kbd">/</span> to focus
        <span aria-hidden="true">·</span>
        <span className="kbd">Esc</span> to stop
      </p>

      <div className="mt-8 w-full">
        <p className="mb-3 flex items-center justify-center gap-1.5 text-[13px] font-medium text-fg-muted">
          <SparkleIcon size={14} className="text-accent-text" />
          Try an example
        </p>
        <ul className="flex flex-wrap justify-center gap-2.5">
          {EXAMPLE_TOPICS.map((topic) => (
            <li key={topic}>
              <button
                type="button"
                onClick={() => onPickExample(topic)}
                className="glass-soft glass-interactive min-h-10 rounded-full px-4 py-2 text-sm text-fg hover:-translate-y-0.5"
              >
                {topic}
              </button>
            </li>
          ))}
        </ul>
      </div>

    </motion.section>
  );
}
