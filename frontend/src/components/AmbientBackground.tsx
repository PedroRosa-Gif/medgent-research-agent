/**
 * Fixed, full-viewport background behind the whole app: a faint blueprint grid
 * and a gentle indigo / violet / slate haze on the theme's base color. Purely
 * decorative (`aria-hidden`, no pointer events). All styling and the very slow
 * drift animation live in `index.css` (`.ambient`, `.orb-*`); the animation is
 * transform-only and is switched off under `prefers-reduced-motion`.
 */
export function AmbientBackground() {
  return (
    <div className="ambient" aria-hidden="true">
      <div className="orb orb-indigo" />
      <div className="orb orb-violet" />
      <div className="orb orb-slate" />
    </div>
  );
}
