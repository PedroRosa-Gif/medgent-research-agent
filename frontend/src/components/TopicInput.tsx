/**
 * Topic entry: a text field plus an outlined pill "Research" button. Input and
 * button are disabled while a run is in progress; an idle/done/error run can be
 * started fresh (App resets state first).
 */

import { useState, type FormEvent } from 'react';
import type { RunStatus } from '../lib/reasoningReducer';

interface TopicInputProps {
  status: RunStatus;
  onSubmit: (topic: string) => void;
}

export function TopicInput({ status, onSubmit }: TopicInputProps) {
  const [value, setValue] = useState('');
  const running = status === 'running';

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const topic = value.trim();
    if (!topic || running) return;
    onSubmit(topic);
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-3 sm:flex-row sm:items-center"
    >
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        disabled={running}
        placeholder="e.g. Efficacy of metformin for type 2 diabetes"
        aria-label="Clinical research topic"
        className="font-w510 h-10 flex-1 rounded border border-smoke bg-carbon px-3.5 text-[15px] text-snow placeholder:text-fog-text focus:border-ash-border focus:outline-none disabled:opacity-50"
      />
      <button
        type="submit"
        disabled={running || !value.trim()}
        className="font-w510 h-10 shrink-0 rounded-full border border-snow px-5 text-[14px] text-snow transition-colors hover:bg-snow/5 disabled:cursor-not-allowed disabled:border-ash-border disabled:text-fog-text disabled:hover:bg-transparent"
      >
        {running ? 'Researching…' : 'Research'}
      </button>
    </form>
  );
}
