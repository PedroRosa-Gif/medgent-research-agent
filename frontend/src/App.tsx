/**
 * MedGent: single-page reasoning UI.
 *
 * Two layouts of the same page:
 *   - idle:   a centered hero with the composer and example chips,
 *   - active: a sticky glass header, the composer showing the topic, then the
 *             transcript (reasoning → report → actions → sources) in a ~780px
 *             column.
 *
 * All run state comes from `useResearchStream` (EventSource + pure reducer).
 * This component only wires hooks to presentational components.
 */

import { AnimatePresence, MotionConfig, useReducedMotion } from 'motion/react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ActionBar } from './components/ActionBar';
import { AmbientBackground } from './components/AmbientBackground';
import { Composer } from './components/Composer';
import { Disclaimer } from './components/Disclaimer';
import { ErrorCard } from './components/ErrorCard';
import { Header } from './components/Header';
import { Hero } from './components/Hero';
import { ReasoningSection } from './components/ReasoningTimeline';
import { ReportView } from './components/ReportView';
import { SourcesPanel } from './components/SourcesPanel';
import { StoppedNotice } from './components/StoppedNotice';
import { downloadTextFile } from './lib/download';
import { buildMarkdownFilename } from './lib/format';
import { useClipboard } from './lib/useClipboard';
import { useFollowLatest } from './lib/useFollowLatest';
import { useNow } from './lib/useNow';
import { useResearchStream } from './lib/useResearchStream';
import { useShortcuts } from './lib/useShortcuts';
import { useTheme } from './lib/useTheme';

export function App() {
  const { state, start, cancel, reset } = useResearchStream();
  const { theme, toggle: toggleTheme } = useTheme();
  const { copied, failed: copyFailed, copy } = useClipboard();
  const reducedMotion = useReducedMotion() ?? false;

  const [draft, setDraft] = useState('');
  const inputRef = useRef<HTMLInputElement | null>(null);

  const idle = state.status === 'idle';
  const running = state.status === 'running';
  const ended = !idle && !running;

  // Elapsed time: live while running, frozen at `endedAt` afterwards.
  const now = useNow(running);
  const elapsedMs =
    state.startedAt === undefined ? 0 : (state.endedAt ?? now) - state.startedAt;

  // Follow the newest step / streamed token (monotonic signal).
  const followRef = useFollowLatest(
    running,
    state.steps.length + state.reportText.length,
    !reducedMotion,
  );

  const focusComposer = useCallback(() => {
    const input = inputRef.current;
    if (!input) return;
    input.focus();
    input.select();
  }, []);

  // After "New research" the hero mounts on the next render; focus it then.
  const pendingFocus = useRef(false);
  useEffect(() => {
    if (idle && pendingFocus.current) {
      pendingFocus.current = false;
      inputRef.current?.focus();
    }
  }, [idle]);

  useShortcuts({ isRunning: running, onFocusComposer: focusComposer, onStop: cancel });

  function runTopic(topic: string) {
    const trimmed = topic.trim();
    if (!trimmed || running) return;
    setDraft(trimmed);
    start(trimmed);
  }

  function handleNewResearch() {
    reset();
    setDraft('');
    pendingFocus.current = true;
    window.scrollTo({ top: 0, behavior: reducedMotion ? 'auto' : 'smooth' });
  }

  function handleCopy() {
    void copy(state.reportText);
  }

  function handleDownload() {
    downloadTextFile(buildMarkdownFilename(state.topic), state.reportText);
  }

  const composer = (
    <Composer
      value={running ? state.topic : draft}
      onChange={setDraft}
      onSubmit={runTopic}
      onStop={cancel}
      status={state.status}
      inputRef={inputRef}
      size={idle ? 'hero' : 'compact'}
    />
  );

  const showReport =
    state.reportText.length > 0 ||
    state.status === 'done' ||
    state.steps.some((step) => step.node === 'synthesizer');

  // Re-key per run so collapse/expand state resets for each new run.
  const runKey = state.startedAt ?? state.nextStepId;

  return (
    <MotionConfig reducedMotion="user">
      <div className="relative isolate flex min-h-dvh flex-col">
        <AmbientBackground />

        <a
          href="#main"
          className="btn btn-primary fixed left-4 top-3 z-50 -translate-y-20 focus:translate-y-0"
        >
          Skip to content
        </a>

        <div className="relative z-10 flex min-h-dvh flex-1 flex-col">
          <Header
            compact={!idle}
            status={state.status}
            elapsedMs={elapsedMs}
            theme={theme}
            onToggleTheme={toggleTheme}
          />

          <main
            id="main"
            aria-busy={running}
            className="mx-auto w-full max-w-[780px] flex-1 px-4 pb-10 sm:px-6"
          >
            {idle ? (
              <Hero onPickExample={runTopic}>{composer}</Hero>
            ) : (
              <div className="flex flex-col gap-6 pt-6">
                {composer}

                <ReasoningSection key={`reasoning-${runKey}`} state={state} elapsedMs={elapsedMs} />

                {state.status === 'error' && state.error && (
                  <ErrorCard name={state.error.name} detail={state.error.detail} />
                )}
                {state.status === 'cancelled' && <StoppedNotice />}

                {showReport && <ReportView state={state} />}

                <AnimatePresence>
                  {ended && (
                    <ActionBar
                      key="actions"
                      hasReport={state.reportText.length > 0}
                      copied={copied}
                      copyFailed={copyFailed}
                      onNewResearch={handleNewResearch}
                      onRunAgain={() => runTopic(state.topic)}
                      onCopy={handleCopy}
                      onDownload={handleDownload}
                    />
                  )}
                </AnimatePresence>

                <SourcesPanel key={`sources-${runKey}`} studies={state.studies} />

                {/* "Follow latest" anchor, kept in view while a run is active. */}
                <div ref={followRef} className="scroll-mb-24" aria-hidden="true" />
              </div>
            )}
          </main>

          <footer className="mx-auto w-full max-w-[780px] px-4 pb-6 sm:px-6">
            <Disclaimer />
          </footer>
        </div>
      </div>
    </MotionConfig>
  );
}
