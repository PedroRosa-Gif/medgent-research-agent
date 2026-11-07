/**
 * Idle state: brand mark, display title, tagline, the composer (passed as
 * children), keyboard hints, example-topic chips, and a one-line "how it works".
 */
import { motion } from 'motion/react';
import type { ReactNode } from 'react';
import { EXAMPLE_TOPICS } from '../lib/examples';
import { Logo } from './Logo';
import { NODE_META } from './nodeMeta';
import { SparkleIcon } from './icons';

interface HeroProps {
  children: ReactNode;
  onPickExample: (topic: string) => void;
}

const HOW_IT_WORKS = [
  { node: 'planner', text: 'Plans the search' },
  { node: 'fetch_evidence', text: 'Searches PubMed and the web' },
  { node: 'evaluator', text: 'Appraises study quality' },
  { node: 'synthesizer', text: 'Writes a cited report' },
] as const;

export function Hero({ children, onPickExample }: HeroProps) {
  return (
    <motion.section
      aria-labelledby="hero-title"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: 'easeOut' }}
      className="flex flex-col items-center pt-[clamp(1.5rem,9vh,5.5rem)] pb-10 text-center"
    >
      <div className="relative mb-6">
        <span
          className="absolute inset-0 -z-10 scale-150 rounded-full bg-accent/30 blur-2xl"
          aria-hidden="true"
        />
        <Logo size={72} className="drop-shadow-[0_10px_28px_rgba(45,212,191,0.35)]" />
      </div>

      <h1
        id="hero-title"
        className="text-gradient text-[clamp(2.75rem,9vw,4.25rem)] font-semibold leading-none tracking-[-0.04em]"
      >
        MedGent
      </h1>
      <p className="mt-4 max-w-md text-balance text-base text-fg-muted sm:text-lg">
        Autonomous clinical-literature research agent
      </p>

      <div className="mt-9 w-full">{children}</div>

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

      <ul
        className="mt-14 grid w-full grid-cols-2 gap-x-4 gap-y-3 text-left text-[13px] text-fg-muted sm:grid-cols-4"
        aria-label="How MedGent works"
      >
        {HOW_IT_WORKS.map(({ node, text }, index) => {
          const { Icon } = NODE_META[node];
          return (
            <li key={node} className="flex items-center gap-2.5">
              <span className="glass-soft flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-accent-text">
                <Icon className="h-4 w-4" />
              </span>
              <span>
                <span className="mr-1 font-mono text-[11px] text-fg-subtle">0{index + 1}</span>
                {text}
              </span>
            </li>
          );
        })}
      </ul>
    </motion.section>
  );
}
