/**
 * Best-effort inline-citation linkifying for the synthesized report.
 *
 * `react-markdown` already turns real Markdown links into anchors. This helper
 * handles two bare patterns the model tends to emit in prose:
 *   - bracketed PMIDs like `[12345678]` → link to the PubMed record
 *   - bare URLs like `https://…`        → clickable links
 *
 * It is pure and string-only (no DOM), split into tokens the ReportView maps to
 * React nodes. Kept intentionally simple: PMIDs are 7–8 digit runs inside
 * square brackets, which is the common PubMed shape.
 */

export type CitationToken =
  | { kind: 'text'; value: string }
  | { kind: 'pmid'; value: string; href: string }
  | { kind: 'url'; value: string; href: string };

// `[12345678]` or the form the synthesizer prompt asks for, `[PMID12345678]` /
// `[PMID: 12345678]`. Two capture groups: prefixed (1) and bare (2).
const PMID_RE = /\[(?:PMID:?\s*(\d{1,9})|(\d{7,8}))\]/g;
const URL_RE = /\bhttps?:\/\/[^\s<>()[\]]+/g;

/** Build the combined matcher fresh each call (global regexes are stateful). */
function matcher(): RegExp {
  return new RegExp(`${PMID_RE.source}|${URL_RE.source}`, 'g');
}

/**
 * Split a plain-text run into text / pmid / url tokens in order. Only operates
 * on text (callers should not feed it code spans or existing links).
 */
export function linkifyCitations(text: string): CitationToken[] {
  const tokens: CitationToken[] = [];
  const re = matcher();
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = re.exec(text)) !== null) {
    if (match.index > lastIndex) {
      tokens.push({ kind: 'text', value: text.slice(lastIndex, match.index) });
    }
    const pmid = match[1] ?? match[2];
    if (pmid) {
      tokens.push({
        kind: 'pmid',
        value: match[0],
        href: `https://pubmed.ncbi.nlm.nih.gov/${pmid}/`,
      });
    } else {
      const url = match[0];
      tokens.push({ kind: 'url', value: url, href: url });
    }
    lastIndex = re.lastIndex;
  }

  if (lastIndex < text.length) {
    tokens.push({ kind: 'text', value: text.slice(lastIndex) });
  }
  return tokens;
}

export interface SourceLink {
  kind: 'pubmed' | 'web';
  /** Short label to display (e.g. `PMID 12345678` or the URL host). */
  label: string;
  href: string;
}

/**
 * Turn a study `identifier` (a PMID, optionally `PMID:`-prefixed, or a URL —
 * see the backend `Evidence` schema) into a link + short label. Returns `null`
 * for anything we can't safely link (only http/https URLs are linked).
 */
export function sourceLink(identifier: string): SourceLink | null {
  const id = identifier.trim();
  const pmid = /^(?:PMID:?\s*)?(\d{1,9})$/i.exec(id);
  if (pmid) {
    return {
      kind: 'pubmed',
      label: `PMID ${pmid[1]}`,
      href: `https://pubmed.ncbi.nlm.nih.gov/${pmid[1]}/`,
    };
  }
  try {
    const url = new URL(id);
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return null;
    return { kind: 'web', label: url.hostname.replace(/^www\./, ''), href: url.href };
  } catch {
    return null;
  }
}
