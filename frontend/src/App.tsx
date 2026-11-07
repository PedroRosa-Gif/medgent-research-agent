/**
 * MedGent — single-page reasoning UI.
 *
 * Composes the one screen: title + tagline, topic input, the reasoning
 * timeline (centerpiece), the live-typing report, the evaluated-studies panel,
 * an error card, and a persistent disclaimer. All run state comes from
 * `useResearchStream`, which owns the EventSource and feeds the pure reducer.
 */

import { useEffect, useRef, type ReactNode } from 'react';
import { TopicInput } from './components/TopicInput';
import { StatusBar } from './components/StatusBar';
import { ReasoningTimeline } from './components/ReasoningTimeline';
import { ReportView } from './components/ReportView';
import { StudiesPanel } from './components/StudiesPanel';
import { ErrorCard } from './components/ErrorCard';
import { Disclaimer } from './components/Disclaimer';
import { useResearchStream } from './lib/useResearchStream';

/** A quiet section shell: label + hairline-bordered body. */
function Section({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="font-w510 text-[13px] uppercase tracking-wide text-steel-text">
        {title}
      </h2>
      <div className="rounded-lg border border-ash-border bg-carbon p-4 sm:p-5">
        {children}
      </div>
    </section>
  );
}

export function App() {
  const { state, start, reset } = useResearchStream();

  // "Follow latest": an anchor at the bottom of the live content that we scroll
  // into view as new timeline steps appear and as report tokens stream in. We
  // key the effect on the number of steps and the report length (both grow
  // monotonically during a run), so each new step/token nudges the view down.
  const followRef = useRef<HTMLDivElement | null>(null);
  const stepCount = state.steps.length;
  const reportLength = state.reportText.length;
  useEffect(() => {
    if (state.status !== 'running') return;
    followRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [state.status, stepCount, reportLength]);

  function handleSubmit(topic: string) {
    // A fresh run after done/error clears the previous timeline + report.
    if (state.status === 'done' || state.status === 'error') reset();
    start(topic);
  }

  return (
    <div className="min-h-screen bg-onyx">
      <main className="mx-auto flex w-full max-w-[780px] flex-col gap-8 px-5 py-12 sm:px-6 sm:py-16">
        {/* Header */}
        <header className="flex flex-col gap-2">
          <div className="flex items-center gap-2.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-teal" aria-hidden="true" />
            <h1 className="font-w590 text-[28px] leading-none text-snow">MedGent</h1>
          </div>
          <p className="text-[14px] text-fog-text">
            Autonomous clinical-literature research agent.
          </p>
        </header>

        {/* Topic input + status */}
        <div className="flex flex-col gap-3">
          <TopicInput status={state.status} onSubmit={handleSubmit} />
          <StatusBar status={state.status} iterations={state.iterations} />
          {state.topic && state.status !== 'idle' && (
            <p className="text-[13px] text-steel-text">
              Topic: <span className="text-mist-text">{state.topic}</span>
            </p>
          )}
        </div>

        {state.status === 'error' && state.error && (
          <ErrorCard name={state.error.name} detail={state.error.detail} />
        )}

        {/* Reasoning timeline — the centerpiece */}
        <Section title="Reasoning">
          <ReasoningTimeline state={state} />
        </Section>

        {/* Report */}
        {(state.reportText || state.status === 'done' || state.status === 'running') && (
          <Section title="Report">
            <ReportView state={state} />
          </Section>
        )}

        {/* Evaluated studies */}
        <StudiesPanel studies={state.studies} />

        {/* Persistent disclaimer */}
        <Disclaimer />

        {/* Scroll anchor: the "follow latest" effect keeps this in view so the
            newest reasoning step / streaming report stays on screen. */}
        <div ref={followRef} aria-hidden="true" />
      </main>
    </div>
  );
}
