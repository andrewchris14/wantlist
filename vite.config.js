import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { wantlistDataPlugin } from './site/data-source.js';

export default defineConfig({
  base: './',
  plugins: [react(), wantlistDataPlugin()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./site/tests/setup.js'],
    include: ['site/**/*.test.{js,jsx}'],
  },
});
