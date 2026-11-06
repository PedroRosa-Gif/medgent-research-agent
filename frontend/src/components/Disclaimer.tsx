/**
 * Persistent medical disclaimer. Always visible — this is a study tool, not a
 * source of medical advice. Rendered as a quiet hairline footer.
 */

export function Disclaimer() {
  return (
    <p className="border-t border-smoke pt-4 text-[12px] leading-relaxed text-steel-text">
      <span className="font-w510 text-fog-text">Disclaimer:</span> MedGent is a
      research and study tool for exploring clinical literature. It does not
      provide medical advice, diagnosis, or treatment. Always consult a qualified
      healthcare professional for medical decisions.
    </p>
  );
}
