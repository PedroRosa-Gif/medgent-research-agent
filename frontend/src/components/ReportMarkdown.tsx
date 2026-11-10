/**
 * Markdown renderer for the report. Split into its own module so the heavy
 * `react-markdown` + `remark-gfm` bundle is lazy-loaded (see `ReportView`).
 *
 * Block styling lives in `index.css` under `.report`; this file only adds the
 * behaviour CSS can't: safe external links, citation linkifying in prose, and
 * a scroll wrapper around tables.
 */
import type { ReactNode } from 'react';
import Markdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { linkifyCitations } from '../lib/citations';

/** Accent citation / markdown link that always opens safely in a new tab. */
function CitationLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  );
}

/** Turn a plain-text node into text + linkified citations. */
function linkifyNode(node: ReactNode, key?: number): ReactNode {
  if (typeof node !== 'string') return node;
  const tokens = linkifyCitations(node);
  if (tokens.length === 1 && tokens[0].kind === 'text') return node;
  return (
    <span key={key}>
      {tokens.map((token, i) =>
        token.kind === 'text' ? (
          token.value
        ) : (
          <CitationLink key={i} href={token.href}>
            {token.value}
          </CitationLink>
        ),
      )}
    </span>
  );
}

function linkifyChildren(children: ReactNode): ReactNode {
  if (Array.isArray(children)) return children.map((child, i) => linkifyNode(child, i));
  return linkifyNode(children);
}

const COMPONENTS: Components = {
  a: ({ href, children }) => <CitationLink href={href ?? '#'}>{children}</CitationLink>,
  p: ({ children }) => <p>{linkifyChildren(children)}</p>,
  li: ({ children }) => <li>{linkifyChildren(children)}</li>,
  td: ({ children }) => <td>{linkifyChildren(children)}</td>,
  table: ({ children }) => (
    <div className="table-wrap">
      <table>{children}</table>
    </div>
  ),
};

export default function ReportMarkdown({ text }: { text: string }) {
  return (
    <Markdown remarkPlugins={[remarkGfm]} components={COMPONENTS}>
      {text}
    </Markdown>
  );
}
