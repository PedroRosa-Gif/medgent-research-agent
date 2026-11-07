/**
 * The MedGent mark: a bold, rounded medical cross (medicine) wired to four
 * corner nodes (an agent / neural graph), on a deep rounded tile. Teal → indigo
 * gradient. Kept deliberately chunky so it reads at 16×16.
 *
 * Mirrors `public/favicon.svg` (keep the geometry in sync). Gradient ids are
 * made unique per instance with `useId` so several logos can coexist.
 */
import { useId } from 'react';

interface LogoProps {
  size?: number;
  className?: string;
  /** Decorative by default; pass a label when the logo is the only content. */
  title?: string;
}

export function Logo({ size = 32, className, title }: LogoProps) {
  const uid = useId().replace(/:/g, '');
  const tile = `tile-${uid}`;
  const cross = `cross-${uid}`;
  const node = `node-${uid}`;

  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      className={className}
      role={title ? 'img' : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      focusable="false"
    >
      <defs>
        <linearGradient id={tile} x1="8" y1="2" x2="56" y2="62" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#12203a" />
          <stop offset="1" stopColor="#1b1546" />
        </linearGradient>
        <linearGradient id={cross} x1="14" y1="12" x2="50" y2="52" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#5eead4" />
          <stop offset="0.55" stopColor="#2dd4bf" />
          <stop offset="1" stopColor="#818cf8" />
        </linearGradient>
        <linearGradient id={node} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#c7d2fe" />
          <stop offset="1" stopColor="#818cf8" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="15" fill={`url(#${tile})`} />
      <rect x="0.75" y="0.75" width="62.5" height="62.5" rx="14.25" fill="none" stroke="#fff" strokeOpacity="0.14" strokeWidth="1.5" />
      <g stroke="#a5b4fc" strokeOpacity="0.7" strokeWidth="2.4" strokeLinecap="round">
        <path d="M32 32 11.5 11.5M32 32l20.5-20.5M32 32 11.5 52.5M32 32l20.5 20.5" />
      </g>
      <g fill={`url(#${node})`}>
        <circle cx="11.5" cy="11.5" r="4.6" />
        <circle cx="52.5" cy="11.5" r="4.6" />
        <circle cx="11.5" cy="52.5" r="4.6" />
        <circle cx="52.5" cy="52.5" r="4.6" />
      </g>
      <g fill={`url(#${cross})`}>
        <rect x="25.5" y="13" width="13" height="38" rx="4.5" />
        <rect x="13" y="25.5" width="38" height="13" rx="4.5" />
      </g>
    </svg>
  );
}
