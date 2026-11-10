/**
 * "Follow latest": while a run is active, keep the newest content in view by
 * scrolling an anchor into view whenever `signal` changes (it should grow
 * monotonically: new steps + report length). If the user scrolls up to read,
 * following pauses until they return near the bottom, so we never fight them.
 */

import { useEffect, useRef, type RefObject } from 'react';

/** How close (px) to the bottom still counts as "following". */
const NEAR_BOTTOM_PX = 220;

export function useFollowLatest(
  active: boolean,
  signal: number,
  smooth: boolean,
): RefObject<HTMLDivElement | null> {
  const anchorRef = useRef<HTMLDivElement | null>(null);
  const following = useRef(true);

  useEffect(() => {
    function onScroll() {
      const doc = document.documentElement;
      const distance = doc.scrollHeight - (window.scrollY + window.innerHeight);
      following.current = distance < NEAR_BOTTOM_PX;
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  // A new run starts at the top, so resume following.
  useEffect(() => {
    if (active) following.current = true;
  }, [active]);

  useEffect(() => {
    if (!active || !following.current) return;
    anchorRef.current?.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto', block: 'end' });
  }, [active, signal, smooth]);

  return anchorRef;
}
