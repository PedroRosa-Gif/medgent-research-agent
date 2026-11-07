/**
 * Thin DOM/localStorage binding for the pure theme logic in `theme.ts`.
 *
 * The inline script in `index.html` has already set `data-theme` on <html>
 * before React loads (so there is no flash); this hook reads that back as the
 * initial state, then keeps the attribute, `color-scheme`, the
 * `<meta name="theme-color">` tags, and localStorage in sync on every change.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  THEME_COLORS,
  THEME_STORAGE_KEY,
  isTheme,
  resolveInitialTheme,
  toggleTheme,
  type Theme,
} from './theme';

function readInitialTheme(): Theme {
  const applied = document.documentElement.getAttribute('data-theme');
  if (isTheme(applied)) return applied;
  try {
    return resolveInitialTheme(localStorage.getItem(THEME_STORAGE_KEY));
  } catch {
    // Storage can throw (privacy mode, blocked cookies): fall back to default.
    return resolveInitialTheme(null);
  }
}

function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  root.setAttribute('data-theme', theme);
  root.style.colorScheme = theme;
  // The media-variant tags follow the OS; our toggle is independent of it, so
  // pin them to the chosen theme once the user (or storage) has decided.
  document
    .querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]')
    .forEach((meta) => meta.setAttribute('content', THEME_COLORS[theme]));
}

export interface UseTheme {
  theme: Theme;
  toggle: () => void;
}

export function useTheme(): UseTheme {
  const [theme, setTheme] = useState<Theme>(readInitialTheme);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const toggle = useCallback(() => {
    setTheme((current) => {
      const next = toggleTheme(current);
      try {
        localStorage.setItem(THEME_STORAGE_KEY, next);
      } catch {
        // Non-fatal: the choice just won't persist.
      }
      return next;
    });
  }, []);

  return { theme, toggle };
}
