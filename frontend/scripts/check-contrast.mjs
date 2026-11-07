#!/usr/bin/env node
/**
 * WCAG AA contrast check for the semantic color tokens in src/index.css.
 *
 * Reads the per-theme custom properties straight from the stylesheet (so it
 * can't drift from the real values), composites the translucent glass layers
 * over the WORST-CASE backdrops (bare canvas, and canvas with each ambient orb,
 * or all of them stacked, at peak opacity), and checks every text/surface pair
 * the UI uses against 4.5:1.
 *
 * Usage: npm run check:contrast   (exit code 1 if any pair fails)
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const css = readFileSync(fileURLToPath(new URL('../src/index.css', import.meta.url)), 'utf8');
const AA = 4.5;

/** Extract `--name: value;` declarations from the block starting at `selector`. */
function readBlock(selectorStart) {
  const start = css.indexOf(selectorStart);
  if (start === -1) throw new Error(`selector not found: ${selectorStart}`);
  const open = css.indexOf('{', start);
  const close = css.indexOf('\n}', open);
  const body = css.slice(open + 1, close);
  const vars = {};
  for (const m of body.matchAll(/--([\w-]+):\s*([^;]+);/g)) vars[m[1]] = m[2].replace(/\s+/g, ' ').trim();
  return vars;
}

function parseColor(value) {
  const hex = /^#([0-9a-f]{6})$/i.exec(value);
  if (hex) {
    const n = parseInt(hex[1], 16);
    return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255, a: 1 };
  }
  const rgb = /^rgb\(\s*(\d+)\s+(\d+)\s+(\d+)(?:\s*\/\s*([\d.]+))?\s*\)$/.exec(value);
  if (rgb) return { r: +rgb[1], g: +rgb[2], b: +rgb[3], a: rgb[4] === undefined ? 1 : +rgb[4] };
  throw new Error(`unsupported color: ${value}`);
}

/** Composite `top` (with alpha) over an opaque `bottom`. */
function over(top, bottom, alphaScale = 1) {
  const a = top.a * alphaScale;
  return {
    r: top.r * a + bottom.r * (1 - a),
    g: top.g * a + bottom.g * (1 - a),
    b: top.b * a + bottom.b * (1 - a),
    a: 1,
  };
}

function luminance({ r, g, b }) {
  const lin = [r, g, b].map((v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2];
}

function ratio(fg, bg) {
  const [hi, lo] = [luminance(fg), luminance(bg)].sort((a, b) => b - a);
  return (hi + 0.05) / (lo + 0.05);
}

const themes = {
  dark: { ...readBlock(":root[data-theme='dark']") },
  light: { ...readBlock(":root[data-theme='light']") },
};

let failures = 0;

for (const [name, v] of Object.entries(themes)) {
  const c = (key) => parseColor(v[key]);
  const canvas = c('canvas');
  const orbs = ['orb-teal', 'orb-indigo', 'orb-sky', 'orb-emerald'].map(c);

  // Backdrops behind a glass card: bare canvas, each orb at peak, all stacked.
  const backdrops = [
    ['canvas', canvas],
    ...['teal', 'indigo', 'sky', 'emerald'].map((o, i) => [`canvas+${o} orb`, over(orbs[i], canvas)]),
    // Orbs fade linearly to transparent, so where two overlap each is ~half strength.
    ...[[0, 1], [0, 2], [1, 3], [2, 3], [0, 3], [1, 2]].map(([i, j]) => [
      `canvas+${i}+${j} overlap`,
      over(orbs[j], over(orbs[i], canvas, 0.5), 0.5),
    ]),
    ['canvas+top wash', over(c('canvas-wash'), canvas)],
  ];

  // Surfaces text sits on (worst case across backdrops is taken per surface).
  const surfaces = {
    canvas: () => backdrops.map(([, b]) => b),
    'glass card': () => backdrops.map(([, b]) => over(c('glass-bg'), b)),
    'glass strong (composer/header)': () => backdrops.map(([, b]) => over(c('glass-bg-strong'), b)),
    'glass soft (timeline card)': () =>
      backdrops.map(([, b]) => over(c('glass-bg-soft'), over(c('glass-bg'), b))),
    'solid surface (fallback)': () => [c('surface')],
    'surface-2 (chips/wells)': () => [c('surface-2')],
  };

  const textTokens = ['fg', 'fg-muted', 'fg-subtle', 'accent-text', 'violet-text', 'ok', 'warn', 'danger'];

  console.log(`\n=== ${name} theme (AA ≥ ${AA}:1, worst case over backdrops) ===`);
  for (const [surfaceName, fn] of Object.entries(surfaces)) {
    const bgs = fn();
    const cells = textTokens.map((t) => {
      const worst = Math.min(...bgs.map((bg) => ratio(c(t), bg)));
      const ok = worst >= AA;
      if (!ok) failures += 1;
      return `${t} ${worst.toFixed(1)}${ok ? '' : ' FAIL'}`;
    });
    console.log(`${surfaceName.padEnd(32)} ${cells.join(' | ')}`);
  }

  // Tinted chips: token text on its own 10-12% tint over a glass-soft card.
  const tintChecks = [
    ['ok', 'ok', 0.1],
    ['warn', 'warn', 0.1],
    ['accent-text', 'accent', 0.12],
    ['violet-text', 'violet', 0.1],
  ];
  const worstBase = backdrops.map(([, b]) => over(c('glass-bg-soft'), over(c('glass-bg'), b)));
  for (const [textKey, tintKey, alpha] of tintChecks) {
    const worst = Math.min(
      ...worstBase.map((base) => ratio(c(textKey), over(c(tintKey), base, alpha / c(tintKey).a))),
    );
    const ok = worst >= AA;
    if (!ok) failures += 1;
    console.log(`chip ${textKey} on ${tintKey}/${Math.round(alpha * 100)}%`.padEnd(32) + ` ${worst.toFixed(1)}${ok ? '' : ' FAIL'}`);
  }

  // Filled primary button and the gradient headline.
  const btn = ratio(c('on-accent'), c('accent-strong'));
  if (btn < AA) failures += 1;
  console.log(`${'primary button'.padEnd(32)} on-accent/accent-strong ${btn.toFixed(1)}${btn >= AA ? '' : ' FAIL'}`);
  for (const stop of ['fg', 'accent-text', 'violet-text']) {
    const worst = Math.min(...backdrops.map(([, b]) => ratio(c(stop), b)));
    if (worst < AA) failures += 1;
    console.log(`${'headline gradient stop'.padEnd(32)} ${stop} on canvas/orbs ${worst.toFixed(1)}${worst >= AA ? '' : ' FAIL'}`);
  }
}

console.log(failures ? `\n${failures} pair(s) below AA` : '\nAll checked pairs meet WCAG AA (4.5:1).');
process.exit(failures ? 1 : 0);
