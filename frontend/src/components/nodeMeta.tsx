/**
 * Per-node presentation metadata for the reasoning timeline: a short label and
 * a small monochrome line icon. Icons are inline SVGs (no icon dependency) so
 * they inherit `currentColor` and stay crisp on the dark canvas.
 *
 * This is a metadata module, not a refreshable component file — its public
 * export is the `NODE_META` map, so the react-refresh "only export components"
 * rule does not apply here.
 */
/* eslint-disable react-refresh/only-export-components */

import type { ReactNode } from 'react';
import type { NodeName } from '../lib/events';

interface IconProps {
  className?: string;
}

function Icon({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

const PlannerIcon = ({ className }: IconProps) => (
  <Icon className={className}>
    <path d="M9 3h6M4 7h16M6 11h12M8 15h8M10 19h4" />
  </Icon>
);

const FetchIcon = ({ className }: IconProps) => (
  <Icon className={className}>
    <circle cx="11" cy="11" r="6" />
    <path d="m20 20-3.5-3.5" />
  </Icon>
);

const EvaluatorIcon = ({ className }: IconProps) => (
  <Icon className={className}>
    <path d="M12 3v18M5 7l-2 6a4 4 0 0 0 8 0L9 7M19 7l-2 6a4 4 0 0 0 8 0l-2-6" />
  </Icon>
);

const RefineIcon = ({ className }: IconProps) => (
  <Icon className={className}>
    <path d="M3 12a9 9 0 0 1 15-6.7L21 8M21 3v5h-5M21 12a9 9 0 0 1-15 6.7L3 16M3 21v-5h5" />
  </Icon>
);

const SynthesizerIcon = ({ className }: IconProps) => (
  <Icon className={className}>
    <path d="M4 4h16v16H4zM8 9h8M8 13h8M8 17h5" />
  </Icon>
);

export interface NodeMeta {
  label: string;
  Icon: (props: IconProps) => ReactNode;
}

export const NODE_META: Record<NodeName, NodeMeta> = {
  planner: { label: 'Planner', Icon: PlannerIcon },
  fetch_evidence: { label: 'Fetch evidence', Icon: FetchIcon },
  evaluator: { label: 'Evaluator', Icon: EvaluatorIcon },
  refine_queries: { label: 'Refine queries', Icon: RefineIcon },
  synthesizer: { label: 'Synthesizer', Icon: SynthesizerIcon },
};
