import { describe, expect, it } from 'vitest';
import {
  buildMarkdownFilename,
  formatElapsed,
  formatStepDuration,
  qualityTier,
  scorePercent,
  slugify,
  studyTypeLabel,
} from './format';

describe('formatElapsed', () => {
  it('formats seconds, minutes and hours', () => {
    expect(formatElapsed(0)).toBe('0s');
    expect(formatElapsed(999)).toBe('0s');
    expect(formatElapsed(42_000)).toBe('42s');
    expect(formatElapsed(59_999)).toBe('59s');
    expect(formatElapsed(60_000)).toBe('1m 0s');
    expect(formatElapsed(72_000)).toBe('1m 12s');
    expect(formatElapsed(3_720_000)).toBe('1h 02m');
  });

  it('treats negative and non-finite input as zero', () => {
    expect(formatElapsed(-5)).toBe('0s');
    expect(formatElapsed(Number.NaN)).toBe('0s');
    expect(formatElapsed(Number.POSITIVE_INFINITY)).toBe('0s');
  });
});

describe('formatStepDuration', () => {
  it('uses ms, then one-decimal seconds, then minutes', () => {
    expect(formatStepDuration(840)).toBe('840ms');
    expect(formatStepDuration(3_400)).toBe('3.4s');
    expect(formatStepDuration(72_000)).toBe('1m 12s');
    expect(formatStepDuration(-1)).toBe('0ms');
  });
});

describe('slugify / buildMarkdownFilename', () => {
  it('slugifies a topic', () => {
    expect(slugify('Efficacy of metformin for type 2 diabetes')).toBe(
      'efficacy-of-metformin-for-type-2-diabetes',
    );
  });

  it('folds accents and collapses punctuation', () => {
    expect(slugify('  Hipertensão: IECA vs. BRA?! ')).toBe('hipertensao-ieca-vs-bra');
  });

  it('caps the length without leaving a trailing hyphen', () => {
    const slug = slugify('word '.repeat(40), 12);
    expect(slug.length).toBeLessThanOrEqual(12);
    expect(slug.endsWith('-')).toBe(false);
  });

  it('builds a .md filename with a safe fallback', () => {
    expect(buildMarkdownFilename('SGLT2 inhibitors in heart failure')).toBe(
      'sglt2-inhibitors-in-heart-failure.md',
    );
    expect(buildMarkdownFilename('???')).toBe('medgent-report.md');
    expect(buildMarkdownFilename('')).toBe('medgent-report.md');
  });
});

describe('quality helpers', () => {
  it('buckets scores into tiers at 0.5 and 0.75', () => {
    expect(qualityTier(0.95)).toBe('high');
    expect(qualityTier(0.75)).toBe('high');
    expect(qualityTier(0.74)).toBe('moderate');
    expect(qualityTier(0.5)).toBe('moderate');
    expect(qualityTier(0.49)).toBe('low');
  });

  it('converts scores to clamped percentages', () => {
    expect(scorePercent(0.876)).toBe(88);
    expect(scorePercent(1.4)).toBe(100);
    expect(scorePercent(-1)).toBe(0);
    expect(scorePercent(Number.NaN)).toBe(0);
  });

  it('humanizes study types', () => {
    expect(studyTypeLabel('meta_analysis')).toBe('Meta analysis');
    expect(studyTypeLabel('rct')).toBe('Rct');
    expect(studyTypeLabel('')).toBe('Unknown');
  });
});
