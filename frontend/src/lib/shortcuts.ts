/**
 * Pure keyboard-shortcut resolution. The hook (`useShortcuts`) reads the real
 * `KeyboardEvent` + `document.activeElement` and hands plain values to
 * `resolveShortcut`; the decision itself is DOM-free and unit-tested.
 *
 *   /            → focus the composer (not while typing in a text field)
 *   Ctrl/Cmd + K → focus the composer (works even while typing)
 *   Esc          → stop a running research (not while editing another field)
 *
 * `Enter` submits through the composer's own <form>, so it is not handled here.
 */

export type ShortcutAction = 'focus-composer' | 'stop';

export interface ShortcutInput {
  key: string;
  ctrlKey: boolean;
  metaKey: boolean;
  altKey: boolean;
  /** True when the event target is a field the user can type into. */
  targetIsEditable: boolean;
  isRunning: boolean;
  /** True while an IME composition is active (never hijack those keys). */
  isComposing?: boolean;
}

export function resolveShortcut(input: ShortcutInput): ShortcutAction | null {
  const { key, ctrlKey, metaKey, altKey, targetIsEditable, isRunning } = input;
  if (input.isComposing) return null;

  if ((ctrlKey || metaKey) && !altKey && key.toLowerCase() === 'k') {
    return 'focus-composer';
  }

  // Remaining shortcuts are plain keys; ignore any with modifiers.
  if (ctrlKey || metaKey || altKey) return null;

  if (key === '/' && !targetIsEditable) return 'focus-composer';
  if (key === 'Escape' && isRunning && !targetIsEditable) return 'stop';
  return null;
}
