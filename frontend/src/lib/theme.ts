/**
 * Pure theme logic. No DOM, no storage: `useTheme` (the thin hook) owns
 * `document` and `localStorage`; everything decidable lives here so it can be
 * unit-tested in Node.
 *
 * Policy: dark is the default. We deliberately do NOT follow the OS
 * `prefers-color-scheme`; only an explicit, valid stored choice overrides dark.
 *
 * NOTE: `index.html` carries a tiny inline script that repeats this resolution
 * (it must run before React to avoid a flash of the wrong theme). If you change
 * the key, the default, or the accepted values here, change it there too.
 */

export type Theme = 'dark' | 'light';

/** localStorage key for the persisted choice. */
export const THEME_STORAGE_KEY = 'medgent-theme';

export const DEFAULT_THEME: Theme = 'dark';

/** Page base colors, mirrored into `<meta name="theme-color">`. */
export const THEME_COLORS: Record<Theme, string> = {
  dark: '#060912',
  light: '#f3f6fc',
};

/** Type guard: is `value` one of the supported themes? */
export function isTheme(value: unknown): value is Theme {
  return value === 'dark' || value === 'light';
}

/**
 * Resolve the theme to use on load from a raw stored value (which may be
 * `null`, missing, or garbage from an older/hand-edited entry).
 */
export function resolveInitialTheme(stored: string | null | undefined): Theme {
  return isTheme(stored) ? stored : DEFAULT_THEME;
}

/** The other theme. */
export function toggleTheme(theme: Theme): Theme {
  return theme === 'dark' ? 'light' : 'dark';
}
