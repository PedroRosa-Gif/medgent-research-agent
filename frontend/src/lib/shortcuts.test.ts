import { describe, expect, it } from 'vitest';
import { resolveShortcut, type ShortcutInput } from './shortcuts';

function input(overrides: Partial<ShortcutInput>): ShortcutInput {
  return {
    key: '',
    ctrlKey: false,
    metaKey: false,
    altKey: false,
    targetIsEditable: false,
    isRunning: false,
    ...overrides,
  };
}

describe('resolveShortcut', () => {
  it('"/" focuses the composer unless typing in a field', () => {
    expect(resolveShortcut(input({ key: '/' }))).toBe('focus-composer');
    expect(resolveShortcut(input({ key: '/', targetIsEditable: true }))).toBeNull();
  });

  it('Ctrl/Cmd+K focuses the composer, even while typing', () => {
    expect(resolveShortcut(input({ key: 'k', ctrlKey: true }))).toBe('focus-composer');
    expect(resolveShortcut(input({ key: 'K', metaKey: true, targetIsEditable: true }))).toBe(
      'focus-composer',
    );
    expect(resolveShortcut(input({ key: 'k' }))).toBeNull();
  });

  it('Escape stops only a running run outside editable fields', () => {
    expect(resolveShortcut(input({ key: 'Escape', isRunning: true }))).toBe('stop');
    expect(resolveShortcut(input({ key: 'Escape', isRunning: false }))).toBeNull();
    expect(
      resolveShortcut(input({ key: 'Escape', isRunning: true, targetIsEditable: true })),
    ).toBeNull();
  });

  it('ignores plain keys carrying modifiers and IME composition', () => {
    expect(resolveShortcut(input({ key: '/', ctrlKey: true }))).toBeNull();
    expect(resolveShortcut(input({ key: 'Escape', isRunning: true, altKey: true }))).toBeNull();
    expect(resolveShortcut(input({ key: '/', isComposing: true }))).toBeNull();
  });

  it('returns null for unrelated keys', () => {
    expect(resolveShortcut(input({ key: 'a' }))).toBeNull();
    expect(resolveShortcut(input({ key: 'Enter' }))).toBeNull();
  });
});
