/**
 * Small pure formatting helpers (durations, slugs, filenames, quality tiers).
 * No DOM, no clock: callers pass in the numbers.
 */

/**
 * Format a run duration for the live counter and summaries.
 *   0–59s      → "42s"
 *   ≥ 1 minute → "1m 12s"
 *   ≥ 1 hour   → "1h 02m"
 * Negative / non-finite input is treated as 0.
 */
export function formatElapsed(ms: number): string {
  const totalSeconds = Number.isFinite(ms) && ms > 0 ? Math.floor(ms / 1000) : 0;
  if (totalSeconds < 60) return `${totalSeconds}s`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes < 60) return `${minutes}m ${seconds}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${String(minutes % 60).padStart(2, '0')}m`;
}

/**
 * Format a per-step duration with finer resolution than `formatElapsed`:
 * "840ms", "3.4s", then falls through to `formatElapsed` from one minute.
 */
export function formatStepDuration(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return '0ms';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return formatElapsed(ms);
}

/**
 * Lowercase, ASCII-only, hyphen-separated slug. Accents are folded
 * ("Hipertensão" → "hipertensao"); anything else non-alphanumeric becomes a
 * separator. Capped at `maxLength` characters, never ending on a hyphen.
 */
export function slugify(input: string, maxLength = 60): string {
  const slug = input
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return slug.slice(0, maxLength).replace(/-+$/g, '');
}

/** Filename for a downloaded report: a slug of the topic plus `.md`. */
export function buildMarkdownFilename(topic: string): string {
  return `${slugify(topic) || 'medgent-report'}.md`;
}

export type QualityTier = 'high' | 'moderate' | 'low';

/** Bucket a 0–1 quality score (same thresholds the sources meter uses). */
export function qualityTier(score: number): QualityTier {
  if (score >= 0.75) return 'high';
  if (score >= 0.5) return 'moderate';
  return 'low';
}

/** Clamp a score to [0, 1] and convert to a whole-number percentage. */
export function scorePercent(score: number): number {
  if (!Number.isFinite(score)) return 0;
  return Math.round(Math.min(1, Math.max(0, score)) * 100);
}

/** "meta_analysis" → "Meta analysis". */
export function studyTypeLabel(studyType: string): string {
  const spaced = studyType.replace(/_/g, ' ').trim();
  return spaced ? spaced.charAt(0).toUpperCase() + spaced.slice(1) : 'Unknown';
}
