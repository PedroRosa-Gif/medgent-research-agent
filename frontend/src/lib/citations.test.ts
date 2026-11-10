import { describe, expect, it } from 'vitest';
import { linkifyCitations, sourceLink } from './citations';

describe('sourceLink', () => {
  it('maps PMIDs (bare or prefixed) to PubMed', () => {
    expect(sourceLink('12345678')).toEqual({
      kind: 'pubmed',
      label: 'PMID 12345678',
      href: 'https://pubmed.ncbi.nlm.nih.gov/12345678/',
    });
    expect(sourceLink('PMID:555')?.href).toBe('https://pubmed.ncbi.nlm.nih.gov/555/');
  });

  it('maps http(s) URLs to a host label and rejects other schemes', () => {
    expect(sourceLink('https://www.example.org/a/b')).toEqual({
      kind: 'web',
      label: 'example.org',
      href: 'https://www.example.org/a/b',
    });
    expect(sourceLink('javascript:alert(1)')).toBeNull();
    expect(sourceLink('not a link')).toBeNull();
  });
});

describe('linkifyCitations', () => {
  it('links bare bracketed PMIDs', () => {
    const tokens = linkifyCitations('Effective [12345678].');
    expect(tokens).toEqual([
      { kind: 'text', value: 'Effective ' },
      { kind: 'pmid', value: '[12345678]', href: 'https://pubmed.ncbi.nlm.nih.gov/12345678/' },
      { kind: 'text', value: '.' },
    ]);
  });

  it('links PMID-prefixed citations, the form the synthesizer prompt asks for', () => {
    const [token] = linkifyCitations('[PMID: 31234567]');
    expect(token).toEqual({
      kind: 'pmid',
      value: '[PMID: 31234567]',
      href: 'https://pubmed.ncbi.nlm.nih.gov/31234567/',
    });
    const [short] = linkifyCitations('[PMID123]');
    expect(short).toMatchObject({ kind: 'pmid', href: 'https://pubmed.ncbi.nlm.nih.gov/123/' });
  });

  it('links bare URLs and leaves plain text alone', () => {
    expect(linkifyCitations('see https://example.org/a now')).toEqual([
      { kind: 'text', value: 'see ' },
      { kind: 'url', value: 'https://example.org/a', href: 'https://example.org/a' },
      { kind: 'text', value: ' now' },
    ]);
    expect(linkifyCitations('nothing here')).toEqual([{ kind: 'text', value: 'nothing here' }]);
  });
});
