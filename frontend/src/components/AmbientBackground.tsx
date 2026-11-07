/**
 * Fixed, full-viewport glow layer behind the whole app: soft teal / indigo /
 * sky / emerald orbs on the theme's base color. Purely decorative (`aria-hidden`,
 * no pointer events). All styling and the slow drift animation live in
 * `index.css` (`.ambient`, `.orb-*`); the animation is transform-only and is
 * switched off under `prefers-reduced-motion`.
 */
export function AmbientBackground() {
  return (
    <div className="ambient" aria-hidden="true">
      <div className="orb orb-teal" />
      <div className="orb orb-indigo" />
      <div className="orb orb-sky" />
      <div className="orb orb-emerald" />
    </div>
  );
}
