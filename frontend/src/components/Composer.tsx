/**
 * The composer: one large glass input with the submit button inside it.
 *
 * - `Enter` submits (native <form> behaviour).
 * - While a run is active the field is read-only (it shows the active topic)
 *   and the submit button becomes a Stop button.
 * - The focus glow ring is drawn by the form (`.composer:focus-within`), so the
 *   bare input needs no outline of its own.
 *
 * Fully controlled: the parent owns `value` so "New research" can clear it and
 * example chips can fill it.
 */
import type { FormEvent, RefObject } from 'react';
import type { RunStatus } from '../lib/reasoningReducer';
import { ArrowUpIcon, SearchIcon, StopIcon } from './icons';

interface ComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (topic: string) => void;
  onStop: () => void;
  status: RunStatus;
  inputRef: RefObject<HTMLInputElement | null>;
  /** `hero` is the large idle composer; `compact` sits under the sticky header. */
  size: 'hero' | 'compact';
}

export function Composer({
  value,
  onChange,
  onSubmit,
  onStop,
  status,
  inputRef,
  size,
}: ComposerProps) {
  const running = status === 'running';
  const hero = size === 'hero';

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const topic = value.trim();
    if (!topic || running) return;
    onSubmit(topic);
  }

  return (
    <form
      onSubmit={handleSubmit}
      role="search"
      aria-label="Start a research"
      className={[
        'composer glass-strong flex w-full items-center gap-2',
        hero ? 'rounded-[22px] p-2.5 pl-5' : 'rounded-2xl p-2 pl-4',
      ].join(' ')}
    >
      <SearchIcon size={hero ? 22 : 20} className="shrink-0 text-fg-subtle" />
      <label htmlFor="topic" className="sr-only">
        Clinical research topic
      </label>
      <input
        id="topic"
        ref={inputRef}
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        readOnly={running}
        autoComplete="off"
        spellCheck={false}
        enterKeyHint="search"
        placeholder="Ask a clinical question, e.g. metformin for type 2 diabetes"
        className={[
          'min-w-0 flex-1 truncate bg-transparent text-fg outline-none placeholder:text-fg-subtle read-only:cursor-default',
          hero ? 'h-12 text-base sm:text-lg' : 'h-10 text-base',
        ].join(' ')}
      />

      {running ? (
        <button
          type="button"
          onClick={onStop}
          className={['btn btn-ghost shrink-0', hero ? 'h-12' : ''].join(' ')}
          aria-label="Stop research"
          aria-keyshortcuts="Escape"
        >
          <StopIcon size={16} className="text-danger" />
          <span>Stop</span>
          <span className="kbd hidden sm:inline-flex" aria-hidden="true">
            Esc
          </span>
        </button>
      ) : (
        <button
          type="submit"
          disabled={!value.trim()}
          className={[
            'btn btn-primary shrink-0',
            hero ? 'h-12 px-4 sm:px-5' : 'btn-icon',
          ].join(' ')}
          aria-label="Start research"
        >
          {hero && <span className="hidden sm:inline">Research</span>}
          <ArrowUpIcon size={18} />
        </button>
      )}
    </form>
  );
}
