/**
 * Medical disclaimer, rendered as a refined notice in the page footer. This is a
 * study tool, not a source of medical advice.
 */
import { InfoIcon } from './icons';

export function Disclaimer() {
  return (
    <p className="glass-soft flex items-start gap-3 px-4 py-3 text-left text-xs leading-relaxed text-fg-muted">
      <InfoIcon size={16} className="mt-px shrink-0 text-fg-subtle" />
      <span>
        <span className="font-medium text-fg">Study tool, not medical advice.</span> MedGent
        explores clinical literature for research and learning. It does not provide diagnosis or
        treatment. Consult a qualified healthcare professional for medical decisions.
      </span>
    </p>
  );
}
