/**
 * Clipboard helper with a transient "copied" flag for a non-blocking
 * confirmation. Uses the async Clipboard API, falling back to a hidden
 * textarea + `execCommand('copy')` for insecure contexts / older browsers.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

async function writeToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // Fall through to the legacy path (permission denied, insecure context…).
  }
  try {
    const area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.cssText = 'position:fixed;top:0;left:0;opacity:0;pointer-events:none';
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(area);
    return ok;
  } catch {
    return false;
  }
}

export interface UseClipboard {
  /** True for ~2s after a successful copy. */
  copied: boolean;
  /** True for ~2s after a failed copy. */
  failed: boolean;
  copy: (text: string) => Promise<void>;
}

export function useClipboard(resetMs = 2000): UseClipboard {
  const [status, setStatus] = useState<'idle' | 'copied' | 'failed'>('idle');
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const copy = useCallback(
    async (text: string) => {
      const ok = await writeToClipboard(text);
      setStatus(ok ? 'copied' : 'failed');
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setStatus('idle'), resetMs);
    },
    [resetMs],
  );

  return { copied: status === 'copied', failed: status === 'failed', copy };
}
