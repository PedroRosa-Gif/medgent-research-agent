/**
 * Global keyboard shortcuts. Collects the impure facts (the event, the focused
 * element) and defers the decision to the pure `resolveShortcut`.
 */

import { useEffect, useRef } from 'react';
import { resolveShortcut } from './shortcuts';

interface ShortcutHandlers {
  isRunning: boolean;
  onFocusComposer: () => void;
  onStop: () => void;
}

/** Can the user type into this element right now? Read-only inputs can't. */
function isEditable(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) {
    return !target.readOnly && !target.disabled;
  }
  return target instanceof HTMLSelectElement;
}

export function useShortcuts(handlers: ShortcutHandlers): void {
  // Keep the latest handlers in a ref so the listener is attached once.
  const latest = useRef(handlers);
  useEffect(() => {
    latest.current = handlers;
  });

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const { isRunning, onFocusComposer, onStop } = latest.current;
      const action = resolveShortcut({
        key: event.key,
        ctrlKey: event.ctrlKey,
        metaKey: event.metaKey,
        altKey: event.altKey,
        isComposing: event.isComposing,
        targetIsEditable: isEditable(event.target),
        isRunning,
      });
      if (!action) return;
      event.preventDefault();
      if (action === 'focus-composer') onFocusComposer();
      else onStop();
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);
}
