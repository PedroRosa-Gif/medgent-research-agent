import { describe, expect, it } from 'vitest';
import {
  DEFAULT_THEME,
  THEME_COLORS,
  THEME_STORAGE_KEY,
  isTheme,
  resolveInitialTheme,
  toggleTheme,
} from './theme';

describe('theme', () => {
  it('defaults to dark when nothing is stored (does not follow the OS)', () => {
    expect(DEFAULT_THEME).toBe('dark');
    expect(resolveInitialTheme(null)).toBe('dark');
    expect(resolveInitialTheme(undefined)).toBe('dark');
    expect(resolveInitialTheme('')).toBe('dark');
  });

  it('honours a valid stored value', () => {
    expect(resolveInitialTheme('light')).toBe('light');
    expect(resolveInitialTheme('dark')).toBe('dark');
  });

  it('falls back to dark for invalid stored values', () => {
    expect(resolveInitialTheme('Light')).toBe('dark');
    expect(resolveInitialTheme('system')).toBe('dark');
    expect(resolveInitialTheme('{"theme":"light"}')).toBe('dark');
  });

  it('validates themes', () => {
    expect(isTheme('dark')).toBe(true);
    expect(isTheme('light')).toBe(true);
    expect(isTheme('auto')).toBe(false);
    expect(isTheme(null)).toBe(false);
    expect(isTheme(1)).toBe(false);
  });

  it('toggles between the two themes and is its own inverse', () => {
    expect(toggleTheme('dark')).toBe('light');
    expect(toggleTheme('light')).toBe('dark');
    expect(toggleTheme(toggleTheme('dark'))).toBe('dark');
  });

  it('exposes a stable storage key and a color per theme', () => {
    expect(THEME_STORAGE_KEY).toBe('medgent-theme');
    expect(THEME_COLORS.dark).toMatch(/^#[0-9a-f]{6}$/i);
    expect(THEME_COLORS.light).toMatch(/^#[0-9a-f]{6}$/i);
    expect(THEME_COLORS.dark).not.toBe(THEME_COLORS.light);
  });
});
