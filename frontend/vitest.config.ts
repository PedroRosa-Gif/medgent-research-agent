import { defineConfig } from 'vitest/config';

// Reducer tests are pure: no DOM, no network. The `node` environment keeps
// Vitest fast and offline. Kept separate from vite.config.ts so the dev/build
// config stays free of Vitest's plugin type surface.
export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
});
