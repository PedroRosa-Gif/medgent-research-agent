/**
 * A ticking clock for live UI such as the elapsed-time counter. Returns the
 * current epoch ms and re-renders every `intervalMs` while `active`; when
 * inactive it does not tick (and holds its last value).
 */

import { useEffect, useState } from 'react';

export function useNow(active: boolean, intervalMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!active) return;
    // Sync immediately so the first tick after activation isn't stale.
    const sync = window.setTimeout(() => setNow(Date.now()), 0);
    const id = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => {
      window.clearTimeout(sync);
      window.clearInterval(id);
    };
  }, [active, intervalMs]);

  return now;
}
