/**
 * The MedGent mark: a thin-stroke, rounded medical cross plus one small filled
 * dot offset at the upper right (the "agent" spark). The cross follows
 * `currentColor` (default `text-fg`); the dot uses the theme accent. No tile,
 * no gradients, so it sits cleanly on any surface and reads at 16×16.
 *
 * Mirrors `public/favicon.svg` (keep the geometry in sync).
 */
interface LogoProps {
  size?: number;
  className?: string;
  /** Decorative by default; pass a label when the logo is the only content. */
  title?: string;
}

export function Logo({ size = 24, className, title }: LogoProps) {
  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      className={['text-fg', className].filter(Boolean).join(' ')}
      role={title ? 'img' : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      focusable="false"
    >
      <path
        d="M30 16v36M12 34h36"
        fill="none"
        stroke="currentColor"
        strokeWidth="5.5"
        strokeLinecap="round"
      />
      <circle cx="49" cy="15" r="5.5" className="fill-accent" />
    </svg>
  );
}
