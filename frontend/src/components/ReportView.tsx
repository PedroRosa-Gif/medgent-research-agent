/**
 * Renders the synthesized report as Markdown. While `token` events stream in,
 * `reportText` grows and the view re-renders so the report "types out", with a
 * blinking caret during the run. Bare URLs and bracketed PMIDs in prose are
 * linkified (teal accent) via a custom text renderer.
 */

import { motion } from 'motion/react';
import type { ReactNode } from 'react';
import Markdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { linkifyCitations } from '../lib/citations';
import type { ReasoningState } from '../lib/reasoningReducer';

interface ReportViewProps {
  state: ReasoningState;
}

/** Teal citation / markdown link. */
function CitationLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-teal underline decoration-teal/40 underline-offset-2 hover:decoration-teal"
    >
      {children}
    </a>
  );
}

/** Turn a plain-text node into text + linkified citations. */
function linkifyNode(node: ReactNode): ReactNode {
  if (typeof node !== 'string') return node;
  const tokens = linkifyCitations(node);
  if (tokens.length === 1 && tokens[0].kind === 'text') return node;
  return tokens.map((t, i) =>
    t.kind === 'text' ? (
      <span key={i}>{t.value}</span>
    ) : (
      <CitationLink key={i} href={t.href}>
        {t.value}
      </CitationLink>
    ),
  );
}

function linkifyChildren(children: ReactNode): ReactNode {
  if (Array.isArray(children)) return children.map(linkifyNode);
  return linkifyNode(children);
}

const MARKDOWN_COMPONENTS: Components = {
  a: ({ href, children }) => (
    <CitationLink href={href ?? '#'}>{children}</CitationLink>
  ),
  h1: ({ children }) => (
    <h1 className="font-w590 mb-3 mt-5 text-[22px] text-snow first:mt-0">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="font-w590 mb-2 mt-5 text-[18px] text-snow first:mt-0">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="font-w510 mb-1.5 mt-4 text-[15px] text-snow first:mt-0">
      {children}
    </h3>
  ),
  p: ({ children }) => (
    <p className="mb-3 text-[15px] leading-relaxed text-mist-text">
      {linkifyChildren(children)}
    </p>
  ),
  li: ({ children }) => (
    <li className="mb-1 ml-5 list-disc text-[15px] leading-relaxed text-mist-text marker:text-steel-text">
      {linkifyChildren(children)}
    </li>
  ),
  ul: ({ children }) => <ul className="mb-3">{children}</ul>,
  ol: ({ children }) => (
    <ol className="mb-3 ml-5 list-decimal text-[15px] text-mist-text marker:text-steel-text">
      {children}
    </ol>
  ),
  code: ({ children }) => (
    <code className="rounded bg-graphite px-1.5 py-0.5 font-mono text-[13px] text-mist-text">
      {children}
    </code>
  ),
  table: ({ children }) => (
    <div className="mb-3 overflow-x-auto">
      <table className="w-full border-collapse text-[13.5px]">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="font-w510 border-b border-ash-border px-2 py-1.5 text-left text-mist-text">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border-b border-smoke px-2 py-1.5 text-fog-text">
      {linkifyChildren(children)}
    </td>
  ),
  blockquote: ({ children }) => (
    <blockquote className="mb-3 border-l-2 border-ash-border pl-3 text-mist-text">
      {children}
    </blockquote>
  ),
};

export function ReportView({ state }: ReportViewProps) {
  const { reportText, status } = state;
  const typing = status === 'running' && reportText.length > 0;

  if (!reportText) {
    return (
      <p className="text-[14px] text-steel-text">
        The synthesized report will appear here once the agent has gathered
        sufficient evidence.
      </p>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      <Markdown remarkPlugins={[remarkGfm]} components={MARKDOWN_COMPONENTS}>
        {reportText}
      </Markdown>
      {typing && (
        <span
          className="caret-blink ml-0.5 inline-block h-4 w-[2px] -translate-y-px bg-teal align-middle"
          aria-hidden="true"
        />
      )}
    </motion.div>
  );
}
