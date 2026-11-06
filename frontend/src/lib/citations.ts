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

const PMID_RE = /\[(\d{7,8})\]/g;
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
    const pmid = match[1];
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
