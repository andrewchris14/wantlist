import base from './playwright.config.js';
import {defineConfig} from '@playwright/test';
export default defineConfig({...base,testDir:'./rehearsal-tests',webServer:{...base.webServer,command:'FULL_REHEARSAL_DB=work/phase3c1-full.sqlite node owner/isolated-server.mjs',timeout:30000},outputDir:'../work/phase3c1-browser-results'});
